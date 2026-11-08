from __future__ import annotations

import csv
import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

from .common import (POSE_COLUMNS, config_digest, fingerprint, make_run_dir, sha256,
                     run_metadata, write_csv, write_json)
from .dataset import load_state
from .evaluation import evaluate
from .geometry import integrate_recover_pose, poses_to_rows, rows_to_poses
from .plotting import plot_trajectory, plot_comparison
from .video import intrinsic_matrix, iter_frames


class MotionFailure(ValueError):
    def __init__(self, reason, diagnostics=None):
        super().__init__(reason)
        self.diagnostics = diagnostics or {}


def ratio_matches(descriptors1, descriptors2, ratio: float):
    if descriptors1 is None or descriptors2 is None or len(descriptors2) < 2:
        return []
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(descriptors1, descriptors2, k=2)
    candidates = sorted((pair[0] for pair in pairs if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance),
                        key=lambda match: match.distance)
    result, seen = [], set()
    for match in candidates:
        if match.trainIdx not in seen:
            result.append(match)
            seen.add(match.trainIdx)
    return result


def estimate_motion(points1, points2, k1, k2, distortion, config):
    if len(points1) < config["matching"]["minimum_matches"]:
        raise MotionFailure("insufficient_ratio_matches")
    p1 = cv2.undistortPoints(np.asarray(points1, float).reshape(-1, 1, 2), k1, distortion).reshape(-1, 2)
    p2 = cv2.undistortPoints(np.asarray(points2, float).reshape(-1, 1, 2), k2, distortion).reshape(-1, 2)
    ransac = config["ransac"]
    focal = np.mean([k1[0, 0], k1[1, 1], k2[0, 0], k2[1, 1]])
    essential, mask = cv2.findEssentialMat(p1, p2, np.eye(3), method=cv2.RANSAC,
                                         prob=float(ransac["confidence"]),
                                         threshold=float(ransac["threshold_pixels"]) / focal,
                                         maxIters=int(ransac["max_iterations"]))
    if essential is None or mask is None or essential.shape[1] != 3 or essential.shape[0] % 3:
        raise MotionFailure("essential_matrix_not_found")
    best = None
    distance_threshold = float(ransac.get("recover_pose_distance_threshold", 50.0))
    if not np.isfinite(distance_threshold) or distance_threshold <= 0:
        raise ValueError("recoverPose distance threshold must be positive")
    for candidate in np.split(essential, essential.shape[0] // 3):
        try:
            recovered_values = cv2.recoverPose(candidate, p1, p2, np.eye(3),
                                               distanceThresh=distance_threshold, mask=mask.copy())
            count, rotation, translation, recovered = recovered_values[:4]
            if best is None or count > best[0]:
                best = (count, rotation, translation, recovered.reshape(-1).astype(bool))
        except cv2.error:
            continue
    if best is None:
        raise MotionFailure("recover_pose_failed")
    count, rotation, translation, inliers = best
    ratio = count / len(points1)
    diagnostics = {"inliers": int(count), "inlier_ratio": ratio, "median_parallax_degrees": None,
                   "essential_ransac_inliers": int(np.count_nonzero(mask)),
                   "essential_ransac_inlier_ratio": float(np.count_nonzero(mask) / len(points1))}
    if count < ransac["minimum_inliers"] or ratio < ransac["minimum_inlier_ratio"]:
        raise MotionFailure(f"insufficient_cheirality_inliers:{count}/{len(points1)}", diagnostics)
    bearings1 = np.column_stack((p1[inliers], np.ones(count)))
    bearings2 = (rotation.T @ np.column_stack((p2[inliers], np.ones(count))).T).T
    bearings1 /= np.linalg.norm(bearings1, axis=1, keepdims=True)
    bearings2 /= np.linalg.norm(bearings2, axis=1, keepdims=True)
    parallax = np.degrees(np.arccos(np.clip(np.sum(bearings1 * bearings2, axis=1), -1, 1)))
    median_parallax = float(np.median(parallax))
    diagnostics["median_parallax_degrees"] = median_parallax
    if median_parallax < ransac["minimum_median_parallax_degrees"]:
        raise MotionFailure(f"low_parallax_or_rotation_only:{median_parallax:.6f}deg", diagnostics)
    return rotation, translation, diagnostics | {"inlier_mask": inliers}


def check_e0_gate(e0_run: Path, sequence_id: str, dataset_config: dict, camera_config: dict):
    root = json.loads((e0_run / "validation.json").read_text(encoding="utf-8"))
    if not root.get("e0_passed") or not root.get("downstream_allowed"):
        raise ValueError("E0 has not passed; E1 real-data inference is prohibited")
    if dataset_config.get("adapter"):
        from .dataset_validation import check_adapter_gate
        return check_adapter_gate(e0_run, sequence_id, dataset_config)
    manifest = json.loads((e0_run / "data_manifest.json").read_text(encoding="utf-8"))
    if manifest["config_digest"] != config_digest(dataset_config, camera_config):
        raise ValueError("E0 input configuration has changed; revalidate before E1")
    entry = next((entry for entry in manifest["sequences"] if entry["sequence_id"] == sequence_id), None)
    if entry is None:
        raise ValueError("Unknown sequence ID")
    local = json.loads((e0_run / sequence_id / "validation.json").read_text(encoding="utf-8"))
    if not local["e0_passed"]:
        raise ValueError("Sequence E0 gate is closed")
    for name, key in (("normalized_ground_truth.csv", "normalized_ground_truth_sha256"),
                      ("frame_associations.csv", "frame_associations_sha256")):
        if sha256(e0_run / sequence_id / name) != local[key]:
            raise ValueError("Validated ground truth/association output changed; revalidate rather than editing CSV results")
    for key, path_key in (("video_fingerprint", "video"), ("state_fingerprint", "state_csv")):
        if fingerprint(entry[path_key]) != entry[key]:
            raise ValueError("Validated input changed; E0 must be rerun")
    return entry, local


def run_orb(e0_run: Path, sequence_id: str, dataset_config: dict, camera_config: dict,
            experiment_config: dict, result_parent: Path, mask_source="none") -> dict:
    entry, validation = check_e0_gate(e0_run, sequence_id, dataset_config, camera_config)
    out = make_run_dir(result_parent / sequence_id, "orb_essential")
    logger = logging.getLogger(f"orb.{out.name}")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(out / "tracking_log.txt", encoding="utf-8")
    logger.addHandler(handler)
    config = experiment_config
    cv2.setRNGSeed(int(config["seed"]))
    cv2.setNumThreads(int(config["opencv_threads"]))
    orb = cv2.ORB_create(nfeatures=int(config["orb"]["nfeatures"]),
                         scaleFactor=float(config["orb"]["scale_factor"]),
                         nlevels=int(config["orb"]["nlevels"]), fastThreshold=int(config["orb"]["fast_threshold"]))
    distortion = np.array(camera_config["distortion_coefficients"], dtype=float)
    if distortion.size not in (4, 5, 8, 12, 14) or not np.isfinite(distortion).all():
        raise ValueError("Unsupported distortion vector; use real calibration coefficients")
    (out / "run_config.yaml").write_text(yaml.safe_dump({"dataset": dataset_config, "camera": camera_config,
                                                         "experiment": config}, sort_keys=False), encoding="utf-8")
    adapter = None
    if dataset_config.get("adapter"):
        from datasets.registry import open_dataset
        adapter = open_dataset(dataset_config)
        state = {"intrinsics": adapter.get_intrinsics()}
        input_frames = adapter.get_frames(config["resize_width"])
        dataset_metadata = adapter.get_metadata()
    else:
        state = load_state(Path(entry["state_csv"]), dataset_config, camera_config)
        input_frames = iter_frames(entry["video"], dataset_config["clip"], config["resize_width"])
        dataset_metadata = {"dataset": dataset_config["dataset"], "POSE_PROVENANCE": "ENGINE_GROUND_TRUTH",
                            "independent_engine_ground_truth": True, "timestamp_kind": "seconds"}
    if mask_source != "none" and (adapter is None or adapter.get_dynamic_masks(0, mask_source) is None):
        raise ValueError("Requested masks are unavailable; do not silently run a masked experiment without masks")
    with (e0_run / sequence_id / "frame_associations.csv").open(encoding="utf-8", newline="") as handle:
        expected_frames = list(csv.DictReader(handle))
    with (e0_run / sequence_id / validation.get("trajectory_file", "normalized_ground_truth.csv")).open(encoding="utf-8", newline="") as handle:
        ground_truth_rows = list(csv.DictReader(handle))
    lookup = {int(row["frame_index"]): row for row in expected_frames}
    expected_gt = [ground_truth_rows[int(row["state_row_index"])] for row in expected_frames]
    gt_times, gt_poses = rows_to_poses(expected_gt)
    previous = None
    transforms, timestamps, statuses = [], [], []
    saved_matches = 0
    input_resolutions = set()
    fatal = None
    match_dir = out / "feature_matches"
    match_dir.mkdir()
    started = time.perf_counter()
    try:
        for frame in input_frames:
            tick = time.perf_counter()
            index = frame["frame_index"]
            if index not in lookup:
                raise ValueError("Decoded frame was not validated in E0")
            association = lookup[index]
            state_index = int(association["state_row_index"])
            timestamp = float(association["evaluation_timestamp"])
            gray = cv2.cvtColor(frame["image"], cv2.COLOR_BGR2GRAY)
            input_resolutions.add((frame["image"].shape[1], frame["image"].shape[0]))
            keypoints, descriptors = orb.detectAndCompute(gray, None)
            before_mask = len(keypoints)
            dynamic_fraction = 0.0
            if mask_source != "none":
                dynamic = adapter.get_dynamic_masks(state_index, mask_source)
                if dynamic is None:
                    raise ValueError("Missing requested dynamic mask for a sampled frame")
                dynamic_fraction = float(np.mean(dynamic))
                dynamic = cv2.resize(dynamic.astype(np.uint8), (gray.shape[1], gray.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
                coordinates = np.array([keypoint.pt for keypoint in keypoints], int).reshape(-1, 2)
                keep = ~dynamic[coordinates[:, 1], coordinates[:, 0]]
                keypoints = [keypoint for keypoint, selected in zip(keypoints, keep, strict=True) if selected]
                descriptors = descriptors[keep] if descriptors is not None else None
            k = intrinsic_matrix(state["intrinsics"][state_index], frame["scale_x"], frame["scale_y"])
            row = {"frame_index": index, "state_row_index": state_index, "timestamp": timestamp,
                   "status": "initialization" if previous is None else "failed", "feature_count": len(keypoints),
                   "feature_count_before_mask": before_mask, "dynamic_mask_fraction": dynamic_fraction,
                   "image_width": frame["image"].shape[1], "image_height": frame["image"].shape[0],
                   "reference_frame_index": previous["frame_index"] if previous is not None else None,
                   "matches": 0, "inliers": 0, "inlier_ratio": None, "median_parallax_degrees": None,
                   "essential_ransac_inliers": None, "essential_ransac_inlier_ratio": None,
                   "processing_seconds": None, "reason": ""}
            transform = np.full((4, 4), np.nan)
            success = previous is None
            matches = []
            if previous is None:
                transform = np.eye(4)
            else:
                matches = ratio_matches(previous["descriptors"], descriptors, config["matching"]["lowe_ratio"])
                row["matches"] = len(matches)
                p1 = np.array([previous["keypoints"][m.queryIdx].pt for m in matches])
                p2 = np.array([keypoints[m.trainIdx].pt for m in matches])
                try:
                    rotation, translation, stats = estimate_motion(p1, p2, previous["k"], k, distortion, config)
                    transform = integrate_recover_pose(previous["transform"], rotation, translation)
                    row.update({name: stats[name] for name in ("inliers", "inlier_ratio", "median_parallax_degrees",
                                                              "essential_ransac_inliers", "essential_ransac_inlier_ratio")})
                    row["status"] = "success"
                    success = True
                except (MotionFailure, cv2.error) as exc:
                    row["reason"] = str(exc)
                    if isinstance(exc, MotionFailure):
                        row.update(exc.diagnostics)
                if (saved_matches < config["output"]["max_match_images"] and
                        len(statuses) % max(1, config["output"]["save_match_every"]) == 0):
                    canvas = cv2.drawMatches(previous["image"], previous["keypoints"], frame["image"], keypoints,
                                              matches[:100], None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
                    cv2.putText(canvas, f"frame {index} {row['status']}; ratio matches (not all inliers)",
                                (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 1)
                    cv2.imwrite(str(match_dir / f"frame_{index:07d}.png"), canvas)
                    saved_matches += 1
            if success:
                previous = {"frame_index": index, "image": frame["image"], "keypoints": keypoints,
                            "descriptors": descriptors, "k": k, "transform": transform}
            row["processing_seconds"] = time.perf_counter() - tick
            transforms.append(transform)
            timestamps.append(timestamp)
            statuses.append(row)
            logger.info(json.dumps(row, ensure_ascii=False))
        if [row["frame_index"] for row in statuses] != [int(row["frame_index"]) for row in expected_frames]:
            raise ValueError("Actual decoded frame sequence differs from E0 validation")
    except Exception as exc:
        fatal = f"{type(exc).__name__}: {exc}"
        logger.exception("Run terminated; all partial observations are retained")
    elapsed = time.perf_counter() - started
    predicted = np.asarray(transforms).reshape(-1, 4, 4)
    trajectory_rows = poses_to_rows(np.asarray(timestamps), predicted)
    write_csv(out / "estimated_trajectory.csv", trajectory_rows, POSE_COLUMNS)
    values = np.array([[row[key] for key in POSE_COLUMNS] for row in trajectory_rows]).reshape(-1, 8)
    np.savetxt(out / "estimated_trajectory.txt", values, fmt="%.10f",
               header="timestamp tx ty tz qx qy qz qw; T_wc CV; arbitrary per-edge unit translation; failed frames=nan; "
                      + "time_axis=" + dataset_metadata["timestamp_kind"])
    write_csv(out / "tracking_status.csv", statuses,
              ["frame_index", "state_row_index", "timestamp", "status", "feature_count", "feature_count_before_mask",
               "dynamic_mask_fraction", "image_width", "image_height", "reference_frame_index",
               "matches", "essential_ransac_inliers", "essential_ransac_inlier_ratio",
               "inliers", "inlier_ratio", "median_parallax_degrees", "processing_seconds", "reason"])
    evaluation_reference_file = ("evaluation_ground_truth.csv" if dataset_metadata["independent_engine_ground_truth"]
                                 else "evaluation_reference_trajectory.csv")
    write_csv(out / evaluation_reference_file, expected_gt, POSE_COLUMNS)
    metrics, details = evaluate(gt_times, gt_poses, timestamps, predicted,
                               config["evaluation"]["timestamp_tolerance_seconds"],
                               config["evaluation"]["rpe_delta_samples"], "arbitrary",
                               dataset_metadata.get("length_unit", camera_config["length_unit"]), elapsed,
                               time_axis=dataset_metadata["timestamp_kind"])
    successful_pairs = sum(row["status"] == "success" for row in statuses)
    attempts = max(0, len(statuses) - 1)
    for row in metrics:
        row.update({"baseline": "ORB+Essential", "sequence_id": sequence_id, "runtime_device": "CPU",
                    "experiment_variant": config.get("variant", "distance50_default"),
                    "recover_pose_distance_threshold": config["ransac"].get("recover_pose_distance_threshold", 50.0),
                    "dataset": dataset_metadata["dataset"], "POSE_PROVENANCE": dataset_metadata["POSE_PROVENANCE"],
                    "independent_engine_ground_truth": dataset_metadata["independent_engine_ground_truth"],
                    "evaluation_reference_type": "engine_ground_truth" if dataset_metadata["independent_engine_ground_truth"] else "estimated_reference",
                    "time_axis": dataset_metadata["timestamp_kind"], "dynamic_mask_source": mask_source,
                    "tracking_pair_success": successful_pairs / (len(expected_frames) - 1) if len(expected_frames) > 1 else None,
                    "attempted_tracking_pair_success": successful_pairs / attempts if attempts else None,
                    "tracking_pair_attempts": attempts, "fatal_error": fatal,
                    "scale_caveat": "Per-edge unit translations are arbitrary, not constant real distances; SE3 diagnostic only",
                    "e0_run": str(e0_run.resolve())})
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "evaluation_details.json", details)
    plot_comparison(gt_times, gt_poses, predicted, details, out,
                    dataset_metadata.get("length_unit", camera_config["length_unit"]),
                    f"{dataset_metadata['dataset']} / {sequence_id}",
                    dataset_metadata["independent_engine_ground_truth"], dataset_metadata["timestamp_kind"])
    plot_trajectory(np.asarray(timestamps), predicted, out, "arbitrary_unit_per_edge", "ORB+Essential estimate",
                    dataset_metadata["timestamp_kind"])
    summary = {**run_metadata(), "experiment_id": config.get("experiment_id", "E1-A"), "baseline": "ORB+Essential",
               "dataset": dataset_metadata["dataset"], "POSE_PROVENANCE": dataset_metadata["POSE_PROVENANCE"],
               "independent_engine_ground_truth": dataset_metadata["independent_engine_ground_truth"],
               "evaluation_reference_file": evaluation_reference_file,
               "dynamic_mask_source": mask_source, "depth_used_for_inference": False,
               "experiment_variant": config.get("variant", "distance50_default"),
               "sequence_id": sequence_id, "status": "FAILED" if fatal else "FINISHED_WITH_REPORTED_FAILURES",
               "fatal_error": fatal, "result_directory": str(out.resolve()), "expected_frames": len(expected_frames),
               "processed_frames": len(statuses), "successful_motion_pairs": successful_pairs,
               "inference_seconds": elapsed, "resize_width_limit": config["resize_width"],
               "actual_input_resolutions_width_height": sorted(input_resolutions),
               "timing_scope": "Decode + feature extraction + geometry + optional match-image export; excludes evaluation/plots",
               "runtime_device": "CPU", "model_weights": "NONE", "gpu_memory_allocated_bytes": 0,
               "scale_status": "arbitrary_per_edge", "e0_gate": validation["e0_passed"]}
    write_json(out / "run_summary.json", summary)
    handler.close()
    logger.removeHandler(handler)
    return summary

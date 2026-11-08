"""Reuse the existing geometric baseline on phase4's exact shared RGB/K files."""
from __future__ import annotations

import _bootstrap
import json
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

from gamecam_vo.common import PROJECT, POSE_COLUMNS, make_run_dir, read_yaml, run_metadata, sha256, write_csv, write_json
from gamecam_vo.dataset_validation import check_adapter_gate
from gamecam_vo.evaluation import evaluate, load_trajectory
from gamecam_vo.geometry import integrate_recover_pose, poses_to_rows
from gamecam_vo.orb import MotionFailure, estimate_motion, ratio_matches
from gamecam_vo.plotting import plot_comparison, plot_trajectory


def main():
    pointer = json.loads((PROJECT / "reports/SOTA/mvs_rgb_input.json").read_text())
    prepared = Path(pointer["directory"])
    inputs = json.loads((prepared / "input_manifest.json").read_text())
    frames = inputs["frames"]
    if len(frames) != 100 or inputs["inference_inputs"] != ["RGB", "camera_intrinsics"]:
        raise ValueError("Expected the shared 100 RGB+K input")
    for row in frames:
        if sha256(row["path"]) != row["sha256"]:
            raise ValueError("Shared RGB input changed")
    dataset = read_yaml(PROJECT / "configs/datasets/mvs_synth.yaml")
    e0 = Path(json.loads((PROJECT / "results/E0_MVS/latest_run.json").read_text())["directory"])
    _, validation = check_adapter_gate(e0, "0000", dataset)
    reference = e0 / "0000" / validation["trajectory_file"]
    gt_times, gt = load_trajectory(reference)
    times = np.array([row["timestamp"] for row in frames], dtype=float)
    if not np.array_equal(gt_times, times):
        raise ValueError("E0/shared-input correspondence failed")
    config = read_yaml(PROJECT / "configs/experiment.yaml")
    config.update(experiment_id="E11_SOTA", resize_width=inputs["width"], variant="shared_RGB_K_distance50_default")
    k = np.array(inputs["fixed_K"], dtype=float)
    out = make_run_dir(PROJECT / "results/E11_SOTA/ORB_ESSENTIAL_MVS_0000", "shared_RGB_K")
    write_json(out / "run_config.json", {
        "experiment": config, "shared_input_directory": str(prepared), "fixed_K": k.tolist(),
        "algorithm": "Existing gamecam_vo.orb.ratio_matches and estimate_motion, unchanged default parameters",
        "algorithm_source_sha256": sha256(PROJECT / "gamecam_vo/orb.py"),
        "historical_result_difference": "Historical MVS runs used original 960x540 RGB and varying K. This run uses shared 640x360 rectified PNGs and fixed K, as the SOTA comparison.",
        "inference_inputs": ["RGB", "camera_intrinsics"], "engine_depth_in_inference": False,
        "engine_pose_in_motion_estimation": False, "evaluation_reference": str(reference),
    })
    shutil.copy2(prepared / "input_manifest.json", out / "input_manifest.json")
    cv2.setRNGSeed(int(config["seed"]))
    cv2.setNumThreads(int(config["opencv_threads"]))
    orb = cv2.ORB_create(nfeatures=int(config["orb"]["nfeatures"]), scaleFactor=float(config["orb"]["scale_factor"]),
                         nlevels=int(config["orb"]["nlevels"]), fastThreshold=int(config["orb"]["fast_threshold"]))
    predicted = np.full((100, 4, 4), np.nan)
    previous, records, fatal = None, [], None
    started = time.perf_counter()
    with (out / "inference_log.txt").open("w", encoding="utf-8") as log:
        try:
            for i, row in enumerate(frames):
                image = cv2.imread(row["path"], cv2.IMREAD_COLOR)
                if image is None or image.shape[:2] != (inputs["height"], inputs["width"]):
                    raise ValueError("Prepared RGB dimensions changed")
                keypoints, descriptors = orb.detectAndCompute(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), None)
                record = {"frame_index": i, "timestamp": float(times[i]), "status": "initialization" if previous is None else "failed",
                          "feature_count": len(keypoints), "reference_frame_index": previous["index"] if previous else None,
                          "matches": 0, "inliers": None, "inlier_ratio": None, "median_parallax_degrees": None,
                          "essential_ransac_inliers": None, "essential_ransac_inlier_ratio": None, "reason": ""}
                success = previous is None
                if previous is None:
                    predicted[i] = np.eye(4)
                else:
                    matches = ratio_matches(previous["descriptors"], descriptors, config["matching"]["lowe_ratio"])
                    record["matches"] = len(matches)
                    p1 = np.array([previous["keypoints"][m.queryIdx].pt for m in matches])
                    p2 = np.array([keypoints[m.trainIdx].pt for m in matches])
                    try:
                        rotation, translation, stats = estimate_motion(p1, p2, k, k, np.zeros(5), config)
                        predicted[i] = integrate_recover_pose(previous["transform"], rotation, translation)
                        record.update({name: value for name, value in stats.items() if name != "inlier_mask"})
                        record["status"], success = "success", True
                    except (MotionFailure, cv2.error) as exc:
                        record["reason"] = str(exc)
                        if isinstance(exc, MotionFailure):
                            record.update(exc.diagnostics)
                if success:
                    previous = {"index": i, "keypoints": keypoints, "descriptors": descriptors, "transform": predicted[i].copy()}
                records.append(record)
                log.write(json.dumps(record) + "\n")
                log.flush()
        except Exception as exc:
            fatal = f"{type(exc).__name__}: {exc}"
            log.write(fatal + "\n")
    wall = time.perf_counter() - started
    metrics, details = evaluate(gt_times, gt, times, predicted, tolerance=1e-6, unit="native_game_unit", inference_seconds=wall, time_axis="frame_index")
    for metric in metrics:
        metric.update(dataset="MVS-Synth", sequence_id="0000", baseline="ORB+Essential", method_category="pairwise_geometry",
                      POSE_PROVENANCE="ENGINE_GROUND_TRUTH", independent_engine_ground_truth=True, runtime_device="CPU_Windows",
                      experiment_variant=config["variant"], input_fps_timing_scope="RGB decoding, feature extraction, geometric estimation and JSONL observation logging",
                      successful_motion_edges=sum(row["status"] == "success" for row in records), expected_motion_edges=99,
                      actual_capture_fps="UNKNOWN", fatal_error=fatal)
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "evaluation_details.json", details)
    write_csv(out / "tracking_status.csv", records)
    rows = poses_to_rows(times, predicted)
    write_csv(out / "estimated_trajectory.csv", rows, POSE_COLUMNS)
    np.savetxt(out / "estimated_trajectory.txt", np.array([[row[name] for name in POSE_COLUMNS] for row in rows]), fmt="%.12g", header="T_wc; frame_index; arbitrary per-edge unit translation; missing=nan")
    plot_comparison(gt_times, gt, predicted, details, out, "native_game_unit", "MVS-Synth / 0000", True, "frame_index", "ORB+Essential")
    plot_trajectory(times, predicted, out, "arbitrary_unit_per_edge", "ORB+Essential / shared MVS0000", "frame_index")
    summary = {**run_metadata(), "status": "FAILED" if fatal else "FINISHED_WITH_REPORTED_FAILURES", "directory": str(out),
               "processed_frames": len(records), "expected_frames": 100, "valid_pose_frames": int(np.isfinite(predicted).all(axis=(1, 2)).sum()),
               "successful_motion_edges": sum(row["status"] == "success" for row in records), "wall_seconds": wall, "fatal_error": fatal}
    write_json(out / "run_summary.json", summary)
    write_json(PROJECT / "reports/SOTA/orb_essential_shared_mvs.json", summary)
    print(json.dumps(summary))
    return int(fatal is not None)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from .common import (POSE_COLUMNS, config_digest, fingerprint, run_metadata, sha256,
                     write_csv, write_json)
from .dataset import discover_sequences, inspect_sequence, load_state
from .geometry import poses_to_rows, project_world, wildworld_to_twc
from .plotting import plot_trajectory, save_figure
from .sync import match_timestamps, timestamp_diagnostics
from .video import iter_frames

INSPECTION_COLUMNS = ["sequence_id", "video", "width", "height", "fps", "frame_count_metadata",
                      "duration_seconds", "state_csv", "pose_count", "depth_exists",
                      "skeleton_exists", "timestamps_complete", "scene_category", "issues"]
STAT_COLUMNS = ["row_index", "timestamp", "pose_valid", "quaternion_original_norm",
                "dt_seconds", "translation_dataset_units", "rotation_degrees",
                "speed_dataset_units_per_second", "angular_speed_degrees_per_second",
                "anomaly_candidate", "reason"]


def inspect_dataset(dataset_config: dict, camera_config: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    if (out / "data_manifest.json").exists():
        raise FileExistsError("Inspection already exists; preserve it and select a new output directory")
    directories, issues = discover_sequences(dataset_config)
    entries = [inspect_sequence(path, dataset_config, camera_config) for path in directories]
    manifest = {**run_metadata(), "dataset": "WildWorld",
                "status": "INSPECTED" if entries else "BLOCKED_NO_DATA",
                "config_digest": config_digest(dataset_config, camera_config),
                "dataset_config": dataset_config, "camera_config": camera_config,
                "issues": issues, "sequences": entries,
                "downloaded_dataset_bytes": 0,
                "note": "Metadata inspection only; no camera ground truth is trusted at this stage."}
    write_json(out / "data_manifest.json", manifest)
    write_csv(out / "dataset_inspection.csv", entries, INSPECTION_COLUMNS)
    return manifest


def motion_statistics(poses, timestamps, valid, norms, time_is_seconds=True) -> list[dict]:
    rows = []
    distances = np.full(len(poses), np.nan)
    for i in range(1, len(poses)):
        if valid[i] and valid[i - 1]:
            distances[i] = np.linalg.norm(poses[i, :3, 3] - poses[i - 1, :3, 3])
    measured = distances[np.isfinite(distances)]
    median = np.median(measured) if len(measured) else np.nan
    mad = np.median(np.abs(measured - median)) if len(measured) else np.nan
    for i in range(len(poses)):
        dt = timestamps[i] - timestamps[i - 1] if i and time_is_seconds else np.nan
        angle = np.nan
        reasons = []
        if not valid[i]:
            reasons.append("missing_or_invalid_pose_or_intrinsics")
        if i and valid[i] and valid[i - 1]:
            angle = np.degrees(Rotation.from_matrix(poses[i - 1, :3, :3].T @ poses[i, :3, :3]).magnitude())
        if i and time_is_seconds and (not np.isfinite(dt) or dt <= 0):
            reasons.append("nonpositive_or_missing_time_interval")
        # A data-driven flag, not a physical impossibility claim. Never remove rows.
        if np.isfinite(distances[i]) and len(measured) >= 10 and mad > 1e-12 and distances[i] > median + 10 * 1.4826 * mad:
            reasons.append("translation_above_median_plus_10_scaled_MAD")
        if np.isfinite(angle) and angle > 90:
            reasons.append("rotation_above_90_degrees_per_adjacent_row")
        rows.append({"row_index": i, "timestamp": timestamps[i], "pose_valid": bool(valid[i]),
                     "quaternion_original_norm": norms[i], "dt_seconds": dt,
                     "translation_dataset_units": distances[i], "rotation_degrees": angle,
                     "speed_dataset_units_per_second": distances[i] / dt if dt > 0 else np.nan,
                     "angular_speed_degrees_per_second": angle / dt if dt > 0 else np.nan,
                     "anomaly_candidate": bool(reasons), "reason": "; ".join(reasons)})
    return rows


def skeleton_preview(directory: Path, frames: list[dict], associations: list[int],
                     poses: np.ndarray, intrinsics: np.ndarray, out: Path, max_mb: float) -> dict:
    archive = directory / "skeleton.npz"
    if not archive.is_file():
        return {"status": "NOT_AVAILABLE", "overlay_is_independent_sync_proof": False}
    metadata = []
    chosen = None
    with zipfile.ZipFile(archive) as handle:
        for info in handle.infolist():
            if not info.filename.endswith(".npy"):
                continue
            with handle.open(info) as stream:
                version = np.lib.format.read_magic(stream)
                shape, fortran, dtype = np.lib.format._read_array_header(stream, version)
            item = {"key": info.filename, "shape": shape, "dtype": str(dtype),
                    "uncompressed_bytes": info.file_size, "object_dtype": bool(dtype.hasobject)}
            metadata.append(item)
            if chosen is None and len(shape) == 3 and shape[2] == 3 and not dtype.hasobject and info.file_size <= max_mb * 1024**2:
                chosen = info.filename
        if chosen:
            with handle.open(chosen) as stream:
                joints = np.load(stream, allow_pickle=False)
        else:
            joints = None
    write_json(out / "skeleton_metadata.json", metadata)
    result = {"status": "NO_BOUNDED_NUMERIC_ENTITY" if joints is None else "CANDIDATE_OVERLAYS",
              "array_key": chosen, "row_count_matches_state": bool(joints is not None and len(joints) == len(poses)),
              "overlay_is_independent_sync_proof": False, "overlays": []}
    if joints is None:
        return result
    for preview_index, frame in enumerate(frames):
        row_index = associations[preview_index]
        if row_index < 0 or row_index >= len(joints) or not np.isfinite(poses[row_index]).all():
            continue
        uv, front = project_world(joints[row_index], poses[row_index], intrinsics[row_index])
        image = frame["image"]
        inside = front & (uv[:, 0] >= 0) & (uv[:, 0] < image.shape[1]) & (uv[:, 1] >= 0) & (uv[:, 1] < image.shape[0])
        fig, ax = plt.subplots(figsize=(9, 5.5), layout="constrained")
        ax.imshow(image[..., ::-1])
        ax.scatter(uv[inside, 0], uv[inside, 1], s=5, c="#f2cf67")
        ax.set(xlim=(0, image.shape[1]), ylim=(image.shape[0], 0),
               title=f"CANDIDATE projection: frame {frame['frame_index']}, state row {row_index}\n"
                     "Joint positions only; manual RGB correspondence review required")
        ax.set_axis_off()
        name = f"projection_{frame['frame_index']:07d}"
        save_figure(fig, out / name)
        result["overlays"].append({"image": name + ".png", "frame_index": frame["frame_index"],
                                   "state_row_index": row_index, "visible_joint_count": int(inside.sum())})
    return result


def validate_sequence(entry: dict, dataset_config: dict, camera_config: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    blockers = list(entry["issues"])
    if blockers:
        return {"sequence_id": entry["sequence_id"], "e0_passed": False, "blockers": blockers}
    if fingerprint(entry["video"]) != entry["video_fingerprint"] or fingerprint(entry["state_csv"]) != entry["state_fingerprint"]:
        raise ValueError("Input changed after inspection")
    state = load_state(Path(entry["state_csv"]), dataset_config, camera_config)
    n = len(state["positions"])
    if n == 0:
        raise ValueError("Empty state CSV")
    expected = {"quaternion_order": "xyzw", "transform_direction": "camera_to_world",
                "position_semantics": "camera_center_in_world",
                "input_camera_axes": "OpenGL_right_up_back",
                "output_camera_axes": "OpenCV_right_down_forward", "camera_handedness": "right"}
    if any(camera_config.get(key) != value for key, value in expected.items()):
        raise ValueError("Unsupported or undocumented camera convention; no guessed conversion permitted")
    norms = np.linalg.norm(state["quaternions"], axis=1)
    valid = np.isfinite(state["positions"]).all(axis=1) & np.isfinite(state["quaternions"]).all(axis=1)
    valid &= np.abs(norms - 1) <= dataset_config["validation"]["max_quaternion_norm_error"]
    valid &= np.isfinite(state["intrinsics"]).all(axis=1) & (state["intrinsics"][:, :2] > 0).all(axis=1)
    poses = np.full((n, 4, 4), np.nan)
    for i in np.flatnonzero(valid):
        poses[i] = wildworld_to_twc(state["positions"][i], state["quaternions"][i])
    sync = dataset_config["sync"]
    timestamps_present = bool(sync.get("timestamp_column"))
    if timestamps_present:
        times = state["timestamps"]
        time_kind = "documented_state_timestamps"
    else:
        fps = entry.get("fps")
        if not fps or fps <= 0:
            raise ValueError("No state timestamps and no usable video FPS; cannot build even candidate times")
        times = state["frame_indices"] / fps
        time_kind = "CANDIDATE_frame_index_divided_by_metadata_fps"
    time_diagnostics = timestamp_diagnostics(times, sync["timestamp_gap_factor"])
    if not time_diagnostics["strictly_increasing"]:
        blockers.append("State timestamps/frame indices are missing, duplicated, or not increasing")
    if time_diagnostics["large_gap_indices"]:
        blockers.append("State time gaps require documented review")
    if not timestamps_present and entry.get("frame_count_metadata") != n:
        blockers.append("Index-only mapping requires agreement of metadata video frame count and state rows")
    missing_fraction = float((~valid).mean())
    if missing_fraction > dataset_config["validation"]["max_missing_pose_fraction"]:
        blockers.append(f"Missing/invalid pose fraction {missing_fraction:.6f} exceeds configured limit")
    if not camera_config.get("world_axes_evidence"):
        blockers.append("World axis directions/handedness require source or calibration evidence")
    if not camera_config.get("length_unit_evidence"):
        blockers.append("Native length unit is unresolved; no metric accuracy may be claimed")
    if camera_config.get("meters_per_dataset_unit") is not None and (
            not np.isfinite(camera_config["meters_per_dataset_unit"]) or camera_config["meters_per_dataset_unit"] <= 0):
        blockers.append("Invalid meters_per_dataset_unit")
    if camera_config.get("distortion_coefficients") is None or not camera_config.get("distortion_evidence"):
        blockers.append("Distortion model/coefficients unresolved")
    if not (dataset_config["validation"].get("projection_review_confirmed") and
            dataset_config["validation"].get("projection_review_evidence")):
        blockers.append("Source-based projection/RGB coordinate review is not confirmed")
    timeline, previews = [], []
    for frame in iter_frames(entry["video"], dataset_config["clip"]):
        timeline.append({key: frame[key] for key in ("frame_index", "video_pts_seconds", "video_relative_seconds")})
        if len(previews) < 6 and (len(timeline) - 1) % max(1, int((entry.get("fps") or 30) * 2)) == 0:
            previews.append(frame)
    if len(timeline) < 2:
        blockers.append("Clip contains fewer than two sampled decoded frames")
    video_pts = np.array([frame["video_pts_seconds"] for frame in timeline])
    video_diagnostics = timestamp_diagnostics(video_pts, sync["timestamp_gap_factor"])
    if not video_diagnostics["strictly_increasing"]:
        blockers.append("Video PTS are missing, duplicated, or not increasing")
    associations = np.full(len(timeline), -1, int)
    match_errors = np.full(len(timeline), np.nan)
    if timestamps_present:
        offset = sync.get("video_pts_to_state_offset_seconds")
        if offset is None or not sync.get("timestamp_clock_evidence"):
            blockers.append("State/video clock origin and offset are undocumented")
        elif time_diagnostics["strictly_increasing"] and video_diagnostics["strictly_increasing"]:
            associations, match_errors = match_timestamps(video_pts + float(offset), times, sync["max_timestamp_error_seconds"])
    else:
        lookup = {int(value): i for i, value in enumerate(state["frame_indices"])}
        associations = np.array([lookup.get(frame["frame_index"], -1) for frame in timeline], int)
        if not (sync.get("frame_mapping_confirmed") and sync.get("frame_mapping_evidence")):
            blockers.append("Frame-index correspondence is only a candidate; independent synchronization evidence required")
        if len(timeline) and np.all(associations >= 0):
            # A constant FPS must also agree with decoded PTS before using index/FPS time.
            inferred_relative = times[associations] - times[associations[0]]
            decoded_relative = video_pts - video_pts[0]
            if np.max(np.abs(inferred_relative - decoded_relative)) > sync["max_timestamp_error_seconds"]:
                blockers.append("Frame-index/FPS clock disagrees with decoded PTS; variable-rate timing needs explicit timestamps")
    if np.any(associations < 0):
        blockers.append("Some sampled RGB frames have no associated pose")
    if any(not valid[index] for index in associations if index >= 0):
        blockers.append("Some sampled RGB frames associate to invalid camera poses")
    for i, item in enumerate(timeline):
        row = int(associations[i])
        item.update({"state_row_index": row, "timestamp_error_seconds": match_errors[i],
                     "evaluation_timestamp": float(times[row]) if row >= 0 else None,
                     "pose_valid": bool(row >= 0 and valid[row])})
    write_csv(out / "frame_associations.csv", timeline,
              ["frame_index", "video_pts_seconds", "video_relative_seconds", "state_row_index",
               "timestamp_error_seconds", "evaluation_timestamp", "pose_valid"])
    write_csv(out / "parse_errors.csv", state["parse_errors"], ["row_index", "reasons"])
    stats = motion_statistics(poses, times, valid, norms)
    write_csv(out / "pose_statistics.csv", stats, STAT_COLUMNS)
    write_csv(out / "anomaly_intervals.csv", [row for row in stats if row["anomaly_candidate"]], STAT_COLUMNS)
    normalized = poses_to_rows(times, poses)
    for i, row in enumerate(normalized):
        row.update({"row_index": i, "frame_index": int(state["frame_indices"][i]), "pose_valid": bool(valid[i]),
                    "original_quaternion_norm": norms[i]})
    write_csv(out / "normalized_ground_truth.csv", normalized,
              POSE_COLUMNS + ["row_index", "frame_index", "pose_valid", "original_quaternion_norm"])
    preview_lookup = {row["frame_index"]: row["state_row_index"] for row in timeline}
    skeleton = skeleton_preview(Path(entry["directory"]), previews,
                                [preview_lookup[f["frame_index"]] for f in previews],
                                poses, state["intrinsics"], out, dataset_config["validation"]["max_skeleton_array_megabytes"])
    if skeleton.get("status") == "CANDIDATE_OVERLAYS" and not skeleton["row_count_matches_state"]:
        blockers.append("Skeleton/state row counts differ")
    passed = not blockers
    result = {"sequence_id": entry["sequence_id"], "e0_passed": passed,
              "blockers": list(dict.fromkeys(blockers)), "pose_count": n,
              "missing_pose_fraction": missing_fraction, "time_kind": time_kind,
              "state_time_diagnostics": time_diagnostics, "video_time_diagnostics": video_diagnostics,
              "sampled_frame_count": len(timeline), "matched_frame_count": int((associations >= 0).sum()),
              "max_timestamp_matching_error_seconds": float(np.nanmax(match_errors)) if np.isfinite(match_errors).any() else None,
              "skeleton_projection": skeleton,
              "focal_length_relative_range": (np.ptp(state["intrinsics"][valid, :2], axis=0) /
                                              np.median(state["intrinsics"][valid, :2], axis=0)).tolist() if valid.any() else None,
              "length_unit": camera_config["length_unit"], "meters_per_dataset_unit": camera_config["meters_per_dataset_unit"],
              "transform_direction": "camera_to_world", "quaternion_order": "xyzw",
              "camera_axes": "right, down, forward", "world_axes": camera_config["world_axes"],
              "quaternion_policy": "Normalize only finite input within norm tolerance; record original norm; preserve invalid rows",
              "validation_scope": "Full selected state CSV; decoded RGB clip only, not full-video synchronization",
              "config_digest": config_digest(dataset_config, camera_config),
              "video_fingerprint": entry["video_fingerprint"], "state_fingerprint": entry["state_fingerprint"],
              "normalized_ground_truth_sha256": sha256(out / "normalized_ground_truth.csv"),
              "frame_associations_sha256": sha256(out / "frame_associations.csv")}
    write_json(out / "normalized_ground_truth.metadata.json", result)
    plot_trajectory(times, poses, out, camera_config["length_unit"],
                    "VALIDATED GT" if passed else "CANDIDATE - E0 NOT PASSED", time_kind)
    write_json(out / "validation.json", result)
    return result


def validate_dataset(inspection: Path, dataset_config: dict, camera_config: dict) -> dict:
    manifest = json.loads((inspection / "data_manifest.json").read_text(encoding="utf-8"))
    if (inspection / "validation.json").exists():
        raise FileExistsError("Validation already exists; do not overwrite past attempts")
    if manifest["config_digest"] != config_digest(dataset_config, camera_config):
        raise ValueError("Configuration changed after inspection")
    entries = []
    for entry in manifest["sequences"]:
        target = inspection / entry["sequence_id"]
        try:
            result = validate_sequence(entry, dataset_config, camera_config, target)
        except Exception as exc:
            result = {"sequence_id": entry["sequence_id"], "e0_passed": False,
                      "blockers": [f"{type(exc).__name__}: {exc}"]}
            write_json(target / "failure.json", result)
        entries.append(result)
    result = {**run_metadata(), "status": "PASS" if entries and all(e["e0_passed"] for e in entries) else
              ("BLOCKED_NO_DATA" if not entries else "FAIL_OR_UNRESOLVED"),
              "e0_passed": bool(entries and all(e["e0_passed"] for e in entries)),
              "sequences": entries, "issues": manifest["issues"],
              "config_digest": manifest["config_digest"],
              "downstream_allowed": bool(entries and all(e["e0_passed"] for e in entries))}
    write_json(inspection / "validation.json", result)
    lines = ["# E0 数据验证", "", f"状态：{result['status']}", "",
             f"实际发现样本数：{len(entries)}。下游 E1 准入：{result['downstream_allowed']}。", "",
             "检查范围：所选 CSV 与 15 秒默认 RGB 片段；没有对未解码视频宣称全程同步。", "",
             "没有实测数据时不生成相机轨迹、位姿统计或精度指标。"]
    lines += ["", *[f"- {issue}" for issue in manifest["issues"]]]
    for entry in entries:
        lines += ["", f"## {entry['sequence_id']}", "", f"E0 passed: {entry['e0_passed']}"]
        lines += [f"- {issue}" for issue in entry["blockers"]]
    (inspection / "E0_data_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result

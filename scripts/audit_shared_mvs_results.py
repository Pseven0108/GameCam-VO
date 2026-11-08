"""Audit existing shared-input results; never run models or select parameters."""
from __future__ import annotations

import _bootstrap
import csv
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, sha256, write_csv, write_json
from gamecam_vo.evaluation import evaluate, load_trajectory
from gamecam_vo.geometry import invert_se3


def main():
    reports = PROJECT / "reports/SOTA"
    directories = {}
    for name, pointer in (("DROID-W", "droid_mvs_evaluation.json"), ("ORB-SLAM3", "orbslam3_mvs_comparison.json"), ("ORB+Essential", "orb_essential_shared_mvs.json")):
        record = json.loads((reports / pointer).read_text(encoding="utf-8"))
        directories[name] = Path(record["directory"])
    ba_path = reports / "ba_track_mvs_evaluation.json"
    if ba_path.exists():
        record = json.loads(ba_path.read_text(encoding="utf-8"))
        if record["status"] != "BA_TRACK_MVS_EXTERNAL_EVALUATION_COMPLETED":
            raise ValueError("BA result pointer is not an actual completed external evaluation")
        directories["BA-Track"] = Path(record["directory"])
    pi3_path = reports / "pi3mos_mvs_evaluation.json"
    if pi3_path.exists():
        record = json.loads(pi3_path.read_text(encoding="utf-8"))
        if record["status"] != "PI3MOS_MVS_EXTERNAL_EVALUATION_COMPLETED":
            raise ValueError("Pi3MOS pointer is not a completed external evaluation")
        directories["Pi3MOS-SLAM"] = Path(record["directory"])
    reference = directories["ORB-SLAM3"] / "evaluation_reference_trajectory.csv"
    gt_times, gt = load_trajectory(reference)
    estimates, primary, evidence = {}, [], {}
    shared_input = None
    shared_K = None
    for name, directory in directories.items():
        times, poses = load_trajectory(directory / "estimated_trajectory.csv")
        if len(times) != 100 or not np.array_equal(times, gt_times):
            raise ValueError("Canonical trajectory must preserve all 100 input indices")
        manifest = json.loads((directory / "input_manifest.json").read_text(encoding="utf-8"))
        matrix = np.asarray(manifest["fixed_K"], dtype=float)
        if shared_K is not None and not np.array_equal(shared_K, matrix):
            raise ValueError("The compared models did not receive identical known intrinsics")
        shared_K = matrix
        signatures = [(r["frame_index"], r["sha256"]) for r in manifest["frames"]]
        if shared_input is not None and signatures != shared_input:
            raise ValueError("The compared models did not use identical RGB inputs")
        shared_input = signatures
        estimates[name] = poses
        with (directory / "metrics.csv").open(newline="", encoding="utf-8") as handle:
            primary.extend({"method": name, **row} for row in csv.DictReader(handle))
        evidence[name] = {"directory": str(directory), "trajectory_sha256": sha256(directory / "estimated_trajectory.csv"),
                          "valid_finite_poses": int(np.isfinite(poses).all(axis=(1, 2)).sum()), "expected_frames": 100}
    orb = directories["ORB-SLAM3"]
    kf_times, kf_poses = load_trajectory(orb / "keyframes_native_tum.txt")
    normalized_kf = invert_se3(kf_poses[0]) @ kf_poses
    target = estimates["ORB-SLAM3"]
    translation_error, rotation_error = [], []
    for time, pose in zip(kf_times, normalized_kf, strict=True):
        index = int(round(time * 30))
        if not 0 <= index < 100 or abs(time - index/30) > 1e-6:
            raise ValueError("Native keyframe timestamp does not map to a shared input")
        if np.isfinite(target[index]).all():
            translation_error.append(float(np.linalg.norm(pose[:3, 3]-target[index, :3, 3])))
            rotation_error.append(float(np.degrees(Rotation.from_matrix(pose[:3, :3].T @ target[index, :3, :3]).magnitude())))
    if not translation_error or max(translation_error) > 5e-6 or max(rotation_error) > 1e-3:
        raise ValueError("Canonical ORB-SLAM3 trajectory disagrees with native camera-to-world keyframes")
    with (orb / "tracking_native.csv").open(newline="", encoding="utf-8") as handle:
        states = list(csv.DictReader(handle))
    state_counts = {state: sum(r["tracking_state"] == state for r in states) for state in sorted({r["tracking_state"] for r in states})}
    common = np.logical_and.reduce([np.isfinite(p).all(axis=(1, 2)) for p in estimates.values()])
    common_rows = []
    for name, poses in estimates.items():
        restricted = poses.copy()
        restricted[~common] = np.nan
        metrics, _ = evaluate(gt_times, gt, gt_times, restricted, tolerance=1e-6, unit="native_game_unit", time_axis="frame_index")
        for row in metrics:
            row["common_support_excluded_frames"] = row.pop("failed_frames")
            row["common_support_exclusion_rate"] = row.pop("failure_rate")
            row["common_support_fraction"] = row.pop("pose_coverage")
            row["actual_primary_valid_pose_frames"] = int(np.isfinite(poses).all(axis=(1, 2)).sum())
        common_rows.extend({"method": name, "support_policy": f"Intersection of existing finite outputs of these {len(directories)} methods; full100 denominator retained; diagnostic only", **row} for row in metrics)
    folder = reports / "E11_shared_input_audit"
    folder.mkdir(exist_ok=True)
    write_csv(folder / "primary_metrics.csv", primary)
    write_csv(folder / "common_support_diagnostic_metrics.csv", common_rows)
    record = {"status": "SHARED_INPUT_AND_ORB_SLAM3_EXPORT_AUDIT_PASSED", "results": evidence,
              "reference_sha256": sha256(reference), "RGB_hashes_identical_for_all_compared_methods": True,
              "known_K_identical_for_all_compared_methods": True,
              "compared_methods": list(directories), "compared_method_count": len(directories),
              "ORB_SLAM3_native_keyframe_comparison_count": len(translation_error),
              "ORB_SLAM3_max_keyframe_translation_difference_map_unit": max(translation_error),
              "ORB_SLAM3_max_keyframe_rotation_difference_degrees": max(rotation_error),
              "ORB_SLAM3_native_online_state_counts": state_counts,
              "ORB_SLAM3_export_direction": "System.cc monocular SaveTrajectoryEuRoC inverts T_cw and writes T_wc, XYZW, nanosecond clock; keyframes normalized by inverse first T_wc agree numerically",
              "common_output_support_frames": int(common.sum()), "common_output_support_frame_indices": np.flatnonzero(common).tolist(),
              "expected_frames": 100, "expected_adjacent_RPE_pairs": 99,
              "do_not_infer_tracking_loss_from_filled_pose_coverage": True,
              "methods_excluded_without_actual_MVS_outputs": [name for name in ("BA-Track", "Pi3MOS-SLAM") if name not in directories],
              "scientific_limit": "Single geometry sequence; no independently labeled object motion, no long-sequence or cross-dataset robustness evidence"}
    write_json(folder / "audit.json", record)
    print(json.dumps(record))


if __name__ == "__main__":
    main()

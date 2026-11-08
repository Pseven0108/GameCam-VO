"""Independently validate a native terminate return after a later BA failure.

The primary sparse pose stage was chosen before GT scoring. This accepts only
its complete native return, never turns a failed full pipeline into success,
and never reads the large optional track/depth pickle or any external GT.
"""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, sha256, write_json
from gamecam_vo.evaluation import load_trajectory
from phase5_motion_support import read, json_lines
from export_ba_track_results import validate_camera


def checked_native_camera(arrays, expected):
    raw = arrays["native_T_wc_translation_quaternion_WXYZ"]
    times = arrays["native_input_indices"]
    retained = arrays["final_retained_T_cw_translation_quaternion_XYZW"]
    keys = arrays["final_retained_input_indices"]
    if raw.shape != (expected, 7) or not np.isfinite(raw).all() or not np.array_equal(times, np.arange(expected)):
        raise ValueError("The original terminate return must cover every finite ordered input")
    norms = np.linalg.norm(raw[:, 3:], axis=1)
    if np.max(np.abs(norms-1)) > 1e-4:
        raise ValueError("Native returned quaternions are not near unit length")
    poses = np.broadcast_to(np.eye(4), (expected, 4, 4)).copy()
    poses[:, :3, 3] = raw[:, :3]
    # This is the documented WXYZ-to-XYZW representation conversion, not a
    # GT-selected inversion, fitted transform, or repair of invalid matrices.
    poses[:, :3, :3] = Rotation.from_quat(raw[:, [4, 5, 6, 3]]).as_matrix()
    times, poses, rigid = validate_camera(times, poses, expected)
    if (keys.ndim != 1 or len(keys) < min(12, expected) or len(np.unique(keys)) != len(keys)
        or not np.array_equal(keys, keys.astype(int)) or (keys < 0).any() or (keys >= expected).any()
        or retained.shape != (len(keys), 7) or not np.isfinite(retained).all()
        or np.max(np.abs(np.linalg.norm(retained[:, 3:], axis=1)-1)) > 1e-4):
        raise ValueError("Independent final retained W2C states have invalid support or quaternions")
    cw = np.broadcast_to(np.eye(4), (len(keys), 4, 4)).copy()
    cw[:, :3, 3] = retained[:, :3]
    cw[:, :3, :3] = Rotation.from_quat(retained[:, 3:]).as_matrix()
    independent = np.linalg.inv(cw)
    selected = poses[keys.astype(int)]
    delta_t = np.linalg.norm(independent[:, :3, 3]-selected[:, :3, 3], axis=1)
    delta_r = np.degrees(Rotation.from_matrix(np.swapaxes(independent[:, :3, :3], 1, 2) @ selected[:, :3, :3]).magnitude())
    if delta_t.max() > 1e-4 or delta_r.max() > .01:
        raise ValueError("Native complete return and independent final W2C states disagree")
    return times, poses, rigid, {"frames": keys.astype(int).tolist(),
        "max_translation_difference_native_unit": float(delta_t.max()),
        "max_rotation_difference_degrees": float(delta_r.max()),
        "maximum_native_return_quaternion_norm_error": float(np.max(np.abs(norms-1)))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--allow-exact-known-legacy-recorder-failure", action="store_true", help="Only the already identified first Crowd recorder: require its exact executed source, actual CUDA-index exception and complete three-field archive")
    args = parser.parse_args()
    out = args.directory.resolve()
    if not any(out.is_relative_to(PROJECT / "results" / e / "BA_TRACK") for e in ("E14_WILD_DYNAMIC", "E15_MOVIE", "E16_BONN")):
        raise ValueError("Only owned new Phase5 BA runs are accepted")
    status, contract = read(out / "status.json"), read(out / "execution_contract.json")
    if status["status"] != "BA_TRACK_PIPELINE_FAILED" or not contract.get("BA_native_terminate_return_archived_before_large_pickle"):
        raise ValueError("Require an actually failed full pipeline with the opt-in original-return archive")
    stages = status["stages"]
    if not stages or stages[-1]["stage"] not in ("sparse_tracker_and_BA", "dense_global_refinement") or not any(r["exit_code"] or r.get("reason") for r in stages):
        raise ValueError("The actual failure must follow sparse processing, with native failure evidence")
    raw_file = out / "motion_decomposition/native_terminated_camera.npz"
    receipt_file = raw_file.with_suffix(".json")
    receipt = read(receipt_file) if receipt_file.exists() else None
    legacy_evidence = None
    if receipt:
        if (receipt["status"] != "NATIVE_TERMINATE_RETURN_ARCHIVED_BEFORE_LARGE_RESULT_SERIALIZATION"
            or sha256(raw_file) != receipt["sha256"] or not receipt["original_terminate_called_once_return_unchanged"]
            or receipt["extra_model_forwards"] != 0 or receipt["RNG_draws"] != 0 or receipt["GT_used"]):
            raise ValueError("Original native return receipt/identity is invalid")
    elif args.allow_exact_known_legacy_recorder_failure:
        known = PROJECT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T152634Z_crowd"
        hook = out / "ba_track_observer.py.executed_source"
        log_file = out / "sparse_tracker_and_BA.log"
        issue_file = out / "pretermination_observer_IO_review.json"
        old_sha = "3bd6ca8b96ffa70968ebf1cd6b4c2f6024ab0720ece17060fd9a41f0025b4d26"
        log = log_file.read_text(encoding="utf-8", errors="replace")
        issue = read(issue_file)
        if (out != known.resolve() or sha256(hook) != old_sha or issue["executed_observer_sha256"] != old_sha
            or issue["current_BA_Crowd_GT_metrics_computed"] or stages[-1]["stage"] != "sparse_tracker_and_BA" or stages[-1]["exit_code"] != 1
            or "ba_track_observer.py" not in log or "terminate" not in log
            or "can't convert cuda:0 device type tensor to numpy" not in log
            or raw_file.stat().st_size > 2*1024**2):
            raise ValueError("This exception route is restricted to the exact predeclared recorder IO fault")
        with zipfile.ZipFile(raw_file) as z:
            names = ["native_T_wc_translation_quaternion_WXYZ.npy", "native_input_indices.npy", "final_retained_T_cw_translation_quaternion_XYZW.npy"]
            if z.namelist() != names or z.testzip() is not None:
                raise ValueError("Require the three actually complete CRC-valid fields; do not repair an incomplete stream")
        legacy_evidence = {"classification": "OPTIONAL_OBSERVER_CUDA_INDEX_SERIALIZATION_ERROR_AFTER_NATIVE_CAMERA_RETURN",
            "log": str(log_file), "log_sha256": sha256(log_file), "executed_observer": str(hook), "executed_observer_sha256": old_sha,
            "pretermination_issue_review": str(issue_file), "pretermination_issue_review_sha256": sha256(issue_file),
            "missing_native_field": "final_retained_input_indices", "missing_native_field_reconstructed_or_claimed": False,
            "independent_state_source": "Separately archived last complete frontend W2C states with actual original-image input keys",
            "native_receipt_not_written_because_recorder_exception": True}
    else:
        raise ValueError("A valid original-return receipt is required; never assume an archive from file presence alone")
    expected = contract["expected_frames"]
    trace_file = out / "motion_decomposition/frontend_calls.jsonl"
    trace = json_lines(trace_file)
    if len(trace) != expected or [r["input_timestamp"] for r in trace] != list(range(expected)):
        raise ValueError("Actual frontend calls must cover every original input")
    with np.load(raw_file, allow_pickle=False) as z:
        arrays = {key: z[key].copy() for key in z.files}
    if legacy_evidence:
        context = trace[-1]
        if not context["online_camera_pose_support_matches_observed_images"]:
            raise ValueError("The failed legacy recorder needs independent final frontend camera/key support")
        saved_retained = arrays["final_retained_T_cw_translation_quaternion_XYZW"]
        if saved_retained.ndim != 2 or saved_retained.shape[1] != 7 or not np.isfinite(saved_retained).all():
            raise ValueError("The third complete native archive field is invalid")
        # Validate against independent already observed final frontend states.
        # These do not recreate the missing native archive timestamp field.
        arrays = {"native_T_wc_translation_quaternion_WXYZ": arrays["native_T_wc_translation_quaternion_WXYZ"],
            "native_input_indices": arrays["native_input_indices"],
            "final_retained_T_cw_translation_quaternion_XYZW": np.asarray(context["online_window_poses_T_cw_xyzw"]),
            "final_retained_input_indices": np.asarray(context["observed_window_input_indices"])}
    times, poses, rigid, comparison = checked_native_camera(arrays, expected)
    comparison["online_trace_sha256"] = sha256(trace_file)
    tum_file = out / "upstream_output" / contract["scene"] / "batrack_traj.txt"
    if tum_file.exists():
        native_times, native = load_trajectory(tum_file)
        if not np.array_equal(native_times, times):
            raise ValueError("Later native TUM timestamps disagree with the archived original return")
        delta_t = np.linalg.norm(native[:, :3, 3]-poses[:, :3, 3], axis=1)
        delta_r = np.degrees(Rotation.from_matrix(np.swapaxes(native[:, :3, :3], 1, 2) @ poses[:, :3, :3]).magnitude())
        if delta_t.max() > 1e-4 or delta_r.max() > .01:
            raise ValueError("Later native TUM values disagree with the original return")
        comparison["native_TUM_comparison"] = {"sha256": sha256(tum_file), "maximum_translation_difference": float(delta_t.max()), "maximum_rotation_difference_degrees": float(delta_r.max())}
    target = out / "native_terminate_camera_review"
    target.mkdir(exist_ok=False)
    archive = target / "canonical_camera_fields.npz"
    np.savez_compressed(archive, tstamps=times, cams_T_world=poses)
    source = PROJECT / "baselines/ba_track/upstream/main/batrack.py"
    shutil.copy2(source, target / "batrack.py.source_for_native_pose_direction")
    shutil.copy2(__file__, target / "review_phase5_ba_terminated_camera.py.executed_source")
    report = {"status": "COMPLETE_NATIVE_TERMINATE_CAMERA_RETURN_INDEPENDENTLY_CHECKED",
        "native_pipeline_status_preserved": status["status"], "full_pipeline_success_claim": False,
        "expected_frames": expected, "complete_camera_frames": len(poses), "rigid_camera_checks": rigid,
        "raw_native_return_archive": str(raw_file), "raw_native_return_archive_sha256": sha256(raw_file),
        "native_return_receipt_sha256": sha256(receipt_file) if receipt else None, "native_status_sha256": sha256(out / "status.json"),
        "legacy_index_IO_exception_evidence": legacy_evidence,
        "complete_camera_archive": str(archive), "complete_camera_archive_sha256": sha256(archive),
        "native_numeric_values_modified": False, "quaternion_to_matrix_representation_conversion": True,
        "model_replayed": False, "GT_used_in_recovery_or_direction_choice": False,
        "independent_native_state_comparison": comparison,
        "source_direction": "Native terminate returns inverse internal SE3, translation then WXYZ, covering every input; independently compare final retained W2C states",
        "serializer_source_sha256": sha256(source), "reviewer_source_sha256": sha256(Path(__file__)),
        "scope": "Predeclared primary sparse camera only. Later optional track/depth serialization or dense refinement failure remains a full-pipeline failure; no repaired large pickle or completed dense output claim."}
    write_json(target / "recovery_review.json", report)
    print(json.dumps({"status": report["status"], "frames": len(poses), "directory": str(target),
        "independent_translation_max": comparison["max_translation_difference_native_unit"], "independent_rotation_max_degrees": comparison["max_rotation_difference_degrees"]}))


if __name__ == "__main__":
    main()

"""CPU arithmetic check using actual archived BA cameras; not a new run."""
from __future__ import annotations

import _bootstrap
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import json_lines
from review_phase5_ba_terminated_camera import checked_native_camera


def main():
    out = PROJECT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T105134Z_person_tracking"
    archive = out / "native_camera_prefix_recovery/complete_native_camera_fields.npz"
    trace_file = out / "motion_decomposition/frontend_calls.jsonl"
    with np.load(archive, allow_pickle=False) as z:
        poses, times = z["cams_T_world"], z["tstamps"]
    context = json_lines(trace_file)[-1]
    xyzw = Rotation.from_matrix(poses[:, :3, :3]).as_quat()
    # This fixture is explicitly constructed from previously accepted actual
    # camera matrices. It does not claim that the old run saved a return archive.
    arrays = {"native_T_wc_translation_quaternion_WXYZ": np.c_[poses[:, :3, 3], xyzw[:, [3, 0, 1, 2]]],
        "native_input_indices": times,
        "final_retained_T_cw_translation_quaternion_XYZW": np.asarray(context["online_window_poses_T_cw_xyzw"]),
        "final_retained_input_indices": np.asarray(context["observed_window_input_indices"])}
    checked_times, checked, rigid, comparison = checked_native_camera(arrays, len(times))
    error = float(np.max(np.abs(checked-poses)))
    if not np.array_equal(checked_times, times) or error > 1e-5:
        raise ValueError("Representation conversion differs from the accepted native camera fixture")
    rejected = []
    for defect in ("missing_input", "wrong_quaternion_order", "wrong_direction"):
        invalid = {k: v.copy() for k, v in arrays.items()}
        if defect == "missing_input":
            invalid["native_input_indices"] = times[:-1]
        elif defect == "wrong_quaternion_order":
            invalid["native_T_wc_translation_quaternion_WXYZ"][:, 3:] = xyzw
        else:
            inverse = np.linalg.inv(checked)
            wrong_quat = Rotation.from_matrix(inverse[:, :3, :3]).as_quat()
            invalid["native_T_wc_translation_quaternion_WXYZ"] = np.c_[inverse[:, :3, 3], wrong_quat[:, [3, 0, 1, 2]]]
        try:
            checked_native_camera(invalid, len(times))
        except ValueError:
            rejected.append(defect)
        else:
            raise ValueError("Expected invalid native source fixture to fail: "+defect)
    report = {"status": "ACTUAL_ARCHIVED_CAMERA_REPRESENTATION_AND_REJECTION_PROBE_PASS",
        "source_camera_archive_sha256": sha256(archive), "source_online_trace_sha256": sha256(trace_file),
        "fixture": "Native camera matrices from the already accepted Person prefix plus separately observed last12 W2C states; reconstructed WXYZ representation only",
        "new_experiment_or_native_return_archive_claim": False, "new_model_execution": False, "GT_used": False,
        "frames": len(times), "maximum_matrix_representation_difference": error,
        "independent_native_state_comparison": comparison, "rigid_camera_checks": rigid,
        "invalid_fixtures_rejected": rejected, "reviewer_source_sha256": sha256(PROJECT / "scripts/review_phase5_ba_terminated_camera.py"),
        "probe_source_sha256": sha256(Path(__file__))}
    write_json(PROJECT / "reports/PHASE5/ba_terminate_return_review_probe.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()

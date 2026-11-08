"""Analytical calibration and missing-GT checks, not Bonn experiments."""
from __future__ import annotations

import _bootstrap
import json

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, write_json
from phase5_bonn_geometry import TM, TROS, convert_bonn_gt
from phase5_partial_reference import evaluate_partial_reference


def main():
    poses = np.broadcast_to(np.eye(4), (6, 4, 4)).copy()
    poses[:, :3, 3] = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [2, 1, 0], [2, 1, 1], [1, 2, 1]]
    poses[:, :3, :3] = Rotation.from_euler("zyx", [[0, 0, 0], [10, 0, 0], [20, 5, 0], [20, 8, 10], [0, 15, 15], [5, 0, 5]], degrees=True).as_matrix()
    raw = np.c_[poses[:, :3, 3], Rotation.from_matrix(poses[:, :3, :3]).as_quat()]
    canonical, normalized, exact, diagnostic, review = convert_bonn_gt(raw, 1)
    # Independent explicit homogeneous multiplication of the published formula.
    direct = np.stack([TROS @ pose @ TROS @ TM for pose in poses])
    expected = np.stack([np.linalg.solve(direct[1], value) for value in direct])
    assert np.max(np.abs(exact-direct)) < 1e-12 and np.max(np.abs(normalized-expected)) < 1e-12
    assert np.array_equal(canonical[:, :3, 3], normalized[:, :3, 3])
    assert np.allclose(canonical[1], np.eye(4), atol=1e-12)
    assert np.max(np.abs(np.linalg.det(canonical[:, :3, :3])-1)) < 1e-12
    keys = np.array([0, 1, 3, 4, 5])
    rows, details = evaluate_partial_reference(keys, poses[keys], np.arange(6), poses, unit="analytical_unit", seconds=2.)
    assert rows[0]["valid_pose_frames"] == 6 and rows[0]["GT_associated_frames"] == 5
    assert rows[0]["valid_rpe_pairs"] == 3 and details["rpe_pairs_original_input_keys"] == [[0, 1], [3, 4], [4, 5]]
    assert rows[0]["ATE_RMSE"] < 1e-12 and rows[0]["RPE_translation_RMSE"] < 1e-12
    blocked, _ = evaluate_partial_reference(keys, poses[keys], np.arange(6), poses, unit="analytical_unit", seconds=2., rotation_metrics_valid=False)
    assert blocked[0]["ATE_RMSE"] < 1e-12 and blocked[0]["RPE_rotation_RMSE_degrees"] is None and blocked[0]["RPE_translation_RMSE"] is None
    record = {"status": "ANALYTICAL_BONN_AFFINE_FORMULA_AND_GT_GAP_PROBES_PASS", "source_formula_max_error": float(np.max(np.abs(normalized-expected))),
        "primary_translations_unchanged_by_rotation_canonicalization": True, "Tm_singular_values": review["Tm_linear_singular_values"],
        "missing_GT_not_counted_as_prediction_failure": True, "RPE_does_not_bridge_missing_GT_keys": True,
        "rotation_dependent_metrics_block_on_defect": True, "real_Bonn_data_or_model_experiment": False}
    write_json(PROJECT / "reports/PHASE5/bonn_geometry_plumbing_probe.json", record)
    print(json.dumps(record))


if __name__ == "__main__":
    main()

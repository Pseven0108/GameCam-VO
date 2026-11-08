"""Full RGB coverage and GT-limited camera metrics without bridging GT gaps."""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.evaluation import evaluate, rmse
from gamecam_vo.geometry import invert_se3


def evaluate_partial_reference(gt_keys, gt, input_keys, predicted, *, unit, seconds, rotation_metrics_valid=True):
    gt_keys, input_keys = np.asarray(gt_keys), np.asarray(input_keys)
    n = len(input_keys)
    if not np.array_equal(input_keys, np.arange(n)) or len(predicted) != n or not np.isfinite(predicted).all():
        raise ValueError("Keep every ordered finite native filled camera for the full-input coverage gate")
    if not np.array_equal(gt_keys, gt_keys.astype(int)) or not np.all(np.diff(gt_keys) > 0) or (gt_keys < 0).any() or (gt_keys >= n).any():
        raise ValueError("Associated GT must use unique retained original RGB sample keys")
    rows, details = evaluate(gt_keys, gt, input_keys, predicted, tolerance=1e-6, unit=unit,
        scale_status="learned_prior_physical_scale_unverified", inference_seconds=seconds, time_axis="frame_index")
    adjacent = np.flatnonzero(np.diff(gt_keys) == 1)
    invariant_rotation_errors = []
    for index in adjacent:
        first, second = int(gt_keys[index]), int(gt_keys[index+1])
        gt_delta_r = gt[index, :3, :3].T @ gt[index+1, :3, :3]
        pr_delta_r = predicted[first, :3, :3].T @ predicted[second, :3, :3]
        invariant_rotation_errors.append(np.degrees(Rotation.from_matrix(gt_delta_r.T @ pr_delta_r).magnitude()))
    for row in rows:
        row.update(expected_frames=n, valid_pose_frames=n, prediction_rows=n, failed_frames=0, pose_coverage=1., failure_rate=0.,
            GT_associated_frames=len(gt_keys), GT_unmatched_input_frames=n-len(gt_keys), camera_metric_pose_support=len(gt_keys),
            GT_input_coverage=len(gt_keys)/n, expected_rpe_pairs=n-1, valid_rpe_pairs=len(adjacent),
            rpe_pair_coverage=len(adjacent)/(n-1) if n > 1 else None, GT_adjacent_pair_support=len(adjacent),
            RPE_does_not_bridge_missing_GT_sample_keys=True,
            missing_GT_is_not_a_model_tracking_failure=True, canonical_reference_rotation_audit_passed=rotation_metrics_valid)
        row["RPE_rotation_RMSE_degrees"] = rmse(invariant_rotation_errors) if rotation_metrics_valid else None
        row["rotation_RPE_semantics"] = "Adjacent camera rotation is world-gauge invariant; does not require position alignment"
        if row["status"] == "COMPUTED":
            alignment = details["alignments"][row["alignment"]]
            aligned = predicted.copy()
            rotation = np.asarray(alignment["rotation"])
            aligned[:, :3, :3] = rotation @ predicted[:, :3, :3]
            aligned[:, :3, 3] = alignment["scale"]*(predicted[:, :3, 3] @ rotation.T)+np.asarray(alignment["translation"])
            trans_error, rot_error = [], []
            for index in adjacent:
                first, second = int(gt_keys[index]), int(gt_keys[index+1])
                expected_delta = invert_se3(gt[index]) @ gt[index+1]
                predicted_delta = invert_se3(aligned[first]) @ aligned[second]
                error = invert_se3(expected_delta) @ predicted_delta
                trans_error.append(np.linalg.norm(error[:3, 3]))
                rot_error.append(np.degrees(Rotation.from_matrix(error[:3, :3]).magnitude()))
            row.update(RPE_translation_RMSE=rmse(trans_error), TransErr_RMSE=rmse(trans_error), RPE_rotation_RMSE_degrees=rmse(rot_error))
        if not rotation_metrics_valid:
            for name in ("RPE_translation_RMSE", "TransErr_RMSE", "RPE_rotation_RMSE_degrees", "RotErr_RMSE_degrees"):
                row[name] = None
            row["rotation_dependent_metrics_unavailable_reason"] = "PUBLISHED_CALIBRATION_NORMALIZED_ROTATION_EXCEEDS_PREDECLARED_SO3_DEFECT"
    details["rpe_pairs_original_input_keys"] = [[int(gt_keys[i]), int(gt_keys[i+1])] for i in adjacent]
    details["GT_sample_keys"] = gt_keys.astype(int).tolist()
    details["full_input_frame_count"] = n
    details["rpe_pairs_expected_indices"] = [[int(i), int(i+1)] for i in adjacent]
    return rows, details

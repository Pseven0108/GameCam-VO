"""Declared diagnostics when synthetic camera positions cannot identify a gauge."""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation


def underconstrained_evaluation(gt, predicted, unit, seconds):
    if gt.shape != predicted.shape or gt.shape[1:] != (4, 4) or not np.isfinite(predicted).all():
        raise ValueError("This diagnostic requires the full finite native camera support")
    n = len(gt)
    gt_step_r = np.swapaxes(gt[:-1, :3, :3], 1, 2) @ gt[1:, :3, :3]
    pr_step_r = np.swapaxes(predicted[:-1, :3, :3], 1, 2) @ predicted[1:, :3, :3]
    rotation_error = np.degrees(Rotation.from_matrix(np.swapaxes(gt_step_r, 1, 2) @ pr_step_r).magnitude())
    rotation_rmse = float(np.sqrt(np.mean(rotation_error**2)))
    common = {"expected_frames": n, "prediction_rows": n, "timestamp_matched_frames": n, "valid_pose_frames": n,
        "failed_frames": 0, "pose_coverage": 1., "failure_rate": 0., "expected_rpe_pairs": n-1, "valid_rpe_pairs": n-1,
        "rpe_pair_coverage": 1., "rpe_delta_samples": 1, "native_ground_truth_unit": unit,
        "prediction_scale_status": "learned_prior_physical_scale_unverified", "inference_seconds": seconds, "input_fps": n/seconds,
        "timestamp_association_unit": "frame_index", "max_frame_index_matching_error": 0., "se3_has_metric_interpretation": False,
        "sim3_is_metric_accuracy": False, "RPE_rotation_RMSE_degrees": rotation_rmse,
        "rotation_RPE_semantics": "Relative camera rotation is world-gauge invariant; available even when positional alignment is unidentifiable"}
    metrics = [{**common, "alignment": alignment, "status": "UNAVAILABLE", "unavailable_reason": "REFERENCE_TRANSLATION_EFFECTIVE_RANK_BELOW_TWO_POSITION_ALIGNMENT_UNDERCONSTRAINED",
        "alignment_scale": None, "ATE_RMSE": None, "RPE_translation_RMSE": None, "RotErr_RMSE_degrees": None, "TransErr_RMSE": None} for alignment in ("SE3", "Sim3")]
    details = {"association": list(range(n)), "valid_mask": [True]*n, "alignments": {},
        "gauge_invariant_adjacent_rotation_error_degrees": rotation_error.tolist(),
        "native_translation_drift_RMS_native_unit": float(np.sqrt(np.mean(np.sum((predicted[:, :3, 3]-predicted[0, :3, 3])**2, axis=1))))}
    delta_r = gt[:, :3, :3] @ np.swapaxes(predicted[:, :3, :3], 1, 2)
    anchor_r = Rotation.from_matrix(delta_r).mean().as_matrix()
    source = predicted[:, :3, 3] @ anchor_r.T
    target = gt[:, :3, 3]
    centered_source, centered_target = source-source.mean(axis=0), target-target.mean(axis=0)
    variance = float(np.sum(centered_source**2))
    scale = float(np.sum(centered_source*centered_target)/variance) if variance > 1e-10 else None
    diagnostic = {"status": "UNAVAILABLE", "reason": "POSITIVE_SCALE_NOT_IDENTIFIABLE", "source_position_variance": variance,
        "scale": scale, "scope": "Separate orientation-anchored diagnostic, not standard position-only SE3/Sim3 ATE"}
    if scale is not None and scale > 0 and np.sum(centered_target**2) > n*1e-10:
        translation = target.mean(axis=0)-scale*source.mean(axis=0)
        aligned = scale*source+translation
        residual = np.linalg.norm(aligned-target, axis=1)
        gt_step_t = np.einsum("nij,nj->ni", np.swapaxes(gt[:-1, :3, :3], 1, 2), np.diff(gt[:, :3, 3], axis=0))
        pr_step_t = np.einsum("nij,nj->ni", np.swapaxes(predicted[:-1, :3, :3], 1, 2), scale*np.diff(predicted[:, :3, 3], axis=0))
        translation_error = np.linalg.norm(gt_step_t-pr_step_t, axis=1)
        orientation_error = np.degrees(Rotation.from_matrix(np.swapaxes(gt[:, :3, :3], 1, 2) @ (anchor_r @ predicted[:, :3, :3])).magnitude())
        alignment = {"scale": scale, "rotation": anchor_r.tolist(), "translation": translation.tolist()}
        row = {**common, "alignment": "orientation_anchored_Sim3_diagnostic", "status": "COMPUTED_DIAGNOSTIC", "unavailable_reason": None,
            "alignment_scale": scale, "ATE_RMSE": float(np.sqrt(np.mean(residual**2))), "RPE_translation_RMSE": float(np.sqrt(np.mean(translation_error**2))),
            "RotErr_RMSE_degrees": float(np.sqrt(np.mean(orientation_error**2))), "TransErr_RMSE": float(np.sqrt(np.mean(translation_error**2)))}
        metrics.append(row)
        diagnostic.update(status="COMPUTED_DIAGNOSTIC", reason=None, alignment=alignment, translation_residuals=residual.tolist(), metrics=row)
    details["orientation_anchored_diagnostic"] = diagnostic
    return metrics, details


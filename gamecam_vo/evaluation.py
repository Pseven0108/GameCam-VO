from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from .geometry import invert_se3, rows_to_poses
from .sync import match_timestamps


def load_trajectory(path: Path) -> tuple[np.ndarray, np.ndarray]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return rows_to_poses(list(csv.DictReader(handle)))
    values = np.loadtxt(path, comments="#", ndmin=2)
    if values.shape[1] != 8:
        raise ValueError("TUM trajectory must have 8 columns: timestamp tx ty tz qx qy qz qw")
    keys = ["timestamp", "tx", "ty", "tz", "qx", "qy", "qz", "qw"]
    return rows_to_poses([dict(zip(keys, row, strict=True)) for row in values])


def fit_alignment(predicted: np.ndarray, ground_truth: np.ndarray, with_scale: bool):
    if len(predicted) < 3:
        raise ValueError("Fewer than three valid matched poses")
    pc, gc = predicted.mean(axis=0), ground_truth.mean(axis=0)
    x, y = predicted - pc, ground_truth - gc
    if np.linalg.matrix_rank(x, tol=1e-9) < 2 or np.linalg.matrix_rank(y, tol=1e-9) < 2:
        raise ValueError("Stationary/collinear trajectory: position-only rotation alignment is underconstrained")
    covariance = y.T @ x / len(x)
    u, singular, vt = np.linalg.svd(covariance)
    signs = np.ones(3)
    signs[2] = np.sign(np.linalg.det(u @ vt))
    rotation = u @ np.diag(signs) @ vt
    variance = np.mean(np.sum(x * x, axis=1))
    scale = float(np.sum(singular * signs) / variance) if with_scale else 1.0
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Nonpositive or invalid global alignment scale")
    translation = gc - scale * rotation @ pc
    return scale, rotation, translation


def rmse(values) -> float | None:
    values = np.asarray(values, float)
    return float(np.sqrt(np.mean(values * values))) if len(values) else None


def evaluate(ground_truth_times, ground_truth, predicted_times, predicted,
             tolerance=0.005, rpe_delta=1, scale_status="arbitrary", unit="dataset_unit",
             inference_seconds=None, time_axis="seconds") -> tuple[list[dict], dict]:
    if rpe_delta < 1 or int(rpe_delta) != rpe_delta:
        raise ValueError("RPE sample lag must be a positive integer")
    rpe_delta = int(rpe_delta)
    gt_times = np.asarray(ground_truth_times, float)
    pred_times = np.asarray(predicted_times, float)
    association, errors = match_timestamps(gt_times, pred_times, tolerance)
    matched = association >= 0
    aligned_input = np.full_like(ground_truth, np.nan, dtype=float)
    aligned_input[matched] = predicted[association[matched]]
    gt_finite = np.isfinite(ground_truth).all(axis=(1, 2))
    if not gt_finite.all():
        raise ValueError("Evaluation GT contains invalid poses; E0 must validate the evaluated subset")
    valid = matched & np.isfinite(aligned_input).all(axis=(1, 2))
    expected_pairs = max(0, len(gt_times) - rpe_delta)
    pairs = [(i, i + rpe_delta) for i in range(expected_pairs) if valid[i] and valid[i + rpe_delta]]
    base = {"expected_frames": len(gt_times), "prediction_rows": len(pred_times),
            "timestamp_matched_frames": int(matched.sum()), "valid_pose_frames": int(valid.sum()),
            "failed_frames": int((~valid).sum()), "pose_coverage": float(valid.mean()) if len(valid) else 0.0,
            "failure_rate": float((~valid).mean()) if len(valid) else None,
            "expected_rpe_pairs": expected_pairs, "valid_rpe_pairs": len(pairs),
            "rpe_pair_coverage": len(pairs) / expected_pairs if expected_pairs else None,
            "rpe_delta_samples": rpe_delta, "native_ground_truth_unit": unit,
            "prediction_scale_status": scale_status,
            "inference_seconds": inference_seconds,
            "input_fps": len(pred_times) / inference_seconds if inference_seconds and inference_seconds > 0 else None,
            "max_timestamp_error_seconds": float(np.nanmax(errors)) if matched.any() and time_axis == "seconds" else None,
            "max_frame_index_matching_error": float(np.nanmax(errors)) if matched.any() and time_axis == "frame_index" else None,
            "timestamp_association_unit": time_axis,
            "se3_has_metric_interpretation": scale_status == "metric" and unit == "meter",
            "sim3_is_metric_accuracy": False}
    rows, details = [], {"valid_mask": valid.tolist(), "association": association.tolist(),
                         "rpe_pairs_expected_indices": pairs, "alignments": {}}
    for kind in ("SE3", "Sim3"):
        row = {**base, "alignment": kind, "status": "UNAVAILABLE", "unavailable_reason": None,
               "alignment_scale": None, "ATE_RMSE": None, "RPE_translation_RMSE": None,
               "RPE_rotation_RMSE_degrees": None, "RotErr_RMSE_degrees": None, "TransErr_RMSE": None}
        try:
            scale, rotation, translation = fit_alignment(aligned_input[valid, :3, 3],
                                                         ground_truth[valid, :3, 3], kind == "Sim3")
            estimated = aligned_input.copy()
            estimated[valid, :3, 3] = scale * (rotation @ aligned_input[valid, :3, 3].T).T + translation
            estimated[valid, :3, :3] = rotation @ aligned_input[valid, :3, :3]
            distances = np.linalg.norm(estimated[valid, :3, 3] - ground_truth[valid, :3, 3], axis=1)
            rotation_errors = np.degrees(Rotation.from_matrix(
                np.swapaxes(ground_truth[valid, :3, :3], 1, 2) @ estimated[valid, :3, :3]).magnitude())
            rpe_t, rpe_r = [], []
            for first, second in pairs:
                gt_delta = invert_se3(ground_truth[first]) @ ground_truth[second]
                pred_delta = invert_se3(estimated[first]) @ estimated[second]
                difference = invert_se3(gt_delta) @ pred_delta
                rpe_t.append(np.linalg.norm(difference[:3, 3]))
                rpe_r.append(np.degrees(Rotation.from_matrix(difference[:3, :3]).magnitude()))
            row.update({"status": "COMPUTED", "alignment_scale": scale, "ATE_RMSE": rmse(distances),
                        "RPE_translation_RMSE": rmse(rpe_t), "RPE_rotation_RMSE_degrees": rmse(rpe_r),
                        "RotErr_RMSE_degrees": rmse(rotation_errors), "TransErr_RMSE": rmse(rpe_t)})
            details["alignments"][kind] = {"scale": scale, "rotation": rotation.tolist(),
                                          "translation": translation.tolist(),
                                          "per_valid_frame_ATE": distances.tolist(),
                                          "per_valid_frame_RotErr_degrees": rotation_errors.tolist()}
        except ValueError as exc:
            row["unavailable_reason"] = str(exc)
        rows.append(row)
    return rows, details

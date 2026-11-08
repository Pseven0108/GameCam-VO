"""Bonn's published sensor/marker transform, with its affine scale exposed."""
from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation

TM = np.array([[1.0157, .1828, -.2389, .0113], [.0009, -.8431, -.6413, -.0098],
    [-.3009, .6147, -.8085, .0111], [0., 0., 0., 1.]])
TROS = np.array([[-1., 0., 0., 0.], [0., 0., 1., 0.], [0., 1., 0., 0.], [0., 0., 0., 1.]])


def proper_rotation(matrix):
    u, _, vt = np.linalg.svd(matrix)
    correction = np.eye(3)
    correction[-1, -1] = np.linalg.det(u @ vt)
    return u @ correction @ vt


def convert_bonn_gt(raw_xyzw, origin_row):
    raw = np.asarray(raw_xyzw, float)
    if raw.ndim != 2 or raw.shape[1] != 7 or not np.isfinite(raw).all():
        raise ValueError("Finite Bonn XYZW sensor pose records required")
    norm_error = float(np.max(np.abs(np.linalg.norm(raw[:, 3:], axis=1)-1)))
    if norm_error > 1e-4:
        raise ValueError("Published MoCap quaternion norm failed tolerance")
    poses = np.broadcast_to(np.eye(4), (len(raw), 4, 4)).copy()
    poses[:, :3, :3] = Rotation.from_quat(raw[:, 3:]).as_matrix()
    poses[:, :3, 3] = raw[:, :3]
    exact = TROS.T @ poses @ TROS @ TM
    normalized = np.linalg.inv(exact[origin_row]) @ exact
    primary = normalized.copy()
    for frame in range(len(primary)):
        primary[frame, :3, :3] = proper_rotation(normalized[frame, :3, :3])
    defect = np.linalg.norm(np.swapaxes(normalized[:, :3, :3], 1, 2) @ normalized[:, :3, :3]-np.eye(3), axis=(1, 2))
    projection = np.linalg.norm(normalized[:, :3, :3]-primary[:, :3, :3], axis=(1, 2))
    rigid_tm = TM.copy()
    rigid_tm[:3, :3] = proper_rotation(TM[:3, :3])
    physical_diagnostic = TROS.T @ poses @ TROS @ rigid_tm
    singular = np.linalg.svd(TM[:3, :3], compute_uv=False)
    review = {"published_Tm": TM.tolist(), "published_Tros": TROS.tolist(), "Tm_linear_singular_values": singular.tolist(),
        "Tm_linear_determinant": float(np.linalg.det(TM[:3, :3])), "normalization_origin_raw_GT_row": int(origin_row),
        "primary_formula": "inv(Tros.T @ raw[origin] @ Tros @ Tm) @ (Tros.T @ raw[i] @ Tros @ Tm)",
        "primary_translation_unit": "Bonn_official_transform_unit", "primary_positions_identical_to_exact_native_affine_normalization": bool(np.array_equal(primary[:, :3, 3], normalized[:, :3, 3])),
        "approximate_raw_translation_scale_factor": float(1/np.mean(singular)),
        "normalized_rotation_max_SO3_Frobenius_defect": float(defect.max()), "normalized_rotation_max_polar_projection_Frobenius_change": float(projection.max()),
        "predeclared_rotation_defect_tolerance": 5e-4, "rotation_metrics_valid": bool(defect.max() <= 5e-4),
        "orientation_canonicalization": "Proper polar rotation only for CSV quaternion export; exact affine matrices retained, translations unchanged",
        "raw_quaternion_max_norm_error": norm_error,
        "physical_diagnostic_formula": "Tros.T @ raw[i] @ Tros @ rigid_polar(Tm); exact Tm translation retained; no affine first-matrix normalization",
        "physical_diagnostic_unit": "raw_MoCap_translation_unit", "best_score_convention_selection": False}
    return primary, normalized, exact, physical_diagnostic, review

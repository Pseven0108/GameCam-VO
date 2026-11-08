from __future__ import annotations

import numpy as np

WORLD_REFLECTION = np.diag([1.0, 1.0, -1.0, 1.0])


def convert_world_to_camera(extrinsic: np.ndarray, tolerance=1e-4) -> tuple[np.ndarray, dict]:
    """Use ONE global world-Z reflection; never project a reflection onto SO(3)."""
    original = np.asarray(extrinsic, dtype=float)
    if original.shape != (4, 4) or not np.isfinite(original).all():
        raise ValueError("MVS extrinsic must be finite 4x4")
    if not np.allclose(original[3], [0, 0, 0, 1], atol=tolerance, rtol=0):
        raise ValueError("Invalid homogeneous extrinsic row")
    rotation = original[:3, :3]
    determinant = float(np.linalg.det(rotation))
    orthogonality = float(np.max(np.abs(rotation.T @ rotation - np.eye(3))))
    if abs(determinant + 1) > tolerance or orthogonality > tolerance:
        raise ValueError(f"Expected the documented orthogonal det=-1 MVS matrix, got det={determinant}, error={orthogonality}")
    # X_world_new = F * X_world_raw; E_new = E_raw * F.
    # Both the relative camera transforms and every pixel projection are preserved.
    camera_from_world = original @ WORLD_REFLECTION
    raw_world_from_camera = np.linalg.inv(camera_from_world)
    world_from_camera = raw_world_from_camera.copy()
    adjustment = 0.0
    numerical_projection = orthogonality > 1e-10 or abs(determinant + 1) > 1e-10
    if numerical_projection:
        # Only AFTER the constant reflection is removed: a tightly bounded
        # polar correction removes measured finite-precision non-orthogonality.
        # Preserve the exact original camera center and retain the raw matrix.
        u, singular, vt = np.linalg.svd(world_from_camera[:3, :3])
        rotation_so3 = u @ vt
        if np.linalg.det(rotation_so3) <= 0:
            raise ValueError("Numeric SO3 correction would introduce a reflection")
        adjustment = float(np.max(np.abs(rotation_so3 - world_from_camera[:3, :3])))
        if adjustment > tolerance:
            raise ValueError("Camera numeric correction exceeds the declared tolerance")
        world_from_camera[:3, :3] = rotation_so3
    return world_from_camera, {"raw_determinant": determinant, "raw_orthogonality_error": orthogonality,
                               "normalized_determinant": float(np.linalg.det(world_from_camera[:3, :3])),
                               "world_basis_transform": WORLD_REFLECTION.tolist(),
                               "raw_matrix_altered": False, "reflection_removed_by_SVD": False,
                               "numeric_SO3_polar_correction_used": numerical_projection,
                               "numeric_rotation_max_abs_adjustment": adjustment,
                               "numeric_correction_tolerance": tolerance,
                               "original_camera_center_preserved": True}

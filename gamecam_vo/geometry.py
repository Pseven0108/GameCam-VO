from __future__ import annotations

import ast
import re
import numpy as np
from scipy.spatial.transform import Rotation

GL_FROM_CV = np.diag([1.0, -1.0, -1.0])


def parse_vector(value: str, size: int) -> np.ndarray:
    """Read numeric CSV tuples without eval; retain explicit missing components."""
    text = re.sub(r"\b(?:nan|NaN|NAN)\b", "None", value.strip())
    result = ast.literal_eval(text)
    if not isinstance(result, (tuple, list)) or len(result) != size:
        raise ValueError(f"Expected a numeric vector of length {size}")
    if any(x is not None and (isinstance(x, bool) or not isinstance(x, (float, int))) for x in result):
        raise ValueError("Vector contains nonnumeric fields")
    return np.array([np.nan if x is None else x for x in result], dtype=float)


def wildworld_to_twc(position: np.ndarray, quaternion_xyzw: np.ndarray) -> np.ndarray:
    """Preserve native world axes; change the local camera basis GL -> CV."""
    transform = np.eye(4)
    transform[:3, :3] = Rotation.from_quat(quaternion_xyzw).as_matrix() @ GL_FROM_CV
    transform[:3, 3] = position
    return transform


def invert_se3(transform: np.ndarray) -> np.ndarray:
    result = np.eye(4)
    result[:3, :3] = transform[:3, :3].T
    result[:3, 3] = -result[:3, :3] @ transform[:3, 3]
    return result


def integrate_recover_pose(twc_previous: np.ndarray, rotation: np.ndarray,
                           translation_direction: np.ndarray) -> np.ndarray:
    # recoverPose maps C_previous -> C_current: x2 = R21*x1 + t21.
    # A unit t is an arbitrary per-edge gauge, never a metric displacement.
    tc2_c1 = np.eye(4)
    tc2_c1[:3, :3] = rotation
    tc2_c1[:3, 3] = np.asarray(translation_direction).reshape(3)
    return twc_previous @ invert_se3(tc2_c1)


def poses_to_rows(timestamps: np.ndarray, transforms: np.ndarray) -> list[dict]:
    rows = []
    previous_q = None
    for timestamp, transform in zip(timestamps, transforms, strict=True):
        if np.isfinite(transform).all():
            quaternion = Rotation.from_matrix(transform[:3, :3]).as_quat()
            if previous_q is not None and np.dot(previous_q, quaternion) < 0:
                quaternion *= -1
            previous_q = quaternion
            components = [*transform[:3, 3], *quaternion]
        else:
            components = [np.nan] * 7
        rows.append(dict(zip(["timestamp", "tx", "ty", "tz", "qx", "qy", "qz", "qw"],
                             [float(timestamp), *map(float, components)], strict=True)))
    return rows


def rows_to_poses(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    timestamps = np.array([float(row["timestamp"]) for row in rows])
    transforms = np.full((len(rows), 4, 4), np.nan)
    for i, row in enumerate(rows):
        values = np.array([float(row[key]) for key in ("tx", "ty", "tz", "qx", "qy", "qz", "qw")])
        if np.isfinite(values).all():
            if abs(np.linalg.norm(values[3:]) - 1) > 0.01:
                raise ValueError("Trajectory quaternion is not unit length")
            transforms[i] = np.eye(4)
            transforms[i, :3, 3] = values[:3]
            transforms[i, :3, :3] = Rotation.from_quat(values[3:]).as_matrix()
    return timestamps, transforms


def project_world(points: np.ndarray, twc: np.ndarray, intrinsics: np.ndarray):
    camera = (points - twc[:3, 3]) @ twc[:3, :3]
    z = camera[:, 2]
    uv = np.full((len(camera), 2), np.nan)
    valid = np.isfinite(camera).all(axis=1) & (z > 0.05)
    fx, fy, cx, cy = intrinsics
    uv[valid, 0] = fx * camera[valid, 0] / z[valid] + cx
    uv[valid, 1] = fy * camera[valid, 1] / z[valid] + cy
    return uv, valid

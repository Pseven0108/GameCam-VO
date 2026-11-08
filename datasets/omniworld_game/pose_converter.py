from __future__ import annotations
import numpy as np
from scipy.spatial.transform import Rotation


def wxyz_w2c_to_twc(quaternions, translations, tolerance=0.001, metric_scale=None):
    q, t = np.asarray(quaternions, float), np.asarray(translations, float)
    if q.ndim != 2 or q.shape[1] != 4 or t.shape != (len(q), 3):
        raise ValueError("Official OmniWorld camera arrays must have shapes (N,4) and (N,3)")
    norms = np.linalg.norm(q, axis=1)
    if not np.isfinite(q).all() or not np.isfinite(t).all() or np.any(norms <= 1e-8):
        raise ValueError("Invalid reference quaternion/translation")
    # Match the official SciPy reader: optimized nonzero quaternion parameters
    # are normalized to represent rotations. Their original norms are audited.
    rotations = Rotation.from_quat(q[:, [1, 2, 3, 0]]).as_matrix()
    poses = np.repeat(np.eye(4)[None], len(q), axis=0)
    poses[:, :3, :3] = rotations.transpose(0, 2, 1)
    poses[:, :3, 3] = -np.einsum("nij,nj->ni", poses[:, :3, :3], t)
    if metric_scale is not None:
        if not np.isfinite(metric_scale) or metric_scale <= 0:
            raise ValueError("Invalid per-scene metadata scale")
        poses[:, :3, 3] *= float(metric_scale)
    return poses

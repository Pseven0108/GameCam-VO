"""CPU decoding contract, not an independent metric calibration certificate."""
import numpy as np


def decode(raw, metric_scale=None):
    a = np.asarray(raw)
    if a.ndim != 2 or a.dtype != np.uint16 or a.size == 0:
        raise ValueError("Nonempty uint16 grayscale depth required")
    if metric_scale is not None and (not np.isfinite(metric_scale) or metric_scale <= 0):
        raise ValueError("Metric Scale must be a finite positive source value")
    x = a.astype(np.float32) / np.float32(65535.)
    valid = ~(x < np.float32(.0015)) & ~(x > np.float32(65500. / 65535.))
    depth = x / (np.float32(1000.) - x * np.float32(999.)) / np.float32(.004)
    depth[~valid] = -1
    if metric_scale is not None: depth[valid] *= float(metric_scale)
    return depth, valid

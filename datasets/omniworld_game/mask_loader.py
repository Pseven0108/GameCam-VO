from __future__ import annotations
import cv2
import numpy as np


def read_dynamic_mask(path):
    mask = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if mask is None:
        raise FileNotFoundError(path)
    if mask.ndim == 3 and mask.shape[2] == 3:
        if not np.array_equal(mask[..., 0], mask[..., 1]) or not np.array_equal(mask[..., 1], mask[..., 2]):
            raise ValueError("A colored instance/class mask is not a documented binary dynamic mask")
        mask = mask[..., 0]
    if mask.ndim != 2 or not set(np.unique(mask)).issubset({0, 1, 255, 65535}):
        raise ValueError("Unsupported binary mask encoding")
    # Official guide: white = dynamic, black = background.
    return mask > 0

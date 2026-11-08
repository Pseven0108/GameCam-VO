from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
import cv2
import numpy as np

from .pose_converter import convert_world_to_camera


def read_camera(path: Path, tolerance=1e-4) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    for key in ("extrinsic", "f_x", "f_y", "c_x", "c_y"):
        if key not in raw:
            raise ValueError(f"Official MVS camera field {key} missing in {path}")
    k = np.array([[raw["f_x"], 0, raw["c_x"]], [0, raw["f_y"], raw["c_y"]], [0, 0, 1]], dtype=float)
    if not np.isfinite(k).all() or min(k[0, 0], k[1, 1]) <= 0:
        raise ValueError("Invalid intrinsic matrix")
    extrinsic = np.asarray(raw["extrinsic"], float)
    twc, diagnostics = convert_world_to_camera(extrinsic, tolerance)
    return {"intrinsics": k, "twc": twc, "raw_extrinsic": extrinsic, "diagnostics": diagnostics}


def read_depth(path: Path):
    depth = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if depth is None or depth.ndim != 2:
        raise ValueError(f"Expected single-channel EXR depth: {path}")
    depth = depth.astype(np.float32)
    # The official schema explicitly permits +inf sky depth. Do not replace it.
    valid = np.isfinite(depth) & (depth > 0)
    return depth, valid

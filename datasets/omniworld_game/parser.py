from __future__ import annotations
import json
import re
from pathlib import Path
import cv2
import numpy as np
from .pose_converter import wxyz_w2c_to_twc


def read_fps(path: Path):
    text = path.read_text(encoding="utf-8-sig").strip()
    try:
        value = float(text)
    except ValueError:
        matches = re.findall(r"(?im)^\s*FPS\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$", text)
        if len(matches) != 1:
            raise ValueError("fps.txt must contain one explicit FPS field")
        value = float(matches[0])
    if not np.isfinite(value) or value <= 0:
        raise ValueError("Invalid source FPS")
    return value


def read_split(directory: Path, split_index: int, metric_scale=None):
    split_info = json.loads((directory / "split_info.json").read_text(encoding="utf-8"))
    frames = np.asarray(split_info["split"][split_index])
    if frames.ndim != 1 or not np.issubdtype(frames.dtype, np.integer) or np.any(frames < 0) or np.any(np.diff(frames) <= 0):
        raise ValueError("Split indices must be explicitly ordered, unique integer frame IDs")
    camera_path = directory / "camera" / f"split_{split_index}.json"
    camera = json.loads(camera_path.read_text(encoding="utf-8"))
    count = len(frames)
    poses = wxyz_w2c_to_twc(camera["quats"], camera["trans"], metric_scale=metric_scale)
    if len(poses) != count:
        raise ValueError("Reference pose count does not match the split frame mapping")
    k = np.repeat(np.eye(3)[None], count, axis=0)
    for key, row, col in (("focals", 0, 0), ("focals", 1, 1), ("cx", 0, 2), ("cy", 1, 2)):
        values = np.broadcast_to(np.asarray(camera[key], dtype=float), (count,))
        if not np.isfinite(values).all() or (row == col and np.any(values <= 0)):
            raise ValueError("Invalid reference intrinsics")
        k[:, row, col] = values
    return frames, k, poses, camera_path


def read_depth(path, metric_scale=None):
    raw = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if raw is None or raw.ndim != 2 or raw.dtype != np.uint16:
        raise ValueError("OmniWorld depth must be a uint16 grayscale PNG")
    normalized = raw.astype(np.float32) / 65535.0
    valid = (normalized >= 0.0015) & (raw <= 65500)
    depth = normalized / (1000.0 - normalized * 999.0) / 0.004
    depth[~valid] = -1
    if metric_scale is not None:
        depth[valid] *= metric_scale
    return depth.astype(np.float32), valid


def read_flow(directory: Path, flow_range=(-300.0, 300.0)):
    components = [cv2.imread(str(directory / name), cv2.IMREAD_UNCHANGED)
                  for name in ("flow_u_16.png", "flow_v_16.png")]
    if any(array is None or array.dtype != np.uint16 or array.ndim != 2 for array in components):
        raise ValueError("Flow requires both uint16 component PNGs")
    if components[0].shape != components[1].shape:
        raise ValueError("Flow component shape mismatch")
    low, high = flow_range
    return np.stack([array.astype(np.float32) / 65535 * (high - low) + low for array in components], axis=-1)

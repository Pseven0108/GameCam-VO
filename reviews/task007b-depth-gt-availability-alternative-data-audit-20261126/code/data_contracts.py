"""Content-based archive classification and non-metric auxiliary math only."""
from __future__ import annotations

from pathlib import PurePosixPath
import re

import numpy as np


def member_modality(name):
    """No archive-filename filter; ambiguous products remain candidates."""
    path = name.replace("\\", "/").lower().strip("/")
    parts = path.split("/")
    suffix = PurePosixPath(path).suffix
    if "__macosx" in parts or suffix in {".md", ".html", ".htm"}:
        return "DOCUMENT_OR_CONTAINER_METADATA"
    if any(p in {"depth", "depths", "depth_left", "depth_right", "disparity", "disp", "gt_depth", "depth_gt"} for p in parts) or suffix in {".exr", ".pfm", ".dpt"}:
        return "POTENTIAL_DEPTH_REQUIRES_PROVENANCE"
    if "flow" in parts or any(p in {"flow_left", "flow_right"} for p in parts):
        return "OPTICAL_FLOW_NOT_DEPTH_GT"
    if "camera" in parts or "calib" in parts or suffix == ".csv":
        return "CAMERA_OR_TABLE_NOT_PIXEL_DEPTH"
    if any(p in {"img", "image", "images", "rgb", "image_left", "image_right"} for p in parts) and suffix in {".jpg", ".jpeg", ".png"}:
        return "RGB_IMAGE"
    if any(p in {"cls", "inst", "instcs", "segmentation", "labels"} for p in parts):
        return "SEGMENTATION_NOT_DEPTH_GT"
    if suffix in {".npy", ".npz", ".png", ".bin", ".tif", ".tiff"}:
        return "AMBIGUOUS_ARRAY_OR_IMAGE_REQUIRES_INSPECTION"
    return "OTHER_MEMBER"


def viper_member(name):
    """Recognize released VIPER layouts from member content, not ZIP names."""
    return re.search(r"(?:^|/)(?:train|val|test)/(?:img|flow|depth|disp|cls|inst|instcs|camera|bb)/[0-9]{3}(?:/|[.])", name.replace("\\", "/"), re.I) is not None


def scale_invariant_log_shape_error(prediction, gt, gt_valid):
    """Synthetic unit-invariance prototype; never metric variance calibration.

    Centering uses GT for an explicit diagnostic and removes ALL uniform scale
    error. Invalid predictions on GT-valid pixels stop rather than being hidden.
    """
    p, g = np.asarray(prediction, np.float64), np.asarray(gt, np.float64)
    mask = np.asarray(gt_valid)
    if p.shape != g.shape or mask.shape != g.shape or mask.dtype != np.bool_:
        raise ValueError("Matching grids and an explicit boolean GT-derived mask required")
    if not mask.any():
        raise ValueError("Empty GT-valid region")
    if not np.isfinite(g[mask]).all() or (g[mask] <= 0).any():
        raise ValueError("GT mask admits invalid depth")
    if not np.isfinite(p[mask]).all() or (p[mask] <= 0).any():
        raise ValueError("Bad predictions on valid GT cannot be filtered")
    delta = np.log(p[mask]) - np.log(g[mask])
    center = float(delta.mean())
    centered = delta - center
    return {"rms_log_shape": float(np.sqrt(np.mean(centered**2))),
            "GT_dependent_log_scale_bias": center, "centered_residual": centered,
            "metric_scale_accuracy_established": False}


def vkitti_scene_partition(scene):
    groups = {"01": "CALIBRATION", "02": "CALIBRATION", "06": "DEVELOPMENT", "18": "EVALUATION", "20": "EVALUATION"}
    key = str(scene).removeprefix("Scene")
    if key not in groups:
        raise ValueError("Unknown base scene: no automatic reassignment")
    return groups[key]

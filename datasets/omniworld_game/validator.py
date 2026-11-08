from __future__ import annotations
import cv2
import numpy as np
from datasets.checks import depth_reprojection, modality_preview
from gamecam_vo.common import write_csv


def validate_omni(dataset, out):
    blockers, rows = [], []
    warnings = ["POSE_PROVENANCE = ESTIMATED_REFERENCE",
                "Depth/pose self-consistency is not independent engine-GT accuracy validation"]
    if dataset.reference_diagnostics["source_invalid_frames"]:
        blockers.append("Official reference metadata marks invalid frames; retain and resolve before evaluation")
    for index, record in enumerate(dataset.records):
        missing = [key for key in ("rgb_path", "depth_path", "pose_path", "mask_path") if not record[key].is_file()]
        if missing:
            blockers.append(f"Frame {record['frame_id']} missing {missing}")
            continue
        image = cv2.imread(str(record["rgb_path"]))
        if image is None:
            blockers.append(f"RGB decode failed: {record['frame_id']}")
            continue
        depth, valid = dataset.get_depth(index)
        mask = dataset.get_dynamic_masks(index)
        if depth.shape != image.shape[:2] or mask.shape != image.shape[:2]:
            blockers.append(f"RGB/depth/mask shape mismatch: {record['frame_id']}")
        if not valid.any():
            blockers.append(f"No valid reference depth pixels: {record['frame_id']}")
        rows.append({"frame_index": record["frame_index"], "width": image.shape[1], "height": image.shape[0],
                     "valid_reference_depth_fraction": float(valid.mean()), "dynamic_mask_fraction": float(mask.mean()),
                     "POSE_PROVENANCE": "ESTIMATED_REFERENCE"})
    write_csv(out / "dataset_inspection.csv", rows)
    diagnostics = []
    if not blockers and len(dataset.records) > 1:
        diagnostics = depth_reprojection(dataset, out, min(5, len(dataset.records) - 1), 12)
        modality_preview(dataset, out)
    return {"e0_passed": not blockers, "blockers": blockers, "warnings": warnings,
            "pose_count": len(dataset.records), "depth_reprojection": diagnostics,
            "frame_id_association": "Explicit split_info.json order maps every pose to named RGB/depth/mask",
            "reference_accuracy_independently_verified": False}

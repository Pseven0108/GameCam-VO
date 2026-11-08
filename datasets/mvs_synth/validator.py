from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np

from datasets.checks import depth_reprojection, modality_preview
from gamecam_vo.common import write_csv


def validate_mvs(dataset, out: Path):
    blockers, warnings, rows = [], [], []
    expected = int(dataset.config["expected_frames"])
    stems = {}
    for directory, extension in (("images", "png"), ("poses", "json"), ("depths", "exr")):
        stems[directory] = {path.stem for path in (dataset.directory / directory).glob("*." + extension)}
    expected_stems = {f"{i:04d}" for i in range(expected)}
    for modality, actual in stems.items():
        if actual != expected_stems:
            blockers.append(f"{modality} is not the complete official {expected}-frame sequence")
    for i, record in enumerate(dataset.records):
        image = cv2.imread(str(record["rgb_path"]))
        if image is None:
            blockers.append(f"RGB decode failure at {record['frame_id']}")
            continue
        depth, valid = dataset.get_depth(i)
        bad = np.isnan(depth) | np.isneginf(depth) | (depth <= 0)
        diagnostics = dataset.cameras[i]["diagnostics"]
        if depth.shape != image.shape[:2]:
            blockers.append(f"RGB/depth shape mismatch at {record['frame_id']}")
        if bad.mean() > dataset.config["validation"]["maximum_nonpositive_or_nan_depth_fraction"]:
            blockers.append(f"Undocumented invalid depths at {record['frame_id']}")
        if not valid.any():
            blockers.append(f"No finite positive depths at {record['frame_id']}")
        rows.append({"frame_index": record["frame_index"], "rgb_path": str(record["rgb_path"]),
                     "pose_path": str(record["pose_path"]), "depth_path": str(record["depth_path"]),
                     "width": image.shape[1], "height": image.shape[0],
                     "depth_finite_positive_fraction": float(valid.mean()), "depth_positive_infinity_fraction": float(np.isposinf(depth).mean()),
                     "depth_invalid_fraction": float(bad.mean()), **{key: diagnostics[key] for key in
                     ("raw_determinant", "raw_orthogonality_error", "normalized_determinant",
                      "numeric_rotation_max_abs_adjustment")}})
    write_csv(out / "dataset_inspection.csv", rows)
    projection = []
    if not blockers and len(dataset.records) >= 2:
        config = dataset.config["validation"]
        projection = depth_reprojection(dataset, out, config["projection_pairs"], config["projection_grid_stride"])
        measured = [row for row in projection if row["overlapping_valid_samples"] >= 100]
        if not measured:
            blockers.append("No usable cross-frame depth/camera validation")
        elif np.median([row["median_relative_depth_error"] for row in measured]) > config["maximum_median_relative_depth_error"]:
            blockers.append("Cross-frame median depth error exceeds the preconfigured E0 threshold")
        elif np.median([row["fraction_within_5_percent_depth"] for row in measured]) < config["minimum_depth_consistent_fraction"]:
            blockers.append("Insufficient depth-consistent overlap for camera validation")
        modality_preview(dataset, out)
    return {"e0_passed": not blockers, "blockers": blockers, "warnings": warnings,
            "pose_count": len(dataset.records), "frame_id_association": "Exact RGB/EXR/JSON numeric stems, official schema",
            "physical_time_verified": False, "time_axis": "frame_index",
            "scale_caveat": "Ground-truth geometry is in native game units; meters and acquisition FPS are not asserted",
            "world_conversion": "One constant world-Z reflection; relative camera transforms and projections invariant",
            "raw_extrinsics_preserved": True, "depth_checks": rows, "depth_reprojection": projection}

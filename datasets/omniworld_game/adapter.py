from __future__ import annotations
import csv
import json
from pathlib import Path
import numpy as np
from datasets.base import GameCameraDataset
from .parser import read_split, read_depth, read_flow, read_fps
from .mask_loader import read_dynamic_mask


class OmniWorldGameDataset(GameCameraDataset):
    def __init__(self, config, project):
        super().__init__(config, project)
        self.directory = self.root / str(config["scene_id"]) if config.get("scene_id") else self.root
        if not (self.directory / "split_info.json").is_file():
            raise FileNotFoundError("No selected official OmniWorld-Game scene with split_info.json")
        self.metric_scale = None
        if config.get("use_metric_scale"):
            metadata_path = Path(config["metadata_csv"])
            if not metadata_path.is_absolute():
                metadata_path = project / metadata_path
            with metadata_path.open(encoding="utf-8-sig", newline="") as handle:
                matching = [row for row in csv.DictReader(handle) if row["UID"] == self.directory.name]
            if len(matching) != 1:
                raise ValueError("Metric scale requires a unique matching official scene metadata row")
            self.metric_scale = float(matching[0]["Metric Scale"])
        self.frames, self.intrinsics, self.poses, camera = read_split(self.directory, config["split_index"], self.metric_scale)
        original_camera = json.loads(camera.read_text(encoding="utf-8"))
        original_norms = np.linalg.norm(np.asarray(original_camera["quats"], float), axis=1)
        self.reference_diagnostics = {
            "raw_quaternion_norm_min": float(np.min(original_norms)),
            "raw_quaternion_norm_median": float(np.median(original_norms)),
            "raw_quaternion_norm_max": float(np.max(original_norms)),
            "quaternion_policy": "Normalize nonzero optimized quaternion parameters, exactly as the official SciPy reader",
            "source_invalid_frames": original_camera.get("invalid_frame", []),
            "source_reported_reprojection_error_before_refine": original_camera.get("reproj_error_before_refine"),
            "source_reported_reprojection_error_after_refine": original_camera.get("reproj_error_after_refine"),
            "source_reported_reprojection_error_refine_filtered": original_camera.get("reproj_error_refine_filtered"),
            "source_reported_input_size_field": original_camera.get("input_size")}
        maximum = config.get("maximum_frames")
        if maximum:
            self.frames, self.intrinsics, self.poses = self.frames[:maximum], self.intrinsics[:maximum], self.poses[:maximum]
        fps_path = self.directory / "fps.txt"
        self.fps = read_fps(fps_path) if fps_path.is_file() else None
        if self.fps is not None and (not np.isfinite(self.fps) or self.fps <= 0):
            raise ValueError("Invalid source fps.txt")
        for index in self.frames:
            stem = f"{index:06d}"
            self.records.append({"frame_index": int(index), "frame_id": stem,
                                 "timestamp": float(index) / self.fps if self.fps else float(index),
                                 "rgb_path": self.directory / "color" / (stem + ".png"), "pose_path": camera,
                                 "depth_path": self.directory / "depth" / (stem + ".png"),
                                 "mask_path": self.directory / "gdino_mask" / (stem + ".png")})

    def get_intrinsics(self):
        return self.intrinsics

    def get_poses(self):
        return self.poses

    def get_depth(self, index):
        return read_depth(self.records[index]["depth_path"], self.metric_scale)

    def get_dynamic_masks(self, index, source="dataset"):
        if source == "predicted":
            return None  # No extra model is installed or silently substituted.
        path = self.records[index]["mask_path"]
        return read_dynamic_mask(path) if path.is_file() else None

    def get_optical_flow(self, index):
        return read_flow(self.directory / "flow" / self.records[index]["frame_id"])

    def input_files(self):
        values = super().input_files() + [self.directory / "split_info.json"]
        if (self.directory / "fps.txt").is_file():
            values.append(self.directory / "fps.txt")
        return list(dict.fromkeys(values))

    def get_metadata(self):
        return {"dataset": "OmniWorld-Game", "sequence_id": f"{self.directory.name}_split_{self.config['split_index']}",
                "POSE_PROVENANCE": "ESTIMATED_REFERENCE", "independent_engine_ground_truth": False,
                "depth_provenance": "ESTIMATED_REFERENCE", "mask_provenance": "DATASET_PROVIDED_MODEL_ANNOTATION",
                "timestamp_kind": "seconds" if self.fps else "frame_index", "fps": self.fps,
                "timestamp_source": "frame_index / explicit fps.txt FPS" if self.fps else "frame_index",
                "physical_sensor_timestamps_available": False, "reference_diagnostics": self.reference_diagnostics,
                "length_unit": "meter" if self.metric_scale else "reference_unit",
                "metric_scale_applied": self.metric_scale, "metric_scale_does_not_make_poses_independent_gt": True,
                "transform_direction": "camera_to_world", "camera_axes": "OpenCV_right_down_forward",
                "quaternion_order": "xyzw", "input_quaternion_order": "wxyz",
                "raw_transform_direction": "world_to_camera", "sources": self.config["sources"],
                "evaluation_scope": "Disagreement with estimated optimized references, not absolute true error"}

    def validate(self, out):
        from .validator import validate_omni
        return validate_omni(self, out)

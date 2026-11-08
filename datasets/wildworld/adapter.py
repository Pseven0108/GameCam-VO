from __future__ import annotations

from pathlib import Path
import numpy as np

from datasets.base import GameCameraDataset
from gamecam_vo.common import read_yaml
from gamecam_vo.dataset import inspect_sequence, load_state
from gamecam_vo.geometry import wildworld_to_twc
from gamecam_vo.sync import match_timestamps
from gamecam_vo.video import intrinsic_matrix, iter_frames


class WildWorldDataset(GameCameraDataset):
    def __init__(self, config, project):
        super().__init__(config, project)
        self.legacy_dataset = read_yaml(project / config["legacy_dataset_config"])
        self.legacy_camera = read_yaml(project / config["legacy_camera_config"])
        sequence = config.get("sequence")
        if sequence:
            directory = self.root / str(sequence)
        else:
            directory = next((path.parent for path in self.root.rglob("rgb.mp4")), None) if self.root.is_dir() else None
        if directory is None or not directory.is_dir():
            raise FileNotFoundError("WildWorld remains pending author approval; no local sample directory")
        self.directory = directory
        self.entry = inspect_sequence(directory, self.legacy_dataset, self.legacy_camera)
        if self.entry["issues"]:
            raise ValueError("; ".join(self.entry["issues"]))
        self.state = load_state(directory / "state.csv", self.legacy_dataset, self.legacy_camera)
        timeline = [{key: frame[key] for key in ("frame_index", "video_pts_seconds")}
                    for frame in iter_frames(directory / "rgb.mp4", self.legacy_dataset["clip"])]
        sync = self.legacy_dataset["sync"]
        if sync.get("timestamp_column"):
            if sync["video_pts_to_state_offset_seconds"] is None:
                raise ValueError("WildWorld timestamp clocks need documented offset")
            query = np.array([row["video_pts_seconds"] for row in timeline]) + sync["video_pts_to_state_offset_seconds"]
            associations, _ = match_timestamps(query, self.state["timestamps"], sync["max_timestamp_error_seconds"])
        else:
            lookup = {value: i for i, value in enumerate(self.state["frame_indices"])}
            associations = np.array([lookup.get(row["frame_index"], -1) for row in timeline])
        if np.any(associations < 0):
            raise ValueError("Some selected WildWorld frames have no candidate state association")
        self.source_rows = associations
        for frame, row in zip(timeline, associations, strict=True):
            self.records.append({"frame_index": frame["frame_index"], "frame_id": str(frame["frame_index"]),
                                 "timestamp": float(self.state["timestamps"][row]) if sync.get("timestamp_column") else frame["video_pts_seconds"],
                                 "rgb_path": directory / "rgb.mp4", "pose_path": directory / "state.csv"})

    def get_frames(self, resize_width=None):
        lookup = {record["frame_index"]: (i, record["timestamp"]) for i, record in enumerate(self.records)}
        for frame in iter_frames(self.directory / "rgb.mp4", self.legacy_dataset["clip"], resize_width):
            index, timestamp = lookup[frame["frame_index"]]
            yield frame | {"state_row_index": index, "timestamp": timestamp}

    def get_intrinsics(self):
        return np.array([intrinsic_matrix(self.state["intrinsics"][i]) for i in self.source_rows])

    def get_poses(self):
        poses = []
        for i in self.source_rows:
            p, q = self.state["positions"][i], self.state["quaternions"][i]
            poses.append(wildworld_to_twc(p, q) if np.isfinite(p).all() and np.isfinite(q).all() and np.linalg.norm(q) > 0
                         else np.full((4, 4), np.nan))
        return np.array(poses)

    def get_depth(self, index):
        # The 8-bit depth.mkv is not a calibrated metric-depth measurement.
        return None

    def get_metadata(self):
        return {"dataset": "WildWorld", "sequence_id": self.directory.name, "POSE_PROVENANCE": "ENGINE_GROUND_TRUTH",
                "independent_engine_ground_truth": True, "timestamp_kind": "seconds",
                "length_unit": self.legacy_camera["length_unit"], "camera_axes": "OpenCV_right_down_forward",
                "transform_direction": "camera_to_world", "quaternion_order": "xyzw",
                "encoded_depth_available": (self.directory / "depth.mkv").is_file(),
                "depth_decode_status": "UNCALIBRATED_8BIT_ENCODING_NOT_EXPOSED_AS_METRIC_DEPTH",
                "sources": self.legacy_camera["convention_source"]}

    def validate(self, out):
        from gamecam_vo.validation import validate_sequence
        return validate_sequence(self.entry, self.legacy_dataset, self.legacy_camera, out / "legacy_audit")

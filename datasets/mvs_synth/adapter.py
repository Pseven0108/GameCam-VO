from __future__ import annotations

from pathlib import Path
import numpy as np

from datasets.base import GameCameraDataset
from .parser import read_camera, read_depth


class MVSSynthDataset(GameCameraDataset):
    def __init__(self, config, project):
        super().__init__(config, project)
        self.sequence = str(config.get("sequence", "0000"))
        self.directory = self.root / self.sequence
        if not self.directory.is_dir():
            raise FileNotFoundError(self.directory)
        self.cameras = []
        for path in sorted((self.directory / "images").glob("*.png")):
            if not path.stem.isdigit():
                raise ValueError("MVS image filename must be an integer frame ID")
            index = int(path.stem)
            pose = self.directory / "poses" / f"{path.stem}.json"
            depth = self.directory / "depths" / f"{path.stem}.exr"
            if not pose.is_file() or not depth.is_file():
                raise ValueError(f"Incomplete frame modalities for {path.stem}")
            camera = read_camera(pose, config["validation"]["matrix_tolerance"])
            self.cameras.append(camera)
            self.records.append({"frame_index": index, "frame_id": path.stem, "timestamp": float(index),
                                 "rgb_path": path, "pose_path": pose, "depth_path": depth})
        if not self.records:
            raise ValueError("No MVS RGB frames")

    def get_intrinsics(self):
        return np.array([camera["intrinsics"] for camera in self.cameras])

    def get_poses(self):
        return np.array([camera["twc"] for camera in self.cameras])

    def get_depth(self, index):
        return read_depth(self.records[index]["depth_path"])

    def get_metadata(self):
        return {"dataset": "MVS-Synth", "adapter": "mvs_synth", "sequence_id": self.sequence,
                "POSE_PROVENANCE": "ENGINE_GROUND_TRUTH", "independent_engine_ground_truth": True,
                "depth_provenance": "ENGINE_GROUND_TRUTH", "mask_provenance": "NOT_PROVIDED",
                "timestamp_kind": "frame_index", "physical_timestamps_available": False, "fps": None,
                "length_unit": "native_game_unit", "meters_per_unit": None,
                "physical_world_axis_directions": "not asserted; normalized world reflects native Z",
                "camera_axes": "OpenCV_right_down_forward", "transform_direction": "camera_to_world",
                "quaternion_order": "xyzw", "world_basis": "X_new=diag(1,1,-1)*X_raw",
                "distortion": "ideal pinhole from official plane-sweep projection",
                "sources": self.config["sources"], "raw_directory": str(self.directory)}

    def validate(self, out):
        from .validator import validate_mvs
        return validate_mvs(self, out)

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import cv2
import numpy as np


class GameCameraDataset(ABC):
    """All poses are T_wc in an explicit right/down/forward camera frame."""

    def __init__(self, config: dict, project: Path):
        self.config, self.project = config, project
        root = Path(config["root"])
        self.root = root.resolve() if root.is_absolute() else (project / root).resolve()
        self.records: list[dict] = []

    def get_frames(self, resize_width=None):
        for index, record in enumerate(self.records):
            image = cv2.imread(str(record["rgb_path"]), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"RGB decode failed: {record['rgb_path']}")
            height, width = image.shape[:2]
            if resize_width and width > resize_width:
                image = cv2.resize(image, (resize_width, round(height * resize_width / width)), interpolation=cv2.INTER_AREA)
            yield {"frame_index": record["frame_index"], "state_row_index": index,
                   "timestamp": record["timestamp"], "image": image,
                   "scale_x": image.shape[1] / width, "scale_y": image.shape[0] / height}

    @abstractmethod
    def get_intrinsics(self) -> np.ndarray:
        pass

    @abstractmethod
    def get_poses(self) -> np.ndarray:
        pass

    @abstractmethod
    def get_depth(self, index: int):
        """Return (float depth, valid mask); units/provenance are in metadata."""
        pass

    def get_dynamic_masks(self, index: int, source="dataset"):
        return None

    @abstractmethod
    def get_metadata(self) -> dict:
        pass

    @abstractmethod
    def validate(self, out: Path) -> dict:
        pass

    def input_files(self) -> list[Path]:
        keys = ("rgb_path", "pose_path", "depth_path", "mask_path")
        return list(dict.fromkeys(Path(record[key]) for record in self.records for key in keys
                                  if record.get(key) is not None))

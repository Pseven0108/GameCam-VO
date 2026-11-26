"""Coordinate contracts, in pixel centers; no implicit crop or frame renumbering."""
from dataclasses import dataclass
import torch


@dataclass(frozen=True)
class ImageGeometry:
    tracker_hw: tuple[int, int]
    map_hw: tuple[int, int]
    feature_stride: float = 8.0
    feature_offset_xy: tuple[float, float] = (0.0, 0.0)

    def __post_init__(self):
        if min(*self.tracker_hw, *self.map_hw, self.feature_stride) <= 0:
            raise ValueError("Positive image sizes and stride required")

    def feature_to_map(self, xy: torch.Tensor) -> torch.Tensor:
        """K/stride geometric coordinates -> tracker -> half-pixel resize map."""
        offset = xy.new_tensor(self.feature_offset_xy)
        scale = xy.new_tensor([self.map_hw[1] / self.tracker_hw[1],
                               self.map_hw[0] / self.tracker_hw[0]])
        return (xy * self.feature_stride + offset + 0.5) * scale - 0.5


def pixel_to_grid(xy: torch.Tensor, hw: tuple[int, int]) -> torch.Tensor:
    """grid_sample(align_corners=False), including singleton axes."""
    return 2 * (xy + 0.5) / xy.new_tensor([hw[1], hw[0]]) - 1

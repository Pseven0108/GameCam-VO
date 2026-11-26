"""Original soft gate implementation. Does not modify coordinates or native U."""
from dataclasses import dataclass
import math
import torch
import torch.nn.functional as F
from .feature_alignment import pixel_to_grid


@dataclass(frozen=True)
class GateConfig:
    enabled: bool = True
    alpha: float = 1.0
    beta: float = 1.0
    min_gate: float = 0.1

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.alpha, self.beta, self.min_gate)):
            raise ValueError("Nonfinite gate parameter")
        if min(self.alpha, self.beta) < 0 or not 0 <= self.min_gate <= 1:
            raise ValueError("Invalid soft gate parameters")


def sample_probability(maps: torch.Tensor, xy: torch.Tensor):
    """maps [E,Hm,Wm], xy [E,H,W,2], returns values and in-image mask.

    Out-of-image or nonfinite correspondences have neutral dynamic evidence.
    Native BA retains responsibility for geometric visibility rejection.
    """
    if maps.ndim != 3 or xy.ndim != 4 or xy.shape[-1] != 2 or maps.shape[0] != xy.shape[0]:
        raise ValueError("Expected [E,Hm,Wm] maps and [E,H,W,2] xy")
    if maps.device != xy.device:
        raise ValueError("Coordinates and maps must share a device")
    if not torch.isfinite(maps).all() or (maps < 0).any() or (maps > 1).any():
        raise ValueError("Dynamic probability must be finite in [0,1]")
    h, w = maps.shape[-2:]
    valid = (torch.isfinite(xy).all(-1) & (xy[..., 0] >= -0.5) &
             (xy[..., 0] <= w-0.5) & (xy[..., 1] >= -0.5) & (xy[..., 1] <= h-0.5))
    safe_xy = torch.nan_to_num(xy, nan=-1e6, posinf=1e6, neginf=-1e6)
    sampled = F.grid_sample(maps[:, None].float(), pixel_to_grid(safe_xy.float(), (h,w)),
                            mode="bilinear", padding_mode="border", align_corners=False)[:, 0]
    return torch.where(valid, sampled, 0.0), valid


class DynamicObservationGate:
    def __init__(self, config: GateConfig = GateConfig()):
        self.config = config

    def __call__(self, weight, source_probability, target_probability,
                 source_xy, target_xy):
        """weight [1,E,H,W,2]; probabilities [E,Hm,Wm]; xy [E,H,W,2]."""
        if not self.config.enabled:
            return weight, {"enabled": False}  # exact object and bit identity
        if weight.ndim != 5 or weight.shape[0] != 1 or weight.shape[-1] != 2:
            raise ValueError("DROID-W weight contract is [1,E,H,W,2]")
        if tuple(weight.shape[1:4]) != tuple(target_xy.shape[:3]) or source_xy.shape != target_xy.shape:
            raise ValueError("Weight/correspondence shape mismatch")
        if not torch.isfinite(weight).all() or (weight < 0).any():
            raise ValueError("Invalid native observation weight")
        mi, vi = sample_probability(source_probability, source_xy)
        mj, vj = sample_probability(target_probability, target_xy)
        g = ((1-mi).pow(self.config.alpha) * (1-mj).pow(self.config.beta)).clamp_min(self.config.min_gate)
        out = weight * g[None, ..., None].to(weight.dtype)
        return out, {"enabled": True, "gate_min": float(g.min()),
                     "gate_mean": float(g.mean()), "gate_max": float(g.max()),
                     "target_outside_fraction": float((~vj).float().mean()),
                     "source_outside_fraction": float((~vi).float().mean()),
                     "attenuated_fraction": float((g < 0.999999).float().mean())}

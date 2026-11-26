"""Read sealed TASK008 predictions, with explicit identity and no model loading."""
from pathlib import Path
import hashlib
import numpy as np
import torch


class Pi3Cache:
    def __init__(self, paths: dict[int, str | Path], tracker_hw: tuple[int, int]):
        self.paths = {int(k): Path(v) for k,v in paths.items()}
        self.tracker_hw = tracker_hw
        self._loaded = {}
        self.receipts = {}

    def read(self, frame_id: int):
        frame_id = int(frame_id)
        if frame_id not in self.paths:
            raise KeyError(f"No admitted dynamic prior for RGB {frame_id}; no adjacent substitution")
        if frame_id not in self._loaded:
            p = self.paths[frame_id]
            with np.load(p, allow_pickle=False) as z:
                actual = int(np.asarray(z["target_rgb_id"]).item())
                if actual != frame_id:
                    raise ValueError(f"Frame identity mismatch: requested {frame_id}, file says {actual}")
                m = np.asarray(z["dynamic_probability_model"], dtype=np.float32).copy()
                c = np.asarray(z["confidence_model"], dtype=np.float32).copy()
                context = np.asarray(z["context_rgb_ids"]).tolist()
                if m.ndim != 2 or c.shape != m.shape or not np.isfinite(m).all() or m.min() < 0 or m.max() > 1:
                    raise ValueError("Invalid prediction map")
            self._loaded[frame_id] = (torch.from_numpy(m), torch.from_numpy(c))
            self.receipts[frame_id] = {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                       "context": context, "map_hw": list(m.shape)}
        return self._loaded[frame_id]

    def batch(self, ids, device):
        return torch.stack([self.read(int(i))[0] for i in ids]).to(device)

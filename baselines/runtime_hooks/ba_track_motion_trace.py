"""Opt-in output observation for the unmodified official MDTracker.

The hook returns None and never mutates inputs or predictions. Its CPU copy,
compression and disk costs belong to the recorded run's elapsed time.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def attach_motion_trace(network, destination, context_provider):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise FileExistsError("Motion trace destination must be new or empty")
    counter = 0

    def observe(module, args, kwargs, output):
        nonlocal counter
        if len(output) != 7 or "queries" not in kwargs or "rgbds" not in kwargs:
            raise ValueError("MDTracker trace schema differs from the reviewed source")
        # These are image-grid coordinates and depth, despite the upstream
        # variable name traj_static_3d_e. They are not world-space XYZ vectors.
        total_uv, _, depth, static_uv_depth, visibility, dynamic_probability, _ = output
        arrays = {
            "total_uv": total_uv.detach().cpu().numpy().copy(),
            "total_depth": depth.detach().cpu().numpy().copy(),
            "static_uv_depth": static_uv_depth.detach().cpu().numpy().copy(),
            "visibility": visibility.detach().cpu().numpy().copy(),
            "dynamic_probability": dynamic_probability.detach().cpu().numpy().copy(),
            "queries_t_uv_depth": kwargs["queries"].detach().cpu().numpy().copy(),
        }
        name = f"network_call_{counter:05d}.npz"
        partial = destination / (name + ".part")
        with partial.open("wb") as handle:
            np.savez_compressed(handle, **arrays)
        partial.rename(destination / name)
        record = {
            "call_index": counter, "file": name, "context": context_provider(),
            "network_input_shape": list(kwargs["rgbds"].shape),
            "coordinate_space": "MDTracker's resized RGBD image grid; UV pixels and predicted depth, not world XYZ",
            "native_model_outputs_before_SLAM_query_overwrite": True,
            "dynamic_signal": "Native sigmoid output at tracked points; calibration and dense segmentation accuracy unverified",
            "arrays": {key: {"shape": list(value.shape), "dtype": str(value.dtype), "finite_fraction": float(np.isfinite(value).mean()) if value.size else None} for key, value in arrays.items()},
        }
        with (destination / "calls.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(record) + "\n")
        counter += 1
        return None

    return network.register_forward_hook(observe, with_kwargs=True)

"""Observe native calls and returned tensors; never run a second model forward."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import numpy as np


def install(slam_module, destination):
    import src.tracker as tracker_module
    from src.mapper import Mapper as NativeMapper

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    NativeFilter, NativeFrontend = tracker_module.MotionFilter, tracker_module.Frontend

    def append(path, row):
        with path.open("a") as stream:
            stream.write(json.dumps(row)+"\n")

    class ObservedMotionFilter(NativeFilter):
        def track(self, timestamp, image, intrinsics=None):
            result = super().track(timestamp, image, intrinsics)
            self.video._phase5_last_input_index = int(timestamp)
            return result

    class ObservedFrontend(NativeFrontend):
        def __call__(self, force_to_add_keyframe):
            before, count = bool(self.is_initialized), int(self.video.counter.value)
            result = super().__call__(force_to_add_keyframe)
            append(destination / "frontend_frames.jsonl", {
                "frame_index": self.video._phase5_last_input_index,
                "initialized_before": before, "frontend_initialized": bool(self.is_initialized),
                "keyframes_before": count, "keyframes_after": int(self.video.counter.value),
                "native_return_observed": True, "explicit_tracking_loss_state": None})
            return result

    class ObservedMapper(NativeMapper):
        def save_fig_everything(self, keyframe_idx, plot_dir, suffix="", depth_max=10.0):
            previous = getattr(self, "_phase5_figure_context", None)
            self._phase5_figure_context = {
                "keyframe_index": int(keyframe_idx),
                "frame_index": int(self.video.timestamp[keyframe_idx].item()),
                "plot_directory": str(plot_dir), "suffix": str(suffix)}
            try:
                return super().save_fig_everything(keyframe_idx, plot_dir, suffix, depth_max)
            finally:
                self._phase5_figure_context = previous

        def get_viewpoint_uncertainty_no_grad(self, viewpoint):
            result = super().get_viewpoint_uncertainty_no_grad(viewpoint)
            context = getattr(self, "_phase5_figure_context", None)
            if context is not None:
                stage = re.sub(r"[^a-zA-Z0-9_.-]", "_", Path(context["plot_directory"]).name+context["suffix"])
                folder = destination / "raw_uncertainty" / stage
                folder.mkdir(parents=True, exist_ok=True)
                filename = folder / f"kf_{context['keyframe_index']:06d}_frame_{context['frame_index']:06d}.npy"
                if filename.exists():
                    # Preserve repeated calls independently, without overwriting a signal.
                    sequence = 1
                    while filename.with_stem(filename.stem+f"_call{sequence}").exists():
                        sequence += 1
                    filename = filename.with_stem(filename.stem+f"_call{sequence}")
                array = result.detach().cpu().numpy().copy()
                np.save(filename, array)
                append(destination / "raw_uncertainty_manifest.jsonl", {
                    **context, "file": str(filename), "sha256": hashlib.sha256(filename.read_bytes()).hexdigest(),
                    "shape": list(array.shape), "dtype": str(array.dtype), "finite": bool(np.isfinite(array).all()),
                    "minimum": float(np.nanmin(array)), "maximum": float(np.nanmax(array)),
                    "semantics": "Native adjusted uncertainty squared; unbounded variance, not dynamic probability",
                    "extra_model_forwards": 0, "returned_native_tensor_unmodified": True})
            return result

    tracker_module.MotionFilter, tracker_module.Frontend = ObservedMotionFilter, ObservedFrontend
    slam_module.Mapper = ObservedMapper


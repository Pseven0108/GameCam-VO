"""Copy visibility to the CPU once before the author's unchanged video renderer."""
from __future__ import annotations

from functools import wraps
import inspect
import json
from pathlib import Path
import time


def install_video_visibility_copy(visualizer, directory):
    import torch

    original = visualizer.draw_tracks_on_video
    signature = inspect.signature(original)
    receipt = Path(directory) / "native_video_visibility_io.jsonl"

    def record(row):
        try:
            with receipt.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
        except OSError:
            pass

    @wraps(original)
    def render(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        visibility = bound.arguments.get("visibility")
        row = {"event": "NATIVE_VIDEO_RENDER", "original_renderer_called_once": True,
               "model_forwards": 0, "RNG_draws": 0, "GT_used": False,
               "native_video_disabled": False, "numeric_cast": False}
        if torch.is_tensor(visibility):
            started = time.monotonic()
            try:
                copied = visibility.detach().cpu().numpy()
            except (TypeError, RuntimeError) as error:
                row.update(copy_status="UNSUPPORTED_COPY_NATIVE_INPUT_PRESERVED",
                           copy_error=str(error))
            else:
                bound.arguments["visibility"] = copied
                row.update(copy_status="VISIBILITY_COPIED_ONCE_WITHOUT_DTYPE_CHANGE",
                           original_device=str(visibility.device), shape=list(copied.shape),
                           dtype=str(copied.dtype), bytes=copied.nbytes)
            row["visibility_copy_seconds"] = time.monotonic() - started
        else:
            row["copy_status"] = "NO_TENSOR_VISIBILITY_ORIGINAL_INPUT_PRESERVED"
        started = time.monotonic()
        try:
            result = original(*bound.args, **bound.kwargs)
        except BaseException:
            row.update(native_renderer_returned=False,
                       native_renderer_seconds=time.monotonic() - started)
            record(row)
            raise
        row.update(native_renderer_returned=True,
                   native_renderer_seconds=time.monotonic() - started)
        record(row)
        return result

    visualizer.draw_tracks_on_video = render

"""CPU-only byte comparison of a narrow IO wrapper around the exact native draw code."""
from __future__ import annotations

import ast
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
from pathlib import Path
import shutil
import sys

import cv2
import numpy as np
from PIL import Image
import torch

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if torch.cuda.is_initialized():
        raise RuntimeError("This probe must never initialize CUDA or run a model")
    source = ROOT / "baselines/ba_track/upstream/main/slam_visualizer.py"
    tree = ast.parse(source.read_text())
    native_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LEAPVisualizer")
    selected = [n for n in native_class.body if isinstance(n, ast.FunctionDef)
                and n.name in ("_draw_pred_tracks", "draw_tracks_on_video")]
    if len(selected) != 2:
        raise ValueError("Require the exact two native rendering functions")
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *selected], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"torch": torch, "np": np, "cv2": cv2}
    exec(compile(module, str(source), "exec"), namespace)
    Native = type("ExtractedNativeRenderer", (), {n.name: namespace[n.name] for n in selected})
    case = ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T220637Z_racket"
    archive = case / "motion_decomposition/raw/network_call_00000.npz"
    manifest = json.loads((case / "input_manifest.json").read_text())
    rgb = Path(manifest["frames"][0]["path"])
    if str(rgb).startswith("D:"):
        rgb = Path("/mnt/d" + str(rgb)[2:].replace("\\", "/"))
    image = np.asarray(Image.open(rgb).convert("RGB")).copy()
    with np.load(archive, allow_pickle=False) as z:
        # Fixed first call, first three temporal entries, all 400 queries; no
        # selection by GT, performance, visibility, or a model rerun.
        tracks = torch.from_numpy(z["total_uv"][:, :3].copy())
        probability = torch.from_numpy(z["visibility"][:, :3].copy())
    video = torch.from_numpy(image).permute(2, 0, 1)[None, None].repeat(1, 3, 1, 1, 1)
    colors = np.empty((*tracks.shape[1:3], 3), dtype=np.float64)
    colors[:] = [180., 80., 40.]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = ROOT / "logs/PHASE5" / (stamp + "_BA_video_visibility_IO_probe")
    folder.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / "baselines/runtime_hooks"))
    from ba_track_video_io import install_video_visibility_copy
    outcomes = []
    for trace in (0, 2, -1):
        for kind, visibility in (("native_float32_values", probability),
                                 ("boolean_fixture_at_fixed_0.9", probability > .9),
                                 ("absent", None), ("numpy_passthrough", probability.numpy())):
            original, wrapped = Native(), Native()
            for instance in (original, wrapped):
                instance.tracks_leave_trace, instance.linewidth = trace, 2
            calls = [0]
            method = wrapped.draw_tracks_on_video

            @wraps(method)
            def counted(*args, **kwargs):
                calls[0] += 1
                return method(*args, **kwargs)

            wrapped.draw_tracks_on_video = counted
            install_video_visibility_copy(wrapped, folder)
            arguments = dict(video=video, tracks=tracks, vector_colors=colors, visibility=visibility)
            reference = original.draw_tracks_on_video(**arguments)
            actual = wrapped.draw_tracks_on_video(**arguments)
            if calls != [1] or not torch.equal(reference, actual):
                raise AssertionError("The unchanged native renderer must be called once and return identical RGB bytes")
            outcomes.append({"trace": trace, "visibility": kind, "native_calls": calls[0],
                             "shape": list(actual.shape), "dtype": str(actual.dtype),
                             "RGB_bytes_identical": True,
                             "RGB_sha256": hashlib.sha256(actual.numpy().tobytes()).hexdigest()})
    if torch.cuda.is_initialized():
        raise AssertionError("The IO fixture unexpectedly initialized CUDA")
    helper = ROOT / "baselines/runtime_hooks/ba_track_video_io.py"
    for file in (source, helper, Path(__file__)):
        shutil.copy2(file, folder / (file.name + ".reviewed_source"))
    report = {"status": "CPU_NATIVE_VIDEO_RGB_BYTE_EQUIVALENCE_PASSED", "directory": str(folder),
              "created_at_utc": datetime.now(timezone.utc).isoformat(), "probe": str(Path(__file__)),
              "probe_sha256": digest(Path(__file__)), "native_source": str(source),
              "native_source_sha256": digest(source), "IO_helper": str(helper), "IO_helper_sha256": digest(helper),
              "actual_saved_network_call": str(archive), "actual_saved_network_call_sha256": digest(archive),
              "RGB": str(rgb), "RGB_sha256": digest(rgb),
              "fixture_scope": "Extracted exact author rendering functions on CPU using saved first-call values; first 3 entries and all 400 queries. Fixed bool threshold is a rendering fixture, not a model setting. No complete GPU video or full-model bitwise-equivalence claim.",
              "CUDA_initialized_before_or_after": False, "model_forwards": 0, "GT_used": False,
              "native_video_disabled": False, "cases": outcomes}
    (folder / "review.json").write_text(json.dumps(report, indent=2) + "\n")
    pointer = ROOT / "reports/PHASE5/BA_native_video_visibility_IO_review.json"
    if pointer.exists():
        raise FileExistsError(pointer)
    pointer.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "cases": len(outcomes), "directory": str(folder)}))


if __name__ == "__main__":
    main()

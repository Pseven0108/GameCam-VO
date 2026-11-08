"""Actual prior inference on the vendored UniDepth Demo RGB; not a BA-Track Demo."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np


ROOT = Path("/mnt/d/aaa/GameCam-VO")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    if json.loads((ROOT / "reports/SOTA/ba_track_native_probe.json").read_text())["status"] != "BA_TRACK_NATIVE_CUDA_CHECKS_PASSED":
        raise RuntimeError("Actual native checks required first")
    assets = ROOT / "data/sota_assets/BA_TRACK"
    priors = json.loads((ROOT / "reports/SOTA/ba_track_hf_prior_assets.json").read_text())
    if priors["status"] != "BA_TRACK_HF_PRIORS_VERIFIED_PARTIAL":
        raise RuntimeError("Verified complete depth checkpoints required")
    for row in priors["assets"]:
        if digest(Path(row["path"])) != row["sha256"]:
            raise ValueError("Prior checkpoint/config changed")
    out = ROOT / "results/E9_BA_TRACK" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_official_prior_RGB_component_smoke")
    out.mkdir(parents=True, exist_ok=False)
    upstream = ROOT / "baselines/ba_track/upstream"
    source = upstream / "UniDepth/assets/demo/rgb.png"
    inputs = out / "input_rgb"
    inputs.mkdir()
    shutil.copy2(source, inputs / "rgb.png")
    env = os.environ.copy()
    env.update({"HF_HOME": str(assets / "huggingface"), "TORCH_HOME": str(assets / "torch_home"), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "PYTHONPATH": str(ROOT / "baselines/runtime_hooks"), "PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg", "QT_QPA_PLATFORM": "offscreen",
                "GAMECAM_CUDA_MEMORY_DIR": str(out / "cuda_allocator_stats"), "OMP_NUM_THREADS": "4"})
    launcher = ROOT / "scripts/run_ba_track_reviewed_entrypoint.py"
    commands = [
        ("depth_anything_v2", [sys.executable, str(launcher), "Depth-Anything/run_videos_v2.py", "--encoder", "vitl", "--load-from", str(assets / "weights/depth_anything_v2_vitl.pth"),
                               "--img-path", str(inputs), "--outdir", str(out / "depth_anything_v2")]),
        ("unidepth_v2", [sys.executable, str(launcher), "UniDepth/scripts/demo_mega-sam.py", "--scene-name", "prior_rgb", "--img-path", str(inputs), "--outdir", str(out / "unidepth_v2")]),
    ]
    (out / "execution_contract.json").write_text(json.dumps({"commands": commands, "cwd": str(upstream), "RGB_source": str(source), "RGB_sha256": digest(source),
        "bundled_depth_and_intrinsics_loaded": False, "inference_inputs": ["RGB"], "official_BA_Track_DAVIS_demo": False, "GameCam_MVS_inference": False,
        "selected_hyperparameters_changed": False, "xformers_fa3_disabled_after_host_failure": True, "launcher_sha256": digest(launcher),
        "environment_overrides": {key: env[key] for key in ("HF_HOME", "TORCH_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "PYTHONPATH", "OMP_NUM_THREADS", "GAMECAM_CUDA_MEMORY_DIR")}}, indent=2))
    results, samples = [], []
    with (out / "gpu_memory.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["stage", "stage_elapsed_seconds", "whole_gpu_used_mib", "whole_gpu_total_mib", "whole_gpu_utilization_percent"])
        for name, command in commands:
            started = time.monotonic()
            with (out / (name + ".log")).open("w") as log:
                process = subprocess.Popen(command, cwd=upstream, env=env, stdout=log, stderr=subprocess.STDOUT)
                while process.poll() is None:
                    probe = subprocess.run(["/usr/lib/wsl/lib/nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=15)
                    if not probe.returncode:
                        sample = [name, time.monotonic()-started, *[float(value.strip()) for value in probe.stdout.strip().split(",")]]
                        writer.writerow(sample)
                        stream.flush()
                        samples.append(sample)
                    if time.monotonic()-started > 900:
                        process.terminate()
                        process.wait(timeout=15)
                        break
                    time.sleep(1)
                code = process.wait()
            results.append({"stage": name, "exit_code": code, "wall_seconds": time.monotonic()-started})
            (out / "execution.json").write_text(json.dumps(results, indent=2))
            print(json.dumps(results[-1]), flush=True)
            if code:
                break
    passed = len(results) == 2 and all(row["exit_code"] == 0 for row in results)
    values = {}
    if passed:
        da = np.load(out / "depth_anything_v2/rgb.npy")
        with np.load(out / "unidepth_v2/prior_rgb/rgb.npz") as raw:
            uni, intrinsics = raw["depth"].copy(), raw["intrinsics"].copy()
        for name, value in (("DA_V2_relative_depth_or_disparity", da), ("UniDepthV2_depth", uni), ("UniDepthV2_predicted_K", intrinsics)):
            invalid_range = ((value < 0).any() or not (value > 0).any()) if name == "DA_V2_relative_depth_or_disparity" else (not (value > 0).all() if name == "UniDepthV2_depth" else False)
            if not np.isfinite(value).all() or invalid_range:
                raise ValueError("Invalid real prior inference output")
            values[name] = {"shape": list(value.shape), "minimum": float(value.min()), "median": float(np.median(value)), "maximum": float(value.max())}
    record = {"status": "BA_PRIOR_COMPONENT_SMOKE_COMPLETED" if passed else "BA_PRIOR_COMPONENT_SMOKE_FAILED", "directory": str(out), "results": results, "output_checks": values,
              "whole_gpu_peak_used_mib_sampled": max((row[2] for row in samples), default=None), "full_BA_Track_DAVIS_demo_completed": False,
              "camera_pose_or_motion_decomposition_inference": False, "GameCam_MVS_inference": False, "scope": "Actual official depth prior scripts on the vendored official UniDepth Demo RGB only; no target/reference depth or intrinsics supplied"}
    (out / "status.json").write_text(json.dumps(record, indent=2))
    (ROOT / "reports/SOTA/ba_track_depth_prior_smoke.json").write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())

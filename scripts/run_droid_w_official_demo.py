"""Execute the reviewed Bonn balloon target in the isolated Linux environment."""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path("/mnt/d/aaa/GameCam-VO")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["bonn", "mvs"], default="bonn")
    parser.add_argument("--input-directory", help="For MVS: RGB+K-only directory, never an E0/GT directory")
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--disable-amp-weight-cache", action="store_true")
    args = parser.parse_args()
    if args.timeout_seconds < 60:
        raise ValueError("Execution timeout must be at least 60 seconds")
    is_mvs = args.target == "mvs"
    if args.disable_amp_weight_cache:
        cache_check = json.loads((ROOT / "reports/SOTA/droid_amp_cache_equivalence.json").read_text())
        if cache_check["status"] != "AMP_WEIGHT_CACHE_EQUIVALENCE_PASSED":
            raise RuntimeError("The runtime cache option needs its numerical equivalence check")
    if json.loads((ROOT / "reports/SOTA/droid_native_probe.json").read_text())["status"] != "NATIVE_CUDA_CHECKS_PASSED":
        raise RuntimeError("Native kernel proof required")
    if json.loads((ROOT / "reports/SOTA/droid_assets.json").read_text())["status"] != "DROID_ASSETS_VERIFIED":
        raise RuntimeError("Verified full checkpoints and official demo data required")
    if is_mvs and json.loads((ROOT / "reports/SOTA/droid_official_demo.json").read_text())["status"] != "OFFICIAL_DEMO_COMPLETED":
        raise RuntimeError("Official Demo must complete before MVS inference")
    upstream = ROOT / "baselines/droid_w/upstream"
    os.chdir(upstream)
    sys.path.insert(0, str(upstream))
    from src import config
    from src.utils.datasets import get_dataset

    attempt = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = ROOT / "results/E8_DROID_W" / (attempt + ("_mvs_0000_rgb_only" if is_mvs else "_official_bonn_balloon"))
    out.mkdir(parents=True, exist_ok=False)
    assets = ROOT / "data/sota_assets/DROID_W"
    cfg = config.load_config("configs/droid_w.yaml" if is_mvs else "configs/Dynamic/Bonn/bonn_balloon.yaml")
    original_cfg = json.loads(json.dumps(cfg))
    cfg["data"]["root_folder"] = str(assets / "demo")
    cfg["data"]["input_folder"] = str(assets / "demo/rgbd_bonn_balloon")
    cfg["data"]["output"] = str(out / "upstream_output")
    cfg["tracking"]["pretrained"] = str(assets / "weights/droid.pth")
    if is_mvs:
        if not args.input_directory:
            raise ValueError("Explicit RGB-only input directory required")
        input_directory = Path(args.input_directory).resolve()
        if not input_directory.is_relative_to(ROOT / "data/sota_inputs/MVS-Synth/0000"):
            raise ValueError("Input directory must be the prepared RGB-only view")
        inputs = json.loads((input_directory / "input_manifest.json").read_text())
        if inputs["inference_inputs"] != ["RGB", "camera_intrinsics"] or len(inputs["frames"]) != 100:
            raise ValueError("Wrong model inputs / expected frame count")
        for row in inputs["frames"]:
            image = Path(row["wsl_path"])
            if not image.resolve().is_relative_to(input_directory) or hashlib.sha256(image.read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError("Prepared RGB escaped the isolated input directory or changed")
        if any(path.suffix in (".exr", ".csv", ".pth") for path in input_directory.rglob("*") if path.is_file()):
            raise ValueError("Unexpected non-RGB model input")
        k = np.asarray(inputs["fixed_K"])
        cfg.update(dataset="youtube", scene="mvs_0000", save_gt_poses=False)
        cfg["data"].update(input_folder=str(input_directory), root_folder=str(input_directory))
        cfg["cam"].update(H=inputs["height"], W=inputs["width"], H_out=inputs["height"], W_out=inputs["width"],
                           fx=float(k[0,0]), fy=float(k[1,1]), cx=float(k[0,2]), cy=float(k[1,2]))
        cfg["cam"].pop("distortion", None)
        shutil.copy2(input_directory / "input_manifest.json", out / "input_manifest.json")
    frozen = out / "run_config.yaml"
    config.save_config(cfg, str(frozen))
    write_json(out / "original_resolved_config.json", original_cfg)
    (Path(cfg["data"]["output"]) / cfg["scene"]).mkdir(parents=True, exist_ok=True)
    # Count the official loader's associated RGB frames, not all ZIP members.
    stream = get_dataset(cfg, device="cpu")
    expected_frames = len(stream)
    if is_mvs and (expected_frames != 100 or stream.poses is not None or stream.depth_paths is not None):
        raise ValueError("MVS stream is not exactly RGB+K only")
    shutil.copy2(Path(__file__), out / "executed_wrapper_source.py")
    shutil.copy2(ROOT / "baselines/runtime_hooks/sitecustomize.py", out / "cuda_telemetry_source.py")
    env = os.environ.copy()
    env.update({"GAMECAM_FIT3D_REPO": str(ROOT / "baselines/droid_w/prior_sources/FiT3D"),
                "GAMECAM_METRIC3D_REPO": str(ROOT / "baselines/droid_w/prior_sources/Metric3D"),
                "GAMECAM_FRAME_TELEMETRY": str(out / "frontend_frames.jsonl"),
                "GAMECAM_XFORMERS_DISABLE_FA3": "1",
                "GAMECAM_SINGLE_PROCESS_TRACKING": "1",
                "GAMECAM_CUDA_MEMORY_DIR": str(out / "cuda_allocator_stats"),
                "PYTHONPATH": str(ROOT / "baselines/runtime_hooks") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""),
                "TORCH_HOME": str(assets / "torch_home"), "HF_HOME": str(assets / "huggingface"),
                "PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg", "QT_QPA_PLATFORM": "offscreen",
                "OMP_NUM_THREADS": "4"})
    if args.disable_amp_weight_cache:
        env["GAMECAM_DISABLE_AMP_WEIGHT_CACHE"] = "1"
    command = [sys.executable, "run.py", "--config", str(frozen)]
    write_json(out / "execution_contract.json", {"command": command, "cwd": str(upstream),
               "environment_overrides": {k: env[k] for k in env if k.startswith("GAMECAM_") or k in ("TORCH_HOME", "HF_HOME", "OMP_NUM_THREADS", "QT_QPA_PLATFORM", "MPLBACKEND", "PYTHONUNBUFFERED", "PYTHONPATH")},
               "cuda_telemetry_hook_sha256": hashlib.sha256((ROOT / "baselines/runtime_hooks/sitecustomize.py").read_bytes()).hexdigest(),
               "official_loader_frame_count": expected_frames,
               "parameter_changes": "For Bonn only paths. For MVS paths, RGB-only loader, actual image dimensions and calibrated K. All model/inference hyperparameters remain official.",
               "demo_gt_note": "MVS process has RGB+K only, poses=None/depth_paths=None; evaluation occurs in a separate Windows process." if is_mvs else "Official Bonn loader loads depth/poses for evaluation; Tracker ignores both fields. This is not the MVS RGB-only isolation run.",
               "timeout_seconds": args.timeout_seconds})
    samples = []
    start = time.monotonic()
    timed_out = False
    fatal_oom_at = None
    stopped_after_oom = False
    with (out / "inference_log.txt").open("w", encoding="utf-8") as log, (out / "gpu_memory.csv").open("w", newline="") as gpu:
        writer = csv.writer(gpu)
        writer.writerow(["elapsed_seconds", "whole_gpu_used_mib", "whole_gpu_total_mib", "whole_gpu_utilization_percent"])
        process = subprocess.Popen(command, cwd=upstream, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write_json(out / "process.json", {"pid": process.pid, "pgid": process.pid})
        while process.poll() is None:
            elapsed = time.monotonic() - start
            probe = subprocess.run(["/usr/lib/wsl/lib/nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=15)
            if probe.returncode == 0:
                values = [float(v.strip()) for v in probe.stdout.strip().split(",")]
                samples.append([elapsed, *values])
                writer.writerow(samples[-1])
                gpu.flush()
            observed_log = (out / "inference_log.txt").read_text(errors="replace")
            if fatal_oom_at is None and "Traceback (most recent call last)" in observed_log and ("OutOfMemoryError" in observed_log or "CUDA out of memory" in observed_log):
                fatal_oom_at = elapsed
            if elapsed > args.timeout_seconds or (fatal_oom_at is not None and elapsed - fatal_oom_at > 20):
                timed_out = elapsed > args.timeout_seconds
                stopped_after_oom = not timed_out
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(1)
        code = process.wait()
    wall = time.monotonic() - start
    trajectories = list((out / "upstream_output").rglob("est_poses_full.txt"))
    pose_count = 0
    trajectory_check = False
    if trajectories:
        poses = np.loadtxt(trajectories[-1], ndmin=2)
        pose_count = len(poses)
        trajectory_check = poses.shape == (expected_frames, 8) and bool(np.isfinite(poses).all()) and bool(np.allclose(np.linalg.norm(poses[:, 4:8], axis=1), 1., atol=1e-4))
    text = (out / "inference_log.txt").read_text(errors="replace")
    success = code == 0 and trajectory_check and "Traceback (most recent call last)" not in text
    status = {"status": (("MVS_INFERENCE_COMPLETED" if is_mvs else "OFFICIAL_DEMO_COMPLETED") if success else ("MVS_INFERENCE_FAILED" if is_mvs else "OFFICIAL_DEMO_FAILED")),
              "directory": str(out), "exit_code": code, "timed_out": timed_out,
              "owned_process_group_stopped_after_fatal_oom": stopped_after_oom,
              "expected_frames": expected_frames, "pose_output_frames": pose_count,
              "trajectory_numerical_check": trajectory_check, "wall_seconds": wall,
              "whole_gpu_peak_used_mib": max((s[1] for s in samples), default=None),
              "whole_gpu_initial_used_mib": samples[0][1] if samples else None,
              "memory_note": "Whole-GPU sampled usage includes desktop/other processes; this is not allocator peak or dedicated model VRAM.",
              "trajectory_files": [str(p) for p in trajectories],
              "gamecam_mvs_inference_executed": is_mvs, "paper_result_match": False}
    status["amp_weight_cache_disabled"] = args.disable_amp_weight_cache
    status["execution_timeout_seconds"] = args.timeout_seconds
    frame_log = out / "frontend_frames.jsonl"
    observed_frames = [json.loads(line) for line in frame_log.read_text().splitlines()] if frame_log.exists() else []
    status.update(processed_frontend_frames=len(observed_frames),
                  frontend_initialized_frames=sum(bool(r["frontend_initialized"]) for r in observed_frames),
                  tracking_state_note="Frontend initialization and keyframe counts are instrumented; the method exposes no ORB-style per-frame tracking-loss state. Filled-pose coverage must not be reported as direct tracking success.")
    status.update(frontend_processing_complete=len(observed_frames)==expected_frames,
                  frontend_initialization_observed=any(bool(r["frontend_initialized"]) for r in observed_frames))
    if success and (not status["frontend_processing_complete"] or not status["frontend_initialization_observed"]):
        success = False
        status["status"] = "MVS_INFERENCE_FAILED" if is_mvs else "OFFICIAL_DEMO_FAILED"
        status["verification_failure"] = "Incomplete frontend processing or no initialization; a filled trajectory alone does not prove tracking"
    status["per_process_cuda_allocator_stats"] = [json.loads(path.read_text()) for path in (out / "cuda_allocator_stats").glob("*.json")]
    write_json(out / "status.json", status)
    write_json(ROOT / ("reports/SOTA/droid_mvs.json" if is_mvs else "reports/SOTA/droid_official_demo.json"), status)
    print(json.dumps(status), flush=True)
    return int(not success)


if __name__ == "__main__":
    raise SystemExit(main())

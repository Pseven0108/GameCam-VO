"""Run one native Crowd Demo/owned shared RGB input with retained terminal evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

import numpy as np
from phase5_runtime import memory_budget

ROOT = Path(__file__).resolve().parents[1]


def local(path):
    return Path(str(path).replace("\\", "/").replace("D:/", "/mnt/d/", 1))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for b in iter(lambda: stream.read(8*1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("official-demo", "shared"), required=True)
    parser.add_argument("--sequence", default="crowd")
    parser.add_argument("--actor-mode", choices=("native-process", "thread-portability"), default="native-process")
    parser.add_argument("--source-cache", type=Path, help="Verified byte-identical WSL ext4 source cache")
    parser.add_argument("--observe-native-returns", action="store_true", help="IO-only observers require a fresh verified cache containing the observer sources")
    parser.add_argument("--input-pointer", type=Path, help="Frozen generic RGB/K view for E15 or E16")
    parser.add_argument("--experiment", choices=("E14_WILD_DYNAMIC", "E15_MOVIE", "E16_BONN"), default="E14_WILD_DYNAMIC")
    args = parser.parse_args()
    if os.name == "nt":
        raise RuntimeError("Use the independent wildgs_slam WSL Python")
    if Path(sys.prefix).resolve() != Path("/home/lsuser/.local/share/gamecam-vo/envs/wildgs_slam").resolve():
        raise RuntimeError("The independent wildgs_slam environment is required")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.sequence):
        raise ValueError("Sequence must be a safe result identifier")
    if args.target == "official-demo" and (args.input_pointer or args.experiment != "E14_WILD_DYNAMIC"):
        raise ValueError("Official Demo target has its fixed Crowd input; generic views are separate shared targets")
    upstream = ROOT / "baselines/wildgs_slam/upstream"
    sys.path.insert(0, str(upstream))
    os.chdir(upstream)
    from src import config
    from src.utils.datasets import get_dataset
    reports = ROOT / "reports/PHASE5"
    assets = json.loads((ROOT / "reports/SOTA/droid_assets.json").read_text())
    for row in assets["assets"]:
        if row["name"].endswith(".pth") and digest(local(row["path"])) != row["sha256"]:
            raise ValueError("An exact required official checkpoint changed")
    bases = json.loads((ROOT / "reports/SOTA/droid_loaded_prior_assets.json").read_text())
    for row in bases["assets"]:
        if digest(local(row["cache_file"])) != row["sha256"]:
            raise ValueError("A pinned FiT3D/DINO base initialization asset changed")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    result_root = "E13_WILDGS" if args.target == "official-demo" else args.experiment+"/WildGS"
    out = ROOT / "results" / result_root / (stamp+"_"+args.sequence+"_"+args.actor_mode)
    out.mkdir(parents=True, exist_ok=False)
    cfg = config.load_config("configs/Dynamic/Wild_SLAM_Mocap/crowd_demo.yaml" if args.target == "official-demo" else "configs/wildgs_slam.yaml")
    original = json.loads(json.dumps(cfg))
    if args.target == "official-demo":
        data = json.loads((reports / "wild_crowd_data.json").read_text())
        cfg["data"].update(input_folder=str(local(data["directory"])), root_folder=str(local(data["directory"]).parent))
    else:
        data = json.loads((args.input_pointer or reports / ("wild_"+args.sequence+"_input.json")).read_text())
        if data["sequence"] != args.sequence:
            raise ValueError("Frozen view sequence and declared result identifier differ")
        inputs = local(data["directory"])
        manifest = json.loads((inputs / "input_manifest.json").read_text())
        for frame in manifest["frames"]:
            if digest(local(frame["path"])) != frame["sha256"]:
                raise ValueError("Common RGB input changed")
        k = np.asarray(manifest["fixed_K"])
        cfg.update(dataset="wild_slam_iphone", scene=args.sequence)
        cfg["data"].update(input_folder=str(inputs), root_folder=str(inputs))
        cfg["cam"].update(H=manifest["height"], W=manifest["width"], fx=float(k[0, 0]), fy=float(k[1, 1]), cx=float(k[0, 2]), cy=float(k[1, 2]))
        cfg["cam"].pop("distortion", None)
        shutil.copy2(inputs / "input_manifest.json", out / "input_manifest.json")
    cfg["cam"].update(H_out=240 if args.target == "official-demo" else manifest["height"], W_out=400 if args.target == "official-demo" else manifest["width"])
    cfg["gui"] = False
    cfg["data"]["output"] = str(out / "upstream_output")
    cfg["tracking"]["pretrained"] = str(ROOT / "data/sota_assets/DROID_W/weights/droid.pth")
    stream = get_dataset(cfg, device="cpu")
    if args.target == "shared" and (len(stream) != data["expected_frames"] or stream.depth_paths is not None or stream.poses is not None):
        raise ValueError("Formal comparison must expose every frozen RGB and no external pose/depth")
    path = out / "run_config.yaml"
    config.save_config(cfg, str(path))
    (out / "original_resolved_config.json").write_text(json.dumps(original, indent=2))
    wrapper = ROOT / "scripts/run_phase5_wildgs_entrypoint.py"
    cache_record = None
    if args.source_cache:
        cache_record = json.loads((args.source_cache / "source_manifest.json").read_text())
        if cache_record["status"] != "WSL_NATIVE_SOURCE_CACHE_BYTE_IDENTICAL":
            raise RuntimeError("Verified source cache required")
        for member in cache_record["files"]:
            if digest(Path(member["cached"])) != member["sha256"] or digest(Path(member["source"])) != member["sha256"]:
                raise ValueError("Original or cached source changed after byte verification")
        wrapper = args.source_cache / "run_phase5_wildgs_cached_entrypoint.py"
    if args.observe_native_returns:
        if not args.source_cache or not (args.source_cache / "wildgs_phase5_observer.py").is_file():
            raise ValueError("Return observers require a verified source cache with observer files")
        wrapper = args.source_cache / "run_phase5_wildgs_observed_entrypoint.py"
    command = [sys.executable, str(wrapper), str(path), "--actor-mode", args.actor_mode]
    env = os.environ.copy()
    env.update(PYTHONUNBUFFERED="1", MPLBACKEND="Agg", QT_QPA_PLATFORM="offscreen", OMP_NUM_THREADS="2",
        TORCH_HOME=str(ROOT / "data/sota_assets/DROID_W/torch_home"), HF_HOME=str(ROOT / "data/sota_assets/DROID_W/huggingface"),
        HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", GAMECAM_FIT3D_REPO=str(ROOT / "baselines/droid_w/prior_sources/FiT3D"),
        GAMECAM_METRIC3D_REPO=str(ROOT / "baselines/droid_w/prior_sources/Metric3D"), GAMECAM_XFORMERS_DISABLE_FA3="1",
        GAMECAM_CUDA_MEMORY_DIR=str(out / "cuda_allocator_stats"), PYTHONPATH=str(ROOT / "baselines/runtime_hooks"))
    if args.source_cache:
        env.update(GAMECAM_FIT3D_REPO=str(args.source_cache / "FiT3D"), GAMECAM_METRIC3D_REPO=str(args.source_cache / "Metric3D"))
        (out / "runtime_source_cache_manifest.json").write_text(json.dumps(cache_record, indent=2))
    if args.observe_native_returns:
        env["GAMECAM_WILD_OBSERVATION_DIR"] = str(out)
    contract = {"target": args.target, "sequence": args.sequence, "expected_frames": len(stream), "command": command, "cwd": str(upstream),
        "WSL_memory_budget_at_launch": memory_budget(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "actor_mode": args.actor_mode,
        "user_authorized_small_resolution": [cfg["cam"]["W_out"], cfg["cam"]["H_out"]], "GUI_omitted": True, "native_fast_mode": cfg["fast_mode"],
        "model_windows_losses_thresholds_points_unchanged": True, "native_online_MLP_and_Gaussian_optimization_retained": True,
        "no_full_model_bitwise_or_paper_score_claim": True,
        "source_execution_cache": str(args.source_cache) if args.source_cache else None,
        "IO_only_native_return_observers": bool(args.observe_native_returns),
        "shared_reader_registry_alias": "wild_slam_iphone" if args.target == "shared" else None,
        "shared_reader_alias_semantics": "Existing native RGB_NoPose reader, not dataset provenance; actual dataset is in the frozen input manifest" if args.target == "shared" else None,
        "input_policy": "Official Demo loader accesses depth/poses for evaluation; core mapper Camera.init_from_dataset receives est_depth/est_pose from frontend" if args.target == "official-demo" else "RGB+knownK-only input view; external reference never passed"}
    (out / "execution_contract.json").write_text(json.dumps(contract, indent=2))
    shutil.copy2(Path(__file__).with_name("phase5_runtime.py"), out / "phase5_runtime.py.executed_source")
    (out / "source_changes_from_upstream.patch").write_bytes(subprocess.check_output(["git", "-c", "core.autocrlf=true", "diff", "--binary", "be187eabbe6862cef3cfe87031ee2e64ad8c4cec"]))
    for source in (Path(__file__), wrapper):
        shutil.copy2(source, out / (source.name+".executed_source"))
    failure_at, reason, peak = None, None, 0.
    start = time.monotonic()
    with (out / "inference_log.txt").open("w") as log, (out / "gpu_memory.csv").open("w", newline="") as gpu:
        child = subprocess.Popen(command, cwd=upstream, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        (out / "process.json").write_text(json.dumps({"pid": child.pid, "pgid": child.pid}))
        writer = csv.writer(gpu)
        writer.writerow(["elapsed_seconds", "whole_gpu_used_mib", "whole_gpu_total_mib", "whole_gpu_utilization_percent"])
        print(json.dumps({"stage": "WILDGS_NATIVE_RUNNING", "directory": str(out), "expected_frames": len(stream), "actor_mode": args.actor_mode}), flush=True)
        while child.poll() is None:
            try:
                values = [float(x) for x in subprocess.check_output(["/usr/lib/wsl/lib/nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], text=True, timeout=5).strip().split(",")]
                writer.writerow([time.monotonic()-start, *values]); gpu.flush(); peak = max(peak, values[0])
            except (subprocess.SubprocessError, ValueError):
                pass
            with (out / "inference_log.txt").open("rb") as streamlog:
                streamlog.seek(max(0, streamlog.seek(0, 2)-32768)); tail = streamlog.read()
            if b"Traceback (most recent call last)" in tail:
                failure_at = failure_at or time.monotonic()
                reason = "CUDA_IPC_INVALID_RESOURCE_HANDLE" if b"invalid resource handle" in tail else ("CUDA_OUT_OF_MEMORY" if b"out of memory" in tail else "NATIVE_EXCEPTION")
            disk_low = shutil.disk_usage(out).free < 2*1024**3
            if disk_low:
                reason = "WORKSPACE_FREE_SPACE_BELOW_2_GIB"
            if disk_low or (failure_at and time.monotonic()-failure_at > 20) or time.monotonic()-start > 86400:
                reason = reason or "EXECUTION_TIMEOUT_24H"
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                break
            time.sleep(1)
        code = child.wait()
    trajectories = list((out / "upstream_output").rglob("est_poses_full.txt"))
    valid = False
    if trajectories:
        poses = np.loadtxt(trajectories[-1], ndmin=2)
        valid = poses.shape == (len(stream), 8) and np.isfinite(poses).all()
    record = {"status": "WILDGS_INFERENCE_COMPLETED" if code == 0 and valid and not reason else "WILDGS_INFERENCE_FAILED",
        "directory": str(out), "target": args.target, "sequence": args.sequence, "expected_frames": len(stream), "exit_code": code,
        "reason": reason, "actor_mode": args.actor_mode, "wall_seconds": time.monotonic()-start, "whole_gpu_peak_used_mib_sampled": peak,
        "trajectories": [str(x) for x in trajectories], "full_finite_camera_output": bool(valid), "model_parameters_changed": False}
    (out / "status.json").write_text(json.dumps(record, indent=2))
    (reports / ("wildgs_"+args.target+"_"+args.sequence+"_"+args.actor_mode+".json")).write_text(json.dumps(record, indent=2))
    if args.target == "shared":
        (reports / (args.experiment+"_WILDGS_"+args.sequence+"_native.json")).write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)
    return int(record["status"] != "WILDGS_INFERENCE_COMPLETED")


if __name__ == "__main__":
    raise SystemExit(main())

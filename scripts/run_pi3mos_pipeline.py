"""One reviewed native Pi3MOS run; no parameter downsizing or automatic retry."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def local(value):
    return Path(str(value).replace("\\", "/").replace("D:/", "/mnt/d/", 1))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("official-demo", "mvs"), required=True)
    args = parser.parse_args()
    if os.name == "nt":
        raise RuntimeError("Execute model inference inside the independent Pi3MOS WSL environment")
    assets = json.loads((ROOT / "reports/SOTA/pi3mos_assets.json").read_text())
    if assets["status"] != "PI3MOS_CORE_WEIGHTS_ACQUIRED":
        raise RuntimeError("Both complete selected checkpoints are required")
    upstream = ROOT / "baselines/pi3mos/upstream"
    for item in assets["assets"]:
        path = local(item["path"])
        if path.stat().st_size != item["size"] or digest(path) != item["sha256"]:
            raise ValueError("A verified checkpoint changed")
        link = upstream / "checkpoints" / item["name"]
        link.parent.mkdir(exist_ok=True)
        if link.exists() or link.is_symlink():
            if link.resolve() != path.resolve():
                raise FileExistsError("Preserve the existing checkpoint path; inspect it before replacement")
        else:
            link.symlink_to(path)
    if args.target == "mvs":
        demo = json.loads((ROOT / "reports/SOTA/pi3mos_official_demo.json").read_text())
        review = json.loads((ROOT / "reports/SOTA/pi3mos_official_demo_output_review.json").read_text())
        if demo["status"] != "PI3MOS_INFERENCE_COMPLETED" or review["status"] != "PI3MOS_OUTPUTS_SANITY_CHECKED":
            raise RuntimeError("Pass the official Demo output checks before MVS")
        if (ROOT / "reports/SOTA/pi3mos_mvs.json").exists():
            raise RuntimeError("Inspect the existing MVS attempt before an explicit retry")
    label = "official_wild_umbrella" if args.target == "official-demo" else "mvs_0000_rgb_K"
    out = ROOT / "results/E10_PI3MOS" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())+"_"+label)
    out.mkdir(parents=True, exist_ok=False)
    if args.target == "official-demo":
        data = json.loads((ROOT / "reports/SOTA/pi3mos_official_demo_data.json").read_text())
        if data["status"] != "PI3MOS_OFFICIAL_UMBRELLA_DATA_VERIFIED":
            raise RuntimeError("Verified selected official Demo data is required")
        frames = json.loads(local(data["RGB_manifest"]).read_text())
        rgb = local(data["rgb_directory"])
        calibration = upstream / "calib/wildgs/umbrella.txt"
        input_manifest = {"dataset": "Wild-SLAM Mocap", "sequence_id": "scene1/umbrella", "frames": frames,
                          "inference_inputs": ["RGB", "camera_intrinsics"], "GT_in_model": False,
                          "official_data": data, "time_axis": "frame_index"}
    else:
        pointer = json.loads((ROOT / "reports/SOTA/mvs_rgb_input.json").read_text())
        prepared = local(pointer["directory"])
        input_manifest = json.loads((prepared / "input_manifest.json").read_text())
        frames = input_manifest["frames"]
        if len(frames) != 100 or input_manifest["inference_inputs"] != ["RGB", "camera_intrinsics"]:
            raise ValueError("Expected the same frozen100 RGB+knownK inputs")
        rgb = prepared / "rgb"
        matrix = np.asarray(input_manifest["fixed_K"])
        calibration = out / "known_intrinsics.txt"
        np.savetxt(calibration, np.array([[matrix[0, 0], matrix[1, 1], matrix[0, 2], matrix[1, 2]]]), fmt="%.18g")
    for frame in frames:
        if digest(local(frame["path"])) != frame["sha256"]:
            raise ValueError("Frozen RGB changed")
    (out / "input_manifest.json").write_text(json.dumps(input_manifest, indent=2))
    (out / "input_rgb").symlink_to(rgb, target_is_directory=True)
    shutil.copy2(calibration, out / "input_calibration.txt")
    launcher = ROOT / "scripts/run_pi3mos_reviewed_entrypoint.py"
    command = [sys.executable, str(launcher), "--imagedir", str(out / "input_rgb"), "--calib", str(out / "input_calibration.txt"),
               "--config", "config/default.yaml", "--outdir", str(out)]
    env = os.environ.copy()
    env.update(PYTHONUNBUFFERED="1", MPLBACKEND="Agg", OMP_NUM_THREADS="2", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               PYTHONPATH=str(ROOT / "baselines/runtime_hooks"), GAMECAM_CUDA_MEMORY_DIR=str(out / "cuda_allocator_stats"))
    patch = subprocess.check_output(["git", "-C", str(upstream), "diff", "--binary", "5e709d27324a935e364e01efc56f3128ac00bf24"])
    (out / "source_changes_from_upstream.patch").write_bytes(patch)
    contract = {"target": args.target, "command": command, "cwd": str(upstream), "expected_frames": len(frames),
                "source_commit": subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip(),
                "source_patch_sha256": hashlib.sha256(patch).hexdigest(), "input_calibration_sha256": digest(out / "input_calibration.txt"),
                "inference_inputs": ["RGB", "camera_intrinsics"], "engine_pose_in_model": False, "engine_depth_in_model": False,
                "default_model_parameters_preserved": True, "native_default_yaml": "config/default.yaml", "frame_stride": 1,
                "optional_GUI_omitted": True, "GUI_cleanup_fix": "Initialize omitted optional gui_process=None in owned subclass; original cleanup method unchanged",
                "observation": "Calls original methods once; copies native outputs to CPU; returns original outputs unchanged; IO costs included",
                "renderer_rng_note": "Optional GUI's random point-display subsampling omitted; global random-number consumption may differ from a GUI run; no full-model bitwise or paper-score match claim",
                "preprocessing": "Native RGB directory stream, optional calibration distortion correction and bottom/right16-multiple crop; native Pi3 preprocessing unchanged",
                "environment_overrides": {k: env[k] for k in ("PYTHONPATH", "OMP_NUM_THREADS", "MPLBACKEND", "HF_HUB_OFFLINE", "GAMECAM_CUDA_MEMORY_DIR")}}
    (out / "execution_contract.json").write_text(json.dumps(contract, indent=2))
    for source in (Path(__file__), launcher, ROOT / "baselines/runtime_hooks/sitecustomize.py"):
        shutil.copy2(source, out / (source.name+".executed_source"))
    started = time.monotonic()
    peak, oom_seen, timeout = None, None, False
    with (out / "inference_log.txt").open("w") as log, (out / "gpu_memory.csv").open("w", newline="") as telemetry:
        process = subprocess.Popen(command, cwd=upstream, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        (out / "process.json").write_text(json.dumps({"pid": process.pid, "process_group": process.pid, "command": command}))
        print(json.dumps({"stage": "NATIVE_INFERENCE_RUNNING", "directory": str(out), "pid": process.pid, "expected_frames": len(frames)}), flush=True)
        writer = csv.writer(telemetry)
        writer.writerow(["elapsed_seconds", "whole_gpu_used_mib", "whole_gpu_total_mib", "whole_gpu_utilization_percent"])
        while process.poll() is None:
            try:
                memory = subprocess.check_output(["/usr/lib/wsl/lib/nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], text=True, timeout=5)
                values = [float(x.strip()) for x in memory.strip().split(",")]
                writer.writerow([time.monotonic()-started, *values]); telemetry.flush()
                peak = max(peak or 0, values[0])
            except (subprocess.SubprocessError, ValueError) as error:
                with (out / "telemetry_errors.jsonl").open("a") as errors:
                    errors.write(json.dumps({"elapsed_seconds": time.monotonic()-started, "error": str(error)})+"\n")
            with (out / "inference_log.txt").open("rb") as observed:
                observed.seek(max(0, observed.seek(0, 2)-32768))
                tail = observed.read()
            if b"CUDA out of memory" in tail:
                oom_seen = oom_seen or time.monotonic()
            if time.monotonic()-started > 7200 or (oom_seen and time.monotonic()-oom_seen > 15):
                timeout = not bool(oom_seen)
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(1)
        code = process.wait()
    completed = code == 0 and (out / "native_run_completed.json").exists()
    stats = [json.loads(path.read_text()) for path in (out / "cuda_allocator_stats").glob("*.json")]
    record = {"status": "PI3MOS_INFERENCE_COMPLETED" if completed else "PI3MOS_INFERENCE_FAILED", "directory": str(out),
              "target": args.target, "expected_frames": len(frames), "exit_code": code, "timed_out": timeout,
              "CUDA_OOM_observed": bool(oom_seen), "wall_seconds": time.monotonic()-started,
              "whole_gpu_peak_used_mib_sampled": peak, "per_process_cuda_allocator_stats": stats,
              "no_hyperparameter_downsizing": True, "model_retry_automatic": False, "GT_in_model": False}
    (out / "status.json").write_text(json.dumps(record, indent=2))
    pointer = "pi3mos_official_demo.json" if args.target == "official-demo" else "pi3mos_mvs.json"
    (ROOT / "reports/SOTA" / pointer).write_text(json.dumps(record, indent=2))
    print(json.dumps({k: record[k] for k in ("status", "directory", "exit_code", "CUDA_OOM_observed", "wall_seconds")}), flush=True)
    return int(not completed)


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared phase5 process lifecycle and telemetry; no model math or replay."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def local(value):
    return Path(str(value).replace("\\", "/").replace("D:/", "/mnt/d/", 1))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for b in iter(lambda: stream.read(8*1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2)+"\n")


def environment(out):
    env = os.environ.copy()
    env.update(PYTHONUNBUFFERED="1", MPLBACKEND="Agg", QT_QPA_PLATFORM="offscreen", OMP_NUM_THREADS="2",
        HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONPATH=str(ROOT / "baselines/runtime_hooks"),
        GAMECAM_CUDA_MEMORY_DIR=str(out / "cuda_allocator_stats"))
    return env


def memory_budget():
    path = Path("/proc/meminfo")
    if not path.exists():
        return {"recorded": False}
    info = {line.split(":", 1)[0]: int(line.split()[1])*1024 for line in path.read_text().splitlines() if len(line.split()) >= 3 and line.split()[2] == "kB"}
    return {"recorded": True, "scope": "WSL guest at native controller launch, not per-model allocated memory",
        **{key+"_bytes": info[key] for key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")}}


def execute(stage, command, cwd, env, out, gpu_writer, gpu_stream, started):
    failure, failure_at, peak = None, None, 0.
    now = time.monotonic()
    logfile = out / ("inference_log.txt" if stage == "native" else stage+".log")
    if shutil.disk_usage(out).free < 3*1024**3:
        logfile.write_text("Workspace free space below 3 GiB; no native subprocess started. Existing data retained.\n")
        return {"stage": stage, "exit_code": None, "wall_seconds": 0., "reason": "WORKSPACE_FREE_SPACE_BELOW_3_GIB_BEFORE_LAUNCH",
            "whole_gpu_peak_used_mib_sampled": 0., "log": str(logfile), "native_subprocess_started": False}
    with logfile.open("w") as log:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write(out / ("process.json" if stage == "native" else stage+"_process.json"), {"pid": process.pid, "pgid": process.pid, "command": command})
        while process.poll() is None:
            try:
                values = [float(x) for x in subprocess.check_output(["/usr/lib/wsl/lib/nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], text=True, timeout=5).strip().split(",")]
                gpu_writer.writerow([time.monotonic()-started, *values]); gpu_stream.flush(); peak = max(peak, values[0])
            except (subprocess.SubprocessError, ValueError) as error:
                # Optional observation logging only. Do not add another GPU
                # query, impute a value, or interrupt the native subprocess.
                try:
                    with (out / "gpu_sampling_errors.jsonl").open("a", encoding="utf-8") as errors:
                        errors.write(json.dumps({"stage": stage, "elapsed_seconds": time.monotonic()-started,
                            "error_type": type(error).__name__, "error": str(error), "query_timeout_seconds": 5,
                            "missing_GPU_value_imputed": False}) + "\n")
                except OSError:
                    pass
            with logfile.open("rb") as reader:
                reader.seek(max(0, reader.seek(0, 2)-32768)); tail = reader.read()
            if b"Traceback (most recent call last)" in tail:
                failure_at = failure_at or time.monotonic()
                failure = "CUDA_OUT_OF_MEMORY" if b"out of memory" in tail else "NATIVE_EXCEPTION"
            disk_low = shutil.disk_usage(out).free < 2*1024**3
            if disk_low:
                failure = "WORKSPACE_FREE_SPACE_BELOW_2_GIB"
            if disk_low or (failure_at and time.monotonic()-failure_at > 20) or time.monotonic()-now > 86400:
                failure = failure or "TIMEOUT_24H"
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(1)
        code = process.wait()
    return {"stage": stage, "exit_code": code, "wall_seconds": time.monotonic()-now,
            "reason": failure, "whole_gpu_peak_used_mib_sampled": peak, "log": str(logfile)}


def freeze_source(upstream, base_commit, out):
    # Match the Windows checkout's CRLF clean filter; exact cached source bytes
    # remain separately indexed. Avoid recording every CRLF as a model patch.
    patch = subprocess.check_output(["git", "-c", "core.autocrlf=true", "-C", str(upstream), "diff", "--binary", base_commit])
    (out / "source_changes_from_upstream.patch").write_bytes(patch)
    return {"source_commit": subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip(),
            "upstream_base_commit": base_commit, "source_patch_sha256": hashlib.sha256(patch).hexdigest(),
            "patch_clean_filter": "core.autocrlf=true; exact execution source bytes separately indexed"}

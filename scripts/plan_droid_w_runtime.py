"""Resolve one isolated runtime before installation; retain solver failures."""
from __future__ import annotations
import _bootstrap
import concurrent.futures
import json
import subprocess
from pathlib import Path
from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    setup = json.loads((PROJECT / "reports/SOTA/conda_setup.json").read_text())
    if setup["exit_code"]:
        raise ValueError("WSL Conda environment has not been created")
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "droid_runtime_plan")
    env = setup["droid_w_environment"]
    conda = setup["conda_prefix"] + "/bin/conda"
    dest = "/mnt/d/" + out.as_posix()[3:]
    cache = "/mnt/d/aaa/GameCam-VO/data/sota_toolchains/pip_cache_linux"
    commands = {
        "torch_plan": [env + "/bin/python", "-m", "pip", "--isolated", "--cache-dir", cache, "install", "--dry-run", "--report", dest + "/torch_plan.json",
            "torch==2.7.1", "torchvision==0.22.1", "torchaudio==2.7.1", "--index-url", "https://download.pytorch.org/whl/cu128"],
        "cuda_compiler_plan": [conda, "install", "--prefix", env, "--dry-run", "--json", "--override-channels", "-c", "nvidia/label/cuda-12.8.1", "-c", "conda-forge",
            "cuda-nvcc=12.8.93", "cuda-cudart-dev=12.8.90", "cuda-cccl=12.8.90"]}
    def run(item):
        name, command = item
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            p = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", *command], stdout=log, stderr=subprocess.STDOUT, timeout=1000)
        return {"stage": name, "exit_code": p.returncode, "command": command}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, commands.items()))
    write_json(out / "plan_results.json", results)
    write_json(PROJECT / "reports/SOTA/runtime_plan.json", {"directory": str(out), "results": results})
    print(json.dumps({"directory": str(out), "results": [{"stage": r["stage"], "exit_code": r["exit_code"]} for r in results]}))
    return int(any(r["exit_code"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())

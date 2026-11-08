from __future__ import annotations
import _bootstrap
import json
import subprocess
from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    setup = json.loads((PROJECT / "reports/SOTA/conda_setup.json").read_text())
    plan = json.loads((PROJECT / "reports/SOTA/runtime_plan.json").read_text())
    if setup["exit_code"] or any(r["exit_code"] for r in plan["results"]):
        raise ValueError("Runtime resolution did not pass")
    env, conda = setup["droid_w_environment"], setup["conda_prefix"] + "/bin/conda"
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "droid_core_runtime_install")
    commands = [
        ("cuda_compiler", [conda, "install", "-y", "--prefix", env, "--override-channels", "-c", "nvidia/label/cuda-12.8.1", "-c", "conda-forge", "cuda-nvcc=12.8.93", "cuda-cudart-dev=12.8.90", "cuda-cccl=12.8.90"]),
        ("torch", [env + "/bin/python", "-m", "pip", "--isolated", "--cache-dir", "/mnt/d/aaa/GameCam-VO/data/sota_toolchains/pip_cache_linux", "install", "numpy==1.26.3", "torch==2.7.1", "torchvision==0.22.1", "torchaudio==2.7.1", "--index-url", "https://download.pytorch.org/whl/cu128"]),
        ("nvcc_version", [env + "/bin/nvcc", "--version"]),
        ("gpu_smoke", [env + "/bin/python", "-c", "import torch,json; assert torch.cuda.is_available(); a=torch.randn(64,64,device='cuda'); b=a@a.T; torch.cuda.synchronize(); assert torch.isfinite(b).all(); print(json.dumps({'torch':torch.__version__,'cuda_build':torch.version.cuda,'device':torch.cuda.get_device_name(),'compute_capability':torch.cuda.get_device_capability(),'compiled_architectures':torch.cuda.get_arch_list(),'float32_matmul_finite':True,'peak_allocated_bytes':torch.cuda.max_memory_allocated()}))"]),
        ("pip_freeze", [env + "/bin/python", "-m", "pip", "freeze"]),
        ("conda_explicit", [conda, "list", "--prefix", env, "--explicit"]),
    ]
    results = []
    write_json(out / "reviewed_commands.json", commands)
    for name, command in commands:
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            p = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", *command], stdout=log, stderr=subprocess.STDOUT, timeout=1500)
        results.append({"stage": name, "exit_code": p.returncode, "command": command})
        write_json(out / "execution.json", results)
        if p.returncode:
            break
    status = {"directory": str(out), "environment": env, "status": "CORE_GPU_RUNTIME_PASSED" if len(results) == len(commands) and not any(r["exit_code"] for r in results) else "CORE_RUNTIME_SETUP_FAILED",
              "results": results, "model_weights_downloaded": False, "model_inference_executed": False,
              "note": "numpy pinned to author's 1.26.3 instead of dry-run's unconstrained 2.2.6. Conda cuda-driver-dev provides link stubs, not a kernel/WSL NVIDIA driver replacement."}
    write_json(PROJECT / "reports/SOTA/droid_core_runtime.json", status)
    print(json.dumps({"directory": str(out), "status": status["status"], "results": [{"stage": r["stage"], "exit_code": r["exit_code"]} for r in results]}))
    return int(status["status"] != "CORE_GPU_RUNTIME_PASSED")


if __name__ == "__main__":
    raise SystemExit(main())

"""Install BA-Track prerequisites sequentially in its own WSL Conda prefix.

No model weights or datasets are downloaded here. The original Windows and
DROID-W environments are never installation targets.
"""
from __future__ import annotations

import _bootstrap
import argparse
import json
import subprocess
from pathlib import Path

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


ENV = "/home/lsuser/.local/share/gamecam-vo/envs/ba-track"
ROOT = "/mnt/d/aaa/GameCam-VO"
CACHE = ROOT + "/data/sota_toolchains/pip_cache_linux"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["core", "dependencies"], required=True)
    parser.add_argument("--direct-network", action="store_true", help="Per-command routing after a recorded proxy TLS timeout; does not change system proxy settings")
    parser.add_argument("--cached-core-wheels", action="store_true", help="Reuse verified torch wheels and obtain CUDA dependencies from the hash-audited PyPI transport")
    args = parser.parse_args()
    demo = json.loads((PROJECT / "reports/SOTA/droid_official_demo.json").read_text())
    attempts = sorted((PROJECT / "results/E8_DROID_W").glob("*_mvs_0000_rgb_only"))
    if demo["status"] != "OFFICIAL_DEMO_COMPLETED" or not attempts or not (attempts[-1] / "status.json").is_file():
        raise RuntimeError("Finish the active DROID-W attempt before installing the second environment")
    conda = json.loads((PROJECT / "reports/SOTA/conda_setup.json").read_text())["conda_prefix"] + "/bin/conda"
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "ba_track_" + args.stage)
    linux_out = ROOT + "/" + out.relative_to(PROJECT).as_posix()
    pip = [ENV + "/bin/python", "-m", "pip", "--isolated", "--cache-dir", CACHE]
    if args.stage == "core":
        exists = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "/usr/bin/test", "-x", ENV + "/bin/python"], capture_output=True).returncode == 0
        commands = [
            ("conda_install_existing" if exists else "conda_create", [conda, "install" if exists else "create", "-y", "--prefix", ENV, "--override-channels", "-c", "nvidia/label/cuda-12.8.1", "-c", "conda-forge",
                              "python=3.10", "pip", "setuptools<80", "eigen=3.4.0", "gcc_linux-64=13.4.0", "gxx_linux-64=13.4.0",
                              "cuda-nvcc=12.8.93", "cuda-cudart-dev=12.8.90", "cuda-cccl=12.8.90"]),
            ("torch", pip + ["install", "numpy==1.24.3", "torch==2.7.1", "torchvision==0.22.1", "--index-url", "https://download.pytorch.org/whl/cu128"]),
            ("gpu_smoke", [ENV + "/bin/python", "-c", "import torch,json; assert torch.cuda.is_available(); a=torch.arange(16,device='cuda',dtype=torch.float32).reshape(4,4); b=a@a.T; torch.cuda.synchronize(); torch.testing.assert_close(b.cpu(), a.cpu()@a.cpu().T); print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'device':torch.cuda.get_device_name(),'capability':torch.cuda.get_device_capability(),'numerical_matmul_passed':True}))"]),
            ("nvcc", [ENV + "/bin/nvcc", "--version"]),
            ("conda_explicit", [conda, "list", "--prefix", ENV, "--explicit"]),
        ]
        if args.cached_core_wheels:
            previous = json.loads((PROJECT / "reports/SOTA/ba_track_core_runtime.json").read_text())
            if not exists or not any(row["stage"].startswith("conda_") and row["exit_code"] == 0 for row in previous["results"]):
                raise RuntimeError("Reuse requires the successful existing BA-Track Conda creation record")
            wheels = json.loads((PROJECT / "reports/SOTA/cached_core_wheelhouse.json").read_text())
            for row in wheels["wheels"]:
                if sha256(row["wheel"]) != row["sha256"]:
                    raise ValueError("Verified cached wheel changed")
            wheel_directory = ROOT + "/" + Path(wheels["directory"]).relative_to(PROJECT).as_posix()
            commands = [
                ("torch_cached_and_pypi_cuda", pip + ["install", "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple", "--find-links", wheel_directory,
                                                    "--report", linux_out + "/core_pip_install_report.json", "numpy==1.24.3", "torch==2.7.1+cu128", "torchvision==0.22.1+cu128"]),
                ("core_publisher_hash_audit", [ENV + "/bin/python", ROOT + "/scripts/verify_pypi_install_report.py", linux_out + "/core_pip_install_report.json", "--pytorch-index-plan", ROOT + "/logs/SOTA_setup/20261030T164732_894515Z_droid_runtime_plan/torch_plan.json"]),
                *commands[2:],
            ]
            write_json(out / "reused_conda_and_cache_evidence.json", {"conda_creation_record": str(Path(previous["directory"]) / "status.json"),
                       "cached_core_wheels_manifest": str(PROJECT / "reports/SOTA/cached_core_wheelhouse.json"), "zero_byte_nvrtc_transport_failure_retained": True})
    else:
        core = json.loads((PROJECT / "reports/SOTA/ba_track_core_runtime.json").read_text())
        if core["status"] != "BA_TRACK_CORE_PASSED":
            raise RuntimeError("The BA-Track CUDA core probe must pass before installing dependencies")
        # Identical torch/CUDA/Python ABI to the independently built and tested
        # DROID scatter wheel; do not use the glibc>=2.32 PyG wheel on Ubuntu20.
        wheel = PROJECT / "logs/SOTA_setup/20261030T172914_610525Z_droid_extensions/wheels/torch_scatter-2.1.2-cp310-cp310-linux_x86_64.whl"
        if sha256(wheel) != "8e2bc698f95edf79e857e0a650a9f51c05c809dbe13ffde2905800b026027587":
            raise ValueError("Previously built scatter wheel checksum changed")
        original = PROJECT / "baselines/ba_track/upstream/requirements.txt"
        lines = original.read_text().splitlines()
        selected = [line for line in lines if not line.strip().lower().startswith("torch-scatter")]
        (out / "requirements_runtime.txt").write_text("\n".join(selected) + "\n", encoding="utf-8")
        (out / "constraints.txt").write_text("torch==2.7.1+cu128\ntorchvision==0.22.1+cu128\nnumpy==1.24.3\nhuggingface-hub==0.25.2\n", encoding="utf-8")
        commands = [
            ("requirements", pip + ["install", "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple", "--report", linux_out + "/pip_install_report.json", "-c", linux_out + "/constraints.txt", "-r", linux_out + "/requirements_runtime.txt", "huggingface-hub==0.25.2", "gdown", "safetensors", "pyyaml"]),
            ("official_pypi_hash_audit", [ENV + "/bin/python", ROOT + "/scripts/verify_pypi_install_report.py", linux_out + "/pip_install_report.json"]),
            ("xformers", pip + ["install", "-c", linux_out + "/constraints.txt", "xformers==0.0.31.post1", "--index-url", "https://download.pytorch.org/whl/cu128"]),
            ("scatter_local_wheel", pip + ["install", "--no-index", "--no-deps", ROOT + "/" + wheel.relative_to(PROJECT).as_posix()]),
            ("pip_check", pip + ["check"]),
            ("pip_freeze", pip + ["freeze"]),
            ("conda_explicit", [conda, "list", "--prefix", ENV, "--explicit"]),
        ]
        write_json(out / "dependency_selection.json", {
            "upstream_requirements_sha256": sha256(original),
            "upstream_runtime_requirements": "All root requirements retained; scatter installed from source-built ABI-matching wheel",
            "nested_UniDepth_requirements": "Use vendored source via PYTHONPATH; its full development/training dependency file conflicts with the GPU stack. Inference imports will be verified separately.",
            "wheel_sha256": sha256(wheel), "no_model_prior_substitution": True,
        })
    write_json(out / "reviewed_commands.json", commands)
    results = []
    routing = ["/usr/bin/env", "-u", "HTTP_PROXY", "-u", "HTTPS_PROXY", "-u", "ALL_PROXY", "-u", "http_proxy", "-u", "https_proxy", "-u", "all_proxy", "NO_PROXY=*", "no_proxy=*"] if args.direct_network else []
    for name, command in commands:
        error = None
        with (out / (name + ".log")).open("w", encoding="utf-8") as stream:
            try:
                process = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", *routing, *command], stdout=stream, stderr=subprocess.STDOUT, timeout=3600)
                code = process.returncode
            except subprocess.TimeoutExpired as exc:
                code, error = 124, str(exc)
        results.append({"stage": name, "exit_code": code, "error": error, "command": command, "routing_prefix": routing})
        write_json(out / "execution.json", results)
        print(name, code, flush=True)
        if code:
            break
    passed = len(results) == len(commands) and all(row["exit_code"] == 0 for row in results)
    status = {
        "status": ("BA_TRACK_CORE_PASSED" if args.stage == "core" else "BA_TRACK_DEPENDENCIES_INSTALLED") if passed else "BA_TRACK_SETUP_FAILED",
        "directory": str(out), "environment": ENV, "stage": args.stage, "results": results,
        "model_weights_downloaded": False, "model_inference_executed": False,
        "original_windows_environment_modified": False, "droid_environment_modified": False,
        "network_routing": "direct_for_this_command_only" if args.direct_network else "existing_environment_proxy",
        "system_proxy_configuration_modified": False,
        "deviation": "Blackwell compatibility stack torch2.7.1/cu128 replaces author torch2.1.1/cu118; model/native numerical checks required before any reproduction claim",
        "eigen_source_note": "README GitLab Eigen3.4.0 archive transport timed out; Conda supplies the same declared header version. Build records actual version macros and header digest, and uses CPATH without editing setup.py.",
    }
    name = "ba_track_core_runtime.json" if args.stage == "core" else "ba_track_dependencies.json"
    write_json(PROJECT / "reports/SOTA" / name, status)
    write_json(out / "status.json", status)
    print(json.dumps({"status": status["status"], "directory": str(out)}))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())

"""Sequential independent Pi3MOS Conda setup after the BA local checks finish."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path
import subprocess

import yaml

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


ENV = "/home/lsuser/.local/share/gamecam-vo/envs/pi3mos"
ROOT = "/mnt/d/aaa/GameCam-VO"
ROUTE = ["/usr/bin/env", "-u", "HTTP_PROXY", "-u", "HTTPS_PROXY", "-u", "ALL_PROXY", "-u", "http_proxy", "-u", "https_proxy", "-u", "all_proxy", "NO_PROXY=*", "no_proxy=*"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["core", "dependencies"], required=True)
    args = parser.parse_args()
    ba = json.loads((PROJECT / "reports/SOTA/ba_track_native_probe.json").read_text())
    smoke = json.loads((PROJECT / "reports/SOTA/ba_track_depth_prior_smoke.json").read_text())
    if ba["status"] != "BA_TRACK_NATIVE_CUDA_CHECKS_PASSED" or smoke["status"] != "BA_PRIOR_COMPONENT_SMOKE_COMPLETED":
        raise RuntimeError("Finish the preceding environment's actual local checks first")
    conda = json.loads((PROJECT / "reports/SOTA/conda_setup.json").read_text())["conda_prefix"] + "/bin/conda"
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "pi3mos_" + args.stage)
    linux_out = ROOT + "/" + out.relative_to(PROJECT).as_posix()
    pip = [ENV + "/bin/python", "-m", "pip", "--isolated", "--cache-dir", ROOT + "/data/sota_toolchains/pip_cache_linux"]
    if args.stage == "core":
        exists = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "/usr/bin/test", "-x", ENV + "/bin/python"], capture_output=True).returncode == 0
        wheelhouse = json.loads((PROJECT / "reports/SOTA/cached_core_wheelhouse.json").read_text())
        wheels = ROOT + "/" + Path(wheelhouse["directory"]).relative_to(PROJECT).as_posix()
        commands = [
            ("conda_create_or_resume", [conda, "install" if exists else "create", "-y", "--prefix", ENV, "--override-channels", "-c", "nvidia/label/cuda-12.8.1", "-c", "conda-forge",
                                       "python=3.10", "pip", "setuptools<80", "eigen=3.4.0", "gcc_linux-64=13.4.0", "gxx_linux-64=13.4.0", "cuda-nvcc=12.8.93", "cuda-cudart-dev=12.8.90", "cuda-cccl=12.8.90"]),
            ("core_torch", pip + ["install", "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple", "--find-links", wheels, "--report", linux_out + "/core_install_report.json",
                                   "numpy==1.26.4", "torch==2.7.1+cu128", "torchvision==0.22.1+cu128"]),
            ("publisher_hash_audit", [ENV + "/bin/python", ROOT + "/scripts/verify_pypi_install_report.py", linux_out + "/core_install_report.json", "--pytorch-index-plan", ROOT + "/logs/SOTA_setup/20261030T164732_894515Z_droid_runtime_plan/torch_plan.json"]),
            ("actual_cuda_smoke", [ENV + "/bin/python", "-c", "import torch,json; x=torch.arange(16,device='cuda',dtype=torch.float32).reshape(4,4); y=x@x.T; torch.cuda.synchronize(); torch.testing.assert_close(y.cpu(),x.cpu()@x.cpu().T); print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'GPU':torch.cuda.get_device_name(),'matmul_passed':True}))"]),
            ("nvcc", [ENV + "/bin/nvcc", "--version"]),
        ]
    else:
        core = json.loads((PROJECT / "reports/SOTA/pi3mos_core_runtime.json").read_text())
        if core["status"] != "PI3MOS_CORE_PASSED":
            raise RuntimeError("Actual Pi3MOS environment CUDA check must pass first")
        definition = PROJECT / "baselines/pi3mos/upstream/environment.yml"
        requirements = next(item["pip"] for item in yaml.safe_load(definition.read_text())["dependencies"] if isinstance(item, dict) and "pip" in item)
        (out / "requirements.txt").write_text("\n".join(requirements) + "\n", encoding="utf-8")
        (out / "constraints.txt").write_text("numpy==1.26.4\ntorch==2.7.1+cu128\ntorchvision==0.22.1+cu128\n", encoding="utf-8")
        wheel = PROJECT / "logs/SOTA_setup/20261030T172914_610525Z_droid_extensions/wheels/torch_scatter-2.1.2-cp310-cp310-linux_x86_64.whl"
        if sha256(wheel) != "8e2bc698f95edf79e857e0a650a9f51c05c809dbe13ffde2905800b026027587":
            raise ValueError("Previously source-built scatter wheel changed")
        commands = [
            ("declared_pip_dependencies", pip + ["install", "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple", "--report", linux_out + "/dependencies_install_report.json",
                                                "-c", linux_out + "/constraints.txt", "-r", linux_out + "/requirements.txt", "ninja"]),
            ("publisher_hash_audit", [ENV + "/bin/python", ROOT + "/scripts/verify_pypi_install_report.py", linux_out + "/dependencies_install_report.json"]),
            ("scatter_source_wheel", pip + ["install", "--no-index", "--no-deps", ROOT + "/" + wheel.relative_to(PROJECT).as_posix()]),
            ("pip_check", pip + ["check"]),
        ]
    commands += [("pip_freeze", pip + ["freeze"]), ("conda_explicit", [conda, "list", "--prefix", ENV, "--explicit"])]
    write_json(out / "reviewed_commands.json", commands)
    results = []
    for name, command in commands:
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            try:
                process = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", *ROUTE, *command], stdout=log, stderr=subprocess.STDOUT, timeout=3600)
                code = process.returncode
            except subprocess.TimeoutExpired:
                code = 124
        results.append({"stage": name, "exit_code": code, "command": command, "routing_prefix": ROUTE})
        write_json(out / "execution.json", results)
        print(name, code, flush=True)
        if code:
            break
    passed = len(results) == len(commands) and all(row["exit_code"] == 0 for row in results)
    record = {"status": ("PI3MOS_CORE_PASSED" if args.stage == "core" else "PI3MOS_DEPENDENCIES_INSTALLED") if passed else "PI3MOS_SETUP_FAILED",
              "environment": ENV, "directory": str(out), "results": results, "weights_downloaded": False, "Pi3MOS_inference_executed": False,
              "deviations": ["Modern sm120-compatible torch2.7.1/cu128 replaces author torch2.3.1/cu121", "Conda Eigen3.4.0 header transport after GitLab connection failure", "Reuse identical-version source-built scatter wheel in independent prefix"],
              "other_environments_modified": False, "system_proxy_configuration_modified": False}
    write_json(out / "status.json", record)
    write_json(PROJECT / ("reports/SOTA/pi3mos_core_runtime.json" if args.stage == "core" else "reports/SOTA/pi3mos_dependencies.json"), record)
    print(json.dumps({"status": record["status"], "directory": str(out)}))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())

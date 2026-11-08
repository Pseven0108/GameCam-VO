from __future__ import annotations

import _bootstrap
import argparse
import json
import subprocess

from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub-compat-only", action="store_true")
    args = parser.parse_args()
    setup = json.loads((PROJECT / "reports/SOTA/conda_setup.json").read_text())
    core = json.loads((PROJECT / "reports/SOTA/droid_core_runtime.json").read_text())
    if core["status"] != "CORE_GPU_RUNTIME_PASSED":
        raise RuntimeError("The actual CUDA runtime probe must pass first")
    env = setup["droid_w_environment"]
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "droid_dependencies")
    constraints = out / "constraints.txt"
    constraints.write_text("numpy==1.26.3\ntorch==2.7.1+cu128\ntorchvision==0.22.1+cu128\ntorchaudio==2.7.1+cu128\nhuggingface-hub==0.25.2\n", encoding="utf-8")
    linux_out = "/mnt/d/aaa/GameCam-VO/" + out.relative_to(PROJECT).as_posix()
    pip = [env + "/bin/python", "-m", "pip", "--isolated", "--cache-dir", "/mnt/d/aaa/GameCam-VO/data/sota_toolchains/pip_cache_linux"]
    commands = [
        ("requirements", pip + ["install", "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple", "--report", linux_out + "/requirements_install_report.json", "-c", linux_out + "/constraints.txt", "-r", "/mnt/d/aaa/GameCam-VO/baselines/droid_w/upstream/requirements.txt", "colorama", "pyyaml", "mmcv-lite==2.2.0", "gdown", "huggingface-hub==0.25.2"]),
        ("pypi_hash_audit", [env + "/bin/python", "/mnt/d/aaa/GameCam-VO/scripts/verify_pypi_install_report.py", linux_out + "/requirements_install_report.json"]),
        ("xformers", pip + ["install", "-c", linux_out + "/constraints.txt", "xformers==0.0.31.post1", "--index-url", "https://download.pytorch.org/whl/cu128"]),
        ("torch_scatter", pip + ["install", "--no-index", "--find-links", "https://data.pyg.org/whl/torch-2.7.0+cu128.html", "torch-scatter==2.1.2"]),
        ("pip_check", pip + ["check"]),
        ("pip_freeze", pip + ["freeze"]),
    ]
    if args.hub_compat_only:
        commands = [
            ("hub_compatibility_pin", pip + ["install", "--no-deps", "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple", "--report", linux_out + "/requirements_install_report.json", "huggingface-hub==0.25.2"]),
            ("pypi_hash_audit", [env + "/bin/python", "/mnt/d/aaa/GameCam-VO/scripts/verify_pypi_install_report.py", linux_out + "/requirements_install_report.json"]),
            ("timm_hub_import", [env + "/bin/python", "-c", "from timm.models._hub import has_hf_hub; assert has_hf_hub(necessary=True); print('timm Hugging Face API compatibility passed')"]),
            ("pip_check", pip + ["check"]), ("pip_freeze", pip + ["freeze"]),
        ]
    write_json(out / "reviewed_commands.json", commands)
    results = []
    for name, command in commands:
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            p = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", *command], stdout=log, stderr=subprocess.STDOUT, timeout=2400)
        results.append({"stage": name, "exit_code": p.returncode, "command": command})
        write_json(out / "execution.json", results)
        print(name, p.returncode, flush=True)
        if p.returncode:
            break
    status = {"directory": str(out), "environment": env, "results": results,
              "status": "DEPENDENCIES_INSTALLED" if len(results) == len(commands) and not any(r["exit_code"] for r in results) else "DEPENDENCY_SETUP_FAILED",
              "deviations": ["Keep the tested Blackwell torch/cu128 stack with explicit constraints", "MMCV-lite supplies Python utilities; no MMCV CUDA ops are used", "xformers and torch-scatter wheels match torch2.7/cu128"],
              "model_inference_executed": False}
    write_json(PROJECT / ("reports/SOTA/droid_hub_compatibility.json" if args.hub_compat_only else "reports/SOTA/droid_dependencies.json"), status)
    print(json.dumps(status))
    return int(status["status"] != "DEPENDENCIES_INSTALLED")


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import _bootstrap
import argparse
import json
import shlex
import subprocess

from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-stage", choices=["lietorch", "droid_backends", "simple_knn", "diff_gaussian_rasterization", "torch_scatter"], default="lietorch")
    parser.add_argument("--wheel-only", action="store_true", help="Build artifacts without changing installed packages")
    parser.add_argument("--until-stage", choices=["lietorch", "droid_backends", "simple_knn", "diff_gaussian_rasterization", "torch_scatter"], default="torch_scatter")
    args = parser.parse_args()
    dependencies = json.loads((PROJECT / "reports/SOTA/droid_dependencies.json").read_text())
    if dependencies["status"] != "DEPENDENCIES_INSTALLED":
        raise RuntimeError("Dependency installation must pass before building")
    setup = json.loads((PROJECT / "reports/SOTA/conda_setup.json").read_text())
    env, conda = setup["droid_w_environment"], setup["conda_prefix"]
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "droid_extensions")
    linux_out = "/mnt/d/aaa/GameCam-VO/" + out.relative_to(PROJECT).as_posix()
    if args.wheel_only:
        (out / "wheels").mkdir()
    root = "/mnt/d/aaa/GameCam-VO/baselines/droid_w/upstream"
    stages = [
        ("lietorch", root + "/thirdparty/lietorch"),
        ("droid_backends", root),
        ("simple_knn", root + "/thirdparty/simple-knn"),
        ("diff_gaussian_rasterization", root + "/thirdparty/diff-gaussian-rasterization-w-pose"),
        ("torch_scatter", "/mnt/d/aaa/GameCam-VO/baselines/droid_w/prior_sources/pytorch_scatter"),
    ]
    all_stages = stages.copy()
    start_index = [name for name, _ in stages].index(args.from_stage)
    end_index = [name for name, _ in stages].index(args.until_stage) + 1
    stages = stages[start_index:end_index]
    if not stages:
        raise ValueError("Invalid stage interval")
    results = []
    for name, cwd in stages:
        shell = "\n".join([
            "#!/bin/bash", "set -eo pipefail",
            "source " + shlex.quote(conda + "/etc/profile.d/conda.sh"),
            "conda activate " + shlex.quote(env),
            "set -u",
            "export MAX_JOBS=1 TORCH_CUDA_ARCH_LIST=12.0",
            "export CUDA_HOME=\"$CONDA_PREFIX\"",
            "export CPATH=\"$CONDA_PREFIX/targets/x86_64-linux/include${CPATH:+:$CPATH}\"",
            "for include_dir in \"$CONDA_PREFIX\"/lib/python3.10/site-packages/nvidia/*/include; do",
            "  if [ -d \"$include_dir\" ]; then export CPATH=\"$include_dir:$CPATH\"; fi",
            "done",
            "export FORCE_ONLY_CUDA=1" if name == "torch_scatter" else ":",
            "cd " + shlex.quote(cwd),
            ("python -m pip wheel --no-index --no-build-isolation --no-deps --verbose --wheel-dir " + shlex.quote(linux_out + "/wheels") + " .") if args.wheel_only else "python -m pip install --no-index --no-build-isolation --no-deps --verbose .",
            "",
        ])
        script = out / (name + ".sh")
        script.write_bytes(shell.encode("utf-8"))
        linux_script = "/mnt/d/aaa/GameCam-VO/" + script.relative_to(PROJECT).as_posix()
        command = ["wsl", "-d", "Ubuntu", "--exec", "/bin/bash", linux_script]
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            p = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=2400)
        results.append({"stage": name, "exit_code": p.returncode, "command": command, "script": str(script)})
        write_json(out / "execution.json", results)
        print(name, p.returncode, flush=True)
        if p.returncode:
            break
    status = {"directory": str(out), "environment": env, "results": results,
              "status": "EXTENSIONS_BUILT" if len(results) == len(stages) and not any(r["exit_code"] for r in results) else "EXTENSION_BUILD_FAILED",
              "model_inference_executed": False, "architecture": "sm_120", "max_jobs": 1,
              "stages_this_attempt": [name for name, _ in stages],
              "earlier_stages_not_repeated": [name for name, _ in all_stages[:start_index]],
              "verification_note": "All installed extensions still require the separate actual numerical CUDA probe, including stages built in earlier attempts."}
    if args.wheel_only:
        status["status"] = "WHEELS_BUILT_PENDING_INSTALL" if status["status"] == "EXTENSIONS_BUILT" else "WHEEL_BUILD_FAILED"
        status["wheel_directory"] = str(out / "wheels")
    write_json(PROJECT / ("reports/SOTA/droid_scatter_wheel_build.json" if args.wheel_only else "reports/SOTA/droid_extension_build.json"), status)
    print(json.dumps(status))
    return int(status["status"] not in ("EXTENSIONS_BUILT", "WHEELS_BUILT_PENDING_INSTALL"))


if __name__ == "__main__":
    raise SystemExit(main())

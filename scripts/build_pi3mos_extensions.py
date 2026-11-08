"""Build official Pi3MOS native sources and record numerical setup evidence."""
from __future__ import annotations

import _bootstrap
import argparse
import json
import shlex
import subprocess

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-only", action="store_true")
    args = parser.parse_args()
    dependencies = json.loads((PROJECT / "reports/SOTA/pi3mos_dependencies.json").read_text())
    if dependencies["status"] != "PI3MOS_DEPENDENCIES_INSTALLED":
        raise RuntimeError("Complete the independent Pi3MOS dependencies first")
    env = dependencies["environment"]
    conda = json.loads((PROJECT / "reports/SOTA/conda_setup.json").read_text())["conda_prefix"]
    root = "/mnt/d/aaa/GameCam-VO"
    upstream = PROJECT / "baselines/pi3mos/upstream"
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "pi3mos_native")
    linux_out = root + "/" + out.relative_to(PROJECT).as_posix()
    commit = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    (out / "source_changes_from_upstream.patch").write_bytes(subprocess.check_output([
        "git", "-C", str(upstream), "diff", "--binary", "5e709d27324a935e364e01efc56f3128ac00bf24"]))
    shell = "\n".join([
        "#!/bin/bash", "set -eo pipefail",
        "source " + shlex.quote(conda + "/etc/profile.d/conda.sh"),
        "conda activate " + shlex.quote(env), "set -u",
        "export MAX_JOBS=1 TORCH_CUDA_ARCH_LIST=12.0",
        'export CUDA_HOME="$CONDA_PREFIX"',
        'export CPATH="$CONDA_PREFIX/include/eigen3:$CONDA_PREFIX/targets/x86_64-linux/include${CPATH:+:$CPATH}"',
        'for include_dir in "$CONDA_PREFIX"/lib/python3.10/site-packages/nvidia/*/include; do',
        '  if [ -d "$include_dir" ]; then export CPATH="$include_dir:$CPATH"; fi', "done",
        "python -c " + shlex.quote("import os,re,json,hashlib; from pathlib import Path; p=Path(os.environ['CONDA_PREFIX'])/'include/eigen3/Eigen/src/Core/util/Macros.h'; b=p.read_bytes(); v=[int(re.search(rb'#define EIGEN_'+field+rb'_VERSION\\s+(\\d+)',b).group(1)) for field in (b'WORLD',b'MAJOR',b'MINOR')]; assert v==[3,4,0],v; print(json.dumps({'Eigen_version':v,'macros_sha256':hashlib.sha256(b).hexdigest(),'header_source':'Conda eigen=3.4.0'}))"),
        "cd " + shlex.quote(root + "/baselines/pi3mos/upstream"),
        "python -m pip install --no-index --no-build-isolation --no-deps --verbose .", "",
    ])
    (out / "build.sh").write_bytes(shell.encode("utf-8"))
    commands = [] if args.probe_only else [("native_build", ["/bin/bash", linux_out + "/build.sh"])]
    commands += [
        ("numerical_cuda_probe", [env + "/bin/python", root + "/scripts/probe_pi3mos_extensions.py"]),
        ("pip_check", [env + "/bin/python", "-m", "pip", "check"]),
        ("pip_freeze", [env + "/bin/python", "-m", "pip", "freeze"]),
    ]
    write_json(out / "reviewed_commands.json", commands)
    results = []
    for name, command in commands:
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            try:
                process = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", *command], stdout=log, stderr=subprocess.STDOUT, timeout=3600)
                code = process.returncode
            except subprocess.TimeoutExpired:
                code = 124
        results.append({"stage": name, "exit_code": code, "command": command})
        write_json(out / "execution.json", results)
        print(name, code, flush=True)
        if code:
            break
    passed = len(results) == len(commands) and all(row["exit_code"] == 0 for row in results)
    probe = None
    if passed:
        records = [line for line in (out / "numerical_cuda_probe.log").read_text().splitlines() if line.startswith('{"status":')]
        probe = json.loads(records[-1])
        if probe["status"] != "PI3MOS_NATIVE_CUDA_CHECKS_PASSED":
            raise ValueError("Unexpected native numerical probe record")
    record = {"status": "PI3MOS_NATIVE_CUDA_CHECKS_PASSED" if passed else "PI3MOS_NATIVE_BUILD_OR_PROBE_FAILED",
              "directory": str(out), "environment": env, "results": results, "numerical_probe": probe,
              "source_commit": commit, "patch_from_original_sha256": sha256(out / "source_changes_from_upstream.patch"),
              "probe_source_sha256": sha256(PROJECT / "scripts/probe_pi3mos_extensions.py"),
              "arch": "sm_120", "max_jobs": 1, "model_inference_executed": False}
    write_json(out / "status.json", record)
    write_json(PROJECT / "reports/SOTA/pi3mos_native_probe.json", record)
    print(json.dumps({"status": record["status"], "directory": str(out)}))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())

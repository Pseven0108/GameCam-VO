from __future__ import annotations

import _bootstrap
import json
import shlex
import subprocess
from pathlib import Path

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def linux(path):
    return "/mnt/d/aaa/GameCam-VO/" + Path(path).relative_to(PROJECT).as_posix()


def main():
    setup = json.loads((PROJECT / "reports/SOTA/conda_setup.json").read_text())
    built = json.loads((PROJECT / "reports/SOTA/droid_scatter_wheel_build.json").read_text())
    if built["status"] != "WHEELS_BUILT_PENDING_INSTALL":
        raise RuntimeError("Source-built torch-scatter wheel required")
    wheels = list(Path(built["wheel_directory"]).glob("torch_scatter-2.1.2-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Expected one exact source-built scatter wheel")
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "droid_native_probe")
    env, conda = setup["droid_w_environment"], setup["conda_prefix"]
    commands = [
        ("install_local_scatter", f"python -m pip install --no-index --no-deps --force-reinstall {shlex.quote(linux(wheels[0]))}"),
        ("numerical_cuda_probe", "python " + shlex.quote(linux(PROJECT / "scripts/probe_droid_w_extensions.py"))),
        ("pip_check", "python -m pip check"),
        ("pip_freeze", "python -m pip freeze"),
    ]
    results = []
    for name, command in commands:
        script = out / (name + ".sh")
        script.write_bytes(("#!/bin/bash\nset -eo pipefail\nsource " + shlex.quote(conda + "/etc/profile.d/conda.sh") + "\nconda activate " + shlex.quote(env) + "\nexport MPLBACKEND=Agg QT_QPA_PLATFORM=offscreen OMP_NUM_THREADS=4\n" + command + "\n").encode())
        with (out / (name + ".log")).open("w", encoding="utf-8") as log:
            p = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "/bin/bash", linux(script)], stdout=log, stderr=subprocess.STDOUT, timeout=240)
        results.append({"stage": name, "exit_code": p.returncode, "script": str(script)})
        write_json(out / "execution.json", results)
        print(name, p.returncode, flush=True)
        if p.returncode:
            break
    passed = len(results) == len(commands) and not any(r["exit_code"] for r in results)
    numeric = {}
    path = out / "numerical_cuda_probe.log"
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            if line.startswith('{"status":'):
                numeric = json.loads(line)
    passed = passed and numeric.get("status") == "NATIVE_CUDA_CHECKS_PASSED"
    status = {**numeric, "status": "NATIVE_CUDA_CHECKS_PASSED" if passed else "NATIVE_CUDA_CHECKS_FAILED",
              "directory": str(out), "results": results, "local_scatter_wheel": str(wheels[0]), "local_scatter_wheel_sha256": sha256(wheels[0]),
              "model_inference_executed": False}
    write_json(PROJECT / "reports/SOTA/droid_native_probe.json", status)
    print(json.dumps(status))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())

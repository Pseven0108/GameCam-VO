"""Run Python in the existing gamecam-vo environment, with D: model caches.

Example: python scripts/run_gamecam_local.py --device gpu -- -c "import torch; print(torch.cuda.is_available())"
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "gpu"), default="gpu")
    parser.add_argument("python_args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    args = options.python_args
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        parser.error("Pass Python arguments after --; this wrapper does not start an experiment by itself")
    project = Path(__file__).resolve().parents[1]
    prefix = Path(r"D:\aaa\envs\gamecam-vo")
    executable = prefix / "python.exe"
    if not executable.is_file():
        raise FileNotFoundError("Reviewed Conda interpreter unavailable: " + str(executable))
    environment = os.environ.copy()
    environment["CONDA_PREFIX"] = str(prefix)
    environment["CONDA_DEFAULT_ENV"] = "gamecam-vo"
    environment["PATH"] = os.pathsep.join(str(prefix / path) for path in
                                         ("", "Library/bin", "Scripts", "DLLs")) + os.pathsep + environment.get("PATH", "")
    environment["OPENCV_IO_ENABLE_OPENEXR"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    temporary = Path(r"D:\aaa\tmp\gamecam-vo")
    temporary.mkdir(parents=True, exist_ok=True)
    environment["TEMP"] = environment["TMP"] = str(temporary)
    environment["PIP_CACHE_DIR"] = r"D:\aaa\caches\pip"
    environment["CONDA_PKGS_DIRS"] = r"D:\aaa\caches\conda_pkgs"
    environment["TORCHINDUCTOR_CACHE_DIR"] = r"D:\aaa\caches\torchinductor"
    cache = project / "maintenance/local_model_cache"
    environment["TORCH_HOME"] = str(cache / "torch")
    environment["HF_HOME"] = str(cache / "huggingface")
    environment["HUGGINGFACE_HUB_CACHE"] = str(cache / "huggingface/hub")
    if options.device == "cpu":
        # On this Windows build an empty mask reports inconsistent availability
        # (is_available=True while device_count=0). -1 was checked explicitly.
        environment["CUDA_VISIBLE_DEVICES"] = "-1"
    else:
        # Select the one reviewed local device in this child process only.
        environment["CUDA_VISIBLE_DEVICES"] = "0"
    return subprocess.call([str(executable), *args], cwd=project, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())

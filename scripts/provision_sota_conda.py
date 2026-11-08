"""Provision only the first isolated Linux Conda environment, with pinned installer."""
from __future__ import annotations
import _bootstrap
import hashlib
import argparse
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen
from gamecam_vo.common import PROJECT, make_run_dir, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-installer", type=Path)
    args = parser.parse_args()
    version = "26.9.4-1"
    filename = f"Miniforge3-{version}-Linux-x86_64.sh"
    url = f"https://github.com/conda-forge/miniforge/releases/download/{version}/{filename}"
    parent = PROJECT / "data/sota_toolchains" / ("miniforge-" + version)
    if args.resume_installer:
        installer_path = args.resume_installer.resolve()
        if not installer_path.is_relative_to(parent.resolve()) or installer_path.name != filename:
            raise ValueError("Resume target must be this project's pinned installer")
        folder = installer_path.parent
    else:
        folder = make_run_dir(parent, "linux_transport")
    log = make_run_dir(PROJECT / "logs/SOTA_setup", "conda_linux_droid_w")
    with urlopen(Request(url + ".sha256", headers={"User-Agent": "GameCam-VO"}), timeout=30) as response:
        checksum_text = response.read(4096).decode()
    checksum = checksum_text.split()[0]
    if len(checksum) != 64:
        raise ValueError("Invalid official SHA256 metadata")
    installer = folder / filename
    digest = hashlib.sha256()
    if installer.is_file():
        with installer.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    if digest.hexdigest() != checksum:
        installer_wsl = "/mnt/d/" + installer.as_posix()[3:]
        with (log / "download.log").open("w", encoding="utf-8") as stream:
            download = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "curl", "-fLsS", "--max-time", "240",
                "--continue-at", "-", "--max-filesize", str(128 * 1024 * 1024), url, "-o", installer_wsl], stdout=stream, stderr=subprocess.STDOUT, timeout=260)
        if download.returncode:
            raise RuntimeError(f"Installer transport exit {download.returncode}; partial file retained in {folder}")
        digest = hashlib.sha256()
        with installer.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    if digest.hexdigest() != checksum:
        raise ValueError("Official installer SHA256 mismatch; retain failed file and stop")
    prefix = "/home/lsuser/.local/share/gamecam-vo/miniforge3"
    env = "/home/lsuser/.local/share/gamecam-vo/envs/droid-w"
    installer_wsl = "/mnt/d/" + installer.as_posix()[3:]
    script = f'''#!/usr/bin/env bash
set -euo pipefail
test "$(id -un)" = lsuser
mkdir -p /home/lsuser/.local/share/gamecam-vo
if [ ! -x {prefix}/bin/conda ]; then
  test ! -e {prefix}
  bash {installer_wsl} -b -p {prefix}
fi
{prefix}/bin/conda --version
if [ ! -x {env}/bin/python ]; then
  {prefix}/bin/conda create -y --prefix {env} --override-channels -c conda-forge python=3.10 pip 'setuptools<80'
fi
{env}/bin/python --version
{prefix}/bin/conda list --prefix {env} --explicit
'''
    (log / "provision.sh").write_bytes(script.encode("utf-8"))
    with (log / "provision.log").open("w", encoding="utf-8") as stream:
        process = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "/bin/bash", "--noprofile", "--norc",
                                  "/mnt/d/" + (log / "provision.sh").as_posix()[3:]], stdout=stream, stderr=subprocess.STDOUT, timeout=900)
    result = {"installer_url": url, "installer_sha256": checksum, "installer_bytes": installer.stat().st_size,
              "conda_prefix": prefix, "droid_w_environment": env, "exit_code": process.returncode,
              "other_environments_created": False, "original_gamecam_vo_untouched": True, "log_directory": str(log)}
    write_json(log / "provision_result.json", result)
    write_json(PROJECT / "reports/SOTA/conda_setup.json", result)
    print(json.dumps(result))
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())

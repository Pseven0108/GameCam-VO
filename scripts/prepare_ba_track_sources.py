"""Acquire only the README's Eigen headers and record the extra DINO source."""
from __future__ import annotations

import _bootstrap
import json
import re
import subprocess
import zipfile
from pathlib import Path

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def main():
    upstream = PROJECT / "baselines/ba_track/upstream"
    dino = PROJECT / "baselines/ba_track/prior_sources/dino"
    dino_pin = subprocess.check_output(["git", "-C", str(dino), "rev-parse", "HEAD"], text=True).strip()
    if dino_pin != "7c446df5b9f45747937fb0d72314eb9f7b66930a":
        raise ValueError("Extra DINO source pin changed")
    out = make_run_dir(PROJECT / "logs/SOTA_setup", "ba_track_eigen_sources")
    assets = PROJECT / "data/sota_assets/BA_TRACK/source_archives"
    assets.mkdir(parents=True, exist_ok=True)
    archive_file = assets / "eigen-3.4.0.zip"
    command = ["wsl", "-d", "Ubuntu", "--exec", "/usr/bin/curl", "--fail", "--location", "--connect-timeout", "15", "--max-time", "90", "--max-filesize", "8388608",
               "https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.zip", "--output", "/mnt/d/aaa/GameCam-VO/data/sota_assets/BA_TRACK/source_archives/eigen-3.4.0.zip.part"]
    write_json(out / "reviewed_command.json", command)
    if not archive_file.exists():
        with (out / "download.log").open("w", encoding="utf-8") as stream:
            process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=110)
        if process.returncode:
            record = {"status": "BA_TRACK_EIGEN_TRANSPORT_FAILED", "exit_code": process.returncode, "directory": str(out), "model_weights_downloaded": False}
            write_json(out / "status.json", record)
            write_json(PROJECT / "reports/SOTA/ba_track_source_prerequisites.json", record)
            print(json.dumps(record))
            return 1
        partial = archive_file.with_suffix(".zip.part")
        with zipfile.ZipFile(partial) as archive:
            if archive.testzip() is not None:
                raise ValueError("Eigen source archive CRC failed")
        partial.rename(archive_file)
    destination = upstream / "thirdparty"
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive_file) as archive:
        if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
            raise ValueError("Source archive expansion cap exceeded")
        for item in archive.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination.resolve()) or not item.filename.startswith("eigen-3.4.0/"):
                raise ValueError("Unsafe or unexpected Eigen archive member")
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unexpected source archive symlink")
        archive.extractall(destination)
    macros = destination / "eigen-3.4.0/Eigen/src/Core/util/Macros.h"
    text = macros.read_text()
    version = [int(re.search(r"#define EIGEN_" + field + r"_VERSION\s+(\d+)", text).group(1)) for field in ("WORLD", "MAJOR", "MINOR")]
    if version != [3, 4, 0]:
        raise ValueError("Expected exactly Eigen3.4.0 headers")
    record = {"status": "BA_TRACK_SOURCE_PREREQUISITES_READY", "directory": str(out), "eigen_version": "3.4.0",
              "eigen_archive": str(archive_file), "eigen_archive_bytes": archive_file.stat().st_size, "eigen_archive_sha256": sha256(archive_file),
              "eigen_verification": "Official README archive URL, full ZIP CRC, version macros and local SHA256; no publisher checksum available",
              "eigen_macros_sha256": sha256(macros), "dino_source_commit": dino_pin,
              "dino_source_url": "https://github.com/facebookresearch/dino", "dino_hubconf_sha256": sha256(dino / "hubconf.py"),
              "dino_license_file": str(dino / "LICENSE"), "model_weights_downloaded": False,
              "transport_note": "Windows DINO clone made no progress and was stopped; WSL git fetch succeeded, and checkout was detached at the recorded commit. Its stale shallow lock was retained under a suffixed filename."}
    write_json(out / "status.json", record)
    write_json(PROJECT / "reports/SOTA/ba_track_source_prerequisites.json", record)
    print(json.dumps(record))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

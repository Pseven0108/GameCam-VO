"""Acquire only the pinned, author-selected umbrella Demo; preserve its ZIP."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REV = "158c7407c513fcf7140d14c2ce6271bc5e0450ec"
EXPECTED = "844607c15550090d1773ebb13d0c774257bb9937d3f8e900348e34ab84e857fe"
SIZE = 839158138


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy")
    parser.add_argument("--reuse-extracted", type=Path, help="Reuse the already extracted same pinned archive after a directory-selection repair")
    args = parser.parse_args()
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = ROOT / "logs/SOTA_setup" / (stamp+"_pi3mos_official_demo_data")
    out.mkdir(exist_ok=False)
    cache = ROOT / "data/sota_assets/PI3MOS/demo"
    cache.mkdir(exist_ok=True)
    archive = cache / "umbrella_844607c15550.zip"
    partial = archive.with_suffix(".zip.part")
    url = f"https://huggingface.co/datasets/gradient-spaces/Wild-SLAM/resolve/{REV}/Mocap/scene1/umbrella.zip"
    command = ["curl.exe" if os.name == "nt" else "curl", "--fail", "--location", "--connect-timeout", "30", "--max-time", "3600",
               "--continue-at", "-", "--max-filesize", str(SIZE), url, "--output", str(partial), "--dump-header", str(out / "download.headers")]
    if args.proxy:
        command[1:1] = ["--proxy", args.proxy]
    print(json.dumps({"stage": "ACQUIRING_SELECTED_UMBRELLA_ONLY", "directory": str(out), "partial": str(partial), "expected_bytes": SIZE}), flush=True)
    (out / "command.json").write_text(json.dumps(command, indent=2), encoding="utf-8")
    if not archive.exists():
        with (out / "download.log").open("w") as log:
            code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0).returncode
        if code or not partial.exists() or partial.stat().st_size != SIZE:
            raise RuntimeError(f"Selected Demo download incomplete: curl exit{code}; original partial retained")
        if digest(partial) != EXPECTED:
            raise ValueError("Official Demo SHA mismatch; original partial retained")
        partial.rename(archive)
    if archive.stat().st_size != SIZE or digest(archive) != EXPECTED:
        raise ValueError("Existing Demo archive differs from the pinned official LFS object")
    extracted = args.reuse_extracted.resolve() if args.reuse_extracted else cache / (stamp+"_official_umbrella")
    if not extracted.resolve().is_relative_to(cache.resolve()):
        raise ValueError("Reuse must stay inside the owned Demo cache")
    if not args.reuse_extracted:
        extracted.mkdir(exist_ok=False)
        with zipfile.ZipFile(archive) as source:
            for item in source.infolist():
                path = (extracted / item.filename).resolve()
                if not path.is_relative_to(extracted.resolve()) or stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError("Unsafe archive path/link")
            source.extractall(extracted)
    # The bundle also contains umbrella/nvs/rgb. The README explicitly selects
    # scene1/umbrella/rgb for tracking, so do not mix the novel-view frames in.
    rgb = extracted / "umbrella/rgb"
    if not rgb.is_dir():
        raise ValueError("The documented umbrella/rgb tracking input is absent")
    images = sorted(p for p in rgb.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if len(images) < 12:
        raise ValueError("Insufficient official Demo RGB frames")
    manifest = [{"frame_index": i, "path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)} for i, path in enumerate(images)]
    if args.reuse_extracted:
        with zipfile.ZipFile(archive) as source:
            for row, path in zip(manifest, images, strict=True):
                if hashlib.sha256(source.read(path.relative_to(extracted).as_posix())).hexdigest() != row["sha256"]:
                    raise ValueError("Reused RGB differs from the pinned official archive")
    (extracted / "RGB_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    record = {"status": "PI3MOS_OFFICIAL_UMBRELLA_DATA_VERIFIED", "directory": str(extracted), "rgb_directory": str(rgb),
              "expected_frames": len(images), "RGB_manifest": str(extracted / "RGB_manifest.json"), "archive": str(archive),
              "archive_bytes": SIZE, "archive_sha256": EXPECTED, "source": url, "dataset_revision": REV,
              "publisher_LFS_digest_verified": True, "all_sequences_downloader_executed": False,
              "archive_preserved": True, "engine_depth_or_pose_to_model": False, "system_proxy_modified": False}
    record["novel_view_RGB_not_used"] = True
    record["reused_extracted_RGB_checked_against_archive"] = bool(args.reuse_extracted)
    (out / "status.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    (ROOT / "reports/SOTA/pi3mos_official_demo_data.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in ("status", "rgb_directory", "expected_frames", "archive_sha256")}))


if __name__ == "__main__":
    main()

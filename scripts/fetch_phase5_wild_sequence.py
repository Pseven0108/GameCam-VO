"""Acquire one pinned Wild-SLAM tracking sequence; retain ZIP and native clocks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REV = "158c7407c513fcf7140d14c2ce6271bc5e0450ec"
ASSETS = {
    "person_tracking": (1529324937, "b732c87a4e31cfe9dd184ed06fd17dd585e2cd1fbe3d77f72316afc44ffd8238", 986),
    "crowd": (2258415869, "5f07391691c9576d3705ac17f7374dc9ff9bcf2051ad0b27e793815ddb61eb3d", 1268),
    "racket": (1739826137, "c979ec2e238dfe7719a2316eefe4eedd8ea78a60746f8cef3cc2f3a7af6caba5", 962),
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sequence", choices=ASSETS)
    parser.add_argument("--proxy", default="http://127.0.0.1:7897")
    parser.add_argument("--reuse-extracted", type=Path)
    args = parser.parse_args()
    reports = ROOT / "reports/PHASE5"
    if args.sequence != "person_tracking":
        person = json.loads((reports / "wild_person_tracking_data.json").read_text(encoding="utf-8"))
        if person["status"] not in ("VERIFIED_PUBLISHED_RGB_SYNCHRONIZED_MOCAP", "VERIFIED_PUBLISHED_MOCAP_PACKAGE_WITH_TIMESTAMP_TIES"):
            raise RuntimeError("Validate Person and its actual clocks before acquiring the next sequence")
    size, expected_sha, expected_frames = ASSETS[args.sequence]
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    log = ROOT / "logs/PHASE5" / (stamp + "_wild_" + args.sequence)
    log.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, log / "fetch_phase5_wild_sequence.executed_source.py")
    cache = ROOT / "data/phase5/Wild_SLAM_Mocap"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (args.sequence + "_" + expected_sha[:12] + ".zip")
    partial = archive.with_suffix(".zip.part")
    destination = args.reuse_extracted.resolve() if args.reuse_extracted else cache / (stamp + "_" + args.sequence)
    if not destination.resolve().is_relative_to(cache.resolve()):
        raise ValueError("Only an owned extracted package can be reused")
    url = f"https://huggingface.co/datasets/gradient-spaces/Wild-SLAM/resolve/{REV}/Mocap/scene1/{args.sequence}.zip"
    command = ["curl.exe" if os.name == "nt" else "curl", "--proxy", args.proxy, "--fail", "--location", "--connect-timeout", "30", "--max-time", "7200", "--continue-at", "-", "--max-filesize", str(size), url, "--output", str(partial), "--dump-header", str(log / "download.headers")]
    (log / "command.json").write_text(json.dumps(command, indent=2))
    print(json.dumps({"stage": "ACQUIRING_ONE_SELECTED_SEQUENCE", "sequence": args.sequence, "expected_bytes": size, "directory": str(log)}), flush=True)
    if not archive.exists():
        if shutil.disk_usage(cache).free < size * 4:
            raise RuntimeError("Insufficient workspace free space for archive and native extraction")
        with (log / "download.log").open("w") as stream:
            code = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0).returncode
        if code or not partial.is_file() or partial.stat().st_size != size:
            raise RuntimeError(f"Download incomplete, curl exit{code}; partial and logs preserved")
        if digest(partial) != expected_sha:
            raise ValueError("Official pinned LFS digest mismatch; preserve the original download")
        partial.rename(archive)
    if archive.stat().st_size != size or digest(archive) != expected_sha:
        raise ValueError("Existing official archive changed")
    if not args.reuse_extracted:
        destination.mkdir(exist_ok=False)
    with zipfile.ZipFile(archive) as source:
        for item in source.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination.resolve()) or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Unsafe ZIP path or link")
        if not args.reuse_extracted:
            source.extractall(destination)
    scene = destination / args.sequence
    image_rows = np.loadtxt(scene / "rgb.txt", dtype=str, ndmin=2, skiprows=3)
    depth_rows = np.loadtxt(scene / "depth.txt", dtype=str, ndmin=2, skiprows=3)
    gt = np.loadtxt(scene / "groundtruth.txt", ndmin=2)
    times = image_rows[:, 0].astype(float)
    if len(times) != expected_frames or not np.isfinite(times).all() or (np.diff(times) < 0).any():
        raise ValueError("Unexpected tracking RGB count or nonmonotonic native camera clock")
    manifest = []
    for i, row in enumerate(image_rows):
        path = (scene / row[1]).resolve()
        if not path.is_relative_to((scene / "rgb").resolve()) or not path.is_file():
            raise ValueError("Missing or misplaced tracking RGB; novel-view RGB must not be mixed in")
        manifest.append({"frame_index": i, "timestamp_seconds": float(row[0]), "path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)})
    if args.reuse_extracted:
        with zipfile.ZipFile(archive) as source:
            for row in manifest:
                file = Path(row["path"])
                if hashlib.sha256(source.read(file.relative_to(destination).as_posix())).hexdigest() != row["sha256"]:
                    raise ValueError("Reused RGB differs from the immutable original ZIP")
    if gt.shape[1] != 8 or not np.isfinite(gt).all() or (np.diff(gt[:, 0]) < 0).any():
        raise ValueError("Invalid native MoCap trajectory")
    if any(not (scene / row[1]).is_file() for row in depth_rows):
        raise ValueError("Missing native depth file")
    synchronized = len(gt) == len(times) and np.array_equal(times, gt[:, 0])
    ties = np.flatnonzero(np.diff(times) == 0)
    tie_records = [{"input_indices": [int(i), int(i+1)], "timestamp_seconds": float(times[i]),
                    "RGB_SHA_equal": manifest[i]["sha256"] == manifest[i+1]["sha256"],
                    "published_GT_poses_identical": bool(np.array_equal(gt[i, 1:], gt[i+1, 1:]))} for i in ties]
    (destination / "RGB_manifest.json").write_text(json.dumps(manifest, indent=2))
    record = {"status": ("VERIFIED_PUBLISHED_MOCAP_PACKAGE_WITH_TIMESTAMP_TIES" if len(ties) else "VERIFIED_PUBLISHED_RGB_SYNCHRONIZED_MOCAP") if synchronized else "ACQUIRED_REQUIRES_OFFICIAL_SYNC_REVIEW", "sequence": args.sequence,
        "directory": str(scene), "archive": str(archive), "archive_bytes": size, "archive_sha256": expected_sha,
        "dataset_revision": REV, "source": url, "log_directory": str(log), "frames": len(times), "depth_frames": len(depth_rows), "GT_rows": len(gt),
        "GT_provenance": "MOCAP_GROUND_TRUTH", "RGB_manifest": str(destination / "RGB_manifest.json"),
        "published_GT_timestamps_exactly_equal_RGB": synchronized, "native_RGB_dt_median_seconds": float(np.median(np.diff(times))),
        "timestamp_tie_diagnostic": tie_records, "all_input_frames_retained": True,
        "timestamp_tie_policy": "Published clock ties are preserved. External evaluation must freeze the official nearest-time first-argmin association and disclose ambiguity; do not select the tied GT pose by prediction error or fabricate a new timestamp.",
        "native_GT_dt_median_seconds": float(np.median(np.diff(gt[:, 0]))), "native_GT_quaternion_max_norm_error": float(np.max(np.abs(np.linalg.norm(gt[:, 4:], axis=1)-1))),
        "clock_policy": "Retain published physical timestamps. If GT is already on identical RGB timestamps, do not invent or apply a second120Hz-to30Hz offset/interpolation. Acquisition-time interpolation/offset source details require separate evidence; frame order is not a synchronization substitute.",
        "intrinsics_file": str(scene / "intrinsics.json"), "inference_inputs": ["RGB", "camera_intrinsics"], "depth_and_GT_to_model": False,
        "novel_view_RGB_excluded": True, "pixel_motion_or_skeleton_GT_claim": False, "archive_preserved": True}
    (log / "status.json").write_text(json.dumps(record, indent=2)+"\n")
    (reports / ("wild_"+args.sequence+"_data.json")).write_text(json.dumps(record, indent=2)+"\n")
    print(json.dumps({k: record[k] for k in ("status", "sequence", "frames", "GT_rows", "published_GT_timestamps_exactly_equal_RGB")}))


if __name__ == "__main__":
    main()

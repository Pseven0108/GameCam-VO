"""Acquire exactly one official Bonn ZIP after the actual E15 stage report."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SEQUENCES = ("person_tracking", "crowd", "moving_obstructing_box")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sequence", choices=SEQUENCES)
    parser.add_argument("--proxy", default="http://127.0.0.1:7897")
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("Use the existing Windows CPU/download environment")
    reports = ROOT / "reports/PHASE5"
    gate_file = reports / "E15_STAGE_DELIVERY.json"
    gate = json.loads(gate_file.read_text(encoding="utf-8"))
    if gate["status"] != "E15_REVIEWED_STAGE_REPORT_WRITTEN" or sha(Path(gate["report"])) != gate["report_sha256"]:
        raise ValueError("Requested E15 stage must be reported before Bonn acquisition")
    pointer = reports / ("bonn_"+args.sequence+"_data.json")
    if pointer.exists():
        raise FileExistsError("Existing acquired sequence must be audited rather than redownloaded")
    position = SEQUENCES.index(args.sequence)
    if position and not (reports / ("bonn_"+SEQUENCES[position-1]+"_input.json")).exists():
        raise ValueError("Acquire and validate one selected sequence before the next")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT / "data/phase5/Bonn" / (stamp+"_"+args.sequence)
    folder.mkdir(parents=True, exist_ok=False)
    log = ROOT / "logs/PHASE5" / (stamp+"_bonn_"+args.sequence)
    log.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, log / "fetch_phase5_bonn.executed_source.py")
    if shutil.disk_usage(folder).free < 5*1024**3:
        raise RuntimeError("Less than 5GiB workspace headroom; preserve all old data")
    basename = "rgbd_bonn_"+args.sequence+".zip"
    commands = []
    successful_url, archive = None, None
    # Transport fallback uses the exact official static-file host/path. Keep
    # both attempt logs; no mirror, archive substitution, or silent deletion.
    for scheme in ("https", "http"):
        url = scheme+"://www.ipb.uni-bonn.de/html/projects/rgbd_dynamic2019/"+basename
        partial = folder / (basename+"."+scheme+".part")
        headers = log / (scheme+"_archive_HTTP.txt")
        command = ["curl.exe", "--proxy", args.proxy, "--location", "--fail", "--show-error", "--connect-timeout", "30", "--max-time", "3600",
            "--max-filesize", str(700*1024**2), "--dump-header", str(headers), "--output", str(partial), url]
        commands.append(command); write(log / "commands.json", commands)
        with (log / (scheme+"_download.log")).open("w") as stream:
            code = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW).returncode
        write(log / (scheme+"_transport_status.json"), {"URL": url, "curl_exit_code": code, "received_bytes": partial.stat().st_size if partial.exists() else 0})
        if code == 0:
            text = headers.read_text(encoding="utf-8", errors="replace")
            sizes = re.findall(r"(?im)^content-length:\s*(\d+)\s*$", text)
            if sizes and partial.stat().st_size != int(sizes[-1]):
                raise ValueError("Official response Content-Length differs from complete body")
            if not zipfile.is_zipfile(partial):
                raise ValueError("Official response was not a ZIP archive; preserve it")
            archive = folder / basename
            partial.rename(archive)
            successful_url = url
            break
        if partial.exists() and partial.stat().st_size:
            raise RuntimeError("A partial body exists; preserve it and audit transport before resuming")
    if archive is None:
        raise RuntimeError("Both official transport attempts failed; logs retained")
    destination = folder / "native"
    destination.mkdir()
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination.resolve()) or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Unsafe archive path/link")
        if z.testzip() is not None:
            raise ValueError("ZIP member CRC failed")
        if shutil.disk_usage(destination).free < sum(item.file_size for item in z.infolist())+2*1024**3:
            raise RuntimeError("Insufficient extraction headroom; archive retained")
        z.extractall(destination)
    candidates = list(destination.rglob("rgb.txt"))
    if len(candidates) != 1:
        raise ValueError("Expected exactly one complete native sequence, not an all-sequences package")
    scene = candidates[0].parent
    rgb, depth = [np.loadtxt(scene / (name+".txt"), dtype=str, ndmin=2) for name in ("rgb", "depth")]
    gt = np.loadtxt(scene / "groundtruth.txt", ndmin=2)
    if rgb.shape[1] != 2 or depth.shape[1] != 2 or gt.shape[1] != 8 or not len(rgb):
        raise ValueError("Official TUM-format package schema differs")
    manifest, depth_manifest = [], []
    for rows, kind, target in ((rgb, "rgb", manifest), (depth, "depth", depth_manifest)):
        times = rows[:, 0].astype(float)
        if not np.isfinite(times).all() or (np.diff(times) < 0).any():
            raise ValueError("Native camera clock is nonfinite/nonmonotonic")
        for index, row in enumerate(rows):
            image = (scene / row[1]).resolve()
            if not image.is_relative_to((scene / kind).resolve()) or not image.is_file():
                raise ValueError("Missing/unsafe native "+kind+" frame")
            target.append({"frame_index": index, "timestamp_seconds": float(row[0]), "path": str(image), "bytes": image.stat().st_size, "sha256": sha(image)})
    if not np.isfinite(gt).all() or (np.diff(gt[:, 0]) < 0).any():
        raise ValueError("Invalid native MoCap clock/poses")
    write(folder / "RGB_manifest.json", manifest); write(folder / "Depth_manifest.json", depth_manifest)
    record = {"status": "BONN_ONE_OFFICIAL_ZIP_CRC_AND_LOCAL_SHA_VERIFIED", "sequence": args.sequence, "directory": str(scene),
        "archive": str(archive), "archive_bytes": archive.stat().st_size, "archive_sha256": sha(archive), "publisher_full_SHA_available": False,
        "integrity_scope": "ZIP member CRC, complete response length when supplied, local full SHA256; no independent publisher SHA claim",
        "source": successful_url, "HTTP_transport_used": successful_url.startswith("http:"), "log_directory": str(log),
        "RGB_manifest": str(folder / "RGB_manifest.json"), "Depth_manifest": str(folder / "Depth_manifest.json"),
        "frames": len(rgb), "depth_frames": len(depth), "GT_rows": len(gt), "groundtruth_txt_sha256": sha(scene / "groundtruth.txt"),
        "RGB_txt_sha256": sha(scene / "rgb.txt"), "depth_txt_sha256": sha(scene / "depth.txt"),
        "GT_provenance": "MOCAP_GROUND_TRUTH", "all_RGB_retained": True, "depth_or_GT_in_model": False,
        "native_RGB_dt_median_seconds": float(np.median(np.diff(rgb[:, 0].astype(float)))), "native_GT_dt_median_seconds": float(np.median(np.diff(gt[:, 0]))),
        "archive_preserved": True, "prior_stage_gate_sha256": sha(gate_file)}
    write(log / "acquisition.json", record); write(pointer, record)
    print(json.dumps({key: record[key] for key in ("status", "sequence", "frames", "depth_frames", "GT_rows", "archive_bytes")}))


if __name__ == "__main__":
    main()

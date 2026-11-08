"""Resume one official public checkpoint with checked HTTP byte ranges.

The original partial file and every failed request are retained. This changes
only network transport, not the selected checkpoint or scientific protocol.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from threading import Event


ROOT = Path(__file__).resolve().parents[1]
TOTAL = 4100235800
URL = "https://drive.usercontent.google.com/download?id=145bC76pMHikhdTGkqDK0t9Ta0R7tw51v&export=download&confirm=t"


def local_path(value):
    text = str(value).replace("\\", "/")
    if os.name == "nt" and text.startswith("/mnt/d/"):
        text = "D:/" + text[len("/mnt/d/"):]
    elif os.name != "nt" and text.startswith("D:/"):
        text = "/mnt/d/" + text[len("D:/"):]
    return Path(text)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-record", type=Path)
    parser.add_argument("--workers", type=int, choices=[1, 2, 4, 8], default=2)
    parser.add_argument("--proxy", help="Existing proxy for this download process only; no system settings changed")
    args = parser.parse_args()
    native = json.loads((ROOT / "reports/SOTA/pi3mos_native_probe.json").read_text())
    if native["status"] != "PI3MOS_NATIVE_CUDA_CHECKS_PASSED":
        raise RuntimeError("Native proof must precede selected-model acquisition")
    folder = ROOT / "data/sota_assets/PI3MOS/weights"
    seed = folder / "model.safetensors.part"
    seed_bytes, seed_hash = seed.stat().st_size, digest(seed)
    if not 16 < seed_bytes < TOTAL:
        raise ValueError("A stopped, nonempty prefix download is required")
    out = ROOT / "logs/SOTA_setup" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_pi3mos_weight_ranges")
    out.mkdir(exist_ok=False)
    chunks = folder / out.name
    chunks.mkdir(exist_ok=False)
    plan = []
    for i in range(8):
        start = seed_bytes + (TOTAL - seed_bytes) * i // 8
        end = seed_bytes + (TOTAL - seed_bytes) * (i + 1) // 8 - 1
        plan.append({"index": i, "start": start, "end": end, "expected_bytes": end-start+1})
    reuse = {}
    if args.resume_record:
        old = json.loads(args.resume_record.read_text())
        original_plan = json.loads((local_path(old["directory"]) / "transport_plan.json").read_text())
        if original_plan["seed_bytes"] != seed_bytes or original_plan["seed_sha256"] != seed_hash or original_plan["source"] != URL:
            raise ValueError("Original transport seed or source changed")
        for segment in old["segments"]:
            if segment["complete"]:
                path = local_path(segment["path"])
                if path.stat().st_size != segment["expected_bytes"] or digest(path) != segment["sha256"]:
                    raise ValueError("Previously verified range changed")
                reuse[segment["index"]] = segment
    (out / "transport_plan.json").write_text(json.dumps({"source": URL, "total": TOTAL, "seed_path": str(seed), "seed_bytes": seed_bytes,
        "seed_sha256": seed_hash, "segments": plan, "concurrent_requests": args.workers, "reused_verified_segments": sorted(reuse),
        "per_process_proxy": args.proxy, "system_proxy_modified": False, "protocol_change": False}, indent=2))
    shutil.copy2(__file__, out / "fetch_pi3mos_weight_ranges.executed.py")
    quota_stop = Event()
    print(json.dumps({"directory": str(out), "chunks": str(chunks), "reused_complete_segments": sorted(reuse), "workers": args.workers}), flush=True)

    def fetch(segment):
        if segment["index"] in reuse:
            return {**reuse[segment["index"]], "reused_verified_complete_segment": True}
        path = chunks / f"segment_{segment['index']:02d}.part"
        path.touch(exist_ok=False)
        records = []
        for attempt in range(3):
            if quota_stop.is_set():
                break
            start = segment["start"] + path.stat().st_size
            if start > segment["end"]:
                break
            name = f"segment_{segment['index']:02d}_attempt_{attempt:02d}"
            fragment = chunks / (name + ".body")
            header = out / (name + ".headers")
            command = ["curl.exe" if os.name == "nt" else "curl", "--fail", "--location", "--connect-timeout", "30", "--max-time", "3600", "--range", f"{start}-{segment['end']}",
                       "--max-filesize", str(segment["end"]-start+1), URL, "--output", str(fragment), "--dump-header", str(header)]
            if args.proxy:
                command[1:1] = ["--proxy", args.proxy]
            with (out / (name + ".log")).open("w") as log:
                code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0).returncode
            ranges = re.findall(r"(?im)^content-range:\s*bytes\s+(\d+)-(\d+)/(\d+)\s*$", header.read_text(encoding="utf-8", errors="replace") if header.exists() else "")
            correct_range = bool(ranges) and tuple(map(int, ranges[-1])) == (start, segment["end"], TOTAL)
            received = fragment.stat().st_size if fragment.exists() else 0
            quota = fragment.exists() and received < 8192 and any(text in fragment.read_bytes().lower() for text in (b"quota exceeded", b"too many users"))
            if quota:
                quota_stop.set()
            if correct_range and 0 < received <= segment["end"]-start+1:
                with fragment.open("rb") as source, path.open("ab") as target:
                    shutil.copyfileobj(source, target, length=8 * 1024 * 1024)
            records.append({"command": command, "exit_code": code, "correct_content_range": correct_range, "received_bytes": received,
                            "accepted_bytes": received if correct_range else 0, "quota_observed": quota})
            (out / (f"segment_{segment['index']:02d}_requests.json")).write_text(json.dumps(records, indent=2))
            if not correct_range and code == 0:
                break
        valid = path.stat().st_size == segment["expected_bytes"]
        result = {**segment, "path": str(path), "complete": valid, "actual_bytes": path.stat().st_size,
                  "sha256": digest(path) if valid else None, "partial_sha256": digest(path) if path.stat().st_size else None, "requests": records,
                  "skipped_after_public_quota": quota_stop.is_set() and not records}
        print(json.dumps({"segment": segment["index"], "complete": valid, "bytes": path.stat().st_size}), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        segments = list(pool.map(fetch, plan))
    complete = all(s["complete"] for s in segments)
    record = {"status": "RANGE_DOWNLOAD_INCOMPLETE", "directory": str(out), "segments": segments, "source": URL,
              "original_seed_retained": True, "upstream_model_changed": False, "publisher_digest": "UNKNOWN",
              "public_quota_observed": quota_stop.is_set(), "per_process_proxy": args.proxy, "system_proxy_modified": False}
    if complete:
        if seed.stat().st_size != seed_bytes or digest(seed) != seed_hash:
            raise ValueError("The stopped seed changed during concurrent acquisition")
        destination = folder / "model.safetensors"
        assembly = folder / "model.safetensors.assembled.part"
        if destination.exists() or assembly.exists():
            raise FileExistsError("Never overwrite an existing checkpoint or assembly")
        with assembly.open("wb") as output:
            for path in [seed, *[local_path(s["path"]) for s in segments]]:
                with path.open("rb") as source:
                    shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
        if assembly.stat().st_size != TOTAL:
            raise ValueError("Final checkpoint size mismatch")
        if os.name == "nt":
            linux_file = str(assembly).replace("\\", "/").replace("D:/", "/mnt/d/", 1)
            code = "from safetensors import safe_open; import json; model=safe_open(" + repr(linux_file) + ", framework='pt', device='cpu'); print(json.dumps({'tensor_count':len(list(model.keys()))}))"
            validation = subprocess.check_output(["wsl.exe", "-d", "Ubuntu", "--exec", "/home/lsuser/.local/share/gamecam-vo/envs/pi3mos/bin/python", "-c", code],
                                                 text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            (out / "safetensors_validation.json").write_text(validation, encoding="utf-8")
            count = json.loads(validation)["tensor_count"]
        else:
            from safetensors import safe_open
            with safe_open(assembly, framework="pt", device="cpu") as model:
                count = len(list(model.keys()))
        if not count:
            raise ValueError("The assembled safetensors header is empty")
        record.update(status="RANGE_DOWNLOAD_ASSEMBLY_VERIFIED", bytes=TOTAL, sha256=digest(assembly), tensor_count=count,
                      verification="All byte ranges and total size checked; exact original prefix preserved; full safetensors header and local SHA256 checked. No independent publisher digest is available.")
        assembly.rename(destination)
    (out / "status.json").write_text(json.dumps(record, indent=2))
    (ROOT / "reports/SOTA/pi3mos_weight_transport.json").write_text(json.dumps(record, indent=2))
    print(json.dumps({"status": record["status"], "directory": str(out)}), flush=True)
    return int(not complete)


if __name__ == "__main__":
    raise SystemExit(main())

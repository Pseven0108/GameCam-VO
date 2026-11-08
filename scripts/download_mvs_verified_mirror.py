"""Run only after explicit authorization to use the documented unpacked mirror."""
from __future__ import annotations
import _bootstrap
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import threading
import time
import urllib.request
from pathlib import Path

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def digest_matches(payload, record):
    if record.get("lfs", {}).get("oid"):
        return hashlib.sha256(payload).hexdigest() == record["lfs"]["oid"]
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest() == record["oid"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--accept-verified-mirror", action="store_true")
    args = parser.parse_args()
    if not args.accept_verified_mirror:
        parser.error("Explicit approval for this third-party mirror is required")
    source = PROJECT / "docs/sources/mvs_synth"
    comparison = json.loads((source / "mirror_official_crosscheck.json").read_text(encoding="utf-8-sig"))
    if not comparison["all_matched"] or comparison["retained_official_files"] < 13:
        raise ValueError("Official/mirror subset cross-check has not passed")
    tree = json.loads((source / "mirror_sequence_0000_tree.json").read_text(encoding="utf-8-sig"))
    files = [record for record in tree if record["type"] == "file"]
    if len(files) != 300 or sum(record["size"] for record in files) > 100 * 1024**2:
        raise ValueError("The approved one-sequence manifest changed")
    destination = (PROJECT / "data/mvs_synth").resolve()
    run = make_run_dir(PROJECT / "logs/acquisition_mvs", "verified_mirror_0000")
    lock = threading.Lock()
    network_bytes = 0
    records = []
    revision = comparison["mirror_revision"]
    plan = {"mirror": comparison["mirror"], "mirror_revision": revision, "official_partial_crosscheck_files": 13,
            "authorization": "User explicitly approved this verified third-party mirror in chat",
            "all_300_independently_compared_to_official_archive": False,
            "selected_files": len(files), "selected_bytes": sum(item["size"] for item in files),
            "network_budget_bytes": 128 * 1024**2, "status": "RUNNING", "files": records}
    write_json(run / "download_manifest.json", plan)

    def fetch(record):
        nonlocal network_bytes
        path = (destination / record["path"]).resolve()
        if not path.is_relative_to(destination):
            raise ValueError("Download target escaped the data directory")
        if path.exists():
            payload = path.read_bytes()
            if not digest_matches(payload, record):
                raise ValueError(f"Existing raw data mismatch: {path}")
            return {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "reused_official": True}
        url = f"https://huggingface.co/datasets/{comparison['mirror']}/resolve/{revision}/{record['path']}"
        last_error = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=30) as response:
                    chunks = []
                    size = 0
                    while True:
                        block = response.read(128 * 1024)
                        if not block:
                            break
                        with lock:
                            network_bytes += len(block)
                            if network_bytes > plan["network_budget_bytes"]:
                                raise ValueError("Mirror compressed-transfer budget exceeded")
                        size += len(block)
                        if size > record["size"]:
                            raise ValueError("Download exceeded declared file size")
                        chunks.append(block)
                payload = b"".join(chunks)
                if len(payload) != record["size"] or not digest_matches(payload, record):
                    raise ValueError("Downloaded file hash/size mismatch")
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as handle:
                    handle.write(payload)
                return {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "reused_official": False}
            except Exception as exc:
                last_error = exc
                if "budget" in str(exc).lower() or "size mismatch" in str(exc).lower():
                    break
                time.sleep(0.3 * (attempt + 1))
        raise last_error
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending = [pool.submit(fetch, record) for record in files]
            for future in as_completed(pending):
                records.append(future.result())
                if len(records) % 25 == 0:
                    print(f"Verified {len(records)}/300 files; received {network_bytes / 1024**2:.1f} MiB", flush=True)
                    plan["network_bytes_read"] = network_bytes
                    write_json(run / "download_manifest.json", plan)
        plan["status"] = "COMPLETE_SELECTED_SAMPLE"
    except Exception as exc:
        plan.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        plan["network_bytes_read"] = network_bytes
        write_json(run / "download_manifest.json", plan)
    print(json.dumps({"status": plan["status"], "files": len(records), "network_bytes": network_bytes,
                      "manifest": str(run / "download_manifest.json")}))


if __name__ == "__main__":
    main()

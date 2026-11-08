"""Fetch the selected official Pi3MOS weights only after native CUDA checks.

Google Drive transport failures remain acquisition failures, not missing releases
or model failures. No benchmark or all-sequence downloader is executed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time
import zipfile


ROOT = Path("/mnt/d/aaa/GameCam-VO")


def checksum(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    native = json.loads((ROOT / "reports/SOTA/pi3mos_native_probe.json").read_text())
    if native["status"] != "PI3MOS_NATIVE_CUDA_CHECKS_PASSED":
        raise RuntimeError("Native build and numerical CUDA proof must pass first")
    out = ROOT / "logs/SOTA_setup" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_pi3mos_assets")
    out.mkdir(exist_ok=False)
    assets = ROOT / "data/sota_assets/PI3MOS"
    (assets / "weights").mkdir(parents=True, exist_ok=True)
    items = [
        {"name": "dpvo.pth", "size": 14167743, "path": assets / "weights/dpvo.pth",
         "url": "https://drive.usercontent.google.com/download?id=1lyDijcDAsqMXBYgQkPnZ_1tKJfYfSXnU&export=download&confirm=t"},
        {"name": "model.safetensors", "size": 4100235800, "path": assets / "weights/model.safetensors",
         "url": "https://drive.usercontent.google.com/download?id=145bC76pMHikhdTGkqDK0t9Ta0R7tw51v&export=download&confirm=t"},
    ]
    records = []
    for item in items:
        destination = item["path"]
        row = {**item, "path": str(destination), "publisher_digest": "UNKNOWN"}
        partial = destination.with_suffix(destination.suffix + ".part")
        command = ["curl", "--fail", "--location", "--connect-timeout", "15", "--max-time", "3600",
                   "--continue-at", "-", "--max-filesize", str(item["size"]), item["url"], "--output", str(partial)]
        row["command"] = command
        if not destination.exists():
            with (out / (item["name"] + ".log")).open("w") as log:
                row["exit_code"] = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
            if row["exit_code"] or not partial.exists() or partial.stat().st_size != item["size"]:
                row["status"] = "OFFICIAL_WEIGHT_TRANSPORT_INCOMPLETE"
                row["partial_bytes"] = partial.stat().st_size if partial.exists() else 0
                records.append(row)
                (out / "assets.json").write_text(json.dumps(records, indent=2))
                continue
            partial.rename(destination)
        if destination.stat().st_size != item["size"]:
            raise ValueError("Existing official weight has the wrong size; retained for inspection")
        if destination.suffix == ".safetensors":
            from safetensors import safe_open
            with safe_open(destination, framework="pt", device="cpu") as model:
                keys = list(model.keys())
                if not keys:
                    raise ValueError("Empty safetensors checkpoint")
                row["tensor_count"] = len(keys)
        elif not zipfile.is_zipfile(destination):
            raise ValueError("Expected the observed official PyTorch ZIP serialization")
        row.update(status="FULL_OFFICIAL_FILE_ACQUIRED", actual_bytes=destination.stat().st_size,
                   sha256=checksum(destination), verification="Full observed size, serialization/header, official HTTPS source and local SHA256; no independent publisher digest available")
        records.append(row)
        (out / "assets.json").write_text(json.dumps(records, indent=2))
    complete = len(records) == 2 and all(row["status"] == "FULL_OFFICIAL_FILE_ACQUIRED" for row in records)
    record = {"status": "PI3MOS_CORE_WEIGHTS_ACQUIRED" if complete else "PI3MOS_WEIGHT_ACQUISITION_INCOMPLETE",
              "directory": str(out), "assets": records, "official_demo_ready": False,
              "official_demo_sequence": "Wild-SLAM Mocap scene1/umbrella; 839158138 byte ZIP observed, not downloaded",
              "model_inference_executed": False, "release_present": True,
              "upstream_release_blocked": False,
              "system_proxy_configuration_modified": False}
    (out / "status.json").write_text(json.dumps(record, indent=2))
    (ROOT / "reports/SOTA/pi3mos_assets.json").write_text(json.dumps(record, indent=2))
    print(json.dumps({"status": record["status"], "directory": str(out)}), flush=True)
    return int(not complete)


if __name__ == "__main__":
    raise SystemExit(main())

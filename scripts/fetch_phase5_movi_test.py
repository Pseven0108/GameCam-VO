"""Fetch four exact official test records after the reviewed E13/E14 gate."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from movi_tfrecord_io import payload, record_length

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, row):
    path.write_text(json.dumps(row, indent=2)+"\n", encoding="utf-8")


def curl(url, output, *, proxy, byte_range=None, headers=None, limit=None):
    if output.exists():
        raise FileExistsError("Preserve prior downloads; use a fresh acquisition directory")
    command = ["curl.exe", "--location", "--fail", "--show-error", "--silent", "--max-time", "300", "--proxy", proxy, "--header", "Accept-Encoding: identity"]
    if byte_range is not None:
        command += ["--range", byte_range, "--max-filesize", str(limit), "--dump-header", str(headers)]
    command += [url, "--output", str(output)]
    subprocess.check_call(command)
    if byte_range is not None:
        text = headers.read_text(encoding="utf-8", errors="replace")
        ranges = re.findall(r"(?im)^content-range:\s*bytes\s+(\d+)-(\d+)/(\d+)", text)
        start, end = map(int, byte_range.split("-"))
        if not ranges or tuple(map(int, ranges[-1][:2])) != (start, end) or output.stat().st_size != end-start+1:
            raise ValueError("Server did not return the exact requested range; do not accept a whole shard")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy", default="http://127.0.0.1:7897")
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("Use the existing Windows CPU Python/curl download path")
    gate_file = ROOT / "reports/PHASE5/E13_E14_STAGE_DELIVERY.json"
    if not gate_file.exists():
        raise RuntimeError("E13/E14 reviewed stage report must be delivered before MOVi sample download")
    gate = json.loads(gate_file.read_text(encoding="utf-8"))
    if gate["status"] != "E13_E14_REVIEWED_STAGE_REPORT_WRITTEN" or digest(Path(gate["report"])) != gate["report_sha256"]:
        raise ValueError("Reviewed stage report gate identity mismatch")
    pointer = ROOT / "reports/PHASE5/movi_test_acquisition.json"
    if pointer.exists():
        raise FileExistsError("Existing acquisition pointer must be audited, never silently redownloaded")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "data/phase5/MOVi_E" / (stamp+"_test_four_records")
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for shard in range(4):
        name = f"tfds/movi_e/256x256/1.0.0/movi_e-test.tfrecord-{shard:05d}-of-00256"
        encoded = name.replace("/", "%2F")
        metadata_file = out / f"shard_{shard:05d}_metadata.json"
        curl("https://storage.googleapis.com/storage/v1/b/kubric-public/o/"+encoded, metadata_file, proxy=args.proxy)
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        if metadata["name"] != name or int(metadata["size"]) < 16:
            raise ValueError("Unexpected official test shard metadata")
        url = "https://storage.googleapis.com/kubric-public/"+name+"?generation="+metadata["generation"]
        header_file = out / f"shard_{shard:05d}_record_header.bin"
        curl(url, header_file, proxy=args.proxy, byte_range="0-11", headers=out / f"shard_{shard:05d}_length_HTTP.txt", limit=12)
        length = record_length(header_file.read_bytes())
        end = length+15
        record = out / f"shard_{shard:05d}_first_record.tfrecord"
        curl(url, record, proxy=args.proxy, byte_range=f"0-{end}", headers=out / f"shard_{shard:05d}_record_HTTP.txt", limit=end+1)
        payload(record.read_bytes())
        row = {"shard": shard, "record_index_in_shard": 0, "record_file": str(record), "bytes": record.stat().st_size, "sha256": digest(record),
            "official_object": name, "generation": metadata["generation"], "whole_shard_bytes_not_downloaded": int(metadata["size"])-record.stat().st_size,
            "whole_shard_publisher_CRC32C": metadata["crc32c"], "whole_shard_CRC_verified": False,
            "TFRecord_length_and_payload_CRC32C_verified": True, "URL": url}
        rows.append(row)
        write(out / "acquisition_progress.json", {"completed_records": rows, "no_automatic_retry": True})
        print(json.dumps({"state": "ONE_TEST_RECORD_VERIFIED", "shard": shard, "bytes": row["bytes"]}), flush=True)
    result = {"status": "FOUR_OFFICIAL_TEST_RECORDS_RANGE_AND_CRC_VERIFIED", "dataset": "MOVi-E", "config": "256x256", "version": "1.0.0", "split": "test",
        "directory": str(out), "records": rows, "selection": "First record of each of test shards 0,1,2,3; fixed before any sample inspection or model scoring",
        "stage_gate": str(gate_file), "stage_gate_sha256": digest(gate_file), "total_sample_bytes": sum(row["bytes"] for row in rows),
        "full_dataset_downloaded": False, "GT_provenance": "SYNTHETIC_GROUND_TRUTH"}
    write(out / "acquisition.json", result)
    write(pointer, result)
    print(json.dumps({"status": result["status"], "directory": str(out), "bytes": result["total_sample_bytes"]}), flush=True)


if __name__ == "__main__":
    main()

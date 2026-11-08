"""Compare downloaded distribution SHA256 values against official PyPI metadata."""
from __future__ import annotations

import concurrent.futures
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--pytorch-index-plan", type=Path)
    args = parser.parse_args()
    report = args.report
    installed = json.loads(report.read_text())["install"]
    index_records = json.loads(args.pytorch_index_plan.read_text())["install"] if args.pytorch_index_plan else []

    def verify(entry):
        name, version = entry["metadata"]["name"], entry["metadata"]["version"]
        info = entry["download_info"]
        filename = unquote(urlparse(info["url"]).path.rsplit("/", 1)[1])
        checksum = info["archive_info"]["hashes"]["sha256"]
        if urlparse(info["url"]).scheme == "file":
            matches = [row for row in index_records if row["metadata"]["name"].lower() == name.lower() and row["metadata"]["version"] == version
                       and row["download_info"]["archive_info"].get("hashes", {}).get("sha256") == checksum]
            if matches:
                return {"name": name, "version": version, "filename": filename, "sha256": checksum,
                        "official_url": matches[0]["download_info"]["url"], "transport_url": info["url"],
                        "status": "MATCHES_RECORDED_OFFICIAL_PYTORCH_INDEX_SHA256", "index_plan_sha256": hashlib.sha256(args.pytorch_index_plan.read_bytes()).hexdigest()}
        with urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=60) as response:
            metadata = json.load(response)
        official = next(f for f in metadata["urls"] if (f["digests"]["sha256"] == checksum if urlparse(info["url"]).scheme == "file" else f["filename"] == filename))
        if official["digests"]["sha256"] != checksum:
            raise ValueError(f"Official digest mismatch: {filename}")
        return {"name": name, "version": version, "filename": filename, "sha256": checksum,
                "official_url": official["url"], "transport_url": info["url"], "status": "MATCHES_OFFICIAL_PYPI"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(verify, installed))
    report.with_name("pypi_hash_audit.json").write_text(json.dumps(results, indent=2))
    print(json.dumps({"status": "OFFICIAL_PUBLISHER_HASH_AUDIT_PASSED" if args.pytorch_index_plan else "OFFICIAL_PYPI_HASH_AUDIT_PASSED", "distributions": len(results)}))


if __name__ == "__main__":
    main()

"""Download the reviewed official pip plan and check C: installation headroom."""
from __future__ import annotations

import hashlib
import json
import shutil
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "before/pip-install-plan.json"
DEST = ROOT / "downloads"
ENV = Path(r"C:\Users\Administrator\.conda\envs\gamecam-vo")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    records = []
    for item in plan["install"]:
        metadata, source = item["metadata"], item["download_info"]
        url = source["url"]
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "download.pytorch.org", "download-r2.pytorch.org", "files.pythonhosted.org"
        }:
            raise ValueError("Unreviewed package host: " + str(parsed.hostname))
        name = Path(urllib.parse.unquote(parsed.path)).name
        if not name.endswith(".whl"):
            raise ValueError("Only wheels are permitted")
        expected = source.get("archive_info", {}).get("hashes", {}).get("sha256")
        hash_source = "reviewed_pip_plan_official_pytorch_index"
        if expected is None:
            # Some mirrored dependency entries omit hash fragments. Resolve the
            # exact wheel's independent publisher digest before accepting it.
            hash_source = f"https://pypi.org/pypi/{metadata['name']}/{metadata['version']}/json"
            with urllib.request.urlopen(hash_source, timeout=45) as response:
                publisher = json.load(response)
            matches = [entry for entry in publisher["urls"] if entry["filename"] == name]
            if len(matches) != 1:
                raise ValueError("Exact publisher wheel digest unavailable: " + name)
            expected = matches[0]["digests"]["sha256"]
            (ROOT / "before" / (metadata["name"] + "-publisher-metadata.json")).write_text(
                json.dumps(publisher, indent=2), encoding="utf-8")
        path = DEST / name
        started = time.perf_counter()
        if path.exists():
            if sha256(path) != expected:
                raise ValueError("Preserve mismatched existing download: " + name)
        else:
            request = urllib.request.Request(url, headers={"User-Agent": "GameCam-VO-local-environment-audit"})
            partial = path.with_suffix(path.suffix + ".partial")
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("xb") as output:
                expected_length = response.headers.get("Content-Length")
                total = 0
                reported = 0
                for chunk in iter(lambda: response.read(8 << 20), b""):
                    output.write(chunk)
                    total += len(chunk)
                    if total - reported >= 256 << 20:
                        print(f"{metadata['name']}: {total / (1 << 20):.0f} MiB downloaded", flush=True)
                        reported = total
            if expected_length is not None and total != int(expected_length):
                raise ValueError("Download length mismatch")
            if sha256(partial) != expected:
                raise ValueError("Official package SHA256 mismatch: " + name)
            partial.rename(path)
        with zipfile.ZipFile(path) as archive:
            expanded = sum(entry.file_size for entry in archive.infolist())
        record = {
            "name": metadata["name"], "version": metadata["version"], "wheel": name,
            "bytes": path.stat().st_size, "uncompressed_bytes": expanded,
            "sha256": expected, "download_url": url,
            "download_seconds": time.perf_counter() - started,
            "publisher_hash_verified": True, "hash_source": hash_source,
        }
        records.append(record)
        (ROOT / "logs/download-progress.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(f"Verified {metadata['name']} {metadata['version']}: {path.stat().st_size:,} bytes", flush=True)
    expanded = sum(row["uncompressed_bytes"] for row in records)
    free = shutil.disk_usage(ENV).free
    reserve = 3 << 30
    # Extra space allows bytecode, metadata and a margin beyond the wheel contents.
    installation_allowance = int(expanded * 1.15) + (256 << 20)
    ready = free >= installation_allowance + reserve
    receipt = {
        "utc": datetime.now(timezone.utc).isoformat(), "environment": str(ENV),
        "files": records, "total_download_bytes": sum(row["bytes"] for row in records),
        "total_uncompressed_bytes": expanded, "install_allowance_bytes": installation_allowance,
        "environment_disk_free_bytes": free, "minimum_post_install_reserve_bytes": reserve,
        "temp_and_wheel_disk": str(ROOT), "installation_space_ready": ready,
    }
    (ROOT / "before/INSTALLATION_STORAGE_BUDGET.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    lines = [f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}" for r in records]
    (ROOT / "requirements.gpu-windows.lock.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in receipt.items() if key != "files"}, indent=2), flush=True)
    if not ready:
        raise SystemExit("Installation stopped before mutation: C: reserve would be insufficient")


if __name__ == "__main__":
    main()

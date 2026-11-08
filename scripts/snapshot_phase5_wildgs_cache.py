"""Preserve exact executed ext4 Python/config bytes beside their result evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    out = args.result.resolve()
    manifest_file = out / "runtime_source_cache_manifest.json"
    manifest = json.loads(manifest_file.read_text())
    cache = Path(manifest["directory"])
    target = out / "executed_source_cache.zip"
    if target.exists():
        raise FileExistsError("Preserve the existing exact source archive")
    entries = []
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for member in manifest["files"]:
            cached = Path(member["cached"])
            relative = cached.relative_to(cache)
            data = cached.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != member["sha256"]:
                raise ValueError("Executed cached source identity changed")
            archive.writestr(relative.as_posix(), data)
            entries.append({"name": relative.as_posix(), "sha256": digest, "bytes": len(data)})
        archive.writestr("source_manifest.json", manifest_file.read_bytes())
    with zipfile.ZipFile(target) as archive:
        for member in entries:
            if hashlib.sha256(archive.read(member["name"])).hexdigest() != member["sha256"]:
                raise ValueError("Archived source byte roundtrip failed")
    record = {"status": "EXECUTED_SOURCE_CACHE_ARCHIVE_BYTE_ROUNDTRIP_PASS", "archive": str(target), "archive_bytes": target.stat().st_size,
        "archive_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "source_files": len(entries),
        "source_manifest_sha256": hashlib.sha256(manifest_file.read_bytes()).hexdigest(), "entries": entries,
        "scope": "Exact already executed cached source/config bytes, no weights, no model replay. Later edits to working launchers do not change this archive."}
    (out / "executed_source_archive.json").write_text(json.dumps(record, indent=2)+"\n")
    print(json.dumps({k: record[k] for k in ("status", "archive_bytes", "source_files")}))


if __name__ == "__main__":
    main()

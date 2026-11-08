"""Acquire one small official OmniWorld-Game scene with complete archive hashes."""
from __future__ import annotations
import _bootstrap
import hashlib
import json
import tarfile
import time
import urllib.request
from pathlib import Path, PurePosixPath
from uuid import uuid4

from gamecam_vo.common import PROJECT, make_run_dir, sha256, write_json


def main():
    scene = "c5e5ed9a4462"
    source = PROJECT / "docs/sources/omniworld"
    metadata = json.loads((source / "repository_metadata.json").read_text(encoding="utf-8-sig"))
    revision = metadata["sha"]
    files = []
    for category in ("annotations", "videos"):
        records = json.loads((source / f"{scene}_{category}_tree.json").read_text(encoding="utf-8-sig"))
        files += records if isinstance(records, list) else [records]
    files = sorted((record for record in files if record["type"] == "file" and "_flow_" not in record["path"]),
                   key=lambda record: (0 if "_others." in record["path"] else 1))
    total_size = sum(record["size"] for record in files)
    if len(files) != 3 or total_size > 200 * 1024**2:
        raise ValueError("One-scene archive plan changed or exceeds the 200MiB sample limit")
    archive_root = (PROJECT / "data/omniworld_game/_archives" / scene).resolve()
    destination = (PROJECT / "data/omniworld_game" / scene).resolve()
    archive_root.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    run = make_run_dir(PROJECT / "logs/acquisition_omni", scene)
    record = {"dataset": "OmniWorld-Game", "repository": "InternRobotics/OmniWorld", "revision": revision,
              "scene_id": scene, "POSE_PROVENANCE": "ESTIMATED_REFERENCE",
              "selection_criterion": "Small complete one-split scene among examined short scenes; no metric-based selection",
              "planned_archive_bytes": total_size, "network_budget_bytes": 256 * 1024**2,
              "network_bytes_read": 0, "status": "RUNNING", "archives": [], "extracted_members": []}
    write_json(run / "download_plan.json", record)
    try:
        for item in files:
            archive_path = archive_root / PurePosixPath(item["path"]).name
            expected_hash = item["lfs"]["oid"]
            if archive_path.exists():
                if sha256(archive_path) != expected_hash:
                    raise ValueError("Existing official archive has a different checksum")
            else:
                last_error = None
                for attempt in range(3):
                    temporary = archive_path.with_name(archive_path.name + "." + uuid4().hex + ".part")
                    url = f"https://huggingface.co/datasets/InternRobotics/OmniWorld/resolve/{revision}/{item['path']}?download=true&nonce={uuid4().hex}"
                    try:
                        digest, received = hashlib.sha256(), 0
                        with urllib.request.urlopen(url, timeout=35) as response, temporary.open("xb") as handle:
                            while True:
                                block = response.read(1024 * 1024)
                                if not block:
                                    break
                                record["network_bytes_read"] += len(block)
                                if record["network_bytes_read"] > record["network_budget_bytes"]:
                                    raise ValueError("Omni sample network budget exceeded")
                                received += len(block)
                                if received > item["size"]:
                                    raise ValueError("Response exceeded the declared archive size")
                                digest.update(block)
                                handle.write(block)
                                if received % (16 * 1024**2) == 0:
                                    print(f"{archive_path.name}: {received / 1024**2:.0f} MiB", flush=True)
                        if received != item["size"] or digest.hexdigest() != expected_hash:
                            raise ValueError("Official archive SHA256/length mismatch")
                        temporary.rename(archive_path)
                        last_error = None
                        break
                    except Exception as exc:
                        last_error = exc
                        if "budget" in str(exc).lower() or "exceeded" in str(exc).lower():
                            break
                        time.sleep(0.3 * (attempt + 1))
                if last_error:
                    raise last_error
            record["archives"].append({"path": item["path"], "size_bytes": item["size"], "sha256": expected_hash,
                                       "full_archive_hash_verified": True, "local_archive": str(archive_path)})
            with tarfile.open(archive_path, "r:gz") as archive:
                for member in archive:
                    path = PurePosixPath(member.name)
                    if path.is_absolute() or ".." in path.parts:
                        raise ValueError("Unsafe archive path")
                    if not member.isfile():
                        if member.isdir():
                            continue
                        raise ValueError("Nonregular archive member")
                    parts = path.parts[1:] if path.parts[0] == scene else path.parts
                    target = (destination / Path(*parts)).resolve()
                    if not target.is_relative_to(destination) or member.size > 64 * 1024**2:
                        raise ValueError("Unsafe or oversized extraction target")
                    payload = archive.extractfile(member).read(member.size + 1)
                    if len(payload) != member.size:
                        raise ValueError("Incomplete archive member")
                    digest = hashlib.sha256(payload).hexdigest()
                    if target.exists():
                        if sha256(target) != digest:
                            raise ValueError("Existing original scene file differs")
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with target.open("xb") as handle:
                            handle.write(payload)
                    record["extracted_members"].append({"archive_member": member.name, "local_path": str(target),
                                                         "size_bytes": member.size, "sha256": digest})
            print(f"Verified and extracted {archive_path.name}; cumulative files={len(record['extracted_members'])}", flush=True)
            write_json(run / "download_manifest.json", record)
        record["status"] = "COMPLETE_SELECTED_SCENE"
    except Exception as exc:
        record.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        write_json(run / "download_manifest.json", record)
    print(json.dumps({key: record[key] for key in ("status", "scene_id", "planned_archive_bytes", "network_bytes_read")}))


if __name__ == "__main__":
    main()

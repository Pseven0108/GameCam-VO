"""Bounded streaming extraction from public, pinned official dataset archives."""
from __future__ import annotations

import hashlib
import json
import tarfile
import time
import urllib.request
from pathlib import Path, PurePosixPath
from uuid import uuid4

from .common import sha256, utc_now, write_json


class BudgetedReader:
    def __init__(self, response, budget_bytes, progress):
        self.response, self.budget_bytes, self.progress = response, budget_bytes, progress
        self.count, self.last_report = 0, 0

    def read(self, size=-1):
        if size < 0:
            raise ValueError("Unbounded reads are prohibited")
        if self.count + size > self.budget_bytes:
            raise RuntimeError(f"Compressed download budget exceeded: {self.budget_bytes} bytes")
        value = self.response.read(size)
        self.count += len(value)
        if self.count - self.last_report >= 8 * 1024**2:
            self.progress(f"Received {self.count / 1024**2:.1f} MiB")
            self.last_report = self.count
        return value


def stream_extract(url: str, destination: Path, selector, complete,
                   budget_bytes: int, manifest_path: Path, max_member_bytes=64 * 1024**2):
    """Extract selected regular files only; stop the HTTP stream as soon as complete."""
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    record = {"created_utc": utc_now(), "canonical_url": url, "status": "RUNNING",
              "compressed_network_budget_bytes": budget_bytes, "network_bytes_read": 0,
              "full_archive_downloaded": False, "members": [], "error": None}
    write_json(manifest_path, record)
    started = time.perf_counter()
    reader = None
    selected = set()
    try:
        # Nonce avoids a stale cached expiring public CDN redirect.
        request = urllib.request.Request(url + ("&" if "?" in url else "?") + "download=true&nonce=" + uuid4().hex,
                                         headers={"User-Agent": "GameCam-VO-research/0.2"})
        with urllib.request.urlopen(request, timeout=45) as response:
            record["http_status"] = response.status
            record["remote_content_length"] = response.headers.get("Content-Length")
            reader = BudgetedReader(response, budget_bytes, lambda message: print(message, flush=True))
            with tarfile.open(fileobj=reader, mode="r|gz") as archive:
                for member in archive:
                    archive_path = PurePosixPath(member.name)
                    if archive_path.is_absolute() or ".." in archive_path.parts:
                        raise ValueError("Unsafe archive path")
                    relative = selector(archive_path)
                    if relative is None:
                        continue
                    if not member.isfile() or member.size > max_member_bytes:
                        raise ValueError(f"Unsupported or oversized selected member: {member.name}")
                    relative = PurePosixPath(str(relative).replace("\\", "/"))
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ValueError("Unsafe extraction target")
                    target = (destination / Path(*relative.parts)).resolve()
                    if not target.is_relative_to(destination):
                        raise ValueError("Target escaped dataset directory")
                    handle = archive.extractfile(member)
                    if handle is None:
                        raise ValueError("Missing member payload")
                    payload = handle.read(member.size + 1)
                    if len(payload) != member.size:
                        raise OSError("Incomplete archive member")
                    digest = hashlib.sha256(payload).hexdigest()
                    if target.exists():
                        if sha256(target) != digest:
                            raise FileExistsError(f"Existing data differs; preserve and inspect: {target}")
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with target.open("xb") as output:
                            output.write(payload)
                    selected.add(str(relative))
                    record["members"].append({"archive_path": member.name, "local_relative_path": str(relative),
                                              "uncompressed_bytes": member.size, "sha256": digest})
                    if len(selected) % 25 == 0:
                        print(f"Retained {len(selected)} selected files; last={relative}", flush=True)
                        record["network_bytes_read"] = reader.count
                        write_json(manifest_path, record)
                    if complete(selected):
                        record["status"] = "COMPLETE_SELECTED_SAMPLE"
                        break
        if record["status"] != "COMPLETE_SELECTED_SAMPLE":
            raise ValueError("Archive ended before selected sample was complete")
    except Exception as exc:
        record["status"] = "FAILED"
        record["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record["network_bytes_read"] = reader.count if reader else 0
        record["elapsed_seconds"] = time.perf_counter() - started
        write_json(manifest_path, record)
    return record

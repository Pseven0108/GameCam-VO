from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

PROJECT = Path(__file__).resolve().parents[1]
POSE_COLUMNS = ["timestamp", "tx", "ty", "tz", "qx", "qy", "qz", "qw"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_yaml(path: str | Path) -> dict:
    with open(path, encoding="utf-8-sig") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML mapping: {path}")
    return value


def write_json(path: str | Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def clean(obj):
        if isinstance(obj, np.ndarray):
            return clean(obj.tolist())
        if isinstance(obj, np.generic):
            return clean(obj.item())
        if isinstance(obj, float) and not np.isfinite(obj):
            return None
        if isinstance(obj, dict):
            return {str(k): clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [clean(v) for v in obj]
        if isinstance(obj, Path):
            return str(obj)
        return obj

    path.write_text(json.dumps(clean(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: str | Path, rows: list[dict], columns: list[str] | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = columns or (list(rows[0]) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fingerprint(path: str | Path) -> dict:
    """Bounded content fingerprint; explicitly not a full-file SHA256."""
    path = Path(path)
    info = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read(65536))
        if info.st_size > 65536:
            handle.seek(max(65536, info.st_size - 65536))
            digest.update(handle.read(65536))
    return {"path": str(path.resolve()), "size_bytes": info.st_size,
            "mtime_ns": info.st_mtime_ns, "head_tail_sha256": digest.hexdigest()}


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def config_digest(*configs: dict) -> str:
    return hashlib.sha256(json.dumps(configs, sort_keys=True).encode()).hexdigest()


def code_version() -> dict:
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=PROJECT, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        revision, dirty = "uncommitted", True
    return {"git_commit": revision, "working_tree_dirty": dirty,
            "source_sha256": {str(p.relative_to(PROJECT)): sha256(p)
                              for pattern in ("gamecam_vo/*.py", "scripts/*.py", "datasets/**/*.py", "configs/**/*.yaml", "configs/*.yaml")
                              for p in sorted(PROJECT.glob(pattern))}}


def run_metadata() -> dict:
    return {"created_utc": utc_now(), "python": platform.python_version(), **code_version()}


def fresh_directory(path: str | Path) -> Path:
    """Never overwrite results of an earlier attempt."""
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"Output is not empty; choose a new run directory: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_run_dir(parent: str | Path, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    return fresh_directory(Path(parent) / f"{stamp}_{label}")

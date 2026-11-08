from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path

import numpy as np

from .common import PROJECT, fingerprint
from .geometry import parse_vector
from .video import probe_video


def absolute_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT / path).resolve()


def discover_sequences(config: dict) -> tuple[list[Path], list[str]]:
    limit = int(config["max_sequences"])
    if not 1 <= limit <= 10:
        raise ValueError("First-round inspection is bounded to 1..10 sequences")
    found, issues = [], []
    explicit = config.get("sequences") or []
    roots = config.get("roots") or []
    if not explicit and not roots:
        return [], ["No local WildWorld roots or sequences configured"]
    for value in explicit:
        directory = absolute_path(value)
        if directory.is_dir():
            found.append(directory)
        else:
            issues.append(f"Missing explicit sequence directory: {directory}")
    for value in roots:
        root = absolute_path(value)
        if not root.is_dir():
            issues.append(f"Missing dataset root: {root}")
            continue
        for current, directories, files in os.walk(root, followlinks=False):
            directories[:] = sorted(d for d in directories if not d.startswith("."))
            if config["video_filename"] in files:
                found.append(Path(current).resolve())
                if len(set(found)) >= limit:
                    break
        if len(set(found)) >= limit:
            break
    unique = list(dict.fromkeys(found))
    if len(unique) > limit:
        issues.append(f"Limited inspection to {limit} explicitly selected sequences")
    return unique[:limit], issues


def sequence_id(path: Path) -> str:
    suffix = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:8]
    return f"{path.name}_{suffix}"


def load_state(path: Path, dataset_config: dict, camera_config: dict) -> dict:
    if path.stat().st_size > float(dataset_config["max_csv_megabytes"]) * 1024**2:
        raise ValueError("CSV exceeds the configured bounded-inspection size limit")
    positions, quaternions, intrinsics, timestamps, frame_indices, errors = [], [], [], [], [], []
    sync = dataset_config["sync"]
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        required = [camera_config[name] for name in ("position_column", "rotation_column", "intrinsics_column")]
        required += [sync[key] for key in ("timestamp_column", "frame_index_column") if sync.get(key)]
        absent = [name for name in required if name not in columns]
        if absent:
            raise ValueError(f"Missing explicitly required CSV columns: {absent}")
        for index, row in enumerate(reader):
            row_errors = []
            vectors = []
            for key, length in zip(("position_column", "rotation_column", "intrinsics_column"), (3, 4, 4), strict=True):
                try:
                    vector = parse_vector(row[camera_config[key]] or "", length)
                except (ValueError, SyntaxError, TypeError) as exc:
                    vector = np.full(length, np.nan)
                    row_errors.append(f"{camera_config[key]}: {exc}")
                vectors.append(vector)
            positions.append(vectors[0])
            quaternions.append(vectors[1])
            intrinsics.append(vectors[2])
            timestamp = np.nan
            if sync.get("timestamp_column"):
                try:
                    factor = float(sync["timestamp_seconds_per_unit"])
                    if not np.isfinite(factor) or factor <= 0:
                        raise ValueError("Timestamp unit must be documented and positive")
                    timestamp = float(row[sync["timestamp_column"]]) * factor
                except (ValueError, TypeError) as exc:
                    row_errors.append(f"timestamp: {exc}")
            timestamps.append(timestamp)
            frame_index = index
            if sync.get("frame_index_column"):
                try:
                    value = float(row[sync["frame_index_column"]])
                    if not np.isfinite(value) or not value.is_integer():
                        raise ValueError("Nonintegral frame index")
                    frame_index = int(value) - int(sync["frame_index_origin"])
                except (ValueError, TypeError) as exc:
                    frame_index = -1
                    row_errors.append(f"frame index: {exc}")
            frame_indices.append(frame_index)
            if row_errors:
                errors.append({"row_index": index, "reasons": "; ".join(row_errors)})
    return {"positions": np.array(positions).reshape(-1, 3),
            "quaternions": np.array(quaternions).reshape(-1, 4),
            "intrinsics": np.array(intrinsics).reshape(-1, 4),
            "timestamps": np.array(timestamps), "frame_indices": np.array(frame_indices, int),
            "parse_errors": errors, "columns": columns}


def inspect_sequence(directory: Path, dataset_config: dict, camera_config: dict) -> dict:
    video = directory / dataset_config["video_filename"]
    state = directory / dataset_config["state_filename"]
    entry = {"sequence_id": sequence_id(directory), "directory": str(directory),
             "video": str(video), "state_csv": str(state), "issues": [],
             "depth_exists": (directory / "depth.mkv").is_file(),
             "skeleton_exists": (directory / "skeleton.npz").is_file(),
             "mask_candidates": [str(p) for p in directory.iterdir() if "mask" in p.name.lower()],
             "scene_category": "UNREVIEWED", "mask_semantics_verified": False}
    if video.is_file():
        entry["video_fingerprint"] = fingerprint(video)
        try:
            entry.update(probe_video(video))
        except Exception as exc:
            entry["issues"].append(f"Video header error: {type(exc).__name__}: {exc}")
    else:
        entry["issues"].append("RGB video missing")
    if state.is_file():
        entry["state_fingerprint"] = fingerprint(state)
        try:
            values = load_state(state, dataset_config, camera_config)
            entry["pose_count"] = len(values["positions"])
            entry["csv_columns"] = values["columns"]
            entry["csv_parse_error_count"] = len(values["parse_errors"])
            entry["timestamp_column_configured"] = dataset_config["sync"].get("timestamp_column")
            entry["timestamp_candidates_not_assumed"] = [c for c in values["columns"] if "time" in c.lower()]
            entry["timestamps_complete"] = bool(dataset_config["sync"].get("timestamp_column") and
                                                  np.isfinite(values["timestamps"]).all() and len(values["timestamps"]))
        except Exception as exc:
            entry["issues"].append(f"CSV error: {type(exc).__name__}: {exc}")
    else:
        entry["issues"].append("state.csv missing")
    return entry

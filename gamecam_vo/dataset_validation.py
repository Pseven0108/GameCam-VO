"""E0 for explicitly configured dataset adapters; legacy WildWorld is retained."""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np

from datasets.registry import open_dataset
from .common import (POSE_COLUMNS, config_digest, fingerprint, make_run_dir, run_metadata,
                     sha256, write_csv, write_json)
from .geometry import poses_to_rows
from .plotting import plot_trajectory
from .validation import motion_statistics, STAT_COLUMNS


def run_dataset_e0(config: dict, result_parent: Path):
    out = make_run_dir(result_parent, config["experiment_ids"]["validation"].lower())
    write_json(out / "run_config.json", config)
    result = {**run_metadata(), "dataset": config["dataset"], "adapter": config["adapter"],
              "experiment_id": config["experiment_ids"]["validation"], "status": "FAILED",
              "e0_passed": False, "downstream_allowed": False, "config_digest": config_digest(config, config["camera"]),
              "result_directory": str(out), "sequences": []}
    try:
        dataset = open_dataset(config)
        metadata = dataset.get_metadata()
        identifier = str(metadata["sequence_id"])
        sequence_out = out / identifier
        sequence_out.mkdir()
        input_files = [{"path": str(path.resolve()), "size_bytes": path.stat().st_size, "sha256": sha256(path)}
                       for path in dataset.input_files()]
        manifest = {**run_metadata(), "format_version": 2, "dataset": config["dataset"],
                    "adapter": config["adapter"], "config_digest": config_digest(config, config["camera"]),
                    "sequences": [{"sequence_id": identifier, "directory": str(dataset.root),
                                   "frame_count": len(dataset.records), "input_files": input_files,
                                   "metadata": metadata}], "config": config}
        write_json(out / "data_manifest.json", manifest)
        diagnostics = dataset.validate(sequence_out)
        poses, intrinsics = dataset.get_poses(), dataset.get_intrinsics()
        times = np.array([record["timestamp"] for record in dataset.records])
        if len(times) < 2 or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
            diagnostics["blockers"].append("Missing, duplicate or nonmonotonic frame time/index")
            diagnostics["e0_passed"] = False
        np.save(sequence_out / "converted_camera_to_world.npy", poses)
        np.save(sequence_out / "intrinsics.npy", intrinsics)
        rows = poses_to_rows(times, poses)
        for i, row in enumerate(rows):
            row.update({"row_index": i, "frame_index": dataset.records[i]["frame_index"],
                        "source_frame_id": dataset.records[i]["frame_id"],
                        "pose_valid": bool(np.isfinite(poses[i]).all())})
        trajectory_file = ("normalized_ground_truth.csv" if metadata["independent_engine_ground_truth"]
                           else "normalized_reference_trajectory.csv")
        normalized = sequence_out / trajectory_file
        write_csv(normalized, rows, POSE_COLUMNS + ["row_index", "frame_index", "source_frame_id", "pose_valid"])
        associations = [{"frame_index": record["frame_index"], "source_rgb": str(record["rgb_path"]),
                         "source_pose": str(record.get("pose_path", "")), "state_row_index": i,
                         "evaluation_timestamp": float(record["timestamp"]), "timestamp_kind": metadata["timestamp_kind"],
                         "pose_valid": bool(np.isfinite(poses[i]).all())} for i, record in enumerate(dataset.records)]
        write_csv(sequence_out / "frame_associations.csv", associations)
        finite = np.isfinite(poses).all(axis=(1, 2))
        stats = motion_statistics(poses, times, finite, np.ones(len(poses)), metadata["timestamp_kind"] == "seconds")
        write_csv(sequence_out / "pose_statistics.csv", stats, STAT_COLUMNS)
        write_csv(sequence_out / "anomaly_intervals.csv", [row for row in stats if row["anomaly_candidate"]], STAT_COLUMNS)
        local = {**metadata, **diagnostics, "sequence_id": identifier,
                 "config_digest": config_digest(config, config["camera"]),
                 "trajectory_file": trajectory_file, "trajectory_sha256": sha256(normalized),
                 "frame_associations_sha256": sha256(sequence_out / "frame_associations.csv"),
                 "source_files_fully_hashed": True, "time_kind": metadata["timestamp_kind"],
                 "trust_scope": "engine_ground_truth" if metadata["independent_engine_ground_truth"] else "estimated_reference_only"}
        write_json(sequence_out / "validation.json", local)
        write_json(normalized.with_suffix(".metadata.json"), local)
        prefix = "ENGINE GT" if metadata["independent_engine_ground_truth"] else "ESTIMATED REFERENCE"
        if not diagnostics["e0_passed"]:
            prefix = "CANDIDATE - E0 NOT PASSED"
        plot_trajectory(times, poses, sequence_out, metadata["length_unit"],
                        f"{config['dataset']}: {prefix}", metadata["timestamp_kind"])
        result.update({"status": "PASS" if diagnostics["e0_passed"] else "FAIL_OR_UNRESOLVED",
                       "e0_passed": bool(diagnostics["e0_passed"]), "downstream_allowed": bool(diagnostics["e0_passed"]),
                       "POSE_PROVENANCE": metadata["POSE_PROVENANCE"],
                       "independent_engine_ground_truth": metadata["independent_engine_ground_truth"],
                       "sequences": [local]})
    except Exception as exc:
        result["failure"] = f"{type(exc).__name__}: {exc}"
        write_json(out / "failure.json", result)
    write_json(out / "validation.json", result)
    write_json(result_parent / "latest_run.json", {"directory": str(out), "status": result["status"]})
    report = [f"# {result['experiment_id']} — {config['dataset']}", "", f"Status: {result['status']}", "",
              f"Actual selected dataset frames: {sum(item.get('pose_count', 0) for item in result['sequences'])}",
              f"POSE_PROVENANCE = {result.get('POSE_PROVENANCE', 'UNAVAILABLE')}",
              "", f"Data/config/code evidence: {out}"]
    if "failure" in result:
        report += ["", "Failure: " + result["failure"]]
    for sequence in result["sequences"]:
        report += ["", *[f"- {reason}" for reason in sequence["blockers"]]]
    (out / "experiment_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return result


def check_adapter_gate(e0_run: Path, identifier: str, config: dict):
    manifest = json.loads((e0_run / "data_manifest.json").read_text(encoding="utf-8"))
    local = json.loads((e0_run / identifier / "validation.json").read_text(encoding="utf-8"))
    if manifest["config_digest"] != config_digest(config, config["camera"]):
        raise ValueError("Dataset configuration changed after E0")
    if not local["e0_passed"]:
        raise ValueError("Dataset E0 gate is closed")
    entry = next(item for item in manifest["sequences"] if item["sequence_id"] == identifier)
    for record in entry["input_files"]:
        if sha256(record["path"]) != record["sha256"]:
            raise ValueError(f"Validated source changed: {record['path']}")
    for filename, key in ((local["trajectory_file"], "trajectory_sha256"),
                          ("frame_associations.csv", "frame_associations_sha256")):
        if sha256(e0_run / identifier / filename) != local[key]:
            raise ValueError("Validated derived trajectory or frame associations changed")
    return entry, local

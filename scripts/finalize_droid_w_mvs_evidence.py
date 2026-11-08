"""Verify and index the completed E8 artifacts, retaining portable source patches."""
from __future__ import annotations

import _bootstrap
import csv
import json
from pathlib import Path
import shutil

import numpy as np

from gamecam_vo.common import PROJECT, run_metadata, sha256, write_json
from gamecam_vo.evaluation import load_trajectory


def main():
    evaluation = json.loads((PROJECT / "reports/SOTA/droid_mvs_evaluation.json").read_text())
    if evaluation["status"] != "MVS_EXTERNAL_EVALUATION_COMPLETED":
        raise RuntimeError("Completed independent MVS evaluation is required")
    out = Path(evaluation["directory"])
    timestamps, poses = load_trajectory(out / "estimated_trajectory.csv")
    if len(timestamps) != 100 or not np.array_equal(timestamps, np.arange(100)) or not np.isfinite(poses).all():
        raise ValueError("Canonical100-frame trajectory verification failed")
    text_times, text_poses = load_trajectory(out / "estimated_trajectory.txt")
    np.testing.assert_array_equal(text_times, timestamps)
    np.testing.assert_allclose(text_poses, poses, rtol=1e-9, atol=1e-9)
    with (out / "uncertainty_maps/manifest.csv").open(newline="") as stream:
        maps = list(csv.DictReader(stream))
    if len(maps) != evaluation["uncertainty_map_count"]:
        raise ValueError("Uncertainty index count changed")
    map_records = []
    for row in maps:
        path = out / "uncertainty_maps" / f"frame_{int(row['frame_index']):05d}.npy"
        raw = np.load(path)
        if raw.shape != (int(row["native_grid_height"]), int(row["native_grid_width"])) or not np.isfinite(raw).all():
            raise ValueError("Native uncertainty array verification failed")
        map_records.append({"frame_index": int(row["frame_index"]), "shape": list(raw.shape), "file": str(path), "sha256": sha256(path)})
    figures = [out / "tracking_visualization" / (name + ".png") for name in (
        "trajectory_comparison", "trajectory_3d", "trajectory_xy", "trajectory_xz", "camera_orientation", "uncertainty_examples", "output_support")]
    figures += [out / "gpu_memory_timeline.png"]
    for path in figures:
        if not path.is_file() or not path.with_suffix(".svg").is_file():
            raise ValueError("Missing reviewed PNG/SVG pair")
    review = {"status": "PASS_AFTER_ONE_LEGEND_LAYOUT_REPAIR", "reviewer": "Assistant visual inspection of actual rendered PNGs in this task",
              "repair": "Move camera-orientation legend outside the plot so it does not obscure the forward-Z curve; data and metrics unchanged",
              "checked": ["visible labels and units", "no title/legend clipping or data obstruction", "ENGINE_GROUND_TRUTH label", "filled poses versus initialization/keyframes",
                          "raw uncertainty display limits and no calibrated-probability claim", "whole-device GPU sampling scope"],
              "figures": [{"file": str(path), "sha256": sha256(path), "svg_sha256": sha256(path.with_suffix('.svg'))} for path in figures]}
    write_json(out / "figure_review.json", review)
    source = json.loads((PROJECT / "reports/SOTA/droid_source_snapshot.json").read_text())
    source_folder = Path(source["directory"])
    manifest = json.loads((source_folder / "manifest.json").read_text())
    if sha256(source["archive"]) != source["sha256"]:
        raise ValueError("Frozen model source archive changed")
    destination = PROJECT / "baselines/droid_w/patches" / source_folder.name
    destination.mkdir(parents=True, exist_ok=True)
    components = []
    for component in manifest["components"]:
        original = source_folder / (component["component"] + ".patch")
        target = destination / original.name
        if sha256(original) != component["patch_sha256"]:
            raise ValueError("Frozen source patch hash mismatch")
        if target.exists() and sha256(target) != component["patch_sha256"]:
            raise ValueError("Refuse to overwrite a different recorded source patch")
        if not target.exists():
            shutil.copy2(original, target)
        components.append({key: component[key] for key in ("component", "upstream_base_commit", "commit", "branch", "patch_sha256")})
    write_json(destination / "manifest.json", {"components": components, "frozen_source_archive_sha256": source["sha256"],
               "apply_policy": "Each patch is relative to the listed component's upstream base commit, including nested submodules. Empty patches mean no source changes."})
    files = [out / name for name in ("estimated_trajectory.txt", "estimated_trajectory.csv", "metrics.csv", "tracking_status.csv", "run_config.yaml",
                                      "execution_contract.json", "input_manifest.json", "coordinate_consistency.json", "evaluation_details.json", "evaluation_summary.json",
                                      "inference_log.txt", "gpu_memory.csv", "status.json", "figure_review.json")]
    record = {**run_metadata(), "status": "E8_INFERENCE_EXPORT_AND_FIGURE_QA_COMPLETED", "directory": str(out), "canonical_frames": 100,
              "raw_keyframe_uncertainty_maps": map_records, "files": [{"file": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in files],
              "portable_source_patches": str(destination), "frozen_model_source_archive": source,
              "native_model_video_sha256": evaluation["coordinate_check"]["video_snapshot_sha256"],
              "not_a_paper_score_match": True, "dynamic_robustness_evidence": False, "model_inference_reexecuted_by_this_verifier": False}
    write_json(out / "final_evidence_manifest.json", record)
    write_json(PROJECT / "reports/SOTA/droid_mvs_delivery.json", record)
    print(json.dumps({"status": record["status"], "directory": str(out), "reviewed_figures": len(figures), "raw_maps": len(map_records), "portable_patches": str(destination)}))


if __name__ == "__main__":
    main()

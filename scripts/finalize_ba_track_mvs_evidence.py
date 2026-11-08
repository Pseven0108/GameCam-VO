"""Index the completed BA experiment after external metrics and actual figure QA."""
from __future__ import annotations

import _bootstrap
import csv
import json
from pathlib import Path
import shutil

import numpy as np
import yaml

from gamecam_vo.common import PROJECT, run_metadata, sha256, write_json
from gamecam_vo.evaluation import load_trajectory


def local(value):
    path = Path(str(value).replace("/mnt/d/", "D:/", 1)).resolve()
    if not path.is_relative_to(PROJECT):
        raise ValueError("Owned result path required")
    return path


def main():
    reports = PROJECT / "reports/SOTA"
    evaluation = json.loads((reports / "ba_track_mvs_evaluation.json").read_text(encoding="utf-8"))
    if evaluation["status"] != "BA_TRACK_MVS_EXTERNAL_EVALUATION_COMPLETED" or not evaluation["figures_visually_reviewed"]:
        raise RuntimeError("Complete external evaluation and explicit visual QA first")
    out = local(evaluation["directory"])
    qa = json.loads((out / "figure_review.json").read_text(encoding="utf-8"))
    if qa["status"] != "VISUALLY_REVIEWED_PASS":
        raise RuntimeError("Figure QA did not pass")
    for item in qa["files"]:
        if sha256(out / item["file"]) != item["sha256"]:
            raise ValueError("A reviewed figure changed")
    times, poses = load_trajectory(out / "estimated_trajectory.csv")
    text_times, text_poses = load_trajectory(out / "estimated_trajectory.txt")
    if len(times) != 100 or not np.array_equal(times, np.arange(100)) or not np.isfinite(poses).all():
        raise ValueError("Canonical full100 camera output failed")
    np.testing.assert_array_equal(times, text_times)
    np.testing.assert_allclose(poses, text_poses, rtol=1e-9, atol=1e-9)
    review = json.loads((out / "output_review.json").read_text(encoding="utf-8"))
    manifest = out / review["refined_depth_manifest"]
    if sha256(manifest) != review["refined_depth_manifest_sha256"]:
        raise ValueError("Native depth manifest changed")
    with manifest.open(encoding="utf-8", newline="") as handle:
        depths = list(csv.DictReader(handle))
    if len(depths) != 100:
        raise ValueError("Incomplete100 native refined depth index")
    for row in depths:
        path = out / "depth_results/global_refined/mvs_0000" / f"frame_{int(row['frame_index']):05d}.npy"
        if sha256(path) != row["sha256"]:
            raise ValueError("Native refined depth array changed")
    contract = json.loads((out / "execution_contract.json").read_text(encoding="utf-8"))
    (out / "run_config.yaml").write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True), encoding="utf-8")
    shutil.copy2(out / "hydra/.hydra/config.yaml", out / "native_hydra_config.yaml")
    shutil.copy2(out / "hydra/.hydra/overrides.yaml", out / "native_hydra_overrides.yaml")
    execution = json.loads((out / "execution.json").read_text(encoding="utf-8"))
    with (out / "inference_log.txt").open("wb") as aggregate:
        aggregate.write(b"Derivative concatenation of the retained native stage logs; originals remain unchanged.\n")
        for row in execution:
            log = out / (row["stage"] + ".log")
            aggregate.write(("\nStage record: "+json.dumps(row)+"\nSource: "+log.name+"; SHA256="+sha256(log)+"\n").encode("utf-8"))
            aggregate.write(log.read_bytes())
    files = [out / name for name in ("estimated_trajectory.txt", "estimated_trajectory.csv", "metrics.csv", "tracking_status.csv", "run_config.yaml",
              "execution_contract.json", "execution.json", "input_manifest.json", "pose_evaluation_protocol.json", "output_review.json", "evaluation_details.json",
              "evaluation_summary.json", "inference_log.txt", "gpu_memory.csv", "status.json", "figure_review.json",
              "native_hydra_config.yaml", "native_hydra_overrides.yaml", "depth_diagnostics/manifest.csv", "depth_diagnostics/native_refinement_iterations.jsonl", "global_alignment_camera_diagnostic/rigid_check.json",
              "global_alignment_camera_diagnostic/native_cams_T_world.npy", "refined_intrinsics.csv", "motion_decomposition/derived/forward_output_manifest.csv")]
    for name in ("endpoint_diagnostic.json", "adjacent_pair_error_diagnostic.csv"):
        if (out / name).exists():
            files.append(out / name)
    source = json.loads((reports / "ba_track_source_snapshot.json").read_text(encoding="utf-8"))
    source_proof = json.loads((reports / "ba_track_executed_source_verification.json").read_text(encoding="utf-8"))
    if source_proof["status"] != "EXECUTED_SOURCE_RECONSTRUCTION_VERIFIED" or not source_proof["all_members_match_frozen_archive"]:
        raise ValueError("Executed source / frozen archive proof did not pass")
    if sha256(Path(source["archive"])) != source["sha256"]:
        raise ValueError("Source archive changed")
    record = {**run_metadata(), "status": "E9_PRIMARY_POSE_EVALUATION_AND_FIGURE_QA_COMPLETED_WITH_DENSE_CAMERA_LIMIT",
              "directory": str(out), "canonical_frames": 100, "native_refined_depth_maps": len(depths),
              "files": [{"file": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in files],
              "figures": qa, "frozen_source_archive": {key: source[key] for key in ("archive", "sha256", "compatibility_commit", "patch_sha256")},
              "executed_source_byte_verification": str(reports / "ba_track_executed_source_verification.json"),
              "dense_camera_rigid_check_passed": review["global_alignment_camera_usable_as_rigid_poses"],
              "dense_camera_projection_or_normalization_applied": False,
              "primary_camera_stage": "Official sparse SLAM pose-evaluation output, fixed before MVS execution/GT scoring",
              "not_a_paper_score_match": True, "independent_object_motion_accuracy_claim": False,
              "model_inference_reexecuted_by_this_finalizer": False}
    write_json(out / "final_evidence_manifest.json", record)
    write_json(reports / "ba_track_mvs_delivery.json", record)
    print(json.dumps({"status": record["status"], "directory": str(out), "frames": 100, "native_depth_maps": len(depths)}))


if __name__ == "__main__":
    main()

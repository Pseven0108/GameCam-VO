"""Index an accepted native run after explicit figure QA; no inference replay."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path

import numpy as np

from gamecam_vo.common import PROJECT, run_metadata, sha256, write_json
from gamecam_vo.evaluation import load_trajectory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    if not out.is_relative_to(PROJECT / "results/E10_PI3MOS"):
        raise ValueError("Owned native result required")
    review = json.loads((out / "output_review.json").read_text(encoding="utf-8"))
    qa = json.loads((out / "figure_review.json").read_text(encoding="utf-8"))
    if review["status"] != "PI3MOS_OUTPUTS_SANITY_CHECKED" or not review["figures_visually_reviewed"] or qa["status"] != "VISUALLY_REVIEWED_PASS":
        raise RuntimeError("Complete native numerical review and explicit visual inspection first")
    for row in qa["files"]:
        if sha256(out / row["file"]) != row["sha256"]:
            raise ValueError("A reviewed figure changed")
    times, poses = load_trajectory(out / "estimated_trajectory.csv")
    txt_times, txt_poses = load_trajectory(out / "estimated_trajectory.txt")
    if len(times) != review["expected_frames"] or not np.array_equal(times, np.arange(len(times))) or not np.isfinite(poses).all():
        raise ValueError("Accepted camera support changed")
    np.testing.assert_array_equal(times, txt_times)
    np.testing.assert_allclose(poses, txt_poses, atol=1e-9, rtol=1e-9)
    if sha256(out / "estimated_trajectory.csv") != review["trajectory_sha256"]:
        raise ValueError("The accepted primary trajectory changed")
    source = json.loads((out / "executed_source_verification.json").read_text(encoding="utf-8"))
    if source["status"] != "EXECUTED_SOURCE_RECONSTRUCTION_VERIFIED" or Path(source["run"]).resolve() != out:
        raise ValueError("A source reconstruction bound to this actual run is required")
    if sha256(out / "source_changes_from_upstream.patch") != source["executed_patch_sha256"]:
        raise ValueError("The verified executed source patch changed")
    files = ["estimated_trajectory.csv", "estimated_trajectory.txt", "native_full_trajectory_tum.txt", "native_poses_T_wc_xyzw.npy", "native_timestamps.npy",
             "native_final_keyframes.npz", "coordinate_consistency.json", "tracking_status.csv", "input_manifest.json", "input_calibration.txt",
             "native_resolved_config.yaml", "native_prior_map_manifest.csv", "execution_contract.json", "inference_log.txt", "gpu_memory.csv", "process.json",
             "status.json", "output_review.json", "figure_review.json", "raw_initialization/manifest.jsonl", "native_prior_outputs/manifest.jsonl",
             "native_run_completed.json", "source_changes_from_upstream.patch", "executed_source_verification.json",
             "run_pi3mos_pipeline.py.executed_source", "run_pi3mos_reviewed_entrypoint.py.executed_source", "sitecustomize.py.executed_source"]
    if review["target"] == "mvs":
        files += ["metrics.csv", "evaluation_details.json", "evaluation_summary.json"]
    manual = json.loads((PROJECT / "reports/SOTA/pi3mos_manual_checkpoint.json").read_text(encoding="utf-8"))
    record = {**run_metadata(), "status": "PI3MOS_NATIVE_EXPORT_AND_FIGURE_QA_COMPLETED", "directory": str(out),
              "target": review["target"], "canonical_frames": len(times), "native_prior_maps": review["native_prior_maps_exported"],
              "files": [{"file": str(out / file), "bytes": (out / file).stat().st_size, "sha256": sha256(out / file)} for file in files],
              "figure_review": qa, "core_checkpoint_bytes": manual["bytes"], "core_checkpoint_sha256": manual["sha256"],
              "executed_source_files_verified": source["files_checked"], "source_verification_scope": source["scope"],
              "core_publisher_digest": "UNKNOWN", "not_a_paper_score_match": True,
              "dynamic_segmentation_accuracy_claim": False, "model_inference_reexecuted_by_this_finalizer": False}
    write_json(out / "final_evidence_manifest.json", record)
    pointer = "pi3mos_official_demo_delivery.json" if review["target"] == "official-demo" else "pi3mos_mvs_delivery.json"
    write_json(PROJECT / "reports/SOTA" / pointer, record)
    print(json.dumps({k: record[k] for k in ("status", "target", "canonical_frames", "native_prior_maps")}))


if __name__ == "__main__":
    main()

"""Separate calibration-interpretation diagnostic; never overwrites the primary."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path
import shutil

from gamecam_vo.common import PROJECT, sha256, write_csv, write_json
from gamecam_vo.evaluation import load_trajectory
from phase5_motion_support import read, local
from phase5_partial_reference import evaluate_partial_reference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--reference-pointer", type=Path, required=True)
    args = parser.parse_args()
    out = args.directory.resolve()
    if not out.is_relative_to(PROJECT / "results/E16_BONN"):
        raise ValueError("Owned new Bonn result required")
    primary_file = out / "evaluation_summary.json"
    primary_sha = sha256(primary_file)
    primary = read(primary_file)
    reference = read(args.reference_pointer)
    gt_file = local(reference["calibration_interpretation_reference"])
    if sha256(gt_file) != reference["calibration_interpretation_reference_sha256"]:
        raise ValueError("Pre-score diagnostic reference changed")
    destination = out / "calibration_interpretation_diagnostic"
    destination.mkdir(exist_ok=False)
    # Later figure-QA annotations may update the live summary. Bind this exact
    # input snapshot so the diagnostic's source identity remains checkable.
    primary_snapshot = destination / "primary_evaluation.snapshot.json"
    shutil.copy2(primary_file, primary_snapshot)
    times, estimated = load_trajectory(out / "estimated_trajectory.csv")
    gt_keys, gt = load_trajectory(gt_file)
    status = read(out / "status.json")
    rows, details = evaluate_partial_reference(gt_keys, gt, times, estimated, unit=reference["calibration_interpretation_unit"],
        seconds=status["wall_seconds"], rotation_metrics_valid=True)
    for row in rows:
        row.update(method=primary["method"], sequence=reference["sequence"], GT_provenance="MOCAP_GROUND_TRUTH",
            interpretation="Rigid polar Tm with exact marker translation, no nonrigid first-matrix inverse",
            reference_is_primary=False, score_convention_selected_by_better_accuracy=False)
    write_csv(destination / "diagnostic_metrics.csv", rows)
    write_json(destination / "diagnostic_details.json", details)
    report = {"status": "SEPARATE_BONN_CALIBRATION_INTERPRETATION_DIAGNOSTIC", "primary_evaluation_sha256": primary_sha,
        "primary_evaluation_snapshot": str(primary_snapshot),
        "reference": str(gt_file), "reference_sha256": sha256(gt_file), "metrics": rows,
        "not_pooled_with_primary": True, "coordinate_convention_selected_by_score": False, "no_new_model_execution": True}
    write_json(destination / "diagnostic_summary.json", report)
    if sha256(primary_file) != primary_sha:
        raise ValueError("Primary evaluation unexpectedly changed")
    print(json.dumps({"status": report["status"], "directory": str(destination)}))


if __name__ == "__main__":
    main()

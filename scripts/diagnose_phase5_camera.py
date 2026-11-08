"""Locate camera-error concentration on accepted new runs; no motion-label claim."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, sha256, write_csv, write_json
from gamecam_vo.evaluation import load_trajectory
from gamecam_vo.geometry import invert_se3
from phase5_motion_support import read, local


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--reference-pointer", type=Path, required=True)
    args = parser.parse_args()
    out = args.directory.resolve()
    if not any(out.is_relative_to(PROJECT / "results" / name) for name in ("E14_WILD_DYNAMIC", "E15_MOVIE", "E16_BONN")):
        raise ValueError("Only owned new accepted phase5 cameras are analyzed")
    destination = out / "camera_error_diagnostic"
    destination.mkdir(exist_ok=False)
    evaluation = read(out / "evaluation_summary.json")
    shutil.copy2(out / "evaluation_summary.json", destination / "evaluation_summary.snapshot.json")
    if evaluation["status"] != "PHASE5_EXTERNAL_CAMERA_EVALUATION_COMPLETED":
        raise ValueError("Native export/direction/support must pass first")
    pointer = read(args.reference_pointer)
    reference = local(pointer["reference"])
    if sha256(reference) != pointer["reference_sha256"]:
        raise ValueError("Frozen independent reference changed")
    gt_keys, gt = load_trajectory(reference)
    input_keys, camera = load_trajectory(out / "estimated_trajectory.csv")
    if not np.array_equal(input_keys, np.arange(len(camera))) or not np.array_equal(gt_keys, gt_keys.astype(int)):
        raise ValueError("Expected exact independently associated sample keys")
    keys = gt_keys.astype(int)
    details = read(out / "evaluation_details.json")
    inputs = read(out / "input_manifest.json")
    clock = np.array([row.get("native_RGB_timestamp_seconds", row.get("timestamp_seconds")) for row in inputs["frames"]], float)
    if len(clock) != len(camera) or not np.isfinite(clock).all() or (np.diff(clock) < 0).any():
        raise ValueError("Retained physical input clock unavailable; never replace it by frame-index velocities")
    report = {"status": "ACCEPTED_CAMERA_ERROR_CONCENTRATION_DIAGNOSTIC", "GT_provenance": evaluation["GT_provenance"],
        "full_input_frames": len(camera), "GT_associated_frames": len(keys), "source_evaluation_sha256": sha256(out / "evaluation_summary.json"),
        "source_evaluation_snapshot": str(destination / "evaluation_summary.snapshot.json"),
        "source_reference_sha256": sha256(reference), "duplicate_clock_pairs_retained": np.flatnonzero(np.diff(clock) == 0).tolist(),
        "camera_speed_does_not_label_dynamic_objects": True, "game_specific_failure_claim": False, "alignments": []}
    for metric in evaluation["metrics"]:
        kind = metric["alignment"]
        if metric["status"] not in ("COMPUTED", "COMPUTED_DIAGNOSTIC"):
            continue
        alignment = details.get("alignments", {}).get(kind)
        if alignment is None and kind == "orientation_anchored_Sim3_diagnostic":
            alignment = details["orientation_anchored_diagnostic"]["alignment"]
        if alignment is None:
            raise ValueError("Accepted metric has no declared gauge transform")
        rotation, translation = np.asarray(alignment["rotation"]), np.asarray(alignment["translation"])
        aligned = camera.copy()
        aligned[:, :3, :3] = rotation @ camera[:, :3, :3]
        aligned[:, :3, 3] = alignment["scale"]*(camera[:, :3, 3] @ rotation.T)+translation
        ate = np.linalg.norm(aligned[keys, :3, 3]-gt[:, :3, 3], axis=1)
        if abs(np.sqrt(np.mean(ate**2))-metric["ATE_RMSE"]) > 1e-8:
            raise ValueError("Per-frame diagnostic does not reproduce the accepted ATE")
        pose_file = destination / (kind+"_per_GT_frame.csv")
        write_csv(pose_file, [{"sample_key": int(key), "physical_timestamp_seconds": float(clock[key]), "aligned_position_residual": float(error)} for key, error in zip(keys, ate, strict=True)])
        pair_rows = []
        if metric["RPE_translation_RMSE"] is not None and metric["RPE_rotation_RMSE_degrees"] is not None:
            for index in np.flatnonzero(np.diff(keys) == 1):
                first, second = int(keys[index]), int(keys[index+1])
                gt_delta = invert_se3(gt[index]) @ gt[index+1]
                pred_delta = invert_se3(aligned[first]) @ aligned[second]
                error = invert_se3(gt_delta) @ pred_delta
                dt = float(clock[second]-clock[first])
                pair_rows.append({"first_input_key": first, "second_input_key": second, "physical_dt_seconds": dt, "zero_dt_pair": dt == 0,
                    "RPE_translation": float(np.linalg.norm(error[:3, 3])), "RPE_rotation_degrees": float(np.degrees(Rotation.from_matrix(error[:3, :3]).magnitude())),
                    "GT_camera_translation_speed": float(np.linalg.norm(gt[index+1, :3, 3]-gt[index, :3, 3])/dt) if dt > 0 else None,
                    "GT_camera_angular_speed_degrees_per_second": float(np.degrees(Rotation.from_matrix(gt_delta[:3, :3]).magnitude())/dt) if dt > 0 else None})
            for field, expected in (("RPE_translation", metric["RPE_translation_RMSE"]), ("RPE_rotation_degrees", metric["RPE_rotation_RMSE_degrees"])):
                values = np.array([r[field] for r in pair_rows])
                if values.size and abs(np.sqrt(np.mean(values**2))-expected) > 1e-8:
                    raise ValueError("Adjacent-pair diagnostic differs from accepted RPE")
        pair_file = destination / (kind+"_adjacent_pairs.csv")
        write_csv(pair_file, pair_rows)
        result = {"alignment": kind, "ATE_RMSE": metric["ATE_RMSE"], "maximum_position_residual": float(ate.max()),
            "maximum_position_residual_input_key": int(keys[np.argmax(ate)]), "GT_adjacent_pairs": len(pair_rows),
            "per_frame_file": str(pose_file), "per_frame_sha256": sha256(pose_file), "per_pair_file": str(pair_file), "per_pair_sha256": sha256(pair_file)}
        for label, field in (("translation", "RPE_translation"), ("rotation", "RPE_rotation_degrees")):
            values = np.array([row[field] for row in pair_rows])
            if len(values):
                squares = values**2
                peak = int(np.argmax(values))
                tail = next((i for i, r in enumerate(pair_rows) if r["first_input_key"] == len(camera)-2 and r["second_input_key"] == len(camera)-1), None)
                result[label] = {"largest_pair": [pair_rows[peak]["first_input_key"], pair_rows[peak]["second_input_key"]],
                    "largest_pair_error": float(values[peak]), "largest_pair_squared_error_fraction": float(squares[peak]/squares.sum()) if squares.sum() else None,
                    "last_input_pair_error": float(values[tail]) if tail is not None else None,
                    "last_input_pair_squared_error_fraction": float(squares[tail]/squares.sum()) if tail is not None and squares.sum() else None,
                    "zero_dt_pairs_excluded_from_speed_but_retained_in_RPE": sum(r["zero_dt_pair"] for r in pair_rows)}
        report["alignments"].append(result)
    write_json(destination / "diagnostic.json", report)
    print(json.dumps({"directory": str(destination), "alignments": [{"alignment": r["alignment"], "translation": r.get("translation"), "rotation": r.get("rotation")} for r in report["alignments"]]}))


if __name__ == "__main__":
    main()

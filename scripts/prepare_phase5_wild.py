"""Freeze all tracking RGB/K and a separately timestamp-associated MoCap reference."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from gamecam_vo.common import PROJECT, POSE_COLUMNS, make_run_dir, sha256, write_csv, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sequence", choices=("person_tracking", "crowd", "racket"))
    args = parser.parse_args()
    report = PROJECT / "reports/PHASE5"
    acquired = json.loads((report / ("wild_"+args.sequence+"_data.json")).read_text(encoding="utf-8"))
    if not acquired["status"].startswith("VERIFIED_PUBLISHED_"):
        raise RuntimeError("Actual acquired package and physical clocks must pass before preparation")
    pointer = report / ("wild_"+args.sequence+"_input.json")
    if pointer.exists():
        raise RuntimeError("A frozen view already exists; inspect it instead of silently creating another")
    source = Path(acquired["directory"])
    originals = json.loads(Path(acquired["RGB_manifest"]).read_text(encoding="utf-8"))
    gt = np.loadtxt(source / "groundtruth.txt", ndmin=2)
    color = json.loads((source / "intrinsics.json").read_text())["color"]
    original_K = np.array([[color["fx"], 0, color["ppx"]], [0, color["fy"], color["ppy"]], [0, 0, 1.]])
    sx, sy = 400 / color["width"], 240 / color["height"]
    transform = np.array([[sx, 0, .5*sx-.5], [0, sy, .5*sy-.5], [0, 0, 1.]])
    matrix = transform @ original_K
    out = make_run_dir(PROJECT / "data/phase5_inputs/Wild_SLAM_Mocap" / args.sequence, "RGB_K_only_400x240")
    (out / "rgb").mkdir()
    external = make_run_dir(PROJECT / "results/E14_WILD_DYNAMIC/data_validation" / args.sequence, "published_clock_association")
    mapx, mapy = cv2.initUndistortRectifyMap(original_K, np.asarray(color["coeffs"]), np.eye(3), matrix, (400, 240), cv2.CV_32FC1)
    frames, associations, pose_rows = [], [], []
    for i, row in enumerate(originals):
        image = Path(row["path"])
        if sha256(image) != row["sha256"]:
            raise ValueError("Native tracking RGB changed")
        rgb = cv2.imread(str(image))
        if rgb is None or rgb.shape[:2] != (color["height"], color["width"]):
            raise ValueError("An original RGB frame is corrupt or has unexpected dimensions")
        output = out / "rgb" / f"frame_{i:05d}.png"
        if not cv2.imwrite(str(output), cv2.remap(rgb, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)):
            raise IOError("Prepared RGB was not written")
        timestamp = row["timestamp_seconds"]
        differences = np.abs(gt[:, 0]-timestamp)
        selected = int(np.argmin(differences))
        if differences[selected] >= .08:
            raise ValueError("Official nearest-time association gate failed; never replace it with row order")
        ties = np.flatnonzero(differences == differences[selected]).tolist()
        associations.append({"sample_key": i, "RGB_timestamp_seconds": timestamp, "GT_timestamp_seconds": gt[selected, 0],
            "absolute_clock_difference_seconds": differences[selected], "GT_row_index": selected, "equal_distance_GT_rows": json.dumps(ties),
            "official_tie_break": "first np.argmin, exactly the published WildGS TUM_RGBD.associate_frames rule"})
        pose_rows.append(dict(zip(POSE_COLUMNS, [i, *map(float, gt[selected, 1:])], strict=True)))
        frames.append({"frame_index": i, "sample_key": i, "native_RGB_timestamp_seconds": timestamp,
            "path": str(output), "wsl_path": "/mnt/d/"+output.as_posix()[3:], "sha256": sha256(output), "original_RGB_sha256": row["sha256"]})
    reference = external / "reference_trajectory.csv"
    write_csv(reference, pose_rows, POSE_COLUMNS)
    write_csv(external / "physical_clock_association.csv", associations)
    write_json(external / "sync_review.json", {"status": "PUBLISHED_PHYSICAL_CLOCK_ASSOCIATION_FROZEN_BEFORE_ANY_MODEL_SCORE",
        "all_frames_retained": len(frames), "GT_provenance": "MOCAP_GROUND_TRUTH", "unit": "meter",
        "GT_source_sha256": sha256(source / "groundtruth.txt"), "reference_sha256": sha256(reference),
        "basis": "Nearest association of published physical timestamps, with explicit first-argmin tie break; never frame-index pose matching",
        "sample_keys": "Unique bookkeeping indices are assigned only after physical-time association; they do not replace a camera clock",
        "native_timestamp_ties": acquired["timestamp_tie_diagnostic"], "max_clock_difference_seconds": max(a["absolute_clock_difference_seconds"] for a in associations),
        "zero_dt_pair_interpretation": "Duplicate RGB records and ambiguous published GT retained. Adjacent-sample RPE is not an angular/linear velocity at zero dt.",
        "no_additional_clock_offset_or_GT_interpolation": True,
        "synchronization_source": "https://arxiv.org/html/2504.03886v1#S6; release GT already uses camera timestamps; raw120Hz recordings and per-recording offsets are not separately exposed in these selected ZIPs",
        "pose_source": "Official src/utils/datasets.py TUM_RGBD.pose_matrix_from_quaternion treats published XYZW as T_wc; Bonn-specific transform is not applied to Wild-SLAM",
        "score_selection_used": False})
    inputs = {"dataset": "Wild-SLAM MoCap", "sequence_id": args.sequence, "width": 400, "height": 240,
        "fixed_K": matrix.tolist(), "original_K": original_K.tolist(), "frames": frames, "inference_inputs": ["RGB", "camera_intrinsics"],
        "physical_clock_preserved_per_frame": True, "model_time_axis": "associated_sample_key_after_physical_clock_validation",
        "preprocessing": "One cv2.remap: original distortion removed, half-pixel400x240 intrinsic scaling. Identical frozen prepared RGB/K for all methods; no GT/depth inputs.",
        "original_distortion": color["coeffs"], "GT_or_depth_in_this_input_view": False, "full_frame_count_preserved": True}
    write_json(out / "input_manifest.json", inputs)
    np.savetxt(out / "calibration.txt", [[matrix[0, 0], matrix[1, 1], matrix[0, 2], matrix[1, 2]]], fmt="%.18g")
    record = {"status": "PHASE5_FROZEN_RGB_K_AND_EXTERNAL_CLOCK_ASSOCIATION_READY", "dataset": inputs["dataset"], "sequence": args.sequence,
        "directory": str(out), "external_validation_directory": str(external), "reference": str(reference), "reference_sha256": sha256(reference),
        "expected_frames": len(frames), "width": 400, "height": 240, "GT_provenance": "MOCAP_GROUND_TRUTH", "unit": "meter",
        "max_clock_difference_seconds": max(a["absolute_clock_difference_seconds"] for a in associations), "timestamp_tie_diagnostic": acquired["timestamp_tie_diagnostic"]}
    write_json(pointer, record)
    print(json.dumps(record))


if __name__ == "__main__":
    main()

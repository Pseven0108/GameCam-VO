"""Freeze full Bonn RGB/K and clock-associated camera references separately."""
from __future__ import annotations

import _bootstrap
import argparse
from datetime import datetime, timezone
import json

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gamecam_vo.common import PROJECT, POSE_COLUMNS, sha256, write_csv, write_json
from gamecam_vo.geometry import poses_to_rows
from phase5_motion_support import local, read
from phase5_bonn_geometry import convert_bonn_gt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sequence", choices=("person_tracking", "crowd", "moving_obstructing_box"))
    args = parser.parse_args()
    reports = PROJECT / "reports/PHASE5"
    acquired = read(reports / ("bonn_"+args.sequence+"_data.json"))
    if acquired["status"] != "BONN_ONE_OFFICIAL_ZIP_CRC_AND_LOCAL_SHA_VERIFIED":
        raise ValueError("Official acquired native package must pass before preparation")
    pointer = reports / ("bonn_"+args.sequence+"_input.json")
    if pointer.exists():
        raise FileExistsError("Reference already frozen; never relabel after model scores")
    source = local(acquired["directory"])
    originals, depths = read(local(acquired["RGB_manifest"])), read(local(acquired["Depth_manifest"]))
    gt_file = source / "groundtruth.txt"
    if sha256(gt_file) != acquired["groundtruth_txt_sha256"]:
        raise ValueError("Native MoCap file changed")
    gt = np.loadtxt(gt_file, ndmin=2)
    times = np.array([row["timestamp_seconds"] for row in originals])
    selected, associations = [], []
    for index, timestamp in enumerate(times):
        differences = np.abs(gt[:, 0]-timestamp)
        match = int(np.argmin(differences))
        accepted = bool(differences[match] <= .02)
        selected.append(match if accepted else -1)
        associations.append({"sample_key": index, "RGB_timestamp_seconds": timestamp, "nearest_GT_timestamp_seconds": gt[match, 0],
            "absolute_clock_difference_seconds": differences[match], "GT_row_index": match if accepted else None, "GT_associated": accepted,
            "equal_distance_GT_rows": json.dumps(np.flatnonzero(differences == differences[match]).tolist()), "tie_rule": "first np.argmin, frozen before scores"})
    keys = np.flatnonzero(np.asarray(selected) >= 0)
    if len(keys) < 3:
        raise ValueError("Too little physical-time associated GT; retain all RGB and audit clocks")
    primary_all, normalized, exact, diagnostic_all, coordinate_review = convert_bonn_gt(gt[:, 1:], selected[int(keys[0])])
    selected_gt = np.asarray(selected)[keys]
    primary, diagnostic = primary_all[selected_gt], diagnostic_all[selected_gt]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    sequence = "bonn_"+args.sequence
    inputs = PROJECT / "data/phase5_inputs/Bonn" / sequence / (stamp+"_RGB_K_only_320x240")
    validation = PROJECT / "results/E16_BONN/data_validation" / sequence / stamp
    inputs.mkdir(parents=True, exist_ok=False); (inputs / "rgb").mkdir()
    validation.mkdir(parents=True, exist_ok=False)
    native_k = np.array([[542.822841, 0., 315.593520], [0., 542.576870, 237.756098], [0., 0., 1.]])
    distortion = np.array([.039903, -.099343, -.000730, -.000144, 0.])
    transform = np.array([[.5, 0., -.25], [0., .5, -.25], [0., 0., 1.]])
    k = transform @ native_k
    mapx, mapy = cv2.initUndistortRectifyMap(native_k, distortion, np.eye(3), k, (320, 240), cv2.CV_32FC1)
    frames = []
    for index, row in enumerate(originals):
        image_file = local(row["path"])
        if sha256(image_file) != row["sha256"]:
            raise ValueError("Native RGB bytes changed")
        image = cv2.imread(str(image_file))
        if image is None or image.shape != (480, 640, 3):
            raise ValueError("Corrupt/unexpected original RGB; do not silently drop it")
        target = inputs / "rgb" / f"frame_{index:06d}.png"
        if not cv2.imwrite(str(target), cv2.remap(image, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)):
            raise IOError("Common prepared RGB write failed")
        frames.append({"frame_index": index, "sample_key": index, "native_RGB_timestamp_seconds": row["timestamp_seconds"],
            "path": str(target), "sha256": sha256(target), "original_RGB_sha256": row["sha256"]})
    manifest = {"dataset": "Bonn RGB-D Dynamic", "sequence_id": sequence, "width": 320, "height": 240, "fixed_K": k.tolist(), "original_K": native_k.tolist(),
        "original_distortion": distortion.tolist(), "frames": frames, "inference_inputs": ["RGB", "camera_intrinsics"], "full_frame_count_preserved": True,
        "preprocessing": "One common cv2.remap, native distortion removed, half-pixel 0.5 scaling; full 4:3 view, no temporal subsampling",
        "GT_or_sensor_depth_in_this_input_view": False, "physical_clock_preserved_per_frame": True}
    write_json(inputs / "input_manifest.json", manifest)
    reference, diagnostic_ref = validation / "reference_trajectory.csv", validation / "rigid_calibration_interpretation_reference.csv"
    write_csv(reference, poses_to_rows(keys, primary), POSE_COLUMNS)
    write_csv(diagnostic_ref, poses_to_rows(keys, diagnostic), POSE_COLUMNS)
    write_csv(validation / "physical_clock_association.csv", associations)
    np.savez_compressed(validation / "exact_official_transform_matrices.npz", raw_GT_xyzw=gt, all_official_composed_matrices=exact,
        all_official_first_associated_normalized_matrices=normalized, associated_RGB_sample_keys=keys, associated_raw_GT_rows=selected_gt)
    review = {"status": "BONN_FULL_RGB_AND_EXTERNAL_PHYSICAL_CLOCK_GT_FROZEN", "sequence": sequence, "GT_provenance": "MOCAP_GROUND_TRUTH",
        "full_input_frames": len(frames), "GT_associated_frames": len(keys), "GT_unmatched_RGB_keys": np.flatnonzero(np.asarray(selected) < 0).tolist(),
        "GT_association_max_dt_seconds": .02, "additional_clock_offset_seconds": 0., "GT_interpolation_applied": False,
        "association_is_physical_time_not_row_order": True, "RGB_clock_duplicate_pairs": np.flatnonzero(np.diff(times) == 0).tolist(),
        "maximum_accepted_clock_difference_seconds": max(associations[int(i)]["absolute_clock_difference_seconds"] for i in keys),
        "coordinate_conversion": coordinate_review, "reference_sha256": sha256(reference), "diagnostic_reference_sha256": sha256(diagnostic_ref),
        "official_transform_source_sha256": sha256(PROJECT / "logs/PHASE5/bonn_source_audit/compute_global_transformation.py"),
        "protocol_sha256": sha256(PROJECT / "docs/PHASE5_BONN_protocol.md"), "input_manifest_sha256": sha256(inputs / "input_manifest.json"),
        "depth_and_reference_excluded_from_model_view": True, "pixel_motion_or_skeleton_GT": False, "model_predictions_used_in_GT_preparation": False,
        "figures_reviewed_at_reference_freeze": False, "subsequent_figure_QA_record": "Separate figure_review.json; frozen GT audit identity is not changed by visual review"}
    write_json(validation / "GT_audit.json", review)
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False}):
        picks = sorted(set((0, len(frames)//2, len(frames)-1)))
        fig, axes = plt.subplots(2, len(picks), figsize=(12, 6), layout="constrained", squeeze=False)
        depth_times = np.array([r["timestamp_seconds"] for r in depths])
        for column, index in enumerate(picks):
            image = cv2.cvtColor(cv2.imread(str(local(originals[index]["path"]))), cv2.COLOR_BGR2RGB)
            depth_index = int(np.argmin(np.abs(depth_times-times[index])))
            depth = cv2.imread(str(local(depths[depth_index]["path"])), cv2.IMREAD_UNCHANGED)
            if depth is None or depth.dtype != np.uint16:
                raise ValueError("Native sensor depth audit decoding failed")
            axes[0, column].imshow(image); axes[0, column].set_title(f"RGB {index} / native 640x480")
            im = axes[1, column].imshow(depth, cmap="viridis", vmin=0, vmax=float(np.quantile(depth[depth > 0], .98)))
            fig.colorbar(im, ax=axes[1, column], fraction=.045, label="Native uint16 depth counts")
            axes[1, column].set_title(f"Sensor depth / time delta {abs(depth_times[depth_index]-times[index]):.4f}s")
            for row in axes:
                row[column].set_xticks([]); row[column].set_yticks([])
        fig.suptitle(f"Bonn / {args.sequence} / first, middle, last native samples\nRGB-only model view is separately rectified to 320x240; sensor depth shown for data audit only", fontsize=11)
        for suffix in ("png", "svg"):
            fig.savefig(validation / ("native_RGB_depth_audit."+suffix), dpi=160)
        plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
        axes[0].plot(np.arange(len(frames)), [r["absolute_clock_difference_seconds"] for r in associations], lw=.8, color="#275c8a")
        axes[0].axhline(.02, ls="--", color="#ae563a", label="Frozen association tolerance")
        axes[0].set(xlabel="Full RGB sample key", ylabel="Nearest RGB/GT clock difference [s]", title=f"a  GT support {len(keys)}/{len(frames)}; all RGB kept")
        axes[0].legend(frameon=False)
        axes[1].plot(primary[:, 0, 3], primary[:, 1, 3], color="#275c8a", lw=1)
        axes[1].set(xlabel="X [Bonn official transform unit]", ylabel="Y [Bonn official transform unit]", title="b  Independently transformed MoCap camera")
        axes[1].set_aspect("equal", adjustable="datalim")
        for ax in axes:
            ax.grid(alpha=.15)
        fig.suptitle("Published physical timestamps and declared native affine calibration; no prediction used", fontsize=11)
        for suffix in ("png", "svg"):
            fig.savefig(validation / ("clock_and_GT_audit."+suffix), dpi=180)
        plt.close(fig)
    record = {"status": "PHASE5_FROZEN_RGB_K_AND_EXTERNAL_BONN_GT_READY", "dataset": manifest["dataset"], "sequence": sequence,
        "directory": str(inputs), "external_validation_directory": str(validation), "reference": str(reference), "reference_sha256": sha256(reference),
        "expected_frames": len(frames), "GT_associated_sample_keys": keys.tolist(), "GT_associated_frames": len(keys), "width": 320, "height": 240,
        "GT_provenance": "MOCAP_GROUND_TRUTH", "unit": "Bonn_official_transform_unit", "rotation_metrics_valid": coordinate_review["rotation_metrics_valid"],
        "GT_audit_sha256": sha256(validation / "GT_audit.json"), "calibration_interpretation_reference": str(diagnostic_ref),
        "calibration_interpretation_reference_sha256": sha256(diagnostic_ref), "calibration_interpretation_unit": "raw_MoCap_translation_unit"}
    write_json(pointer, record)
    print(json.dumps({key: record[key] for key in ("status", "sequence", "expected_frames", "GT_associated_frames", "rotation_metrics_valid")}))


if __name__ == "__main__":
    main()

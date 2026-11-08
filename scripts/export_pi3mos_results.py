"""CPU-side export of native Pi3MOS poses and observed learned priors; no GT."""
from __future__ import annotations

import _bootstrap
import argparse
import csv
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, POSE_COLUMNS, sha256, write_csv, write_json
from gamecam_vo.evaluation import load_trajectory
from gamecam_vo.geometry import rows_to_poses
from gamecam_vo.plotting import plot_trajectory


def local(value):
    return Path(str(value).replace("/mnt/d/", "D:/", 1)).resolve()


def json_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--phase5", action="store_true", help="Export only owned new phase5 results; never update phase4 pointers")
    args = parser.parse_args()
    out = args.directory.resolve()
    roots = [PROJECT / "results" / name / "PI3MOS" for name in ("E14_WILD_DYNAMIC", "E15_MOVIE", "E16_BONN")] if args.phase5 else [PROJECT / "results/E10_PI3MOS"]
    if not any(out.is_relative_to(root) for root in roots):
        raise ValueError("Owned Pi3MOS result required")
    status = json.loads((out / "status.json").read_text(encoding="utf-8"))
    if status["status"] != "PI3MOS_INFERENCE_COMPLETED":
        raise RuntimeError("Native inference must complete before output acceptance")
    contract = json.loads((out / "execution_contract.json").read_text(encoding="utf-8"))
    inputs = json.loads((out / "input_manifest.json").read_text(encoding="utf-8"))
    expected = contract["expected_frames"]
    raw = np.load(out / "native_poses_T_wc_xyzw.npy")
    times = np.load(out / "native_timestamps.npy")
    if raw.shape != (expected, 7) or not np.array_equal(times, np.arange(expected)) or not np.isfinite(raw).all():
        raise ValueError("Full expected ordered finite native camera poses required for this acceptance gate")
    quaternion_error = float(np.max(np.abs(np.linalg.norm(raw[:, 3:], axis=1)-1)))
    if quaternion_error > 1e-4:
        raise ValueError("Native camera quaternion norm failed; do not silently normalize")
    rows = [dict(zip(POSE_COLUMNS, [float(t), *map(float, pose)], strict=True)) for t, pose in zip(times, raw, strict=True)]
    _, poses = rows_to_poses(rows)
    native_times, native_pose_text = load_trajectory(out / "native_full_trajectory_tum.txt")
    if not np.array_equal(times, native_times) or not np.allclose(poses, native_pose_text, atol=1e-9, rtol=1e-9):
        raise ValueError("Native NumPy/TUM exports differ")
    with np.load(out / "native_final_keyframes.npz") as saved:
        kf_values, kf_indices = saved["poses_T_cw"], saved["input_frame_indices"].astype(int)
    if len(np.unique(kf_indices)) != len(kf_indices) or (kf_indices < 0).any() or (kf_indices >= expected).any():
        raise ValueError("Native final keyframe input indices are not valid and unique")
    kf_rows = [dict(zip(POSE_COLUMNS, [int(index), *map(float, pose)], strict=True)) for index, pose in zip(kf_indices, kf_values, strict=True)]
    _, kf_w2c = rows_to_poses(kf_rows)
    inverse = np.linalg.inv(kf_w2c)
    translation_error = float(np.max(np.linalg.norm(inverse[:, :3, 3]-poses[kf_indices, :3, 3], axis=1)))
    rotation_error = float(np.max(np.degrees(Rotation.from_matrix(np.swapaxes(inverse[:, :3, :3], 1, 2) @ poses[kf_indices, :3, :3]).magnitude())))
    if translation_error > 1e-4 or rotation_error > .01:
        raise ValueError("Native final keyframe W2C inverse disagrees with full T_wc export")
    write_csv(out / "estimated_trajectory.csv", rows, POSE_COLUMNS)
    np.savetxt(out / "estimated_trajectory.txt", np.column_stack([times, raw]), fmt="%.12g", header="Native Pi3MOS T_wc; XYZW; frame_index; learned-prior map scale")
    coordinate = {"status": "PASS", "native_terminate_direction": "T_wc: explicit inverse of internal T_cw",
                  "keyframes_compared": len(kf_indices), "max_translation_difference_map_unit": translation_error,
                  "max_rotation_difference_degrees": rotation_error, "max_native_quaternion_norm_error": quaternion_error}
    write_json(out / "coordinate_consistency.json", coordinate)
    init_calls = json_lines(out / "raw_initialization/manifest.jsonl")
    prior_calls = json_lines(out / "native_prior_outputs/manifest.jsonl")
    sources = {}
    for call in init_calls:
        if sha256(out / "raw_initialization" / call["file"]) != call["sha256"]:
            raise ValueError("Observed initialization archive changed")
        with np.load(out / "raw_initialization" / call["file"]) as values:
            points = values["local_points"][0]
            dynamic = values["dynamic_masks"].reshape(len(points), *points.shape[1:3])
            confidence = values["conf"].reshape(len(points), *points.shape[1:3])
            if len(points) != len(call["input_frame_indices"]):
                raise ValueError("Initialization model frames do not match observed real input indices")
            for i, frame in enumerate(call["input_frame_indices"]):
                sources[int(frame)] = (points[i, ..., 2].copy(), dynamic[i].copy(), confidence[i].copy(),
                                      "Raw initialization model local-Z/sigmoid/confidence; model output grid, before feature-grid resize", call["file"])
    current_rows = {int(call["current_input_index"]): call for call in prior_calls}
    masks, depth_folder = out / "dynamic_masks", out / "depth"
    masks.mkdir(exist_ok=True); depth_folder.mkdir(exist_ok=True)
    picks = sorted(set([0, expected//2, expected-1]))
    examples, records = [], []
    for frame in range(expected):
        if frame in current_rows:
            call = current_rows[frame]
            file = out / "native_prior_outputs" / call["file"]
            if sha256(file) != call["sha256"]:
                raise ValueError("Observed native prior archive changed")
            with np.load(file) as values:
                depth, dynamic, confidence = [values[key].copy() for key in ("depth_prior_fmap_current", "dynamic_probability_fmap_current", "confidence_fmap_current")]
            source, raw_file = "Native current-frame feature-grid priors used by DPVO", call["file"]
        elif frame in sources:
            depth, dynamic, confidence, source, raw_file = sources[frame]
        else:
            raise ValueError("An input has no recorded native prior; do not fabricate a map")
        if any(not np.isfinite(array).all() for array in (depth, dynamic, confidence)) or (depth <= 0).any():
            raise ValueError("Native priors are nonfinite or nonpositive; retain raw arrays for inspection")
        if dynamic.min() < -1e-6 or dynamic.max() > 1+1e-6:
            raise ValueError("Native dynamic sigmoid is outside its probability range")
        depth_file, mask_file = depth_folder / f"frame_{frame:05d}.npy", masks / f"frame_{frame:05d}.npy"
        np.save(depth_file, depth); np.save(mask_file, dynamic)
        records.append({"frame_index": frame, "native_height": depth.shape[0], "native_width": depth.shape[1], "source": source, "raw_file": raw_file,
                        "depth_sha256": sha256(depth_file), "dynamic_probability_sha256": sha256(mask_file),
                        "depth_min": float(depth.min()), "depth_median": float(np.median(depth)), "depth_max": float(depth.max()),
                        "dynamic_probability_min": float(dynamic.min()), "dynamic_probability_max": float(dynamic.max()),
                        "calibrated_probability": False, "spatial_or_temporal_interpolation_in_export": False})
        if frame in picks:
            examples.append((frame, depth, dynamic, confidence, source))
    write_csv(out / "native_prior_map_manifest.csv", records)
    (out / "tracking_visualization").mkdir(exist_ok=True)
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none"}):
        fig, axes = plt.subplots(len(examples), 4, figsize=(15, 8), squeeze=False, layout="constrained")
        for row, (frame, depth, dynamic, confidence, source) in zip(axes, examples, strict=True):
            image = cv2.cvtColor(cv2.imread(str(local(inputs["frames"][frame]["path"]))), cv2.COLOR_BGR2RGB)
            row[0].imshow(image); row[0].set_title(f"Input{frame}: original RGB\nNative inference may undistort/crop")
            for ax, value, title, cmap in zip(row[1:], (dynamic, depth, confidence), ("Native dynamic sigmoid", "Native depth prior", "Native confidence weight"), ("magma", "viridis", "cividis"), strict=True):
                lo, hi = (0, 1) if title.startswith("Native dynamic") else np.quantile(value, [.02, .98])
                im = ax.imshow(value, cmap=cmap, vmin=lo, vmax=hi)
                fig.colorbar(im, ax=ax, fraction=.045)
                ax.set_title(f"{title}\n{value.shape[1]}x{value.shape[0]} native grid")
            for ax in row:
                ax.set_xticks([]); ax.set_yticks([])
        fig.suptitle("Pi3MOS native outputs / initialization and steady-state grids differ\nUncalibrated sigmoid; depth/confidence display clipped at2-98% only; raw values retained", fontsize=11)
        fig.savefig(out / "tracking_visualization/native_prior_examples.png", dpi=170)
        fig.savefig(out / "tracking_visualization/native_prior_examples.svg")
        plt.close(fig)
    plot_trajectory(times, poses, out / "tracking_visualization", "learned_prior_map_unit", "Pi3MOS / unaligned native trajectory", "frame_index")
    frontend = json_lines(out / "frontend_frames.jsonl")
    if len(frontend) != expected or [r["input_frame_index"] for r in frontend] != list(range(expected)):
        raise ValueError("Native frontend processing does not match expected input count/order")
    write_csv(out / "tracking_status.csv", frontend)
    with (out / "gpu_memory.csv").open(encoding="utf-8", newline="") as stream:
        samples = list(csv.DictReader(stream))
    elapsed = np.array([float(r["elapsed_seconds"]) for r in samples])
    memory = np.array([float(r["whole_gpu_used_mib"]) for r in samples])
    total = np.array([float(r["whole_gpu_total_mib"]) for r in samples])
    if len(elapsed) < 2 or not np.all(np.diff(elapsed) > 0) or not np.all((memory >= 0) & (memory <= total)):
        raise ValueError("Actual GPU telemetry failed its sanity check")
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(2, 1, figsize=(10, 6), layout="constrained")
        axes[0].plot(elapsed/60, memory, color="#275c8a", lw=1)
        axes[0].axhline(total.max(), color=".4", lw=.8, ls="--")
        axes[0].set(xlabel="Native subprocess wall time (min)", ylabel="Whole GPU memory (MiB)",
                    ylim=(0, total.max()*1.08), title=f"a  Sampled whole-device peak{memory.max():.0f} MiB; other apps included")
        indices = np.arange(expected)
        axes[1].plot(indices, [r["retained_keyframes"] for r in frontend], color="#275c8a", lw=1, label="Retained native keyframes")
        axes[1].scatter(indices, np.zeros(expected), marker="|", color=".8", s=35)
        ready = np.array([r["initialized_before"] for r in frontend])
        axes[1].scatter(indices[ready], np.zeros(ready.sum()), marker="|", color="#ae563a", s=35, label="Already initialized before call")
        axes[1].set(xlabel="Input frame index", ylabel="Retained keyframes", title=f"b  Finite filled poses {expected}/{expected}; startup status is separate")
        axes[1].legend(frameon=False, fontsize=9)
        for ax in axes:
            ax.grid(alpha=.17, lw=.5)
        fig.suptitle("Pi3MOS native timing / initialization, tracking, final BA, fill and output IO; GUI omitted", fontsize=11)
        fig.savefig(out / "tracking_visualization/runtime_and_output_support.png", dpi=180)
        fig.savefig(out / "tracking_visualization/runtime_and_output_support.svg")
        plt.close(fig)
    record = {"status": "PI3MOS_OUTPUTS_SANITY_CHECKED", "directory": str(out), "target": contract["target"],
              "expected_frames": expected, "finite_filled_pose_frames": len(poses), "coordinate_check": coordinate,
              "frontend_calls": len(frontend), "initialized_before_calls": sum(r["initialized_before"] for r in frontend),
              "initialized_after_calls": sum(r["initialized_after"] for r in frontend), "native_keyframes": len(kf_indices),
              "raw_initialization_model_calls": len(init_calls), "raw_pi3_prior_calls": len(prior_calls),
              "input_indices_with_current_feature_grid_archives": sorted(current_rows),
              "input_indices_with_only_initial_model_grid_archives": sorted(set(sources)-set(current_rows)),
              "native_prior_maps_exported": len(records), "native_prior_values_finite_positive_depth_probability_in_range": True,
              "whole_gpu_memory_sample_count": len(samples), "whole_gpu_peak_used_mib_sampled": float(memory.max()),
              "prior_map_manifest_sha256": sha256(out / "native_prior_map_manifest.csv"), "trajectory_sha256": sha256(out / "estimated_trajectory.csv"),
              "time_axis": "frame_index", "units": "learned_prior_map_unit; game/metric conversion unverified",
              "GUI_omitted": True, "model_or_hyperparameters_changed": False, "GT_in_this_export": False,
              "paper_result_match": False, "figures_visually_reviewed": False}
    write_json(out / "output_review.json", record)
    if args.phase5:
        record["physical_clock_note"] = "Unique sample keys follow separately frozen physical-timestamp association; GT is not loaded by this exporter"
        write_json(out / "output_review.json", record)
        write_json(PROJECT / "reports/PHASE5" / ("pi3mos_"+out.name+"_output_review.json"), record)
    else:
        pointer = "pi3mos_official_demo_output_review.json" if contract["target"] == "official-demo" else "pi3mos_mvs_output_review.json"
        write_json(PROJECT / "reports/SOTA" / pointer, record)
    print(json.dumps({k: record[k] for k in ("status", "expected_frames", "finite_filled_pose_frames", "native_keyframes", "native_prior_maps_exported")}))


if __name__ == "__main__":
    main()

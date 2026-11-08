"""External Windows-side evaluation/export; never imported by the model process."""
from __future__ import annotations
import _bootstrap
import csv
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, POSE_COLUMNS, read_yaml, run_metadata, sha256, write_csv, write_json
from gamecam_vo.dataset_validation import check_adapter_gate
from gamecam_vo.evaluation import evaluate, load_trajectory
from gamecam_vo.geometry import poses_to_rows, rows_to_poses
from gamecam_vo.plotting import plot_comparison, plot_trajectory
from gamecam_vo.sync import match_timestamps


def local_path(value):
    value = str(value).replace("\\", "/")
    if value.startswith("/mnt/d/"):
        value = "D:/" + value[len("/mnt/d/"):]
    path = Path(value).resolve()
    if not path.is_relative_to(PROJECT):
        raise ValueError("Result path escaped project")
    return path


def export_uncertainty(out, timestamps, uncertainties, inputs, label="DROID-W / MVS0000"):
    destination = out / "uncertainty_maps"
    destination.mkdir(exist_ok=True)
    finite = uncertainties[np.isfinite(uncertainties)]
    if not len(finite):
        raise ValueError("No finite native uncertainties; cannot fabricate maps")
    low, high = np.quantile(finite, [.02, .98])
    if high-low < 1e-10:
        high = low + 1e-6
    cmap = plt.get_cmap("magma")
    records = []
    for i, (frame, raw) in enumerate(zip(timestamps, uncertainties, strict=True)):
        frame = int(frame)
        np.save(destination / f"frame_{frame:05d}.npy", raw)
        normalized = np.clip((np.nan_to_num(raw, nan=float(low), posinf=float(high), neginf=float(low))-low)/(high-low), 0, 1)
        rgb = (cmap(normalized)[..., :3]*255).astype(np.uint8)
        rgb[~np.isfinite(raw)] = 128
        image = cv2.resize(rgb, (inputs["width"], inputs["height"]), interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(str(destination / f"frame_{frame:05d}.png"), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        valid = raw[np.isfinite(raw)]
        records.append({"keyframe_index": i, "frame_index": frame, "native_grid_height": raw.shape[0], "native_grid_width": raw.shape[1],
                        "finite_fraction": float(np.isfinite(raw).mean()), "minimum": float(valid.min()) if len(valid) else None,
                        "median": float(np.median(valid)) if len(valid) else None, "maximum": float(valid.max()) if len(valid) else None,
                        "calibrated_dynamic_probability": False})
    write_csv(destination / "manifest.csv", records)
    write_json(destination / "display_policy.json", {"raw_values": "Unmodified native keyframe uncertainty arrays", "native_map_count": len(records),
               "non_keyframe_maps": "NOT_PROVIDED; no temporal interpolation", "display_low_quantile_02": float(low), "display_high_quantile_98": float(high),
               "display_resize": "Nearest-neighbor enlargement only", "dynamic_probability": False, "invalid_display_color": "gray"})
    choices = sorted(set([0, len(records)//2, len(records)-1]))
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"}):
        fig, axes = plt.subplots(len(choices), 3, figsize=(12, 2.6*len(choices)), squeeze=False, layout="constrained")
        for row, index in enumerate(choices):
            frame = int(timestamps[index])
            raw = uncertainties[index]
            image = cv2.cvtColor(cv2.imread(inputs["frames"][frame]["path"]), cv2.COLOR_BGR2RGB)
            display = cv2.resize(raw, (inputs["width"], inputs["height"]), interpolation=cv2.INTER_NEAREST)
            axes[row, 0].imshow(image)
            map_image = axes[row, 1].imshow(display, cmap="magma", vmin=low, vmax=high)
            axes[row, 2].imshow(image)
            axes[row, 2].imshow(display, cmap="magma", vmin=low, vmax=high, alpha=.5)
            for col, title in enumerate(("RGB", "Native uncertainty", "Display overlay")):
                axes[row, col].set_title(f"Frame {frame:03d} / {title}")
                axes[row, col].set_axis_off()
        fig.colorbar(map_image, ax=list(axes[:, 1]), fraction=.025, label="Raw uncertainty (display clipped at 2-98% quantiles)")
        fig.suptitle(label+": keyframe-only native uncertainty; not a dynamic probability", fontsize=12)
        fig.savefig(out / "tracking_visualization/uncertainty_examples.png", dpi=220)
        fig.savefig(out / "tracking_visualization/uncertainty_examples.svg")
        plt.close(fig)
    return records


def plot_output_support(out, telemetry, keyframe_times, expected=100, label="DROID-W / MVS0000"):
    frames = np.array([row["frame_index"] for row in telemetry])
    initialized = np.array([row["frontend_initialized"] for row in telemetry], dtype=bool)
    keyframes = np.isin(frames, np.asarray(keyframe_times, dtype=int))
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True, height_ratios=[1.4, 1], layout="constrained")
        selections = [np.ones(len(frames), dtype=bool), initialized, keyframes]
        labels = [f"Finite filled poses ({len(frames)}/{expected})", f"Frontend initialized ({initialized.sum()}/{expected})", f"Native keyframes ({keyframes.sum()}/{expected})"]
        for index, (selection, color) in enumerate(zip(selections, ["#b77946", "#356778", "#275c8a"], strict=True)):
            axes[0].scatter(frames, np.full(len(frames), index), color="#d7d7d7", marker="|", s=100)
            axes[0].scatter(frames[selection], np.full(selection.sum(), index), color=color, marker="|", s=100)
        axes[0].set(yticks=[0, 1, 2], yticklabels=labels, ylim=(-.7, 2.7), title="a  Output support and frontend evidence have different meanings")
        axes[0].invert_yaxis()
        axes[1].step(frames, [row["keyframe_count"] for row in telemetry], where="post", color="#275c8a")
        axes[1].set(xlabel="Input sample key", ylabel="Keyframes in buffer", xlim=(-1, expected), title="b  Recorded frontend keyframe count")
        axes[1].grid(alpha=.17, lw=.5)
        fig.suptitle(label+": filled poses do not expose a per-frame tracking-loss rate", fontsize=11)
        fig.savefig(out / "tracking_visualization/output_support.png", dpi=220)
        fig.savefig(out / "tracking_visualization/output_support.svg")
        plt.close(fig)


def main():
    status = json.loads((PROJECT / "reports/SOTA/droid_mvs.json").read_text())
    if status["status"] != "MVS_INFERENCE_COMPLETED":
        raise RuntimeError("No completed MVS inference; no accuracy metric will be manufactured")
    out = local_path(status["directory"])
    inputs = json.loads((out / "input_manifest.json").read_text())
    config = read_yaml(PROJECT / "configs/datasets/mvs_synth.yaml")
    e0 = Path(json.loads((PROJECT / "results/E0_MVS/latest_run.json").read_text())["directory"])
    _, validation = check_adapter_gate(e0, "0000", config)
    reference = e0 / "0000" / validation["trajectory_file"]
    gt_times, gt = load_trajectory(reference)
    predicted_file = local_path(status["trajectory_files"][-1])
    pred_times, predicted = load_trajectory(predicted_file)
    expected = np.array([r["timestamp"] for r in inputs["frames"]])
    if len(gt_times) != 100 or len(pred_times) != 100 or not np.array_equal(gt_times, expected) or not np.array_equal(pred_times, expected):
        raise ValueError("Full 100-frame correspondence failed")
    native_video = out / "upstream_output/mvs_0000/video.npz"
    with np.load(native_video) as video:
        times = video["timestamps"].copy()
        internal = video["tum_poses"].copy()
        uncertainties = video["uncertainties"].copy()
    if not np.allclose(times, np.round(times), atol=1e-6) or len(np.unique(times)) != len(times):
        raise ValueError("Invalid native keyframe timestamps")
    _, w2c = rows_to_poses([dict(zip(POSE_COLUMNS, [t, *p], strict=True)) for t, p in zip(times, internal, strict=True)])
    inverse = np.linalg.inv(w2c)
    matched, _ = match_timestamps(times, pred_times, 1e-6)
    if (matched < 0).any():
        raise ValueError("Keyframe/full-trajectory association failed")
    translation_difference = np.linalg.norm(inverse[:, :3, 3]-predicted[matched, :3, 3], axis=1)
    rotation_difference = np.rad2deg(Rotation.from_matrix(np.swapaxes(inverse[:, :3, :3], 1, 2) @ predicted[matched, :3, :3]).magnitude())
    if translation_difference.max() > 1e-4 or rotation_difference.max() > .01:
        raise ValueError("Native W2C inverse does not match final T_wc output; inspect direction before evaluation")
    coordinate_check = {"status": "PASS", "internal_direction": "world_to_camera", "export_direction": "camera_to_world",
                        "max_keyframe_inverse_translation_difference_map_units": float(translation_difference.max()),
                        "max_keyframe_inverse_rotation_difference_degrees": float(rotation_difference.max()),
                        "video_snapshot_sha256": sha256(native_video), "native_full_trajectory_sha256": sha256(predicted_file)}
    write_json(out / "coordinate_consistency.json", coordinate_check)
    rows = poses_to_rows(pred_times, predicted)
    write_csv(out / "estimated_trajectory.csv", rows, POSE_COLUMNS)
    np.savetxt(out / "estimated_trajectory.txt", np.array([[r[k] for k in POSE_COLUMNS] for r in rows]), fmt="%.12g", header="T_wc; frame_index; learned-prior map scale; not asserted metric game scale")
    metrics, details = evaluate(gt_times, gt, pred_times, predicted, tolerance=1e-6, scale_status="learned_prior_game_scale_unverified",
                                unit="native_game_unit", inference_seconds=status["wall_seconds"], time_axis="frame_index")
    telemetry = [json.loads(line) for line in (out / "frontend_frames.jsonl").read_text().splitlines()]
    if len(telemetry) != 100 or not any(r["frontend_initialized"] for r in telemetry):
        raise ValueError("Frontend processing/initialization did not complete")
    write_csv(out / "tracking_status.csv", telemetry)
    (out / "tracking_visualization").mkdir(exist_ok=True)
    map_records = export_uncertainty(out, times, uncertainties, inputs)
    plot_output_support(out, telemetry, times)
    pid = json.loads((out / "process.json").read_text())["pid"]
    allocator = [r for r in status["per_process_cuda_allocator_stats"] if r["pid"] == pid and r["cuda_initialized"]]
    for row in metrics:
        row.update(dataset="MVS-Synth", sequence_id="0000", baseline="DROID-W", method_category="online_SLAM",
                   POSE_PROVENANCE="ENGINE_GROUND_TRUTH", independent_engine_ground_truth=True,
                   experiment_variant="official_parameters_sm120_WSL_single_process" + ("_amp_weight_cache_disabled" if status.get("amp_weight_cache_disabled") else ""), expected_frames=100,
                   processed_frontend_frames=len(telemetry), initialized_frontend_frames=sum(bool(r["frontend_initialized"]) for r in telemetry),
                   pose_output_coverage=row["pose_coverage"], tracking_loss_rate=None,
                   failure_rate_semantics="Missing/nonfinite filled-pose fraction; upstream does not expose an ORB-style per-frame tracking-loss rate",
                   timing_scope="End-to-end model subprocess: initialization, tracking, final BA, trajectory fill, native output/visualization; telemetry included",
                   actual_capture_fps="UNKNOWN", runtime_device="RTX5060_WSL_torch2.7.1_cu128", keyframe_count=len(times), uncertainty_map_count=len(map_records),
                   learned_depth_prior="Metric3D_ViT_Large", feature_prior="FiT3D_DINOv2_reg_small_fine",
                   engine_depth_in_inference=False, engine_pose_in_inference=False,
                   gpu_peak_used_mib_whole_device_sampled=status["whole_gpu_peak_used_mib"],
                   gpu_peak_allocated_bytes_main_process=max((r["peak_allocated_bytes"] for r in allocator), default=None),
                   gpu_peak_reserved_bytes_main_process=max((r["peak_reserved_bytes"] for r in allocator), default=None))
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "evaluation_details.json", details)
    plot_comparison(gt_times, gt, predicted, details, out / "tracking_visualization", "native_game_unit", "MVS-Synth / 0000", True, "frame_index", "DROID-W", "Finite filled poses")
    plot_trajectory(pred_times, predicted, out / "tracking_visualization", "learned_prior_map_unit", "DROID-W / MVS0000 unaligned estimate", "frame_index")
    summary = {**run_metadata(), "status": "MVS_EXTERNAL_EVALUATION_COMPLETED", "directory": str(out), "expected_frames": 100,
               "reference_for_external_evaluation": str(reference), "reference_sha256": sha256(reference), "metrics": metrics,
               "coordinate_check": coordinate_check, "uncertainty_map_count": len(map_records), "uncertainty_finite_fraction": float(np.isfinite(uncertainties).mean()),
               "uncertainty_probability_claim": False, "dynamic_robustness_claim": False, "input_scope": "RGB + known K only",
               "ground_truth_in_model_process": False, "paper_result_match": False}
    write_json(out / "evaluation_summary.json", summary)
    write_json(PROJECT / "reports/SOTA/droid_mvs_evaluation.json", summary)
    print(json.dumps({"directory": str(out), "metrics": metrics, "keyframes": len(times)}))


if __name__ == "__main__":
    main()

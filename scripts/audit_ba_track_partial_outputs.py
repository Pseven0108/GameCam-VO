"""Review saved native forward outputs from a failed Demo; never invent poses."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_csv, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    if not out.is_relative_to(PROJECT / "results/E9_BA_TRACK"):
        raise ValueError("Expected an owned result directory")
    raw = out / "motion_decomposition/raw"
    calls = [json.loads(line) for line in (raw / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    frontend = [json.loads(line) for line in (raw.parent / "frontend_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    inputs = json.loads((out / "RGB_manifest.json").read_text(encoding="utf-8"))
    prior_rows = []
    for item in inputs:
        stem = Path(item["name"]).stem
        first = out / "depth_results/depthAny_disp_first/tennis" / (stem + ".npy")
        second = out / "depth_results/depthAny_disp/tennis" / (stem + ".npy")
        uni = out / "depth_results/unidepthv2/tennis" / (stem + ".npz")
        aligned = out / "depth_results/unidepth_dav2/tennis" / (stem + ".npy")
        a, b = np.load(first), np.load(second)
        with np.load(uni) as data:
            u, k = data["depth"].copy(), data["intrinsics"].copy()
        d = np.load(aligned)
        if not all(np.isfinite(v).all() for v in (a, b, u, k, d)) or (a < 0).any() or not (u > 0).all() or (d < 0).any():
            raise ValueError("A saved prior output failed numerical validation")
        prior_rows.append({"frame_index": item["frame_index"], "DA_first_sha256": sha256(first), "DA_second_sha256": sha256(second),
                           "DA_two_actual_runs_bitwise_equal": bool(np.array_equal(a, b)), "UniDepth_sha256": sha256(uni),
                           "aligned_predicted_depth_sha256": sha256(aligned), "all_outputs_finite": True,
                           "GT_depth_or_K_loaded_by_prior_models": False})
    derived = raw.parent / "derived"
    derived.mkdir(exist_ok=True)
    rows, last = [], None
    for call in calls:
        with np.load(raw / call["file"]) as saved:
            arrays = {name: saved[name].copy() for name in saved.files}
        if any(not np.isfinite(value).all() for value in arrays.values()):
            raise ValueError("Native output contains nonfinite values")
        total, static = arrays["total_uv"], arrays["static_uv_depth"][..., :2]
        query = arrays["queries_t_uv_depth"][..., 1:3]
        probability = arrays["dynamic_probability"]
        if total.shape != static.shape or total.shape[:3] != probability.shape or probability.min() < 0 or probability.max() > 1:
            raise ValueError("Native motion output shape or sigmoid range changed")
        total_flow = total - query[:, None]
        camera_flow = static - query[:, None]
        object_flow = total - static
        # Exact official default quantile/threshold expression. This is a
        # sparse point decision, not an interpolated dense segmentation mask.
        static_e = 1 - probability
        threshold = min(float(np.quantile(static_e, 1.)), .1)
        nonstatic = ~(static_e >= threshold)
        frame_ids = call["context"]["retained_window_input_indices"]
        real = len(frame_ids)
        if real > total.shape[1]:
            raise ValueError("Context exceeds native padded temporal output")
        destination = derived / call["file"]
        np.savez_compressed(destination, total_motion_uv=total_flow, camera_induced_motion_uv=camera_flow,
                            object_residual_motion_uv=object_flow, dynamic_probability=probability,
                            native_nonstatic_point_mask=nonstatic, real_input_indices=np.asarray(frame_ids),
                            valid_unpadded_time_mask=np.arange(total.shape[1]) < real)
        rows.append({"call_index": call["call_index"], "source_file": call["file"], "raw_sha256": sha256(raw / call["file"]),
                     "derived_sha256": sha256(destination), "padded_network_time_count": total.shape[1], "real_window_time_count": real,
                     "query_points": total.shape[2], "last_real_input_index": frame_ids[-1],
                     "probability_minimum": float(probability[:, :real].min()), "probability_median": float(np.median(probability[:, :real])),
                     "probability_maximum": float(probability[:, :real].max()), "native_static_threshold": threshold,
                     "nonstatic_point_fraction_on_real_window": float(nonstatic[:, :real].mean()),
                     "all_raw_outputs_finite": True})
        last = (call, arrays, total_flow, camera_flow, object_flow, nonstatic)
    if last is None:
        raise ValueError("No actual native forward output exists")
    call, arrays, total_flow, camera_flow, object_flow, nonstatic = last
    real_ids = call["context"]["retained_window_input_indices"]
    time_index, frame_id = len(real_ids)-1, real_ids[-1]
    source_path = Path(inputs[frame_id]["path"].replace("/mnt/d/", "D:/", 1))
    image = cv2.cvtColor(cv2.imread(str(source_path)), cv2.COLOR_BGR2RGB)
    h, w = image.shape[:2]
    image = image[:h-h%16, :w-w%16]
    height, width = call["network_input_shape"][-2:]
    display = cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)
    query = arrays["queries_t_uv_depth"][0, :, 1:3]
    visibility = arrays["visibility"][0, time_index] >= .9
    selected = np.flatnonzero(visibility & (arrays["queries_t_uv_depth"][0, :, 0] <= time_index))
    choices = selected[np.linspace(0, len(selected)-1, min(80, len(selected)), dtype=int)] if len(selected) else selected
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none"}):
        fig, axes = plt.subplots(1, 4, figsize=(16, 3.7), layout="constrained")
        for ax in axes:
            ax.imshow(display)
            ax.set(xlim=(0, width), ylim=(height, 0))
            ax.set_xticks([])
            ax.set_yticks([])
        for ax, motion, title in zip(axes[:3], [total_flow, camera_flow, object_flow], ["Total motion", "Camera-induced branch", "Object residual"], strict=True):
            origin = arrays["static_uv_depth"][0, time_index, :, :2] if title == "Object residual" else query
            flow = motion[0, time_index]
            ax.quiver(origin[choices, 0], origin[choices, 1], flow[choices, 0], -flow[choices, 1], color="#ffd43b", angles="uv", scale_units="xy", scale=1, width=.006)
            ax.set_title(title + "\nUV pixels, display subset of visible points")
        uv = arrays["total_uv"][0, time_index]
        artist = axes[3].scatter(uv[visibility, 0], uv[visibility, 1], c=arrays["dynamic_probability"][0, time_index, visibility],
                                 s=7, cmap="magma", vmin=0, vmax=1, alpha=.7)
        axes[3].set_title("Native dynamic probability at points\nSparse outputs; calibration unverified")
        fig.colorbar(artist, ax=axes[3], fraction=.045, label="Native sigmoid")
        fig.suptitle(f"BA-Track official tennis / input {frame_id}: partial forward output before CUDA OOM\nNo completed camera trajectory or dense refinement; padded time slots excluded", fontsize=11)
        fig.savefig(derived / "partial_motion_decomposition.png", dpi=170)
        fig.savefig(derived / "partial_motion_decomposition.svg")
        plt.close(fig)
    write_csv(derived / "forward_output_manifest.csv", rows)
    write_csv(derived / "depth_prior_manifest.csv", prior_rows)
    record = {"status": "REAL_PARTIAL_TRACKER_OUTPUTS_REVIEWED_NOT_FULL_DEMO", "directory": str(out),
              "native_forward_calls_with_saved_outputs": len(calls), "completed_frontend_calls": len(frontend),
              "official_depth_prior_frames_verified": len(prior_rows),
              "duplicate_official_DA_runs_bitwise_equal_for_all_frames": all(r["DA_two_actual_runs_bitwise_equal"] for r in prior_rows),
              "last_completed_frontend_input_timestamp": frontend[-1]["input_timestamp"], "expected_official_RGB_frames": len(inputs),
              "last_output_real_input_indices": real_ids, "padded_outputs_not_counted_as_real_frames": True,
              "motion_units": "2D resized model-grid UV pixels relative to each original query UV; not world XYZ or object velocity",
              "decomposition": "total_uv-query_uv, static_uv-query_uv, total_uv-static_uv; raw learned branches unchanged",
              "mask_scope": "Native threshold decision at sparse points only; no dense mask interpolation or accuracy claim",
              "source_model_log_sha256": sha256(out / "sparse_tracker_and_BA.log"), "outputs": rows,
              "camera_trajectory_available": False, "ATE_RPE_FPS_available": False, "motion_accuracy_ground_truth_available": False,
              "figure_visually_reviewed": False}
    write_json(derived / "output_review.json", record)
    write_json(PROJECT / "reports/SOTA/ba_track_partial_tracker_output_review.json", record)
    print(json.dumps({key: value for key, value in record.items() if key not in {"outputs"}}))


if __name__ == "__main__":
    main()

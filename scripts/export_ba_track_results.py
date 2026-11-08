"""CPU-only export/review of completed local BA outputs; GT stays external."""
from __future__ import annotations

import _bootstrap
import argparse
import gc
import json
from pathlib import Path
import pickle
import shutil

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, POSE_COLUMNS, sha256, write_csv, write_json
from gamecam_vo.evaluation import load_trajectory
from gamecam_vo.geometry import poses_to_rows


def local(value):
    return Path(str(value).replace("/mnt/d/", "D:/", 1)).resolve()


def depth_array(value):
    value = np.asarray(value)
    if value.ndim == 4 and value.shape[1] == 1:
        value = value[:, 0]
    elif value.ndim == 4 and value.shape[-1] == 1:
        value = value[..., 0]
    if value.ndim != 3 or not np.isfinite(value).all() or not (value > 0).all():
        raise ValueError("Expected finite positive predicted/refined depth")
    return value


def inspect_camera(times, poses, expected):
    poses = np.asarray(poses, dtype=float)
    times = np.asarray(times, dtype=float)
    if poses.shape != (expected, 4, 4) or not np.array_equal(times, np.arange(expected)) or not np.isfinite(poses).all():
        raise ValueError("Camera output must contain the expected ordered finite input indices")
    rotation = poses[:, :3, :3]
    orthogonality = float(np.max(np.abs(np.swapaxes(rotation, 1, 2) @ rotation - np.eye(3))))
    determinant = float(np.max(np.abs(np.linalg.det(rotation)-1)))
    bottom_valid = bool(np.allclose(poses[:, 3], [0, 0, 0, 1], atol=1e-6))
    check = {"max_rotation_orthogonality_error": orthogonality, "max_determinant_error": determinant,
             "rigid_tolerance": 1e-4, "bottom_rows_valid": bottom_valid,
             "rigid_check_passed": orthogonality <= 1e-4 and determinant <= 1e-4 and bottom_valid}
    return times.copy(), poses.copy(), check


def validate_camera(times, poses, expected):
    times, poses, check = inspect_camera(times, poses, expected)
    if not check["rigid_check_passed"]:
        raise ValueError("The camera rotations/bottom rows are not near rigid transforms")
    return times, poses, check


def save_camera(folder, times, poses, header):
    folder.mkdir(exist_ok=True)
    rows = poses_to_rows(times, poses)
    write_csv(folder / "estimated_trajectory.csv", rows, POSE_COLUMNS)
    np.savetxt(folder / "estimated_trajectory.txt", [[row[k] for k in POSE_COLUMNS] for row in rows], fmt="%.12g", header=header)


def observed_input_indices(call):
    values = call["context"].get("observed_window_input_indices", call["context"]["retained_window_input_indices"])
    if any(value is None or not np.isfinite(value) or int(value) != value for value in values):
        raise ValueError("Actual image observation indices are not finite integral sample keys")
    return [int(value) for value in values]


def export_motion(out, images):
    raw = out / "motion_decomposition/raw"
    calls = [json.loads(line) for line in (raw / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    destination = raw.parent / "derived"
    destination.mkdir(exist_ok=True)
    records, observed_inputs = [], set()
    chosen = sorted(set([0, len(calls)//2, len(calls)-1]))
    examples = []
    for call in calls:
        with np.load(raw / call["file"]) as saved:
            arrays = {name: saved[name].copy() for name in saved.files}
        if any(not np.isfinite(value).all() for value in arrays.values()):
            raise ValueError("Nonfinite raw native motion outputs")
        total = arrays["total_uv"]
        camera = arrays["static_uv_depth"][..., :2]
        probability = arrays["dynamic_probability"]
        queries = arrays["queries_t_uv_depth"][..., 1:3]
        real_inputs = observed_input_indices(call)
        if len(real_inputs) > total.shape[1] or total.shape != camera.shape or (probability < 0).any() or (probability > 1).any():
            raise ValueError("Native motion shape/temporal/probability contract changed")
        observed_inputs.update(real_inputs)
        target = destination / call["file"]
        np.savez_compressed(target, total_motion_uv=total-queries[:, None], camera_induced_motion_uv=camera-queries[:, None],
                            object_residual_motion_uv=total-camera, dynamic_probability=probability,
                            probability_above_09=probability > .9, real_input_indices=np.asarray(real_inputs),
                            valid_unpadded_time_mask=np.arange(total.shape[1]) < len(real_inputs))
        records.append({"call_index": call["call_index"], "raw_file": call["file"], "raw_sha256": sha256(raw / call["file"]),
                        "derived_sha256": sha256(target), "native_time_slots": total.shape[1], "real_window_inputs": len(real_inputs),
                        "query_points": total.shape[2], "last_real_input": real_inputs[-1], "all_finite": True})
        if call["call_index"] in chosen:
            examples.append((call, arrays))
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none"}):
        fig, axes = plt.subplots(len(examples), 4, figsize=(16, 3*len(examples)), squeeze=False, layout="constrained")
        for row, (call, arrays) in zip(axes, examples, strict=True):
            times = observed_input_indices(call)
            t, input_index = len(times)-1, times[-1]
            rgb = cv2.cvtColor(cv2.imread(str(local(images[input_index]["path"]))), cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            rgb = rgb[:h-h%16, :w-w%16]
            height, width = call["network_input_shape"][-2:]
            rgb = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_LINEAR)
            query = arrays["queries_t_uv_depth"][0, :, 1:3]
            total, static = arrays["total_uv"][0, t], arrays["static_uv_depth"][0, t, :, :2]
            visible = arrays["visibility"][0, t] >= .9
            selection = np.flatnonzero(visible & (arrays["queries_t_uv_depth"][0, :, 0] <= t))
            selection = selection[np.linspace(0, len(selection)-1, min(80, len(selection)), dtype=int)] if len(selection) else selection
            for ax in row:
                ax.imshow(rgb)
                ax.set(xlim=(0, width), ylim=(height, 0), xticks=[], yticks=[])
            for ax, origin, motion, label in zip(row[:3], [query, query, static], [total-query, static-query, total-static], ["Total motion", "Camera-induced branch", "Object residual"], strict=True):
                ax.quiver(origin[selection, 0], origin[selection, 1], motion[selection, 0], -motion[selection, 1], color="#ffd43b", angles="uv", scale_units="xy", scale=1, width=.006)
                ax.set_title(f"Input {input_index}: {label}\nUV pixels; visible display subset")
            artist = row[3].scatter(total[visible, 0], total[visible, 1], c=arrays["dynamic_probability"][0, t, visible], s=7, cmap="magma", vmin=0, vmax=1, alpha=.7)
            row[3].set_title("Native dynamic sigmoid at points\nCalibration/dense accuracy unverified")
            fig.colorbar(artist, ax=row[3], fraction=.045)
        fig.suptitle("BA-Track native point motion / real input indices only\nDisplay arrows use each query's origin; padded times excluded", fontsize=12)
        fig.savefig(destination / "motion_decomposition_examples.png", dpi=160)
        fig.savefig(destination / "motion_decomposition_examples.svg")
        plt.close(fig)
    write_csv(destination / "forward_output_manifest.csv", records)
    return {"native_forward_calls": len(calls), "unique_input_indices_with_native_point_predictions": sorted(observed_inputs),
            "raw_maps_missing_for_input_indices": sorted(set(range(len(images)))-observed_inputs),
            "motion_units": "Resized-model-grid UV pixels relative to each original query; native depth retained in raw output; no world XYZ/velocity claim",
            "display_probability_threshold": .9, "probability_threshold_is_not_final_SLAM_mask": True,
            "padded_times_not_counted_as_real_inputs": True, "calibrated_probability_or_motion_accuracy_claim": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--phase5", action="store_true", help="Only new owned phase5 results, without changing phase4 pointers")
    args = parser.parse_args()
    out = args.directory.resolve()
    roots = [PROJECT / "results" / name / "BA_TRACK" for name in ("E14_WILD_DYNAMIC", "E15_MOVIE", "E16_BONN")] if args.phase5 else [PROJECT / "results/E9_BA_TRACK"]
    if not any(out.is_relative_to(root) for root in roots):
        raise ValueError("Only completed owned BA results can be exported")
    status = json.loads((out / "status.json").read_text(encoding="utf-8"))
    contract = json.loads((out / "execution_contract.json").read_text(encoding="utf-8"))
    if status["status"] != "BA_TRACK_PIPELINE_COMPLETED":
        raise RuntimeError("All actual official stages must complete first")
    scene, expected = contract["scene"], contract["expected_frames"]
    images = json.loads((out / "RGB_manifest.json").read_text(encoding="utf-8"))
    native = out / "upstream_output" / scene
    # These are trusted results created by the local reviewed inference, not
    # downloaded arbitrary pickle files. Load one large dictionary at a time.
    with (native / "results.pkl").open("rb") as stream:
        sparse = pickle.load(stream)
    times, poses, sparse_camera_check = validate_camera(sparse["tstamps"], sparse["cams_T_world"], expected)
    native_times, native_poses = load_trajectory(native / "batrack_traj.txt")
    if not np.array_equal(native_times, times):
        raise ValueError("Native TUM/export timestamps disagree")
    translation_error = float(np.max(np.linalg.norm(poses[:, :3, 3]-native_poses[:, :3, 3], axis=1)))
    rotation_error = float(np.max(np.degrees(Rotation.from_matrix(np.swapaxes(poses[:, :3, :3], 1, 2) @ native_poses[:, :3, :3]).magnitude())))
    if translation_error > 1e-4 or rotation_error > .001:
        raise ValueError("Sparse pickle does not agree with native T_wc TUM export")
    save_camera(out / "sparse_camera", times, poses, "Sparse T_wc; XYZW; frame_index; arbitrary learned-depth scale")
    # The official README's pose-evaluation scripts run run_batrack.py and
    # evaluate slam.terminate(), before dense global depth alignment. Keep that
    # documented pose output primary, decided before loading any MVS truth.
    save_camera(out, times, poses, "Official pose-evaluation output: sparse SLAM T_wc; XYZW; frame_index; learned-depth scale")
    masks = out / "dynamic_motion_masks"
    masks.mkdir(exist_ok=True)
    static, visibility, query_valid = [np.asarray(sparse[key]) for key in ("trajs_static", "trajs_vis", "trajs_valid")]
    if not np.isin(static, [0, 1]).all() or not np.isin(visibility, [0, 1]).all():
        raise ValueError("Expected native Boolean sparse static/visibility labels")
    support = visibility.astype(bool) & query_valid.astype(bool)[..., None]
    np.savez_compressed(masks / "native_sparse_motion_labels.npz", native_static_labels=static, native_visibility=visibility,
                        native_query_valid=query_valid, grid_query_frames=np.asarray(sparse["grid_query_frames"]),
                        observed_nonstatic_mask=(~static.astype(bool)) & support, observation_support=support)
    prior_examples = depth_array(sparse["dmaps"])[[0, expected//2, expected-1]].copy()
    del sparse, static, visibility, query_valid, support
    gc.collect()
    with (native / "results_refined.pkl").open("rb") as stream:
        refined = pickle.load(stream)
    refined_times, refined_poses, refined_camera_check = inspect_camera(refined["tstamps"], refined["cams_T_world"], expected)
    # Preserve the native matrix verbatim even if it is outside SO(3). Never
    # convert a failed rotation to a quaternion (which could hide its drift).
    diagnostic = out / "global_alignment_camera_diagnostic"
    diagnostic.mkdir(exist_ok=True)
    np.save(diagnostic / "native_cams_T_world.npy", refined_poses)
    write_json(diagnostic / "rigid_check.json", {**refined_camera_check,
               "native_values_modified": False, "used_for_primary_pose_evaluation": False,
               "normalization_or_projection_applied": False})
    depth = depth_array(refined["dmaps_scaled"])
    intrinsics = np.asarray(refined["intrinsics"])
    if len(depth) != expected or intrinsics.shape != (expected, 4) or not np.isfinite(intrinsics).all() or not (intrinsics[:, :2] > 0).all():
        raise ValueError("Refined depth/intrinsics completeness failed")
    write_csv(out / "refined_intrinsics.csv", [{"frame_index": i, "fx": row[0], "fy": row[1], "cx": row[2], "cy": row[3]} for i, row in enumerate(intrinsics)])
    depth_folder = out / "depth_results/global_refined" / scene
    depth_folder.mkdir(parents=True, exist_ok=True)
    depth_rows = []
    for i, array in enumerate(depth):
        path = depth_folder / f"frame_{i:05d}.npy"
        np.save(path, array)
        depth_rows.append({"frame_index": i, "height": array.shape[0], "width": array.shape[1], "dtype": str(array.dtype), "minimum": float(array.min()),
                           "median": float(np.median(array)), "maximum": float(array.max()), "sha256": sha256(path), "source": "Unmodified native dmaps_scaled"})
    write_csv(depth_folder / "manifest.csv", depth_rows)
    picks = [0, expected//2, expected-1]
    final_examples = depth[picks].copy()
    del refined, depth
    gc.collect()
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"}):
        fig, axes = plt.subplots(3, 3, figsize=(12, 8), layout="constrained")
        lo, hi = np.quantile(np.concatenate([prior_examples.ravel(), final_examples.ravel()]), [.02, .98])
        for row, i, prior, final in zip(axes, picks, prior_examples, final_examples, strict=True):
            rgb = cv2.cvtColor(cv2.imread(str(local(images[i]["path"]))), cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            row[0].imshow(rgb[:h-h%16, :w-w%16])
            row[0].set_title(f"Input {i}: RGB / native crop")
            for ax, array, label in zip(row[1:], [prior, final], ["Predicted input prior", "Global refined depth"], strict=True):
                im = ax.imshow(array, cmap="viridis", vmin=lo, vmax=hi)
                ax.set_title(label)
                fig.colorbar(im, ax=ax, fraction=.045, label="Learned depth unit")
            for ax in row:
                ax.set_xticks([]); ax.set_yticks([])
        fig.suptitle("BA-Track depth outputs / display2–98% quantile clipping only; raw arrays retained", fontsize=12)
        fig.savefig(depth_folder / "depth_examples.png", dpi=160)
        fig.savefig(depth_folder / "depth_examples.svg")
        plt.close(fig)
    depth_diagnostics = out / "depth_diagnostics"
    depth_diagnostics.mkdir(exist_ok=True)
    for name in ("manifest.csv", "depth_examples.png", "depth_examples.svg"):
        shutil.copy2(depth_folder / name, depth_diagnostics / name)
    trace = out / "depth_results/refine_trace/iterations.jsonl"
    trace_review = {"available": False, "reason": "This historical Demo predates the opt-in iteration observer"}
    if trace.exists():
        iterations = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
        niter = contract["dense_iterations"]
        if len(iterations) != niter or [r["iteration_zero_based"] for r in iterations] != list(range(niter)):
            raise ValueError("Dense iteration trace is incomplete or unordered")
        if not all(r["native_loss_finite"] and r["original_step_called_once_return_value_unchanged"] for r in iterations):
            raise ValueError("Dense native loss/observation contract failed")
        trace_review = {"available": True, "completed_iterations": len(iterations), "all_native_losses_finite": True,
                        "first_loss": iterations[0]["native_loss"], "last_loss": iterations[-1]["native_loss"],
                        "source_sha256": sha256(trace), "observer_calls_original_once_return_unchanged": True}
        shutil.copy2(trace, depth_diagnostics / "native_refinement_iterations.jsonl")
    motion = export_motion(out, images)
    frontend = [json.loads(line) for line in (out / "motion_decomposition/frontend_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(frontend) != expected:
        raise ValueError("Actual frontend input count differs")
    record = {"status": "BA_TRACK_COMPLETED_OUTPUTS_SANITY_CHECKED", "directory": str(out), "target": contract["target"], "expected_frames": expected,
              "finite_final_camera_poses": len(poses), "frontend_calls": len(frontend), "initialized_frontend_calls": sum(r["initialized"] for r in frontend),
              "primary_camera_source": "Official sparse SLAM pose-evaluation output: results.pkl / batrack_traj.txt; not selected by a GT score",
              "primary_pose_protocol_evidence": ["README.md: Evaluations / Run pose evaluation", "scripts/eval_sintel/eval_sintel_pose.sh", "scripts/eval_shibuya/eval_shibuya_pose.sh", "main/run_batrack.py: slam.terminate / save_trajectory / eval_metrics"],
              "native_sparse_pickle_TUM_max_translation_difference": translation_error, "native_sparse_pickle_TUM_max_rotation_difference_degrees": rotation_error,
              "coordinate_direction": "T_wc: sparse get_results explicitly inverts internal poses; agrees with native TUM",
              "sparse_camera_checks": sparse_camera_check, "refined_camera_checks": refined_camera_check,
              "refined_depth_maps": len(depth_rows), "refined_depth_all_finite_positive": True,
              "refined_depth_manifest": "depth_diagnostics/manifest.csv", "refined_depth_manifest_sha256": sha256(depth_diagnostics / "manifest.csv"),
              "dense_refinement_trace": trace_review,
              "global_alignment_camera_usable_as_rigid_poses": refined_camera_check["rigid_check_passed"],
              "global_alignment_joint_reconstruction_caveat": "Native depth is exported unchanged and finite positive; jointly refined camera matrices are independently checked. A failed rigid check limits geometric interpretation and is not repaired by normalization.",
              "refined_depth_display_quantiles": {"low02_on_display_examples": float(lo), "high98_on_display_examples": float(hi)},
              "motion": motion, "sparse_results_sha256": sha256(native / "results.pkl"), "refined_results_sha256": sha256(native / "results_refined.pkl"),
              "final_trajectory_sha256": sha256(out / "estimated_trajectory.csv"), "native_sparse_motion_labels_sha256": sha256(masks / "native_sparse_motion_labels.npz"),
              "figures_visually_reviewed": False, "independent_ground_truth_in_this_export": False, "paper_score_match": False}
    write_json(out / "output_review.json", record)
    pointer = "ba_track_official_demo_output_review.json" if contract["target"] == "official-demo" else "ba_track_mvs_output_review.json"
    if args.phase5:
        write_json(PROJECT / "reports/PHASE5" / ("ba_track_"+out.name+"_output_review.json"), record)
    else:
        write_json(PROJECT / "reports/SOTA" / pointer, record)
    print(json.dumps({key: record[key] for key in ("status", "directory", "expected_frames", "finite_final_camera_poses", "frontend_calls", "initialized_frontend_calls")}))


if __name__ == "__main__":
    main()

"""Independent rigid-motion comparison of native BA UV/Z, never world-XYZ labels."""
from __future__ import annotations

import _bootstrap
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml
from scipy.ndimage import map_coordinates

from gamecam_vo.common import PROJECT, sha256, write_csv, write_json, run_metadata
from phase5_motion_support import load_movi_ground_truth, assert_movi_result, json_lines
from phase5_motion_metrics import evaluate_motion_scores, binary_statistics
from phase5_movi_geometry import camera_parameters, dequantize, unproject_range, project, transport_object_points, wxyz_rotations


def xyz_from_z(uv, z, k):
    return np.column_stack(((uv[:, 0]-k[0, 2])/k[0, 0], (uv[:, 1]-k[1, 2])/k[1, 1], np.ones(len(uv))))*np.asarray(z).reshape(-1, 1)


def error_summary(values):
    array = np.asarray(values, float)
    return {"observations": int(array.size), "RMSE": float(np.sqrt(np.mean(array**2))) if array.size else None,
        "median": float(np.median(array)) if array.size else None, "p95": float(np.quantile(array, .95)) if array.size else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--reference-pointer", type=Path, required=True)
    args = parser.parse_args()
    out = args.directory.resolve()
    pointer, audit, fields, motion = load_movi_ground_truth(args.reference_pointer)
    native_status = assert_movi_result(out, pointer)
    if out.parent.name != "BA_TRACK":
        raise ValueError("This evaluator accepts only native BA-Track output")
    destination = out / "motion_evaluation" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")+"_M2")
    destination.mkdir(parents=True, exist_ok=False)
    trace = out / "motion_decomposition/raw"
    calls = json_lines(trace / "calls.jsonl")
    report = {**run_metadata(), "status": "UNAVAILABLE", "method": "BA_TRACK", "sequence": pointer["sequence"], "directory": str(destination),
        "evaluation_source_files": [{"file": str(Path(__file__).with_name(name)), "sha256": sha256(Path(__file__).with_name(name))}
            for name in (Path(__file__).name, "phase5_motion_metrics.py", "phase5_motion_support.py", "phase5_movi_geometry.py")],
        "GT_provenance": "SYNTHETIC_GROUND_TRUTH", "GT_audit_sha256": pointer["GT_audit_sha256"], "native_status": native_status["status"],
        "native_output_space": "Network-grid UV pixels and learned Z depth, not world XYZ", "network_calls": len(calls),
        "native_query_values_captured_before_SLAM_overwrite": True, "sensor_GT_in_model": False, "figures_visually_reviewed": False,
        "point_support": "Foreground 3x3-eroded query interiors; first native source-frame/UV/target observation; no padded or zero-lag pairs",
        "image_query_coordinate_origin_caveat": "Native bilinear RGBD resize uses half-pixel centers, while native queries and returned tracks use pure width/height scale with no offset. This coordinate-origin discrepancy is disclosed, not subtracted from predictions or treated as an empirical EPE/error bound or proof of object-motion failure.",
        "released_model_training_domain": "Kubric, as documented in the pinned upstream README. MOVi-E is a related synthetic domain; exact per-video training/test overlap or disjointness is not established by those release docs.",
        "observed_network_coordinate_mappings": [],
        "motion_direction_definition": "Sign of world-surface displacement dot world-camera-center displacement; zeros separate",
        "uncertainty_pixels_pooled_with_point_scores": False, "independent_clip_count": 1}
    if not audit["object_motion_geometry_validated"]:
        report["unavailable_reason"] = "Independent moving-foreground GT flow geometry lacks validated support; M2 blocked"
    elif not calls:
        report["unavailable_reason"] = "No archived native network return; no extra inference"
    else:
        config_file = out / "hydra/.hydra/config.yaml"
        config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        if config["slam"]["STATIC_QUANTILE"] != 0. or config["slam"]["STATIC_THRESHOLD"] != .1:
            raise ValueError("Actual native static-mask settings differ from the frozen default; audit before scoring")
        report["resolved_native_config_sha256"] = sha256(config_file)
        k, cameras = camera_parameters(fields)
        ranges = dequantize(fields["depth"], fields["metadata__depth_range"])
        positions = fields["instances__positions"].astype(float)
        rotations = wxyz_rotations(fields["instances__quaternions"])
        interior = np.zeros(fields["segmentations"].shape, bool)
        for frame in range(24):
            for identity in np.unique(fields["segmentations"][frame]):
                if identity:
                    interior[frame] |= cv2.erode((fields["segmentations"][frame] == identity).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        seen_queries, seen_observations = set(), set()
        scale_pairs, rows, hashes = [], [], []
        window_score_variation = []
        coordinate_mappings = {}
        counts = {"padded_target_slots_excluded": 0, "same_frame_pairs_excluded": 0, "duplicate_observations_excluded": 0,
            "query_points_outside_verified_foreground_interiors": 0, "GT_target_offscreen_excluded": 0, "nonpositive_native_depth_3D_excluded": 0,
            "GT_camera_only_projection_undefined_excluded": 0, "missing_online_camera_intrinsics_3D_excluded": 0, "direction_unverified_calls_excluded": 0}
        xyz_total_pred, xyz_static_pred, xyz_total_gt, xyz_static_gt = [], [], [], []
        for call in calls:
            context = call["context"]
            if context.get("native_network_direction") != "forward":
                counts["direction_unverified_calls_excluded"] += 1
                continue
            observed = context.get("observed_window_input_indices", [])
            if not observed or any(value is None or int(value) != value or not 0 <= int(value) < 24 for value in observed):
                raise ValueError("Actual original-image window support is missing; do not infer from retained buffer length")
            ids = np.asarray(observed, int)
            shape = call["network_input_shape"]
            if shape[0] != 1 or shape[2] != 4 or len(ids) > shape[1]:
                raise ValueError("Native network/window shape differs")
            nh, nw = shape[-2:]
            image_shape = context["native_input_image_shape"]
            if image_shape != [3, 256, 256]:
                raise ValueError("Native BA preprocessing changed the common input grid")
            scale_uv = np.array([nw/256, nh/256])
            mapping_key = (256, 256, nh, nw)
            if mapping_key not in coordinate_mappings:
                center_shift = .5*(scale_uv-1)
                coordinate_mappings[mapping_key] = {
                    "input_RGB_shape_height_width": [256, 256], "actual_network_shape_height_width": [nh, nw],
                    "native_no_offset_query_scale_uv": scale_uv.tolist(),
                    "RGB_half_pixel_center_minus_native_query_origin_shift_network_uv": center_shift.tolist(),
                    "origin_shift_L2_network_pixels": float(np.linalg.norm(center_shift)),
                    "first_observed_forward_call_index": call["call_index"],
                    "is_empirically_measured_prediction_error_or_error_bound": False}
            path = trace / call["file"]
            hashes.append({"file": str(path), "sha256": sha256(path), "call_index": call["call_index"]})
            with np.load(path) as z:
                arrays = {key: z[key].copy()[0] for key in z.files}
            if not all(np.isfinite(a).all() for a in arrays.values()):
                raise ValueError("Nonfinite native point outputs; do not silently remove failed predictions")
            query = arrays["queries_t_uv_depth"]
            total, static = arrays["total_uv"], arrays["static_uv_depth"]
            total_depth = arrays["total_depth"][..., 0]
            probability, visibility = arrays["dynamic_probability"], arrays["visibility"]
            window_score_variation.append(float(np.max(np.ptp(probability[:len(ids)], axis=0))))
            # Native STATIC_QUANTILE=0 uses the maximum static score, capped at
            # 0.1. Preserve its float32 comparison, including the all-dynamic
            # corner case; configured dynamic 0.9 is a separate fixed boundary.
            static_probability = np.float32(1)-probability.astype(np.float32)
            native_static_boundary = np.float32(min(float(np.max(static_probability)), .1))
            native_dynamic_filter = static_probability < native_static_boundary
            if total.shape[:2] != (shape[1], len(query)) or query.shape[1] != 4:
                raise ValueError("Native return/query shape differs")
            qt = query[:, 0].astype(int)
            if not np.array_equal(qt, query[:, 0]) or (qt < 0).any() or (qt >= len(ids)).any():
                raise ValueError("A query refers to a padded/missing original input")
            source_ids = ids[qt]
            uv = query[:, 1:3]/scale_uv
            inside = (uv[:, 0] >= 0) & (uv[:, 0] <= 255) & (uv[:, 1] >= 0) & (uv[:, 1] <= 255)
            nearest = np.rint(np.clip(uv, 0, 255)).astype(int)
            valid = inside & interior[source_ids, nearest[:, 1], nearest[:, 0]]
            counts["query_points_outside_verified_foreground_interiors"] += int((~valid).sum())
            world = np.full((len(query), 3), np.nan)
            identities = fields["segmentations"][source_ids, nearest[:, 1], nearest[:, 0]]
            source_gt_z = np.full(len(query), np.nan)
            for source in np.unique(source_ids[valid]):
                selected = valid & (source_ids == source)
                distance = map_coordinates(ranges[source], [uv[selected, 1], uv[selected, 0]], order=1, mode="nearest", prefilter=False)
                world[selected] = unproject_range(uv[selected], distance, k, cameras[source])
                check, z, _ = project(world[selected], k, cameras[source])
                if np.max(np.abs(check-uv[selected])) > 1e-8:
                    raise ValueError("Range/UV query roundtrip failed")
                source_gt_z[selected] = z
            keys = [(int(source), round(float(x), 6), round(float(y), 6)) for source, (x, y) in zip(source_ids, uv, strict=True)]
            for q in np.flatnonzero(valid):
                if keys[q] not in seen_queries:
                    seen_queries.add(keys[q])
                    if query[q, 3] > 0 and source_gt_z[q] > 0:
                        scale_pairs.append([float(query[q, 3]), float(source_gt_z[q])])
            traced = context.get("online_camera_pose_support_matches_observed_images", False)
            intrinsics = np.asarray(context.get("online_window_intrinsics_fx_fy_cx_cy", []), float)
            expected_k = np.array([k[0, 0], k[1, 1], k[0, 2], k[1, 2]])
            if traced and (intrinsics.shape != (len(ids), 4) or not np.allclose(intrinsics, expected_k[None], atol=1e-3, rtol=1e-5)):
                raise ValueError("Actual online camera intrinsics differ; audit the 3D convention before scoring")
            counts["padded_target_slots_excluded"] += (shape[1]-len(ids))*len(query)
            for slot, target in enumerate(ids):
                world_target = world.copy()
                for source in np.unique(source_ids[valid]):
                    selected = valid & (source_ids == source)
                    world_target[selected] = transport_object_points(world[selected], identities[selected], source, target, positions, rotations)
                gt_total, positive_z, distance = project(world_target, k, cameras[target])
                gt_static, static_positive_z, _ = project(world, k, cameras[target])
                in_view = np.isfinite(gt_total).all(axis=1) & (positive_z > 0) & (gt_total[:, 0] >= 0) & (gt_total[:, 0] <= 255) & (gt_total[:, 1] >= 0) & (gt_total[:, 1] <= 255)
                nonzero = source_ids != target
                counts["same_frame_pairs_excluded"] += int((valid & ~nonzero).sum())
                counts["GT_target_offscreen_excluded"] += int((valid & nonzero & ~in_view).sum())
                static_defined = np.isfinite(gt_static).all(axis=1) & (static_positive_z > 0)
                counts["GT_camera_only_projection_undefined_excluded"] += int((valid & nonzero & in_view & ~static_defined).sum())
                keep = valid & nonzero & in_view & static_defined
                for q in np.flatnonzero(keep):
                    key = (*keys[q], int(target))
                    if key in seen_observations:
                        counts["duplicate_observations_excluded"] += 1
                        continue
                    seen_observations.add(key)
                    gt_flow = (gt_total[q]-uv[q])*scale_uv
                    gt_camera = (gt_static[q]-uv[q])*scale_uv
                    gt_object = gt_flow-gt_camera
                    pr_flow = total[slot, q]-query[q, 1:3]
                    pr_camera = static[slot, q, :2]-query[q, 1:3]
                    pr_object = pr_flow-pr_camera
                    source = int(source_ids[q])
                    delta_world = world_target[q]-world[q]
                    delta_camera = cameras[target, :3, 3]-cameras[source, :3, 3]
                    denom = np.linalg.norm(delta_world)*np.linalg.norm(delta_camera)
                    cosine = float(np.dot(delta_world, delta_camera)/denom) if denom > 1e-10 else None
                    target_xy = np.rint(gt_total[q]).astype(int)
                    future_range = ranges[target, target_xy[1], target_xy[0]]
                    quantum = float(np.diff(fields["metadata__depth_range"])[0])/65535
                    hidden = bool(future_range > 0 and distance[q] > future_range+2*quantum+.005*distance[q])
                    row = {"call_index": call["call_index"], "source_frame": source, "target_frame": int(target), "input_query_u": uv[q, 0], "input_query_v": uv[q, 1],
                        "signed_target_minus_source_frame_lag": int(target)-source, "absolute_frame_horizon": abs(int(target)-source),
                        "absolute_time_horizon_seconds": abs(int(target)-source)/12.,
                        "instance_id": int(identities[q]), "GT_dynamic_instance_at_target": bool(motion["moving_instances"][int(identities[q])-1, target]),
                        "GT_instance_moves_in_any_actual_window_frame": bool(motion["moving_instances"][int(identities[q])-1, ids].any()),
                        "dynamic_sigmoid": float(probability[slot, q]), "native_visibility_sigmoid": float(visibility[slot, q]),
                        "native_effective_dynamic_filter": bool(native_dynamic_filter[slot, q]),
                        "native_effective_dynamic_boundary": float(1-native_static_boundary),
                        "GT_occluded_in_view": hidden, "GT_motion_direction_cosine": cosine,
                        "GT_direction": "same" if cosine is not None and cosine > 0 else "opposite" if cosine is not None and cosine < 0 else "zero_or_orthogonal",
                        "GT_surface_speed_world_unit_per_second": float(np.linalg.norm(delta_world)*12/abs(int(target)-source)),
                        "GT_visible_static_pixel_fraction_at_target": float((~motion["dynamic_pixel_mask"][target]).mean()),
                        "camera_only_EPE_network_pixels": float(np.linalg.norm(pr_camera-gt_camera)),
                        "object_residual_EPE_network_pixels": float(np.linalg.norm(pr_object-gt_object)), "total_EPE_network_pixels": float(np.linalg.norm(pr_flow-gt_flow)),
                        "zero_object_control_EPE_network_pixels": float(np.linalg.norm(gt_object)),
                        "total_as_camera_control_EPE_network_pixels": float(np.linalg.norm(pr_flow-gt_camera))}
                    rows.append(row)
                    native_depth_valid = total_depth[slot, q] > 0 and static[slot, q, 2] > 0
                    if not traced:
                        counts["missing_online_camera_intrinsics_3D_excluded"] += 1
                    if not native_depth_valid:
                        counts["nonpositive_native_depth_3D_excluded"] += 1
                    if traced and native_depth_valid:
                        # Query scaling is the native no-offset convention; do not
                        # silently substitute the RGB resize half-pixel transform.
                        net_k = np.diag([scale_uv[0], scale_uv[1], 1.]) @ k
                        xyz_total_pred.append(xyz_from_z(total[slot, q:q+1], total_depth[slot, q:q+1], net_k)[0])
                        xyz_static_pred.append(xyz_from_z(static[slot, q:q+1, :2], static[slot, q:q+1, 2], net_k)[0])
                        xyz_total_gt.append((world_target[q]-cameras[target, :3, 3]) @ cameras[target, :3, :3])
                        xyz_static_gt.append((world[q]-cameras[target, :3, 3]) @ cameras[target, :3, :3])
                        row["has_3D_diagnostic"] = True
                    else:
                        row["has_3D_diagnostic"] = False
        report.update(exclusions=counts, native_archive_files=hashes, depth_scale_correspondences=len(scale_pairs), distinct_source_queries=len(seen_queries),
            observed_network_coordinate_mappings=list(coordinate_mappings.values()))
        if rows:
            depth_scale = None
            if len(scale_pairs) >= 30:
                scale_values = np.asarray(scale_pairs)
                depth_scale = float(np.sum(scale_values[:, 0]*scale_values[:, 1])/np.sum(scale_values[:, 0]**2))
                if not np.isfinite(depth_scale) or depth_scale <= 0:
                    depth_scale = None
            diagnostic3d = {"status": "UNAVAILABLE", "reason": "INSUFFICIENT_POSITIVE_SOURCE_DEPTH_SCALE_OR_INTRINSICS_SUPPORT", "scale": depth_scale,
                "scope": "One GT-source-query-Z scale in post-evaluation; target-camera component error, not native scale recovery or world-track accuracy",
                "unit": "Kubric_world_unit"}
            if depth_scale is not None and xyz_total_pred:
                pt, ps, gt, gs = map(np.asarray, (xyz_total_pred, xyz_static_pred, xyz_total_gt, xyz_static_gt))
                errors = {"total": np.linalg.norm(depth_scale*pt-gt, axis=1), "camera_only": np.linalg.norm(depth_scale*ps-gs, axis=1),
                    "object_residual": np.linalg.norm(depth_scale*(pt-ps)-(gt-gs), axis=1)}
                j = 0
                for row in rows:
                    if row["has_3D_diagnostic"]:
                        for name, values in errors.items():
                            row[name+"_3D_component_error"] = float(values[j])
                        j += 1
                diagnostic3d.update(status="COMPUTED_DEPTH_SCALE_ALIGNED_COMPONENT_DIAGNOSTIC", reason=None,
                    metrics={name: error_summary(values) for name, values in errors.items()})
            labels = np.array([r["GT_dynamic_instance_at_target"] for r in rows])
            scores = np.array([r["dynamic_sigmoid"] for r in rows])
            speeds = np.array([r["GT_surface_speed_world_unit_per_second"] for r in rows])
            point_m1, _ = evaluate_motion_scores(labels, scores, semantics="dynamic_sigmoid", probability_threshold=.9,
                threshold_inclusive=False, continuous_speed=speeds)
            point_m1["operating_point"] = "Predeclared configured native dynamic 0.9 cap; actual quantile-capped native hard decisions reported separately"
            point_m1["actual_native_quantile_capped_mask_metrics"] = binary_statistics(labels, [r["native_effective_dynamic_filter"] for r in rows])
            point_m1["target_event"] = "Target-frame frozen GT instance-motion union; native score is repeated across the native window, so this is an event-specific diagnostic, not an assertion about released training-label calibration"
            window_m1, _ = evaluate_motion_scores([r["GT_instance_moves_in_any_actual_window_frame"] for r in rows], scores,
                semantics="dynamic_sigmoid", probability_threshold=.9, threshold_inclusive=False)
            window_m1["target_event"] = "Any frozen GT motion in the actual unpadded observed window for this query's instance; additional predeclared temporal-event diagnostic, not asserted original training semantics"
            names = ("total_EPE_network_pixels", "camera_only_EPE_network_pixels", "object_residual_EPE_network_pixels",
                "zero_object_control_EPE_network_pixels", "total_as_camera_control_EPE_network_pixels")
            summary = {name: error_summary([r[name] for r in rows]) for name in names}
            slices = {}
            speed_median = float(np.median(speeds))
            slice_masks = {"same_direction": [r["GT_direction"] == "same" for r in rows], "opposite_direction": [r["GT_direction"] == "opposite" for r in rows],
                "occluded_in_view": [r["GT_occluded_in_view"] for r in rows], "visible_in_view": [not r["GT_occluded_in_view"] for r in rows],
                "speed_above_GT_median": speeds > speed_median, "speed_at_or_below_GT_median": speeds <= speed_median,
                "static_visible_fraction_below_half": [r["GT_visible_static_pixel_fraction_at_target"] < .5 for r in rows],
                "static_visible_fraction_at_least_half": [r["GT_visible_static_pixel_fraction_at_target"] >= .5 for r in rows]}
            for name, mask in slice_masks.items():
                selected = [r for r, keep in zip(rows, mask, strict=True) if keep]
                slices[name] = {key: error_summary([r[key] for r in selected]) for key in names}
            horizon_slices = {}
            for horizon in sorted({r["absolute_frame_horizon"] for r in rows}):
                horizon_slices[str(horizon)] = {}
                for name, mask in slice_masks.items():
                    selected = [r for r, keep in zip(rows, mask, strict=True) if keep and r["absolute_frame_horizon"] == horizon]
                    horizon_slices[str(horizon)][name] = {key: error_summary([r[key] for r in selected]) for key in names}
            points_file = destination / "independent_point_comparison.csv"
            write_csv(points_file, rows, list(dict.fromkeys(key for row in rows for key in row)))
            report.update(status="INDEPENDENT_NATIVE_POINT_MOTION_EVALUATION_COMPLETED", observed_point_target_pairs=len(rows),
                point_motion_metrics=summary, point_dynamic_sigmoid_metrics=point_m1, post_evaluation_3D_component_diagnostic=diagnostic3d,
                point_sigmoid_window_any_motion_diagnostic=window_m1,
                maximum_dynamic_score_variation_within_actual_native_windows=max(window_score_variation),
                GT_slices=slices, speed_slice_median_world_unit_per_second=speed_median, point_comparison=str(points_file), point_comparison_sha256=sha256(points_file),
                GT_slices_by_absolute_frame_horizon=horizon_slices,
                slice_interpretation="Unrestricted slice summaries are descriptive. All observed exact absolute frame horizons are reported separately; speed/occlusion/direction differences are not isolated causal effects.",
                control_semantics="Output analysis controls, not model ablations or demonstrated SLAM improvements")
            with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False}):
                fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout="constrained")
                errors2d = np.array([r["object_residual_EPE_network_pixels"] for r in rows])
                order = np.sort(errors2d)
                axes[0].plot(order, np.arange(1, len(order)+1)/len(order), color="#275c8a")
                axes[0].set(xlabel="Object-residual EPE [network px]", ylabel="Cumulative fraction", ylim=(0, 1), title="a  Native decomposition error")
                picks = np.arange(len(rows))[::max(1, len(rows)//4000)]
                axes[1].scatter(speeds[picks], errors2d[picks], s=3, alpha=.3, color="#275c8a", rasterized=True)
                axes[1].set(xlabel="GT surface speed [world-unit/s]", ylabel="Object-residual EPE [network px]", title="b  Fixed-stride display sample")
                categories = ["same_direction", "opposite_direction", "visible_in_view", "occluded_in_view"]
                for x, name in enumerate(categories):
                    result = slices[name]["object_residual_EPE_network_pixels"]
                    if result["observations"]:
                        axes[2].bar(x, result["RMSE"], width=.6, color="#ae563a")
                        axes[2].text(x, result["RMSE"], f" n={result['observations']}", ha="center", va="bottom", fontsize=7)
                axes[2].set_xticks(range(4), ["Same", "Opposite", "Visible", "Occluded"], rotation=25)
                axes[2].set(ylabel="Object-residual RMSE [network px]", title="c  Independently labeled GT slices")
                for ax in axes:
                    ax.grid(alpha=.15)
                fig.suptitle(f"BA-Track / {pointer['sequence']} / {len(rows):,} first-observed foreground point-target pairs\nSynthetic GT; padded/same-frame/offscreen targets excluded; analysis controls do not establish a causal model improvement", fontsize=10)
                for suffix in ("png", "svg"):
                    fig.savefig(destination / ("native_motion_decomposition."+suffix), dpi=180)
                plt.close(fig)
        else:
            report["unavailable_reason"] = "No independently validated nonpadded foreground point-target support"
    write_json(destination / "M2_evaluation.json", report)
    write_json(out / "M2_evaluation_pointer.json", {"report": str(destination / "M2_evaluation.json"), "sha256": sha256(destination / "M2_evaluation.json"), "status": report["status"]})
    print(json.dumps({"status": report["status"], "point_target_pairs": report.get("observed_point_target_pairs"), "directory": str(destination)}))


if __name__ == "__main__":
    main()

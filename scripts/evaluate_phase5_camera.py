"""Externally check native camera direction/support before independent GT scoring."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, POSE_COLUMNS, run_metadata, sha256, write_csv, write_json
from gamecam_vo.evaluation import evaluate, load_trajectory
from gamecam_vo.geometry import poses_to_rows, rows_to_poses
from gamecam_vo.plotting import plot_comparison, plot_trajectory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=("DROID_W", "PI3MOS", "BA_TRACK", "WILDGS"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--reference-pointer", type=Path, required=True)
    parser.add_argument("--allow-reviewed-terminal-cleanup-failure", action="store_true", help="WildGS only: require a separate exact cleanup-only completion review")
    parser.add_argument("--allow-reviewed-native-camera-prefix-recovery", action="store_true", help="BA only: complete final native camera fields independently recovered after observed serialization OOM")
    parser.add_argument("--allow-reviewed-native-terminate-camera", action="store_true", help="BA only: independently checked complete original sparse terminate return; later full pipeline still failed")
    args = parser.parse_args()
    if args.allow_reviewed_native_camera_prefix_recovery and args.allow_reviewed_native_terminate_camera:
        raise ValueError("Select exactly one independently reviewed sparse-camera source")
    out = args.directory.resolve()
    if not any(out.is_relative_to(PROJECT / "results" / e) for e in ("E13_WILDGS", "E14_WILD_DYNAMIC", "E15_MOVIE", "E16_BONN")):
        raise ValueError("Expected a new owned phase5 result")
    status = json.loads((out / "status.json").read_text(encoding="utf-8"))
    recovered_sparse_camera = False
    camera_source_review = None
    if not status["status"].endswith("_COMPLETED"):
        prefix_review = out / "native_camera_prefix_recovery/recovery_review.json"
        if args.method == "BA_TRACK" and args.allow_reviewed_native_camera_prefix_recovery and prefix_review.exists():
            prefix = json.loads(prefix_review.read_text(encoding="utf-8"))
            recovered_sparse_camera = prefix["status"] == "COMPLETE_NATIVE_FINAL_SPARSE_CAMERA_PREFIX_RECOVERED_AND_INDEPENDENTLY_CHECKED" and not prefix["native_numeric_values_modified"] and not prefix["GT_used_in_recovery_or_direction_choice"]
            if recovered_sparse_camera:
                camera_source_review = prefix_review
        return_review = out / "native_terminate_camera_review/recovery_review.json"
        if args.method == "BA_TRACK" and args.allow_reviewed_native_terminate_camera and return_review.exists():
            returned = json.loads(return_review.read_text(encoding="utf-8"))
            accepted = returned["status"] == "COMPLETE_NATIVE_TERMINATE_CAMERA_RETURN_INDEPENDENTLY_CHECKED" and not returned["native_numeric_values_modified"] and not returned["GT_used_in_recovery_or_direction_choice"]
            if accepted:
                if camera_source_review is not None:
                    raise ValueError("Ambiguous sparse-camera source reviews")
                recovered_sparse_camera = True
                camera_source_review = return_review
        review_path = out / "map_uncertainty_review.json"
        review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
        if not recovered_sparse_camera and not (args.method == "WILDGS" and args.allow_reviewed_terminal_cleanup_failure and review.get("status") == "WILDGS_OUTPUTS_COMPLETE_TERMINAL_CLEANUP_FAILED" and review.get("native_computation_outputs_complete") and review.get("post_computation_cleanup_exception_only")):
            raise RuntimeError("Native pipeline not completed; retain failure without fabricated camera metrics")
    contract = json.loads((out / "execution_contract.json").read_text(encoding="utf-8"))
    reference_meta = json.loads(args.reference_pointer.read_text(encoding="utf-8"))
    expected = reference_meta["expected_frames"]
    if expected != contract["expected_frames"]:
        raise ValueError("Reference and native input supports differ")
    folder = out / "tracking_visualization"
    folder.mkdir(exist_ok=True)
    if args.method in ("PI3MOS", "BA_TRACK"):
        script = "export_phase5_ba_recovered_camera.py" if recovered_sparse_camera else "export_pi3mos_results.py" if args.method == "PI3MOS" else "export_ba_track_results.py"
        subprocess.check_call([sys.executable, "-X", "utf8", str(PROJECT / "scripts" / script), str(out), *([] if recovered_sparse_camera else ["--phase5"])])
        checked = json.loads((out / "output_review.json").read_text(encoding="utf-8"))
        times, poses = load_trajectory(out / "estimated_trajectory.csv")
        init = checked["initialized_after_calls"] if args.method == "PI3MOS" else checked["initialized_frontend_calls"]
        coordinate = checked.get("coordinate_check", checked.get("sparse_camera_checks"))
    else:
        native_files = list((out / "upstream_output").rglob("est_poses_full.txt"))
        if len(native_files) != 1:
            raise ValueError("Exactly one native full camera trajectory is required")
        native = native_files[0]
        raw = np.loadtxt(native, ndmin=2)
        if raw.shape != (expected, 8) or not np.isfinite(raw).all() or np.max(np.abs(np.linalg.norm(raw[:, 4:], axis=1)-1)) > 1e-4:
            raise ValueError("Native ordered finite pose/quaternion support check failed")
        times, poses = load_trajectory(native)
        video_file = native.parent.parent / "video.npz"
        with np.load(video_file) as video:
            indices = video["timestamps"].astype(int)
            if not np.array_equal(indices, video["timestamps"]) or len(np.unique(indices)) != len(indices) or (indices < 0).any() or (indices >= expected).any():
                raise ValueError("Native keyframe input indices are invalid")
            if args.method == "DROID_W":
                internal = video["tum_poses"].copy()
                _, w2c = rows_to_poses([dict(zip(POSE_COLUMNS, [i, *p], strict=True)) for i, p in zip(indices, internal, strict=True)])
                keyframes = np.linalg.inv(w2c)
                uncertainties = video["uncertainties"].copy()
            else:
                keyframes = video["poses"].copy()
        if len(indices) < 12:
            raise ValueError("Native initialization evidence has insufficient keyframes")
        translation = np.linalg.norm(keyframes[:, :3, 3]-poses[indices, :3, 3], axis=1)
        rotation = np.degrees(Rotation.from_matrix(np.swapaxes(keyframes[:, :3, :3], 1, 2) @ poses[indices, :3, :3]).magnitude())
        if translation.max() > 1e-4 or rotation.max() > .01:
            raise ValueError("Native camera/keyframe direction check failed; never choose the direction by GT score")
        coordinate = {"status": "PASS", "canonical_direction": "T_wc", "native_keyframes_compared": len(indices),
            "max_translation_difference_native_unit": float(translation.max()), "max_rotation_difference_degrees": float(rotation.max()),
            "native_video_sha256": sha256(video_file), "native_full_trajectory_sha256": sha256(native)}
        write_json(out / "coordinate_consistency.json", coordinate)
        pose_rows = poses_to_rows(times, poses)
        write_csv(out / "estimated_trajectory.csv", pose_rows, POSE_COLUMNS)
        np.savetxt(out / "estimated_trajectory.txt", [[r[k] for k in POSE_COLUMNS] for r in pose_rows], fmt="%.12g", header="Native T_wc; associated sample keys after physical-clock matching; native map scale")
        shutil.copy2(native, out / "native_full_trajectory_tum.txt")
        if args.method == "DROID_W":
            from evaluate_droid_w_mvs import export_uncertainty, plot_output_support
            inputs = json.loads((out / "input_manifest.json").read_text(encoding="utf-8"))
            export_uncertainty(out, indices, uncertainties, inputs, label="DROID-W / "+reference_meta["sequence"])
            telemetry = [json.loads(x) for x in (out / "frontend_frames.jsonl").read_text().splitlines()]
            if len(telemetry) != expected or not any(r["frontend_initialized"] for r in telemetry):
                raise ValueError("Actual frontend processing/initialization proof failed")
            write_csv(out / "tracking_status.csv", telemetry)
            plot_output_support(out, telemetry, indices, expected, "DROID-W / "+reference_meta["sequence"])
            init = sum(r["frontend_initialized"] for r in telemetry)
        else:
            trace = out / "frontend_frames.jsonl"
            if trace.exists():
                telemetry = [json.loads(x) for x in trace.read_text().splitlines()]
                if len(telemetry) != expected or [r["frame_index"] for r in telemetry] != list(range(expected)):
                    raise ValueError("WildGS native observed frontend calls do not cover every input")
                init = sum(r["frontend_initialized"] for r in telemetry)
                write_csv(out / "tracking_status.csv", telemetry)
            else:
                init = None
        checked = {"status": "PHASE5_CAMERA_EXPORT_SANITY_CHECKED", "coordinate_check": coordinate, "expected_frames": expected,
                   "keyframes": len(indices), "frontend_initialization_count": init,
                   "native_init_evidence": "Mapping completed and native keyframe count>=12; no ORB-style loss state claimed"}
        write_json(out / "output_review.json", checked)
    if len(times) != expected or not np.array_equal(times, np.arange(expected)) or not np.isfinite(poses).all():
        raise ValueError("Preserve full native pose output and associated sample-key denominator")
    reference = Path(reference_meta["reference"])
    if sha256(reference) != reference_meta["reference_sha256"]:
        raise ValueError("Frozen independent GT changed")
    gt_times, gt = load_trajectory(reference)
    partial_reference = "GT_associated_sample_keys" in reference_meta
    if partial_reference and not np.array_equal(gt_times, reference_meta["GT_associated_sample_keys"]):
        raise ValueError("Reference differs from the frozen independently associated GT support")
    if not partial_reference and not np.array_equal(gt_times, times):
        raise ValueError("Physical-clock-associated sample keys do not match")
    unit = reference_meta["unit"]
    if partial_reference:
        from phase5_partial_reference import evaluate_partial_reference
        metrics, details = evaluate_partial_reference(gt_times, gt, times, poses, unit=unit, seconds=status["wall_seconds"],
            rotation_metrics_valid=reference_meta.get("rotation_metrics_valid", False))
    elif reference_meta.get("position_alignment_identifiability_rank", 3) < 2:
        from phase5_camera_gauge import underconstrained_evaluation
        metrics, details = underconstrained_evaluation(gt, poses, unit, status["wall_seconds"])
    else:
        metrics, details = evaluate(gt_times, gt, times, poses, tolerance=1e-6, unit=unit,
            scale_status="learned_prior_physical_scale_unverified", inference_seconds=status["wall_seconds"], time_axis="frame_index")
    names = {"DROID_W": "DROID-W", "PI3MOS": "Pi3MOS-SLAM", "BA_TRACK": "BA-Track", "WILDGS": "WildGS-SLAM"}
    resource_file = out / "memory_budget_intervention.json"
    resource_intervention = json.loads(resource_file.read_text(encoding="utf-8")) if resource_file.exists() else None
    for row in metrics:
        row.update(method=names[args.method], dataset=reference_meta["dataset"], sequence=reference_meta["sequence"],
            POSE_PROVENANCE=reference_meta["GT_provenance"], processed_input_frames=expected, initialized_frontend_calls=init,
            initialized_call_semantics="Observed after native frontend call; not filled-camera coverage or sequence-level success rate",
            initialized_frontend_call_fraction=init/expected if init is not None else None,
            sequence_initialization_succeeded=(init > 0) if init is not None else None,
            scale_aligned_translation_error_unit=unit, physical_scale_recovery_claim=False,
            tracking_loss_rate=None, failure_semantics="Missing/nonfinite filled-camera fraction; not an explicit per-frame tracking-loss state",
            physical_clock_association="Frozen separately before prediction; unique sample keys do not replace physical timestamp synchronization",
            GPU_peak_whole_device_MiB=status["whole_gpu_peak_used_mib_sampled"], timing_scope=contract.get("BA_timing_scope") or "Cold native pipeline including native optimization, fill, IO; external export/evaluation excluded",
            WSL_memory_budget_at_launch=contract.get("WSL_memory_budget_at_launch"),
            resource_intervention_during_run=resource_intervention is not None,
            runtime_intervention_note=resource_intervention.get("summary", "Observed wall time includes full-swap memory pressure, read-only profiling and live extra-swap activation; no exclusive fair-FPS claim") if resource_intervention else None,
            method_category="offline_window_reconstruction" if args.method == "BA_TRACK" else "online_SLAM",
            runtime_variant=contract.get("actor_mode", "Existing independently verified compatibility paths"),
            paper_score_match=False, sensor_depth_in_model=False, reference_pose_in_model=False)
        row["native_exit_code"] = status.get("exit_code", status["stages"][-1]["exit_code"] if status.get("stages") else None)
        row["native_pipeline_terminal_status"] = status["status"]
        row["native_final_sparse_camera_recovered_after_serialization_failure"] = recovered_sparse_camera and not args.allow_reviewed_native_terminate_camera
        row["native_primary_sparse_camera_accepted_with_failed_pipeline"] = recovered_sparse_camera
        row["post_computation_cleanup_failure"] = bool(args.allow_reviewed_terminal_cleanup_failure)
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "evaluation_details.json", details)
    display_name = names[args.method]+(" / recovered final sparse camera; pipeline failed" if recovered_sparse_camera else "")
    plot_trajectory(times, poses, folder, "native_map_unit", display_name+" / unaligned native camera", "frame_index")
    plot_comparison(gt_times, gt, poses, details, folder, unit, reference_meta["dataset"]+" / "+reference_meta["sequence"], True, "frame_index", display_name, "GT-associated filled poses" if partial_reference else "Finite filled poses",
        reference_label={"MOCAP_GROUND_TRUTH": "MoCap ground truth", "SYNTHETIC_GROUND_TRUTH": "Synthetic ground truth", "ENGINE_GROUND_TRUTH": "Engine ground truth"}[reference_meta["GT_provenance"]], dense_support=expected > 200)
    anchored = details.get("orientation_anchored_diagnostic", {})
    if anchored.get("status") == "COMPUTED_DIAGNOSTIC":
        write_json(out / "orientation_anchored_camera_diagnostic.json", anchored)
        diagnostic_details = {**details, "alignments": {"Sim3": anchored["alignment"]}}
        plot_comparison(gt_times, gt, poses, diagnostic_details, folder, unit, reference_meta["dataset"]+" / "+reference_meta["sequence"], True, "frame_index", names[args.method], "Finite filled poses",
            reference_label="Synthetic ground truth", dense_support=False, alignment_label="orientation-anchored diagnostic",
            alignment_note="Orientation-anchored diagnostic; position-only alignment is underconstrained")
    subprocess.check_call([sys.executable, "-X", "utf8", str(PROJECT / "scripts/plot_phase5_gpu_memory.py"), str(out), "--method-label", names[args.method]])
    record = {**run_metadata(), "status": "PHASE5_EXTERNAL_CAMERA_EVALUATION_COMPLETED", "method": args.method, "directory": str(out),
        "expected_frames": expected, "GT_provenance": reference_meta["GT_provenance"], "reference": str(reference), "reference_sha256": sha256(reference),
        "metrics": metrics, "output_review": checked, "coordinate_check": coordinate, "figures_visually_reviewed": False,
        "same_prepared_RGB_claim": contract["target"] != "official-demo", "dynamic_pixel_or_object_motion_accuracy_claim": False}
    record["runtime_resource_intervention"] = resource_intervention
    record["native_final_sparse_camera_recovered_after_serialization_failure"] = recovered_sparse_camera and not args.allow_reviewed_native_terminate_camera
    record["native_primary_sparse_camera_accepted_with_failed_pipeline"] = recovered_sparse_camera
    record["sparse_camera_recovery_review"] = str(camera_source_review) if camera_source_review else None
    write_json(out / "evaluation_summary.json", record)
    write_json(PROJECT / "reports/PHASE5" / (args.method+"_"+out.name+"_evaluation.json"), record)
    print(json.dumps({"directory": str(out), "status": record["status"], "metrics": [{k: r[k] for k in ("alignment", "status", "ATE_RMSE", "RPE_translation_RMSE", "RPE_rotation_RMSE_degrees", "valid_pose_frames")} for r in metrics]}))


if __name__ == "__main__":
    main()

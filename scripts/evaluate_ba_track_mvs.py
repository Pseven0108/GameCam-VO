"""External engine-GT evaluation of the official BA-Track pose output.

The selected sparse pose stage is fixed by the author's pose-evaluation scripts
before MVS execution. Dense refinement camera matrices are a raw diagnostic;
they are never projected to SO(3) or selected according to a GT score.
"""
from __future__ import annotations

import _bootstrap
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gamecam_vo.common import PROJECT, read_yaml, run_metadata, sha256, write_csv, write_json
from gamecam_vo.dataset_validation import check_adapter_gate
from gamecam_vo.evaluation import evaluate, load_trajectory
from gamecam_vo.plotting import plot_comparison, plot_trajectory


def local(value):
    path = Path(str(value).replace("/mnt/d/", "D:/", 1)).resolve()
    if not path.is_relative_to(PROJECT):
        raise ValueError("Result escaped the project")
    return path


def plot_runtime(out, frontend):
    with (out / "gpu_memory.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    elapsed = np.array([float(r["run_elapsed_seconds"]) for r in rows])
    used = np.array([float(r["whole_gpu_used_mib"]) for r in rows])
    total = np.array([float(r["whole_gpu_total_mib"]) for r in rows])
    if len(rows) < 2 or not np.all(np.diff(elapsed) > 0) or not np.all((used >= 0) & (used <= total)):
        raise ValueError("GPU telemetry failed sanity checks")
    stage_starts = [(r["stage"], elapsed[i]) for i, r in enumerate(rows) if i == 0 or r["stage"] != rows[i-1]["stage"]]
    folder = out / "tracking_visualization"
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none",
                         "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(3, 1, figsize=(11, 9), height_ratios=[1.5, 1.3, 1], layout="constrained")
        axes[0].plot(elapsed/60, used, color="#275c8a", lw=1)
        axes[0].axhline(total.max(), color=".4", lw=.8, ls="--")
        for stage, time in stage_starts:
            axes[0].axvline(time/60, color=".7", lw=.6)
        axes[0].set(xlabel="Full pipeline wall time (min)", ylabel="Whole GPU memory (MiB)",
                    ylim=(0, total.max()*1.07), title=f"a  Sampled whole-device peak {used.max():.0f} MiB; includes other apps")
        stages = json.loads((out / "execution.json").read_text(encoding="utf-8"))
        names = [r["stage"].replace("_", " ") for r in stages]
        seconds = np.array([r["wall_seconds"] for r in stages])
        axes[1].barh(np.arange(len(stages)), seconds/60, color=["#275c8a"]*(len(stages)-1)+["#ae563a"])
        for i, value in enumerate(seconds):
            axes[1].text(value/60+.25, i, f"{value:.1f} s", va="center", fontsize=9)
        axes[1].set(yticks=np.arange(len(stages)), yticklabels=names, xlabel="Wall time of each native stage (min)",
                    xlim=(0, seconds.max()/60*1.17), title="b  Stage times include native IO and observation")
        axes[1].invert_yaxis()
        indices = np.array([int(r["input_timestamp"]) for r in frontend])
        initialized = np.array([bool(r["initialized"]) for r in frontend])
        axes[2].scatter(indices, np.zeros(len(indices)), color="#275c8a", marker="|", s=100)
        axes[2].scatter(indices, np.ones(len(indices)), color=".85", marker="|", s=100)
        axes[2].scatter(indices[initialized], np.ones(initialized.sum()), color="#ae563a", marker="|", s=100)
        axes[2].set(yticks=[0, 1], yticklabels=[f"Finite pose output ({len(indices)}/100)", f"Initialized calls ({initialized.sum()}/100)"],
                    xlabel="Input frame index", ylim=(-.6, 1.6), xlim=(-1, 100), title="c  Output support differs from frontend initialization")
        for ax in axes:
            ax.grid(alpha=.17, lw=.5)
        fig.suptitle("BA-Track / MVS0000: official sparse camera trajectory; offline full-pipeline timing", fontsize=11)
        fig.savefig(folder / "runtime_and_output_support.png", dpi=180)
        fig.savefig(folder / "runtime_and_output_support.svg")
        plt.close(fig)
    return {"samples": len(rows), "whole_gpu_peak_used_mib_sampled": float(used.max()),
            "median_sampling_interval_seconds": float(np.median(np.diff(elapsed))),
            "scope": "Whole device including other apps; sampled maximum, not minimum VRAM or a dedicated process peak"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plot-runtime-only", action="store_true", help="Regenerate the runtime figure from existing data; no metric/output changes")
    args = parser.parse_args()
    reports = PROJECT / "reports/SOTA"
    status = json.loads((reports / "ba_track_mvs.json").read_text(encoding="utf-8"))
    if status["status"] != "BA_TRACK_PIPELINE_COMPLETED":
        raise RuntimeError("No completed native MVS pipeline; no accuracy metrics fabricated")
    out = local(status["directory"])
    review = json.loads((out / "output_review.json").read_text(encoding="utf-8"))
    if review["status"] != "BA_TRACK_COMPLETED_OUTPUTS_SANITY_CHECKED" or not review["sparse_camera_checks"]["rigid_check_passed"]:
        raise RuntimeError("Official primary sparse pose output has not passed sanity checks")
    if sha256(out / "estimated_trajectory.csv") != review["final_trajectory_sha256"]:
        raise ValueError("Reviewed primary trajectory changed")
    protocol = json.loads((out / "pose_evaluation_protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] != "OFFICIAL_POSE_PROTOCOL_CONFIRMED_BEFORE_MVS_EXECUTION_OR_GT_SCORING":
        raise ValueError("Primary evaluation stage was not frozen")
    inputs = json.loads((out / "input_manifest.json").read_text(encoding="utf-8"))
    calibration_files = sorted((out / "known_intrinsics").glob("*.npy"))
    if len(calibration_files) != 100 or any(not np.array_equal(np.load(p), np.asarray(inputs["fixed_K"])) for p in calibration_files):
        raise ValueError("Actual sparse input calibration files differ from the frozen known K")
    e0 = Path(json.loads((PROJECT / "results/E0_MVS/latest_run.json").read_text(encoding="utf-8"))["directory"])
    _, gate = check_adapter_gate(e0, "0000", read_yaml(PROJECT / "configs/datasets/mvs_synth.yaml"))
    reference = e0 / "0000" / gate["trajectory_file"]
    gt_times, gt = load_trajectory(reference)
    times, poses = load_trajectory(out / "estimated_trajectory.csv")
    expected = np.array([r["timestamp"] for r in inputs["frames"]])
    if len(gt_times) != 100 or len(times) != 100 or not np.array_equal(gt_times, expected) or not np.array_equal(times, expected):
        raise ValueError("Full100 correspondence failed; do not shrink the evaluation denominator")
    frontend = [json.loads(line) for line in (out / "motion_decomposition/frontend_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(frontend) != 100 or [r["input_timestamp"] for r in frontend] != times.tolist():
        raise ValueError("Actual frontend processing does not cover the same100 inputs")
    if args.plot_runtime_only:
        print(json.dumps(plot_runtime(out, frontend)))
        return
    write_csv(out / "tracking_status.csv", frontend)
    wall = status["whole_pipeline_wall_seconds"]
    metrics, details = evaluate(gt_times, gt, times, poses, tolerance=1e-6, scale_status="learned_prior_game_scale_unverified",
                                unit="native_game_unit", inference_seconds=wall, time_axis="frame_index")
    allocator = [json.loads(p.read_text(encoding="utf-8")) for p in (out / "cuda_allocator_stats").glob("*.json")]
    for row in metrics:
        row.update(dataset="MVS-Synth", sequence_id="0000", baseline="BA-Track", method_category="offline_or_windowed_dynamic_reconstruction",
                   POSE_PROVENANCE="ENGINE_GROUND_TRUTH", independent_engine_ground_truth=True,
                   experiment_variant="official_default_parameters_sm120_memory_indexing_compatibility",
                   primary_camera_stage="official_sparse_SLAM_pose_evaluation", primary_pose_selected_by_GT=False,
                   processed_frontend_frames=len(frontend), initialized_frontend_frames=sum(bool(r["initialized"]) for r in frontend),
                   pose_output_coverage=row["pose_coverage"], tracking_loss_rate=None,
                   failure_rate_semantics="Missing/nonfinite sparse-SLAM pose fraction; not an upstream per-frame tracking-loss state",
                   timing_scope="All six native stages: two official DA runs, UniDepth, predicted-depth alignment, sparse tracker/BA, dense300/grid12; IO and observation included; external export/evaluation excluded",
                   actual_capture_fps="UNKNOWN", runtime_device="RTX5060_WSL_torch2.7.1_cu128",
                   learned_depth_prior="DepthAnythingV2_Large + UniDepthV2, official scale alignment", engine_depth_in_inference=False, engine_pose_in_inference=False,
                   native_sparse_crop="640x352 from shared640x360; top-left K unchanged", native_tracker_resize="512x384; official implementation",
                   dense_refines_intrinsics=True, dense_iterations=300, dense_grid_size=12,
                   global_refined_camera_rigid_check_passed=review["global_alignment_camera_usable_as_rigid_poses"],
                   gpu_peak_used_mib_whole_device_sampled=status["whole_gpu_peak_used_mib_sampled"],
                   gpu_peak_allocated_bytes_max_one_process=max((r["peak_allocated_bytes"] for r in allocator if r["cuda_initialized"]), default=None),
                   gpu_peak_reserved_bytes_max_one_process=max((r["peak_reserved_bytes"] for r in allocator if r["cuda_initialized"]), default=None),
                   allocator_memory_scope="Maximum of individual stage process allocator peaks; not a sum, not physical dedicated VRAM")
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "evaluation_details.json", details)
    folder = out / "tracking_visualization"
    folder.mkdir(exist_ok=True)
    plot_comparison(gt_times, gt, poses, details, folder, "native_game_unit", "MVS-Synth / 0000", True, "frame_index", "BA-Track sparse SLAM", "Finite sparse pose output")
    plot_trajectory(times, poses, folder, "learned_prior_map_unit", "BA-Track / MVS0000 unaligned sparse estimate", "frame_index")
    memory = plot_runtime(out, frontend)
    record = {**run_metadata(), "status": "BA_TRACK_MVS_EXTERNAL_EVALUATION_COMPLETED", "directory": str(out), "expected_frames": 100,
              "reference_for_external_evaluation": str(reference), "reference_sha256": sha256(reference), "metrics": metrics,
              "primary_pose_protocol": protocol, "output_review": review, "memory_sampling": memory,
              "per_stage_cuda_allocator_stats": allocator, "ground_truth_in_model_process": False,
              "paper_result_match": False, "dynamic_robustness_claim": False, "object_motion_accuracy_claim": False,
              "figures_visually_reviewed": False}
    write_json(out / "evaluation_summary.json", record)
    write_json(reports / "ba_track_mvs_evaluation.json", record)
    print(json.dumps({"directory": str(out), "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()

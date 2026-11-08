"""Independent Windows-side MVS engine-GT evaluation after native output checks."""
from __future__ import annotations

import _bootstrap
import json
from pathlib import Path

import numpy as np

from gamecam_vo.common import PROJECT, read_yaml, run_metadata, sha256, write_csv, write_json
from gamecam_vo.dataset_validation import check_adapter_gate
from gamecam_vo.evaluation import evaluate, load_trajectory
from gamecam_vo.plotting import plot_comparison


def main():
    reports = PROJECT / "reports/SOTA"
    status = json.loads((reports / "pi3mos_mvs.json").read_text(encoding="utf-8"))
    if status["status"] != "PI3MOS_INFERENCE_COMPLETED":
        raise RuntimeError("Completed native MVS inference required; no fabricated metrics")
    out = Path(status["directory"].replace("/mnt/d/", "D:/", 1)).resolve()
    review = json.loads((out / "output_review.json").read_text(encoding="utf-8"))
    if review["status"] != "PI3MOS_OUTPUTS_SANITY_CHECKED" or sha256(out / "estimated_trajectory.csv") != review["trajectory_sha256"]:
        raise ValueError("Primary native pose output has not passed its checks or changed")
    inputs = json.loads((out / "input_manifest.json").read_text(encoding="utf-8"))
    matrix = np.asarray(inputs["fixed_K"])
    known = np.loadtxt(out / "input_calibration.txt")
    if not np.allclose(known, [matrix[0, 0], matrix[1, 1], matrix[0, 2], matrix[1, 2]], atol=1e-12, rtol=0):
        raise ValueError("Actual known input K differs from the common comparison")
    e0 = Path(json.loads((PROJECT / "results/E0_MVS/latest_run.json").read_text(encoding="utf-8"))["directory"])
    _, validation = check_adapter_gate(e0, "0000", read_yaml(PROJECT / "configs/datasets/mvs_synth.yaml"))
    reference = e0 / "0000" / validation["trajectory_file"]
    gt_times, gt = load_trajectory(reference)
    times, poses = load_trajectory(out / "estimated_trajectory.csv")
    if len(times) != 100 or not np.array_equal(times, gt_times) or not np.array_equal(times, np.arange(100)):
        raise ValueError("Preserve the same full100 input indices and99 adjacent-pair denominator")
    metrics, details = evaluate(gt_times, gt, times, poses, tolerance=1e-6, scale_status="learned_prior_game_scale_unverified",
                                unit="native_game_unit", inference_seconds=status["wall_seconds"], time_axis="frame_index")
    allocator = status["per_process_cuda_allocator_stats"]
    main_pid = json.loads((out / "process.json").read_text(encoding="utf-8"))["pid"]
    main_allocator = [r for r in allocator if r["pid"] == main_pid and r["cuda_initialized"]]
    for row in metrics:
        row.update(dataset="MVS-Synth", sequence_id="0000", baseline="Pi3MOS-SLAM", method_category="online_SLAM",
                   POSE_PROVENANCE="ENGINE_GROUND_TRUTH", independent_engine_ground_truth=True,
                   experiment_variant="official_default_model_sm120_optional_GUI_omitted_native_output_observer",
                   processed_frontend_frames=review["frontend_calls"], initialized_frontend_frames=review["initialized_before_calls"],
                   initialized_after_frontend_calls=review["initialized_after_calls"],
                   initialization_count_semantics="Before-call initialized counts steady-state calls; after-call count also includes the initialization-completing call",
                   pose_output_coverage=row["pose_coverage"], tracking_loss_rate=None,
                   failure_rate_semantics="Missing/nonfinite filled-pose fraction; upstream has no exported ORB-style per-frame loss state",
                   timing_scope="Cold native subprocess: checkpoint/model load, initialization, tracking, final12 BA updates, trajectory fill, native output observation IO; external export/evaluation excluded; optional GUI omitted",
                   actual_capture_fps="UNKNOWN", runtime_device="RTX5060_WSL_torch2.7.1_cu128", native_keyframe_count=review["native_keyframes"],
                   learned_depth_prior="Official Pi3MOS core model", native_prior_maps=review["native_prior_maps_exported"], calibrated_dynamic_probability=False,
                   engine_depth_in_inference=False, engine_pose_in_inference=False,
                   native_sparse_crop="640x352 from common640x360; K unchanged under top-left crop", native_Pi3_preprocessing="Official preprocess_tensor_for_pi3 unchanged",
                   native_model_config="config/default.yaml; PATCHES_PER_FRAME128; PI3_FRAME_RANGE5; original12-frame initialization",
                   gpu_peak_used_mib_whole_device_sampled=status["whole_gpu_peak_used_mib_sampled"],
                   gpu_peak_allocated_bytes_main_process=max((r["peak_allocated_bytes"] for r in main_allocator), default=None),
                   gpu_peak_reserved_bytes_main_process=max((r["peak_reserved_bytes"] for r in main_allocator), default=None),
                   memory_scope="Whole-device sampling and individual-process PyTorch allocator are distinct; no physical dedicated/minimum VRAM claim")
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "evaluation_details.json", details)
    plot_comparison(gt_times, gt, poses, details, out / "tracking_visualization", "native_game_unit", "MVS-Synth / 0000", True, "frame_index", "Pi3MOS-SLAM", "Finite filled poses")
    record = {**run_metadata(), "status": "PI3MOS_MVS_EXTERNAL_EVALUATION_COMPLETED", "directory": str(out), "expected_frames": 100,
              "reference_for_external_evaluation": str(reference), "reference_sha256": sha256(reference), "metrics": metrics,
              "coordinate_check": review["coordinate_check"], "output_review": review, "GT_in_model": False,
              "paper_result_match": False, "dynamic_segmentation_accuracy_claim": False, "figures_visually_reviewed": False}
    write_json(out / "evaluation_summary.json", record)
    write_json(reports / "pi3mos_mvs_evaluation.json", record)
    print(json.dumps({"directory": str(out), "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()

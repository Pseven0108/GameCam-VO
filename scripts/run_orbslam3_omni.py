from __future__ import annotations
import _bootstrap
import csv
import json
import shlex
import shutil
import subprocess
import time
from pathlib import Path
import numpy as np

from gamecam_vo.common import PROJECT, POSE_COLUMNS, make_run_dir, read_yaml, run_metadata, sha256, write_csv, write_json
from gamecam_vo.dataset_validation import check_adapter_gate
from gamecam_vo.evaluation import evaluate, load_trajectory
from gamecam_vo.geometry import poses_to_rows, rows_to_poses
from gamecam_vo.plotting import plot_comparison, plot_trajectory
from gamecam_vo.sync import match_timestamps
from prepare_orbslam3_omni import wsl


def main():
    prepared = Path(json.loads((PROJECT / "baselines/orb_slam3/latest_input.json").read_text())["directory"])
    inputs = json.loads((prepared / "input_manifest.json").read_text(encoding="utf-8"))
    sequence = inputs["sequence_id"]
    config = read_yaml(PROJECT / "configs/datasets/omniworld_game.yaml")
    e0 = Path(inputs["e0_run"])
    entry, validation = check_adapter_gate(e0, sequence, config)
    for frame in inputs["frames"]:
        if sha256(frame["path"]) != frame["sha256"]:
            raise ValueError("Prepared RGB changed")
    out = make_run_dir(PROJECT / "results/E1B_OMNI/orb_slam3" / sequence, "orb_slam3")
    native = PROJECT / "baselines/orb_slam3"
    shutil.copy2(prepared / "input_manifest.json", out / "input_manifest.json")
    shutil.copy2(prepared / "camera.yaml", out / "camera.yaml")
    shutil.copy2(native / "opencv42_build_only.patch", out / "opencv42_build_only.patch")
    times = np.array([frame["timestamp"] for frame in inputs["frames"]])
    command = ["/usr/bin/env", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1",
               "LD_LIBRARY_PATH=" + wsl(native / "install/lib"), wsl(native / "build-runner/gamecam_orbslam3"),
               wsl(native / "upstream/Vocabulary/ORBvoc.txt"), wsl(prepared / "camera.yaml"),
               wsl(prepared / "frames.tsv"), wsl(out)]
    frozen = {"dataset_config": config, "prepared_directory": str(prepared), "e0_run": str(e0), "command": command,
              "source_revision": "0df83dde1c85c7ab91a0d47de7a29685d046f637", "pangolin_revision": "dd801d244db3a8e27b7fe8020cd751404aa818fd",
              "runner_sha256": sha256(native / "mono_runner.cc"), "runner_binary_sha256": sha256(native / "build-runner/gamecam_orbslam3"),
              "upstream_library_sha256": sha256(native / "upstream/lib/libORB_SLAM3.so"),
              "vocabulary_sha256": sha256(native / "upstream/Vocabulary/ORBvoc.txt"),
              "build_script_sha256": sha256(PROJECT / "scripts/build_orbslam3_wsl.sh"),
              "evaluation_policy": "Upstream largest-map export intersected with online tracking state OK=2; no map stitching, no interpolation, all expected rows retained",
              "POSE_PROVENANCE": "ESTIMATED_REFERENCE", "depth_used_for_inference": False, "mask_used_for_inference": False}
    write_json(out / "run_config.json", frozen)
    started = time.perf_counter()
    fatal = None
    try:
        shell = f"cd {shlex.quote(wsl(out))} && exec {shlex.join(command)}"
        with (out / "native_stdout.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "/bin/bash", "--noprofile", "--norc", "-c", shell],
                                       stdout=log, stderr=subprocess.STDOUT, timeout=600, check=False)
        if completed.returncode:
            raise RuntimeError(f"Native process exit {completed.returncode}; see native_stdout.log")
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        fatal = f"{type(exc).__name__}: {exc}"
    wrapper_seconds = time.perf_counter() - started
    pred = np.full((len(times), 4, 4), np.nan)
    states = []
    if (out / "tracking_native.csv").is_file():
        with (out / "tracking_native.csv").open(newline="", encoding="utf-8") as handle:
            states = list(csv.DictReader(handle))
    raw = out / "trajectory_native_euroc.txt"
    raw_count = 0
    if raw.is_file() and raw.stat().st_size:
        values = np.loadtxt(raw, ndmin=2)
        if values.shape[1] != 8:
            raise ValueError("Unexpected official EuRoC export columns")
        values[:, 0] *= 1e-9
        nt, npred = rows_to_poses([dict(zip(POSE_COLUMNS, row, strict=True)) for row in values])
        association, errors = match_timestamps(times, nt, 1e-6)
        raw_count = len(values)
        for i, j in enumerate(association):
            if j >= 0 and i < len(states) and int(states[i]["tracking_state"]) == 2:
                pred[i] = npred[j]
    ref_path = Path(inputs["reference_trajectory"])
    gt_times, gt = load_trajectory(ref_path)
    if len(gt_times) != len(times) or not np.allclose(times, gt_times, rtol=0, atol=1e-12):
        raise ValueError("Native expected frame set differs from E0 reference")
    shutil.copy2(ref_path, out / "evaluation_reference_trajectory.csv")
    write_csv(out / "estimated_trajectory.csv", poses_to_rows(times, pred), POSE_COLUMNS)
    np.savetxt(out / "estimated_trajectory.txt", np.array([[row[key] for key in POSE_COLUMNS] for row in poses_to_rows(times, pred)]),
               fmt="%.12g", header="T_wc, arbitrary monocular map scale, timestamp seconds; missing=nan; largest map and online OK intersection")
    timing = json.loads((out / "timing_native.json").read_text()) if (out / "timing_native.json").is_file() else {}
    measured_seconds = timing.get("track_call_seconds")
    metrics, details = evaluate(times, gt, times, pred, tolerance=1e-6, unit="reference_unit", inference_seconds=measured_seconds)
    valid = np.isfinite(pred).all(axis=(1, 2))
    valid_pairs = int(np.count_nonzero(valid[:-1] & valid[1:]))
    tracking_rows = [{"frame_index": frame["frame_index"], "timestamp": frame["timestamp"],
                      "status": "success" if valid[i] else "failed",
                      "online_tracking_state": int(states[i]["tracking_state"]) if i < len(states) else None,
                      "final_largest_map_pose_available": bool(valid[i]),
                      "processing_seconds": float(states[i]["track_seconds"]) if i < len(states) else None}
                     for i, frame in enumerate(inputs["frames"])]
    write_csv(out / "tracking_status.csv", tracking_rows)
    for row in metrics:
        row.update({"dataset": "OmniWorld-Game", "POSE_PROVENANCE": "ESTIMATED_REFERENCE", "independent_engine_ground_truth": False,
                    "evaluation_reference_type": "estimated_reference", "baseline": "ORB-SLAM3", "experiment_variant": "official_release_monocular",
                    "sequence_id": sequence, "dynamic_mask_source": "none", "runtime_device": "CPU_WSL_Ubuntu20.04",
                    "tracking_pair_success": valid_pairs / (len(times) - 1),
                    "tracking_pair_success_definition": "Adjacent expected frames both valid in final largest map and online OK; different from essential accepted-motion-edge fraction",
                    "online_ok_frames": timing.get("online_ok_frames"), "native_export_rows": raw_count,
                    "wall_seconds_including_initialization_pacing_shutdown_export": timing.get("wall_seconds_including_initialization_pacing_shutdown_export"),
                    "input_fps_timing_scope": "Sum of synchronous TrackMonocular call durations only; concurrent mapping work may continue between calls",
                    "wrapper_wall_seconds": wrapper_seconds, "e0_run": str(e0), "fatal_error": fatal})
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "evaluation_details.json", details)
    plot_comparison(times, gt, pred, details, out, "reference_unit", f"OmniWorld-Game / {sequence}", False, "seconds", "ORB-SLAM3")
    plot_trajectory(times, pred, out, "arbitrary_map_unit", "ORB-SLAM3 final largest-map estimate", "seconds")
    summary = {**run_metadata(), "experiment_id": "E1B_OMNI", "baseline": "ORB-SLAM3", "dataset": "OmniWorld-Game",
               "POSE_PROVENANCE": "ESTIMATED_REFERENCE", "independent_engine_ground_truth": False,
               "status": "FAILED" if fatal else "FINISHED_WITH_REPORTED_FAILURES", "fatal_error": fatal,
               "experiment_variant": "official_release_monocular", "result_directory": str(out), "sequence_id": sequence,
               "expected_frames": len(times), "processed_frames": len(states), "valid_final_pose_frames": int(valid.sum()),
               "timing_native": timing, "source_revision": frozen["source_revision"], "runner_sha256": frozen["runner_sha256"],
               "depth_used_for_inference": False, "dynamic_mask_source": "none", "e0_gate": True}
    write_json(out / "run_summary.json", summary)
    write_json(PROJECT / "results/E1B_OMNI/latest_run.json", {"directory": str(out), "status": summary["status"]})
    print(json.dumps({"directory": str(out), "status": summary["status"], "metrics": metrics}, ensure_ascii=False))
    return 2 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())

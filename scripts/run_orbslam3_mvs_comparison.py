"""Reuse the existing official ORB-SLAM3 build on the shared MVS RGB+K input.

No new traditional algorithm is added. Evaluation stays outside the native
process, and uses the same full 100-frame E0 engine reference as the SOTA runs.
"""
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
    pointer = json.loads((PROJECT / "reports/SOTA/mvs_rgb_input.json").read_text())
    prepared = Path(pointer["directory"])
    inputs = json.loads((prepared / "input_manifest.json").read_text())
    config = read_yaml(PROJECT / "configs/datasets/mvs_synth.yaml")
    e0 = Path(json.loads((PROJECT / "results/E0_MVS/latest_run.json").read_text())["directory"])
    _, validation = check_adapter_gate(e0, "0000", config)
    frames = inputs["frames"]
    if len(frames) != 100 or inputs["inference_inputs"] != ["RGB", "camera_intrinsics"]:
        raise ValueError("Comparison requires the same 100 RGB+K frames")
    for frame in frames:
        if sha256(frame["path"]) != frame["sha256"]:
            raise ValueError("Shared RGB input changed")
    k = np.asarray(inputs["fixed_K"], float)
    height, width = inputs["height"], inputs["width"]
    out = make_run_dir(PROJECT / "results/E11_SOTA/ORB_SLAM3_MVS_0000", "official_monocular")
    camera = f'''%YAML:1.0
File.version: "1.0"
Camera.type: "PinHole"
Camera1.fx: {k[0,0]:.12f}
Camera1.fy: {k[1,1]:.12f}
Camera1.cx: {k[0,2]:.12f}
Camera1.cy: {k[1,2]:.12f}
Camera1.k1: 0.0
Camera1.k2: 0.0
Camera1.p1: 0.0
Camera1.p2: 0.0
Camera.width: {width}
Camera.height: {height}
Camera.fps: 30
Camera.RGB: 0
ORBextractor.nFeatures: 1000
ORBextractor.scaleFactor: 1.2
ORBextractor.nLevels: 8
ORBextractor.iniThFAST: 20
ORBextractor.minThFAST: 7
Viewer.KeyFrameSize: 0.05
Viewer.KeyFrameLineWidth: 1.0
Viewer.GraphLineWidth: 0.9
Viewer.PointSize: 2.0
Viewer.CameraSize: 0.08
Viewer.CameraLineWidth: 3.0
Viewer.ViewpointX: 0.0
Viewer.ViewpointY: -0.7
Viewer.ViewpointZ: -1.8
Viewer.ViewpointF: 500.0
'''
    (out / "camera.yaml").write_text(camera)
    evaluation_times = np.array([f["timestamp"] for f in frames], float)
    native_times = np.arange(100) / 30.
    (out / "frames.tsv").write_text("".join(f"{t:.17g}\t{wsl(Path(f['path']))}\n" for t, f in zip(native_times, frames, strict=True)))
    native = PROJECT / "baselines/orb_slam3"
    command = ["/usr/bin/env", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1", "LD_LIBRARY_PATH=" + wsl(native / "install/lib"),
               wsl(native / "build-runner/gamecam_orbslam3"), wsl(native / "upstream/Vocabulary/ORBvoc.txt"),
               wsl(out / "camera.yaml"), wsl(out / "frames.tsv"), wsl(out)]
    frozen = {"command": command, "shared_input_directory": str(prepared), "e0_run": str(e0), "dataset_config": config,
              "source_revision": "0df83dde1c85c7ab91a0d47de7a29685d046f637", "runner_sha256": sha256(native / "mono_runner.cc"),
              "runner_binary_sha256": sha256(native / "build-runner/gamecam_orbslam3"), "library_sha256": sha256(native / "upstream/lib/libORB_SLAM3.so"),
              "vocabulary_sha256": sha256(native / "upstream/Vocabulary/ORBvoc.txt"),
              "clock_assumption": "Native uniform nominal 30Hz and Camera.fps=30 for scheduling; actual capture FPS UNKNOWN. Export timestamps are mapped back to frame_index for evaluation.",
              "inference_inputs": ["RGB", "camera_intrinsics"], "engine_depth_in_inference": False, "engine_pose_in_inference": False,
              "evaluation_policy": "Largest-map final poses intersected with online OK=2; no interpolation/map stitching; full 100 denominator."}
    write_json(out / "run_config.json", frozen)
    shutil.copy2(prepared / "input_manifest.json", out / "input_manifest.json")
    started, fatal = time.perf_counter(), None
    try:
        shell = "cd " + shlex.quote(wsl(out)) + " && exec " + shlex.join(command)
        with (out / "inference_log.txt").open("w", encoding="utf-8") as log:
            result = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "/bin/bash", "--noprofile", "--norc", "-c", shell],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=600)
        if result.returncode:
            fatal = f"Native process exit {result.returncode}"
    except (OSError, subprocess.TimeoutExpired) as error:
        fatal = f"{type(error).__name__}: {error}"
    wrapper_wall = time.perf_counter() - started
    states = []
    if (out / "tracking_native.csv").exists():
        with (out / "tracking_native.csv").open(newline="") as handle:
            states = list(csv.DictReader(handle))
    predicted = np.full((100, 4, 4), np.nan)
    exported = out / "trajectory_native_euroc.txt"
    raw_count = 0
    if exported.exists() and exported.stat().st_size:
        values = np.loadtxt(exported, ndmin=2)
        if values.shape[1] != 8:
            raise ValueError("Unexpected native export")
        values[:, 0] *= 1e-9
        times, poses = rows_to_poses([dict(zip(POSE_COLUMNS, row, strict=True)) for row in values])
        matches, _ = match_timestamps(native_times, times, 1e-6)
        raw_count = len(values)
        for i, j in enumerate(matches):
            if j >= 0 and i < len(states) and int(states[i]["tracking_state"]) == 2:
                predicted[i] = poses[j]
    reference = e0 / "0000" / validation["trajectory_file"]
    gt_times, gt = load_trajectory(reference)
    if not np.allclose(gt_times, evaluation_times, rtol=0, atol=1e-12):
        raise ValueError("E0 frame correspondence changed")
    rows = poses_to_rows(evaluation_times, predicted)
    write_csv(out / "estimated_trajectory.csv", rows, POSE_COLUMNS)
    np.savetxt(out / "estimated_trajectory.txt", np.array([[r[k] for k in POSE_COLUMNS] for r in rows]), fmt="%.12g", header="T_wc; frame_index; arbitrary monocular map scale; missing=nan")
    shutil.copy2(reference, out / "evaluation_reference_trajectory.csv")
    timing = json.loads((out / "timing_native.json").read_text()) if (out / "timing_native.json").exists() else {}
    metrics, details = evaluate(gt_times, gt, evaluation_times, predicted, tolerance=1e-6, unit="native_game_unit",
                                inference_seconds=timing.get("track_call_seconds"), time_axis="frame_index")
    valid = np.isfinite(predicted).all(axis=(1, 2))
    tracking = [{"frame_index": i, "timestamp": float(evaluation_times[i]), "native_nominal_timestamp": float(native_times[i]),
                 "online_tracking_state": int(states[i]["tracking_state"]) if i < len(states) else None,
                 "valid_final_largest_map_and_online_ok": bool(valid[i])} for i in range(100)]
    write_csv(out / "tracking_status.csv", tracking)
    for metric in metrics:
        metric.update(dataset="MVS-Synth", sequence_id="0000", baseline="ORB-SLAM3", method_category="online_SLAM",
                      POSE_PROVENANCE="ENGINE_GROUND_TRUTH", independent_engine_ground_truth=True, runtime_device="CPU_WSL_Ubuntu20.04",
                      experiment_variant="official_monocular_shared_RGB_K_nominal_native_30Hz", wrapper_wall_seconds=wrapper_wall,
                      input_fps_timing_scope="TrackMonocular calls only; concurrent mapping may continue outside calls", actual_capture_fps="UNKNOWN",
                      native_export_rows=raw_count, fatal_error=fatal)
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "evaluation_details.json", details)
    plot_comparison(evaluation_times, gt, predicted, details, out, "native_game_unit", "MVS-Synth / 0000", True, "frame_index", "ORB-SLAM3")
    plot_trajectory(evaluation_times, predicted, out, "arbitrary_map_unit", "ORB-SLAM3 / MVS 0000", "frame_index")
    summary = {**run_metadata(), "status": "FAILED" if fatal else "FINISHED_WITH_REPORTED_FAILURES", "directory": str(out),
               "baseline": "ORB-SLAM3", "dataset": "MVS-Synth", "sequence_id": "0000", "POSE_PROVENANCE": "ENGINE_GROUND_TRUTH",
               "expected_frames": 100, "processed_frames": len(states), "valid_final_pose_frames": int(valid.sum()),
               "timing_native": timing, "fatal_error": fatal, "actual_capture_fps": "UNKNOWN", "clock_assumption": frozen["clock_assumption"]}
    write_json(out / "run_summary.json", summary)
    write_json(PROJECT / "reports/SOTA/orbslam3_mvs_comparison.json", summary)
    print(json.dumps(summary))
    return int(fatal is not None)


if __name__ == "__main__":
    raise SystemExit(main())

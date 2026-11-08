"""Prepare exactly MVS0000's RGB+K, gated on a completed official DROID Demo."""
from __future__ import annotations

import _bootstrap
import csv
import json
from pathlib import Path

import cv2
import numpy as np

from datasets.registry import open_dataset
from gamecam_vo.common import PROJECT, make_run_dir, read_yaml, run_metadata, sha256, write_json
from gamecam_vo.dataset_validation import check_adapter_gate
from gamecam_vo.video import intrinsic_matrix


def main():
    demo = json.loads((PROJECT / "reports/SOTA/droid_official_demo.json").read_text())
    if demo["status"] != "OFFICIAL_DEMO_COMPLETED":
        raise RuntimeError("The actual official Demo must complete before GameCam adaptation")
    config = read_yaml(PROJECT / "configs/datasets/mvs_synth.yaml")
    e0 = Path(json.loads((PROJECT / "results/E0_MVS/latest_run.json").read_text())["directory"])
    _, validation = check_adapter_gate(e0, "0000", config)
    with (e0 / "0000/frame_associations.csv").open(newline="", encoding="utf-8") as handle:
        associated = list(csv.DictReader(handle))
    if len(associated) != 100:
        raise ValueError("Only the complete 100-frame sequence is authorized")
    dataset = open_dataset(config)
    intrinsics = dataset.get_intrinsics()
    out = make_run_dir(PROJECT / "data/sota_inputs/MVS-Synth/0000", "rgb_K_only_640x360")
    (out / "rgb").mkdir()
    fixed, frames, max_deviation = None, [], 0.
    for i, frame in enumerate(dataset.get_frames(640)):
        if i >= 100 or frame["frame_index"] != int(associated[i]["frame_index"]):
            raise ValueError("E0/input frame order changed")
        height, width = frame["image"].shape[:2]
        if (height, width) != (360, 640):
            raise ValueError("Unexpected prepared RGB dimensions")
        ki = intrinsic_matrix(intrinsics[i], frame["scale_x"], frame["scale_y"])
        if fixed is None:
            fixed = ki.copy()
        mapx, mapy = cv2.initUndistortRectifyMap(ki, np.zeros(5), np.eye(3), fixed, (width, height), cv2.CV_32FC1)
        rgb = cv2.remap(frame["image"], mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        path = out / "rgb" / f"frame_{i:05d}.png"
        if not cv2.imwrite(str(path), rgb):
            raise IOError("Prepared RGB write failed")
        max_deviation = max(max_deviation, float(np.max(np.abs(ki-fixed))))
        frames.append({"frame_index": i, "timestamp": float(associated[i]["evaluation_timestamp"]),
                       "path": str(path), "wsl_path": "/mnt/d/" + path.as_posix()[3:],
                       "sha256": sha256(path), "source_scaled_K": ki.tolist()})
    if len(frames) != 100:
        raise ValueError("Incomplete RGB input")
    # The model-input directory contains no reference trajectory/engine depth.
    manifest = {"dataset": "MVS-Synth", "sequence_id": "0000", "expected_frames": 100,
                "inference_inputs": ["RGB", "camera_intrinsics"], "time_axis": "frame_index", "capture_fps": "UNKNOWN",
                "engine_depth_in_inference": False, "engine_pose_in_inference": False,
                "width": width, "height": height, "fixed_K": fixed,
                "maximum_scaled_K_element_deviation_pixels": max_deviation,
                "preprocessing": "Adapter area-resize to640x360 with half-pixel K scaling, then each known Ki is rectified to the first-frame K using linear remap and zero distortion. No reference poses/depth are written to the model input.",
                "frames": frames}
    write_json(out / "input_manifest.json", manifest)
    external = {**run_metadata(), "directory": str(out), "e0_run": str(e0), "sequence_id": "0000", "e0_gate": True,
                "expected_frames": 100, "POSE_PROVENANCE": "ENGINE_GROUND_TRUTH", "evaluation_unit": "native_game_unit",
                "reference_trajectory_for_external_evaluation_only": str(e0 / "0000" / validation["trajectory_file"]),
                "official_demo_gate": demo["directory"], "model_input_manifest_sha256": sha256(out / "input_manifest.json")}
    write_json(PROJECT / "reports/SOTA/mvs_rgb_input.json", external)
    print(json.dumps({"directory": str(out), "frames": len(frames), "maximum_K_deviation_pixels": max_deviation}))


if __name__ == "__main__":
    main()

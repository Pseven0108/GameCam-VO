from __future__ import annotations
import _bootstrap
import csv
import json
from pathlib import Path
import cv2
import numpy as np

from datasets.registry import open_dataset
from gamecam_vo.common import PROJECT, make_run_dir, read_yaml, run_metadata, sha256, write_csv, write_json
from gamecam_vo.dataset_validation import check_adapter_gate
from gamecam_vo.video import intrinsic_matrix


def wsl(path):
    path = Path(path).resolve()
    if path.drive.lower() != "d:":
        raise ValueError("This local runner requires project inputs on D:")
    return "/mnt/d/" + path.as_posix()[3:]


def main():
    config = read_yaml(PROJECT / "configs/datasets/omniworld_game.yaml")
    e0 = Path(json.loads((PROJECT / "results/E0_OMNI/latest_run.json").read_text())["directory"])
    root = json.loads((e0 / "validation.json").read_text(encoding="utf-8"))
    if len(root["sequences"]) != 1:
        raise ValueError("Select one complete scene explicitly")
    sequence = root["sequences"][0]["sequence_id"]
    entry, local = check_adapter_gate(e0, sequence, config)
    dataset = open_dataset(config)
    k = dataset.get_intrinsics()
    with (e0 / sequence / "frame_associations.csv").open(newline="", encoding="utf-8") as handle:
        associations = list(csv.DictReader(handle))
    out = make_run_dir(PROJECT / "data/omniworld_game/_orbslam3_prepared", "fixed_intrinsics_rgb")
    input_manifest = []
    fixed = None
    max_deviation = 0.
    for i, frame in enumerate(dataset.get_frames(960)):
        if int(associations[i]["frame_index"]) != frame["frame_index"]:
            raise ValueError("E0 frame association changed")
        ki = intrinsic_matrix(k[i], frame["scale_x"], frame["scale_y"])
        if fixed is None:
            fixed = ki.copy()
        height, width = frame["image"].shape[:2]
        mapx, mapy = cv2.initUndistortRectifyMap(ki, np.zeros(5), np.eye(3), fixed, (width, height), cv2.CV_32FC1)
        image = cv2.remap(frame["image"], mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        path = out / f"{frame['frame_index']:06d}.png"
        if not cv2.imwrite(str(path), image):
            raise IOError("Rectified RGB write failed")
        timestamp = float(associations[i]["evaluation_timestamp"])
        max_deviation = max(max_deviation, float(np.max(np.abs(ki - fixed))))
        input_manifest.append({"frame_index": frame["frame_index"], "timestamp": timestamp,
                               "path": str(path), "wsl_path": wsl(path), "sha256": sha256(path), "source_K": ki.tolist()})
    if len(input_manifest) != len(associations):
        raise ValueError("Prepared sequence incomplete")
    # Official EuRoC defaults; actual K, resolution, color decoding and FPS are supplied here.
    camera_text = f'''%YAML:1.0
File.version: "1.0"
Camera.type: "PinHole"
Camera1.fx: {fixed[0,0]:.12f}
Camera1.fy: {fixed[1,1]:.12f}
Camera1.cx: {fixed[0,2]:.12f}
Camera1.cy: {fixed[1,2]:.12f}
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
    (out / "camera.yaml").write_text(camera_text, encoding="utf-8")
    (out / "frames.tsv").write_text("".join(f"{row['timestamp']:.17g}\t{row['wsl_path']}\n" for row in input_manifest), encoding="utf-8")
    write_json(out / "input_manifest.json", {**run_metadata(), "sequence_id": sequence, "e0_run": str(e0),
               "POSE_PROVENANCE": "ESTIMATED_REFERENCE", "reference_trajectory": str(e0 / sequence / local["trajectory_file"]),
               "fixed_K": fixed, "maximum_K_element_deviation_pixels": max_deviation, "frames": input_manifest,
               "preprocessing": "960px maximum width with area resize, then per-frame K to fixed first-frame K via linear remap, zero distortion; no reference poses, depth or masks passed to inference."})
    write_json(PROJECT / "baselines/orb_slam3/latest_input.json", {"directory": str(out)})
    print(json.dumps({"prepared_directory": str(out), "frames": len(input_manifest), "maximum_K_element_deviation_pixels": max_deviation}))


if __name__ == "__main__":
    main()

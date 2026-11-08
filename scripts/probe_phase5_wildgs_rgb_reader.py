"""Actual cached native RGB_NoPose IO probe, without launching a GPU model."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

import cv2
import numpy as np

ROOT = Path("/mnt/d/aaa/GameCam-VO")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(value):
    return Path(str(value).replace("\\", "/").replace("D:/", "/mnt/d/", 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-cache", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_cache / "wildgs"
    os.chdir(source); sys.path.insert(0, str(source))
    from src import config
    from src.utils.datasets import get_dataset, RGB_NoPose
    started = datetime.now(timezone.utc).isoformat()
    cases = []
    for sequence in ("person_tracking", "crowd", "racket"):
        pointer = ROOT / "reports/PHASE5" / ("wild_"+sequence+"_input.json")
        metadata = json.loads(pointer.read_text())
        inputs = local(metadata["directory"])
        manifest = json.loads((inputs / "input_manifest.json").read_text())
        k = np.asarray(manifest["fixed_K"])
        cfg = config.load_config("configs/wildgs_slam.yaml")
        cfg.update(dataset="wild_slam_iphone", scene=sequence)
        cfg["data"].update(input_folder=str(inputs), root_folder=str(inputs))
        cfg["cam"].update(H=manifest["height"], W=manifest["width"], H_out=manifest["height"], W_out=manifest["width"],
            fx=float(k[0, 0]), fy=float(k[1, 1]), cx=float(k[0, 2]), cy=float(k[1, 2]))
        cfg["cam"].pop("distortion", None)
        stream = get_dataset(cfg, device="cpu")
        expected_paths = [str(local(row["path"])) for row in manifest["frames"]]
        if not isinstance(stream, RGB_NoPose) or stream.color_paths != expected_paths or len(stream) != metadata["expected_frames"]:
            raise ValueError("Native RGB-only reader drops/reorders common input files")
        if stream.poses is not None or stream.depth_paths is not None or stream.H_edge or stream.W_edge:
            raise ValueError("Native reader exposes external pose/depth or changes the frozen crop")
        if not np.allclose(stream.get_intrinsic().numpy(), k[[0, 1, 0, 1], [0, 1, 2, 2]], atol=1e-4, rtol=1e-6):
            raise ValueError("Native K differs")
        errors = []
        for index in sorted(set((0, len(stream)//2, len(stream)-1))):
            key, color, depth, pose = stream[index]
            image = cv2.cvtColor(cv2.imread(expected_paths[index]), cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32)/255
            if key != index or tuple(color.shape) != image.shape or pose is not None or depth.count_nonzero().item():
                raise ValueError("Actual native IO tensors or absent-GT placeholders differ")
            error = float(np.max(np.abs(color.numpy()-image)))
            if error > 1e-7:
                raise ValueError("Native RGB tensor differs from the exact frozen common view")
            errors.append(error)
        cases.append({"sequence": sequence, "input_pointer_sha256": sha(pointer), "frames": len(stream), "full_path_order_matches_manifest": True,
            "first_middle_last_RGB_max_value_errors": errors, "depth_paths": None, "poses": None, "native_RGB_NoPose_instance": True,
            "native_GT_evaluation_skips_via_existing_isinstance_branch": True})
    result = {"status": "ACTUAL_CACHED_NATIVE_RGB_ONLY_IO_PROBE_PASS", "started_at_utc": started, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_reader_registry_alias": "wild_slam_iphone", "alias_is_reader_selection_not_data_provenance": True,
        "source": str(source / "src/utils/datasets.py"), "source_sha256": sha(source / "src/utils/datasets.py"),
        "cases": cases, "GPU_model_launched": False, "native_model_or_dataset_source_modified": False}
    (ROOT / "reports/PHASE5/wildgs_shared_RGB_reader_probe.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

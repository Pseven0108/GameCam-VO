"""Read completed local outputs and quantify rigid-pose validation failure."""
from __future__ import annotations
import _bootstrap
import json
from pathlib import Path
import pickle

import numpy as np

from gamecam_vo.common import PROJECT, write_json


def main():
    out = PROJECT / "results/E9_BA_TRACK/20261031T112523Z_official_demo_tennis"
    with (out / "upstream_output/tennis/results_refined.pkl").open("rb") as handle:
        results = pickle.load(handle)
    poses = np.asarray(results["cams_T_world"])
    r = poses[:, :3, :3]
    gram = np.swapaxes(r, 1, 2) @ r - np.eye(3)
    errors = np.max(np.abs(gram), axis=(1, 2))
    det = np.linalg.det(r)
    depth = np.asarray(results["dmaps_scaled"])
    k = np.asarray(results["intrinsics"])
    record = {"directory": str(out), "pose_shape": list(poses.shape), "all_pose_entries_finite": bool(np.isfinite(poses).all()),
              "orthogonality_error_min_median_max": [float(errors.min()), float(np.median(errors)), float(errors.max())],
              "rotation_determinant_min_median_max": [float(det.min()), float(np.median(det)), float(det.max())],
              "max_bottom_row_error": float(np.max(np.abs(poses[:, 3]-[0, 0, 0, 1]))),
              "worst_rotation": r[int(np.argmax(errors))].tolist(), "refined_intrinsics_shape": list(k.shape),
              "intrinsics_first": k[0].tolist(), "intrinsics_all_finite": bool(np.isfinite(k).all()),
              "depth_shape": list(depth.shape), "depth_all_finite": bool(np.isfinite(depth).all()),
              "depth_min_max": [float(np.nanmin(depth)), float(np.nanmax(depth))], "raw_outputs_modified": False}
    write_json(out / "native_refined_pose_diagnostic.json", record)
    write_json(PROJECT / "reports/SOTA/ba_track_refined_pose_diagnostic.json", record)
    print(json.dumps(record))


if __name__ == "__main__":
    main()

"""Inspect actual full camera/map outputs without changing native terminal status."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path

import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_json


def read_ply(path):
    names, types, count, encoding = [], [], None, None
    with path.open("rb") as stream:
        if stream.readline().strip() != b"ply":
            raise ValueError("Invalid PLY magic")
        vertex = False
        for _ in range(1000):
            line = stream.readline().decode("ascii").strip()
            fields = line.split()
            if fields[:1] == ["format"]:
                encoding = fields[1]
            elif fields[:2] == ["element", "vertex"]:
                count, vertex = int(fields[2]), True
            elif fields[:1] == ["element"]:
                vertex = False
            elif fields[:1] == ["property"] and vertex:
                if fields[1] not in ("float", "float32"):
                    raise ValueError("Expected native Gaussian float properties")
                names.append(fields[2]); types.append("<f4")
            elif line == "end_header":
                break
        else:
            raise ValueError("PLY header too long")
        if encoding != "binary_little_endian" or not count or count < 1:
            raise ValueError("Expected nonempty native binary little-endian Gaussian map")
        data = np.fromfile(stream, dtype=np.dtype(list(zip(names, types, strict=True))), count=count)
        if len(data) != count or stream.read(1):
            raise ValueError("PLY payload size mismatch")
    if not all(np.isfinite(data[name]).all() for name in names):
        raise ValueError("Nonfinite native Gaussian parameters")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--allow-terminal-cleanup-failure", action="store_true")
    args = parser.parse_args()
    out = args.directory.resolve()
    if not any(out.is_relative_to(PROJECT / "results" / e) for e in ("E13_WILDGS", "E14_WILD_DYNAMIC/WildGS", "E15_MOVIE/WildGS", "E16_BONN/WildGS")):
        raise ValueError("Expected owned WildGS output")
    status = json.loads((out / "status.json").read_text(encoding="utf-8"))
    contract = json.loads((out / "execution_contract.json").read_text(encoding="utf-8"))
    log = (out / "inference_log.txt").read_text(encoding="utf-8", errors="replace")
    cleanup_only = False
    if status["status"] != "WILDGS_INFERENCE_COMPLETED":
        token = "has no attribute 'active_children'"
        cleanup_only = (args.allow_terminal_cleanup_failure and status["exit_code"] == 1
            and log.count("Traceback (most recent call last)") == 1
            and token in log and "AttributeError:" in log and "Metrics Evaluation Done!" in log
            and "slam.py\", line 313, in run" in log)
        if not cleanup_only:
            raise RuntimeError("Native failure is not the exact post-computation cleanup exception; no success reclassification")
    trajectory_files = list((out / "upstream_output").rglob("est_poses_full.txt"))
    if len(trajectory_files) != 1:
        raise ValueError("Exactly one full native camera file required")
    full = trajectory_files[0]
    scene = full.parent.parent
    values = np.loadtxt(full, ndmin=2)
    if values.shape != (contract["expected_frames"], 8) or not np.isfinite(values).all() or not np.array_equal(values[:, 0], np.arange(len(values))):
        raise ValueError("Native camera support is incomplete")
    ply = scene / "final_gs.ply"
    data = read_ply(ply)
    xyz = np.column_stack([data[k] for k in ("x", "y", "z")])
    checkpoint = scene / "uncertainty_mlp_weight.pth"
    if not checkpoint.exists() or checkpoint.stat().st_size < 128:
        raise ValueError("Native final uncertainty checkpoint missing")
    with np.load(scene / "video.npz") as saved:
        indices = saved["timestamps"].astype(int)
        keyframes, depth = saved["poses"], saved["depths"]
        if len(indices) < 12 or not np.isfinite(keyframes).all() or not np.isfinite(depth).all():
            raise ValueError("Native initialized keyframe/depth support failed")
    figures = sorted((scene / "plots_after_refine").glob("*.png"))
    if len(figures) < len(indices):
        raise ValueError("Native final per-keyframe uncertainty/render figures incomplete")
    raw_manifest = out / "raw_uncertainty_manifest.jsonl"
    raw_rows = [json.loads(s) for s in raw_manifest.read_text().splitlines()] if raw_manifest.exists() else []
    for row in raw_rows:
        p = Path(str(row["file"]).replace("/mnt/d/", "D:/", 1))
        if sha256(p) != row["sha256"] or not np.isfinite(np.load(p)).all():
            raise ValueError("Observed raw uncertainty identity/finite check failed")
    result = {"status": "WILDGS_OUTPUTS_COMPLETE_TERMINAL_CLEANUP_FAILED" if cleanup_only else "WILDGS_CAMERA_MAP_UNCERTAINTY_OUTPUT_INSPECTION_PASS",
        "native_status_preserved": status["status"], "native_exit_code": status["exit_code"],
        "native_computation_outputs_complete": True, "post_computation_cleanup_exception_only": cleanup_only,
        "full_camera_frames": len(values), "keyframes": len(indices), "final_native_render_uncertainty_figures": len(figures),
        "native_gaussian_vertices": len(data), "all_native_gaussian_parameters_finite": True,
        "map_bounds_native_unit": {"minimum": xyz.min(axis=0).tolist(), "maximum": xyz.max(axis=0).tolist()},
        "raw_uncertainty_calls": len(raw_rows), "raw_uncertainty_is_probability": False,
        "native_plot_notes": ["Metric Depth panel is frontend depth prediction, not sensor GT", "Native uint8 Diff RGB display wraps subtraction; do not use its L1 display as quantitative image error"],
        "files": [{"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in (full, ply, checkpoint, scene / "video.npz")],
        "figures_visually_reviewed": False, "map_accuracy_or_dynamic_segmentation_accuracy_claim": False}
    write_json(out / "map_uncertainty_review.json", result)
    print(json.dumps({k: result[k] for k in ("status", "full_camera_frames", "keyframes", "native_gaussian_vertices", "raw_uncertainty_calls")}))


if __name__ == "__main__":
    main()

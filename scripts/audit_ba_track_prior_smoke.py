"""Review already-saved real outputs without rerunning either pretrained model."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    if not out.is_relative_to(PROJECT / "results/E9_BA_TRACK"):
        raise ValueError("Expected an owned component-smoke result directory")
    executions = json.loads((out / "execution.json").read_text())
    if len(executions) != 2 or any(row["exit_code"] for row in executions):
        raise ValueError("Both actual model processes must have exited successfully")
    image = cv2.cvtColor(cv2.imread(str(out / "input_rgb/rgb.png")), cv2.COLOR_BGR2RGB)
    da_path = out / "depth_anything_v2/rgb.npy"
    uni_path = out / "unidepth_v2/prior_rgb/rgb.npz"
    da = np.load(da_path)
    with np.load(uni_path) as data:
        uni, k = data["depth"].copy(), data["intrinsics"].copy()
    if da.shape != image.shape[:2] or uni.shape != image.shape[:2] or k.shape != (3, 3):
        raise ValueError("Output shape differs from the single RGB input")
    if not np.isfinite(da).all() or (da < 0).any() or not (da > 0).any():
        raise ValueError("DA-V2 requires finite nonnegative relative output with some positive support")
    if not np.isfinite(uni).all() or not (uni > 0).all() or not np.isfinite(k).all() or min(k[0, 0], k[1, 1]) <= 0:
        raise ValueError("UniDepth output validation failed")
    stats = {}
    for name, data in (("DA_V2_relative_depth_or_disparity", da), ("UniDepthV2_predicted_depth", uni)):
        stats[name] = {"shape": list(data.shape), "minimum": float(data.min()), "median": float(np.median(data)), "maximum": float(data.max()), "zero_fraction": float(np.mean(data == 0))}
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"}):
        fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), layout="constrained")
        axes[0].imshow(image)
        axes[0].set_title("Official UniDepth Demo RGB")
        for ax, data, title in zip(axes[1:], [da, uni], ["DA-V2 / relative output", "UniDepthV2 / predicted depth"], strict=True):
            low, high = np.quantile(data, [.02, .98])
            plotted = ax.imshow(data, cmap="magma", vmin=low, vmax=high)
            ax.set_title(title)
            fig.colorbar(plotted, ax=ax, shrink=.7, label="Predicted value")
        for ax in axes:
            ax.set_axis_off()
        fig.suptitle("Depth-prior component check / no target depth or K supplied; no accuracy claim", fontsize=11)
        fig.savefig(out / "depth_prior_component_check.png", dpi=220)
        fig.savefig(out / "depth_prior_component_check.svg")
        plt.close(fig)
    record = {"status": "BA_PRIOR_COMPONENT_SMOKE_COMPLETED", "directory": str(out), "results": executions, "output_checks": stats,
              "predicted_K": k.tolist(), "DA_V2_zero_values_allowed": True,
              "verification_correction": "The first owned postcheck incorrectly required strictly positive DA-V2 output. Its ReLU relative/disparity output legitimately includes zero; both model processes already exited0. Original log and executed sources retained, corrected audit reads the same saved arrays.",
              "output_sha256": {"DA_V2": sha256(da_path), "UniDepthV2": sha256(uni_path)},
              "model_inference_reexecuted_by_this_audit": False, "full_BA_Track_DAVIS_demo_completed": False,
              "camera_pose_or_motion_decomposition_inference": False, "GameCam_MVS_inference": False,
              "scope": "Official prior component scripts on the vendored official UniDepth Demo RGB only; no reference depth or K supplied"}
    write_json(out / "status_output_review.json", record)
    write_json(PROJECT / "reports/SOTA/ba_track_depth_prior_smoke.json", record)
    print(json.dumps(record))


if __name__ == "__main__":
    main()

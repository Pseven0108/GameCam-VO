"""Visual audit of acquired inputs and physical clocks, without running models."""
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

from gamecam_vo.common import PROJECT
from gamecam_vo.evaluation import load_trajectory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sequence")
    args = parser.parse_args()
    reports = PROJECT / "reports/PHASE5"
    acquired = json.loads((reports / ("wild_"+args.sequence+"_data.json")).read_text(encoding="utf-8"))
    prepared = json.loads((reports / ("wild_"+args.sequence+"_input.json")).read_text(encoding="utf-8"))
    source = Path(acquired["directory"])
    rows = json.loads(Path(acquired["RGB_manifest"]).read_text(encoding="utf-8"))
    depths = np.loadtxt(source / "depth.txt", dtype=str, ndmin=2, skiprows=3)
    intrinsics = json.loads((source / "intrinsics.json").read_text())
    folder = Path(prepared["external_validation_directory"]) / "visualization"
    folder.mkdir(exist_ok=True)
    indices = [0, len(rows)//2, len(rows)-1]
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(2, 3, figsize=(12, 5.8), layout="constrained")
        for col, index in enumerate(indices):
            rgb = cv2.cvtColor(cv2.imread(rows[index]["path"]), cv2.COLOR_BGR2RGB)
            dep = cv2.imread(str(source / depths[index, 1]), cv2.IMREAD_UNCHANGED).astype(float) * intrinsics["depth_scale"]
            positive = dep[dep > 0]
            axes[0, col].imshow(rgb)
            axes[0, col].set_title(f"Original RGB / sample{index}")
            im = axes[1, col].imshow(np.ma.masked_less_equal(dep, 0), cmap="viridis", vmin=np.quantile(positive, .02), vmax=np.quantile(positive, .98))
            axes[1, col].set_title("Native sensor depth / display2-98%")
            fig.colorbar(im, ax=axes[1, col], fraction=.035, label="Depth (m)")
            for row in axes:
                row[col].axis("off")
        fig.suptitle(f"Wild-SLAM MoCap / {args.sequence} / input audit, no dynamic labels\nOriginal capture grids shown; sensor depth is excluded from RGB-only inference")
        for ext in ("png", "svg"):
            fig.savefig(folder / ("native_RGB_depth_audit."+ext), dpi=180)
        plt.close(fig)
        times = np.array([r["timestamp_seconds"] for r in rows])
        _, poses = load_trajectory(Path(prepared["reference"]))
        fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
        axes[0].plot(np.arange(1, len(times)), np.diff(times)*1000, color="#34677a", lw=.8)
        axes[0].set(xlabel="Second sample index in adjacent pair", ylabel="Published RGB interval (ms)", title=f"a  Physical capture clock / {len(times)} samples")
        for tie in acquired["timestamp_tie_diagnostic"]:
            index = tie["input_indices"][1]
            axes[0].scatter([index], [0], color="#bc6b31", s=22, zorder=4)
            gt_note = "GT poses identical" if tie["published_GT_poses_identical"] else "GT poses differ"
            rgb_note = "RGB identical" if tie["RGB_SHA_equal"] else "RGB differs"
            axes[0].annotate("Published duplicate clock\n"+rgb_note+", "+gt_note, (index, 0), xytext=(index+35, 8), fontsize=8, arrowprops={"arrowstyle": "-", "color": ".4"})
        axes[1].plot(poses[:, 0, 3], poses[:, 2, 3], color="#34677a", lw=1)
        axes[1].scatter(poses[[0, -1], 0, 3], poses[[0, -1], 2, 3], color=["#34677a", "#bc6b31"], s=20)
        axes[1].set(xlabel="Published world X (m)", ylabel="Published world Z (m)", title="b  Independent published MoCap path")
        axes[1].set_aspect("equal", adjustable="datalim")
        for ax in axes:
            ax.grid(alpha=.15, lw=.5)
        fig.suptitle(f"{args.sequence}: physical-clock association frozen before any model score\nUnique sample keys are bookkeeping after timestamp matching; all input frames retained", fontsize=10)
        for ext in ("png", "svg"):
            fig.savefig(folder / ("clock_and_reference_audit."+ext), dpi=180)
        plt.close(fig)
    print(json.dumps({"sequence": args.sequence, "directory": str(folder), "PNG_count": 2, "purpose": "input-and-clock-audit-only"}))


if __name__ == "__main__":
    main()

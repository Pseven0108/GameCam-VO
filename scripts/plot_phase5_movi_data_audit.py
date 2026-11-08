"""Actual held-out synthetic data audit figures, before model interpretation."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gamecam_vo.common import sha256, write_json
from phase5_motion_support import load_movi_ground_truth, local
from phase5_movi_geometry import camera_parameters, dequantize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_pointer", type=Path)
    args = parser.parse_args()
    pointer, audit, fields, motion = load_movi_ground_truth(args.reference_pointer)
    folder = local(pointer["external_validation_directory"]) / "visualization"
    folder.mkdir(exist_ok=False)
    _, cameras = camera_parameters(fields)
    ranges = dequantize(fields["depth"], fields["metadata__depth_range"])
    lo, hi = np.quantile(ranges[ranges > 0], [.02, .98])
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(3, 4, figsize=(12.5, 8.6), layout="constrained")
        for row, frame in zip(axes, (0, 12, 23), strict=True):
            row[0].imshow(fields["video"][frame]); row[0].set_title(f"RGB {frame} / t={frame/12:.3f}s")
            row[1].imshow(motion["dynamic_pixel_mask"][frame], cmap="gray", vmin=0, vmax=1); row[1].set_title("GT moving-instance pixels")
            im = row[2].imshow(ranges[frame], vmin=lo, vmax=hi, cmap="viridis")
            fig.colorbar(im, ax=row[2], fraction=.045, label="Euclidean range [world unit]")
            row[2].set_title("GT range / display 2-98% clipped")
            row[3].imshow(fields["segmentations"][frame], cmap="tab20", vmin=0, vmax=20); row[3].set_title("Instance IDs / 0=environment")
            for ax in row:
                ax.set_xticks([]); ax.set_yticks([])
        fig.suptitle(f"MOVi-E test / {pointer['sequence']} / native 256x256 / condition {audit['condition']}\nIndependent synthetic GT; sensor range and motion labels are excluded from every RGB/K model input", fontsize=11)
        for suffix in ("png", "svg"):
            fig.savefig(folder / ("native_RGB_motion_range_instances."+suffix), dpi=165)
        plt.close(fig)
        fig, axes = plt.subplots(2, 2, figsize=(11, 7.6), layout="constrained")
        position = cameras[:, :3, 3]
        axes[0, 0].plot(position[:, 0], position[:, 1], color="#275c8a", marker=".", ms=3)
        axes[0, 0].scatter(*position[0, :2], color="#275c8a", marker="o", s=25, label="First camera")
        axes[0, 0].scatter(*position[-1, :2], color="#ae563a", marker="s", s=25, label="Last camera")
        axes[0, 0].set(xlabel="X [Kubric world unit]", ylabel="Y [Kubric world unit]", title=f"a  GT camera XY / effective position rank {audit['camera_effective_translation_rank']}")
        axes[0, 0].legend(frameon=False)
        frames = np.arange(24)
        axes[0, 1].plot(frames, motion["dynamic_pixel_mask"].mean(axis=(1, 2)), color="#275c8a")
        axes[0, 1].set(xlabel="Input frame", ylabel="Visible moving-pixel fraction", ylim=(0, 1), title="b  Labels use actual per-frame rigid motion")
        mean_speed = [float(motion["GT_surface_speed_world_unit_per_second"][i][motion["dynamic_pixel_mask"][i]].mean()) if motion["dynamic_pixel_mask"][i].any() else np.nan for i in frames]
        axes[1, 0].plot(frames, mean_speed, color="#275c8a")
        axes[1, 0].set(xlabel="Input frame", ylabel="Mean visible moving-surface speed [world-unit/s]", title="c  Finite-displacement speed; rotation included")
        interior = motion["GT_foreground_interior"]
        offscreen = motion["GT_offscreen"]
        hidden = motion["GT_occluded_in_view"]
        visibility_counts = (interior & ~offscreen).sum(axis=(1, 2))
        interior_counts = interior.sum(axis=(1, 2))
        occlusion_fraction = np.divide((hidden & interior).sum(axis=(1, 2)), visibility_counts, out=np.full(23, np.nan), where=visibility_counts > 0)
        exit_fraction = np.divide((offscreen & interior).sum(axis=(1, 2)), interior_counts, out=np.full(23, np.nan), where=interior_counts > 0)
        axes[1, 1].plot(np.arange(23), occlusion_fraction, color="#ae563a", label="Occluded / in-view foreground")
        axes[1, 1].plot(np.arange(23), exit_fraction, color="#275c8a", label="Offscreen / all foreground")
        axes[1, 1].set(xlabel="Origin input frame (next-frame target)", ylabel="GT geometry fraction", ylim=(0, 1), title="d  Depth-tested occlusion and field-of-view exits")
        axes[1, 1].legend(frameon=False, fontsize=8)
        for ax in axes.ravel():
            ax.grid(alpha=.15)
        fig.suptitle(f"Actual source clocks: 24 frames at 12FPS / SYNTHETIC_GROUND_TRUTH\nCenter/bounding-box conventions independently checked; flow audit {audit['flow_geometry_review']['status']}; FOV scalar, M3 unvalidated", fontsize=10)
        for suffix in ("png", "svg"):
            fig.savefig(folder / ("camera_motion_visibility_audit."+suffix), dpi=180)
        plt.close(fig)
    write_json(folder / "figure_provenance.json", {"GT_audit_sha256": pointer["GT_audit_sha256"], "figures_visually_reviewed": False,
        "files": [{"file": p.name, "sha256": sha256(p)} for p in sorted(folder.iterdir()) if p.suffix in (".png", ".svg")],
        "GT_condition": audit["condition"], "occlusion_fraction": occlusion_fraction.tolist(), "offscreen_fraction": exit_fraction.tolist(),
        "sensor_GT_in_model": False, "source_selection_uses_model_scores": False})
    print(json.dumps({"directory": str(folder), "PNG_count": 2, "SVG_count": 2, "visual_QA_pending": True}))


if __name__ == "__main__":
    main()

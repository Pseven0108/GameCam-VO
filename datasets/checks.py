from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np

from gamecam_vo.common import write_csv
from gamecam_vo.geometry import invert_se3
from gamecam_vo.plotting import plt, save_figure


def depth_reprojection(dataset, out: Path, pair_count=9, grid_stride=8):
    """Compare measured depth under documented camera transforms; retain occlusions."""
    poses, intrinsics = dataset.get_poses(), dataset.get_intrinsics()
    indices = np.unique(np.linspace(0, len(poses) - 2, min(pair_count, len(poses) - 1), dtype=int))
    rows = []
    for first in indices:
        second = first + 1
        d1, valid1 = dataset.get_depth(int(first))
        d2, valid2 = dataset.get_depth(int(second))
        height, width = d1.shape
        v, u = np.mgrid[grid_stride // 2:height:grid_stride, grid_stride // 2:width:grid_stride]
        v, u = v.ravel(), u.ravel()
        keep = valid1[v, u]
        v, u = v[keep], u[keep]
        z = d1[v, u]
        k1, k2 = intrinsics[first], intrinsics[second]
        xyz = np.column_stack(((u - k1[0, 2]) / k1[0, 0] * z,
                               (v - k1[1, 2]) / k1[1, 1] * z, z))
        relative = invert_se3(poses[second]) @ poses[first]
        xyz2 = xyz @ relative[:3, :3].T + relative[:3, 3]
        positive = xyz2[:, 2] > 0
        projected = xyz2 @ k2.T
        with np.errstate(divide="ignore", invalid="ignore"):
            uv = projected[:, :2] / projected[:, 2:]
        finite = np.isfinite(uv).all(axis=1) & positive
        rounded = np.zeros_like(uv, dtype=int)
        rounded[finite] = np.rint(uv[finite]).astype(int)
        inside = finite & (rounded[:, 0] >= 0) & (rounded[:, 0] < d2.shape[1]) & (rounded[:, 1] >= 0) & (rounded[:, 1] < d2.shape[0])
        src, dst = np.flatnonzero(inside), rounded[inside]
        good_target = valid2[dst[:, 1], dst[:, 0]]
        src, dst = src[good_target], dst[good_target]
        target_depth = d2[dst[:, 1], dst[:, 0]]
        relative_error = np.abs(xyz2[src, 2] - target_depth) / np.maximum(target_depth, 1e-9)
        row = {"first_frame": dataset.records[first]["frame_index"], "second_frame": dataset.records[second]["frame_index"],
               "finite_source_samples": len(z), "overlapping_valid_samples": len(relative_error),
               "median_relative_depth_error": float(np.median(relative_error)) if len(relative_error) else None,
               "p95_relative_depth_error": float(np.percentile(relative_error, 95)) if len(relative_error) else None,
               "fraction_within_5_percent_depth": float(np.mean(relative_error <= 0.05)) if len(relative_error) else None}
        rows.append(row)
        if len(rows) == 1 and len(src):
            image1 = cv2.imread(str(dataset.records[first]["rgb_path"]))
            image2 = cv2.imread(str(dataset.records[second]["rgb_path"]))
            colors = image2[dst[:, 1], dst[:, 0]][:, ::-1] / 255.0
            fig, axes = plt.subplots(1, 3, figsize=(12, 3.7), layout="constrained")
            axes[0].imshow(image1[..., ::-1])
            axes[1].imshow(image2[..., ::-1])
            axes[2].imshow(image1[..., ::-1], alpha=0.35)
            axes[2].scatter(u[src], v[src], c=colors, s=6, marker="s")
            for ax, title in zip(axes, (f"Source frame {row['first_frame']}", f"Target frame {row['second_frame']}",
                                       "Target RGB reprojected to source\nusing dataset depth and camera pose"), strict=True):
                ax.set_title(title)
                ax.set_axis_off()
            save_figure(fig, out / "depth_reprojection_check")
    write_csv(out / "depth_reprojection.csv", rows)
    return rows


def modality_preview(dataset, out: Path):
    record = dataset.records[0]
    image = cv2.imread(str(record["rgb_path"]))
    depth, valid = dataset.get_depth(0)
    mask = dataset.get_dynamic_masks(0)
    count = 3 if mask is not None else 2
    fig, axes = plt.subplots(1, count, figsize=(5 * count, 3.8), layout="constrained")
    axes[0].imshow(image[..., ::-1])
    axes[0].set_title(f"Original RGB: frame {record['frame_index']}")
    observed = depth[valid]
    vmax = float(np.percentile(observed, 95)) if len(observed) else 1
    dots = axes[1].imshow(np.ma.masked_where(~valid, depth), cmap="cividis", vmin=0, vmax=vmax)
    axes[1].set_title("Depth; invalid / infinite values masked\nDisplay clipped at finite p95")
    fig.colorbar(dots, ax=axes[1], label=dataset.get_metadata()["length_unit"], shrink=0.75)
    if mask is not None:
        axes[2].imshow(image[..., ::-1])
        axes[2].imshow(np.ma.masked_where(~mask, mask), cmap="autumn", vmin=0, vmax=1, alpha=0.55)
        axes[2].set_title("Dataset-provided dynamic mask\nModel-derived annotation, not oracle GT")
    for ax in axes:
        ax.set_axis_off()
    save_figure(fig, out / "modalities_preview")

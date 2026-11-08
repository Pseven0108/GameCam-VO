from __future__ import annotations

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.ticker import FixedLocator, FormatStrFormatter
import numpy as np

plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
                     "font.size": 9, "svg.fonttype": "none", "pdf.fonttype": 42,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "legend.frameon": False, "axes.linewidth": 0.8})


def save_figure(figure, path: Path):
    figure.savefig(path.with_suffix(".png"), dpi=220, bbox_inches="tight", pad_inches=0.2)
    figure.savefig(path.with_suffix(".svg"), bbox_inches="tight", pad_inches=0.2)
    plt.close(figure)


def style_3d_axes(ax):
    # Long native coordinates and tiny reference units both need uncluttered ticks.
    for axis, limits in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim()), (ax.zaxis, ax.get_zlim())):
        axis.set_major_locator(FixedLocator(np.linspace(*limits, 5)[1:-1]))
        axis.set_major_formatter(FormatStrFormatter("%.5g"))
        axis.labelpad = 4
    ax.tick_params(labelsize=8, pad=0)


def plot_trajectory(timestamps: np.ndarray, poses: np.ndarray, directory: Path,
                    unit: str, status: str, time_kind: str = "seconds") -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    finite = np.isfinite(poses).all(axis=(1, 2)) & np.isfinite(timestamps)
    indices = np.flatnonzero(finite)
    if not len(indices):
        return []
    xyz = poses[:, :3, 3].copy()
    xyz[~finite] = np.nan
    times = timestamps - timestamps[indices[0]]
    norm = Normalize(float(np.nanmin(times[finite])), max(float(np.nanmax(times[finite])), 1e-9))
    prefix = f"{status}\nCamera-to-world, OpenCV camera axes; native world [{unit}]"
    time_label = ("Relative frame index" if time_kind == "frame_index" else
                  ("Elapsed candidate time [s]" if "CANDIDATE" in time_kind else "Elapsed time [s]"))
    fig = plt.figure(figsize=(7.2, 5.6), layout="constrained")
    ax = fig.add_subplot(projection="3d")
    ax.plot(*xyz.T, color="#999999", linewidth=0.7)
    dots = ax.scatter(*xyz[finite].T, c=times[finite], norm=norm, cmap="cividis", s=5)
    selected = indices[np.linspace(0, len(indices) - 1, min(14, len(indices)), dtype=int)]
    span = max(float(np.nanmax(np.ptp(xyz[finite], axis=0))), 1e-5)
    forward = poses[selected, :3, 2] * span * 0.04
    ax.quiver(*xyz[selected].T, *forward.T, color="#356778", linewidth=0.8)
    endpoints = [(indices[0], "Start / End")] if len(indices) == 1 else [(indices[0], "Start"), (indices[-1], "End")]
    for index, label in endpoints:
        ax.text(*xyz[index], label, fontsize=8)
    lower, upper = np.nanmin(xyz, axis=0), np.nanmax(xyz, axis=0)
    center = (lower + upper) / 2
    for setter, value in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), center, strict=True):
        setter(value - span * 0.55, value + span * 0.55)
    ax.set_box_aspect((1, 1, 1))
    style_3d_axes(ax)
    ax.set(xlabel="X", ylabel="Y", zlabel="Z", title=prefix)
    fig.colorbar(dots, ax=ax, shrink=0.65, label=time_label)
    save_figure(fig, directory / "trajectory_3d")
    for axes, name in (((0, 1), "xy"), ((0, 2), "xz")):
        fig, ax = plt.subplots(figsize=(6.4, 4.8), layout="constrained")
        a, b = axes
        ax.plot(xyz[:, a], xyz[:, b], color="#999999", linewidth=0.7)
        dots = ax.scatter(xyz[finite, a], xyz[finite, b], c=times[finite], norm=norm, cmap="cividis", s=5)
        for index, label in endpoints:
            ax.annotate(label, xyz[index, [a, b]], xytext=(5, 5), textcoords="offset points")
        ax.set(xlabel=f"{'XYZ'[a]} [{unit}]", ylabel=f"{'XYZ'[b]} [{unit}]", title=prefix)
        ax.set_aspect("equal", adjustable="datalim")
        fig.colorbar(dots, ax=ax, label=time_label)
        save_figure(fig, directory / f"trajectory_{name}")
    fig, ax = plt.subplots(figsize=(7.2, 3.6), layout="constrained")
    for component, color in zip(range(3), ("#376d89", "#b08049", "#7a6b9b"), strict=True):
        forward = poses[:, component, 2].copy()
        forward[~finite] = np.nan
        ax.plot(times, forward, label=f"Forward {'XYZ'[component]}", color=color, linewidth=0.9)
    ax.set(xlabel=time_label, ylabel="Camera forward unit vector in world",
           ylim=(-1.1, 1.1), title=f"{status}: camera orientation")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
    save_figure(fig, directory / "camera_orientation")
    return ["trajectory_3d.png", "trajectory_xy.png", "trajectory_xz.png", "camera_orientation.png"]


def plot_comparison(gt_times, gt_poses, predicted, details, directory: Path,
                    unit: str, dataset_label: str, independent_gt: bool, time_kind: str,
                    method_label: str = "ORB + Essential", pose_support_label: str = "Valid poses",
                    reference_label: str | None = None, dense_support: bool = False,
                    alignment_label: str = "global Sim(3)", alignment_note: str | None = None):
    alignment = details.get("alignments", {}).get("Sim3")
    if not alignment:
        return []
    association = np.asarray(details["association"], int)
    valid = np.asarray(details["valid_mask"], bool)
    estimated = np.full((len(gt_times), 3), np.nan)
    rotation = np.asarray(alignment["rotation"])
    translation = np.asarray(alignment["translation"])
    estimated[valid] = alignment["scale"] * (rotation @ predicted[association[valid], :3, 3].T).T + translation
    source = gt_poses[:, :3, 3]
    error = np.full(len(gt_times), np.nan)
    error[valid] = np.linalg.norm(estimated[valid] - source[valid], axis=1)
    reference_label = reference_label or ("Engine ground truth" if independent_gt else "Estimated reference")
    fig = plt.figure(figsize=(11.4, 5.2), layout="constrained")
    grid = fig.add_gridspec(1, 2, width_ratios=(1.3, 1))
    ax = fig.add_subplot(grid[0], projection="3d")
    ax.plot(*source.T, color="#356778", linewidth=1.6, label=reference_label)
    ax.plot(*estimated.T, color="#b77946", linewidth=.8 if dense_support else 1.3, label=f"{method_label}, {alignment_label}")
    if not dense_support:
        ax.scatter(*estimated[valid].T, color="#b77946", s=12)
    ax.scatter(*source[0], color="#356778", marker="o", s=24)
    ax.scatter(*source[-1], color="#356778", marker="s", s=24)
    lower, upper = np.nanmin(np.vstack((source, estimated)), axis=0), np.nanmax(np.vstack((source, estimated)), axis=0)
    center = (lower + upper) / 2
    span = max(float(np.max(upper - lower)), 1e-5)
    for setter, value in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), center, strict=True):
        setter(value - span * 0.55, value + span * 0.55)
    ax.set_box_aspect((1, 1, 1))
    style_3d_axes(ax)
    ax.set(xlabel="X", ylabel="Y", zlabel="Z",
           title=f"a  World positions [{unit}]")
    ax.legend(loc="upper left", fontsize=8)
    residual = fig.add_subplot(grid[1])
    residual.plot(gt_times, error, color="#b77946", linewidth=.65 if dense_support else 1.0, marker="." if dense_support else "o", markersize=1.5 if dense_support else 3)
    failed = ~valid
    if failed.any():
        for value in gt_times[failed]:
            residual.axvline(value, color="#b7b7b7", linewidth=0.5, alpha=0.55)
    residual.set(xlabel="Frame index" if time_kind == "frame_index" else "Timestamp [s]",
                 ylabel=f"Position residual [{unit}]", title=f"b  {pose_support_label} {valid.sum()}/{len(valid)}\nFailed frames remain in coverage statistics")
    fig.suptitle(f"{dataset_label}: RGB-only camera trajectory\n"+(alignment_note or "Global scale alignment is post-processing; no metric-scale recovery claimed"), fontsize=11)
    save_figure(fig, directory / "trajectory_comparison")
    return ["trajectory_comparison.png"]

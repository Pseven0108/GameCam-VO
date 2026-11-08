"""Two full-bounds projections of actual native Gaussian centers, not map GT."""
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
from inspect_phase5_wildgs_outputs import read_ply


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    review = json.loads((out / "map_uncertainty_review.json").read_text(encoding="utf-8"))
    if not review["native_computation_outputs_complete"]:
        raise ValueError("Accept actual map payload before plotting")
    file = next((out / "upstream_output").rglob("final_gs.ply"))
    data = read_ply(file)
    xyz = np.column_stack([data[k] for k in ("x", "y", "z")])
    colors = np.clip(.5+.28209479177387814*np.column_stack([data[f"f_dc_{i}"] for i in range(3)]), 0, 1)
    stride = max(1, int(np.ceil(len(data)/16000)))
    indices = np.unique(np.r_[np.arange(0, len(data), stride), len(data)-1])
    folder = out / "tracking_visualization"
    folder.mkdir(exist_ok=True)
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), layout="constrained")
        for ax, (first, second, title) in zip(axes, ((0, 2, "a  Native Gaussian centers / XZ"), (0, 1, "b  Native Gaussian centers / XY")), strict=True):
            ax.scatter(xyz[indices, first], xyz[indices, second], c=colors[indices], s=.5, edgecolors="none", rasterized=True)
            bounds = xyz[:, [first, second]]
            lo, hi = bounds.min(axis=0), bounds.max(axis=0)
            pad = np.maximum((hi-lo)*.02, 1e-4)
            ax.set(xlabel="XYZ"[first]+" (native map unit)", ylabel="XYZ"[second]+" (native map unit)", title=title,
                xlim=(lo[0]-pad[0], hi[0]+pad[0]), ylim=(lo[1]-pad[1], hi[1]+pad[1]))
            ax.set_aspect("equal", adjustable="box")
            ax.grid(alpha=.15, lw=.5)
        fig.suptitle(f"WildGS-SLAM native map: {len(data):,} Gaussian centers, {len(indices):,} displayed\nDeterministic stride {stride}; full bounds retained; native DC color; no map-accuracy claim", fontsize=10)
        for ext in ("png", "svg"):
            fig.savefig(folder / ("native_gaussian_map."+ext), dpi=200, bbox_inches="tight", pad_inches=.06)
        plt.close(fig)
    write_json(out / "map_plot_provenance.json", {"native_PLY": str(file), "native_PLY_sha256": sha256(file), "native_vertices": len(data),
        "displayed_vertices": len(indices), "deterministic_stride": stride, "full_bounds": True, "point_filtering": False,
        "color": "Native degree-zero spherical harmonic DC to RGB, clip to display gamut", "unit": "native_map_unit",
        "figures": [{"file": str(p.relative_to(out)), "sha256": sha256(p)} for p in sorted(folder.glob("native_gaussian_map.*"))]})


if __name__ == "__main__":
    main()

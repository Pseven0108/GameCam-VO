from __future__ import annotations
import _bootstrap
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gamecam_vo.common import write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--method-label", default="DROID-W")
    args = parser.parse_args()
    out = args.run_directory.resolve()
    status = json.loads((out / "status.json").read_text())
    with (out / "gpu_memory.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    elapsed = np.array([float(r["elapsed_seconds"]) for r in rows])
    memory = np.array([float(r["whole_gpu_used_mib"]) for r in rows])
    total = np.array([float(r["whole_gpu_total_mib"]) for r in rows])
    utilization = np.array([float(r["whole_gpu_utilization_percent"]) for r in rows])
    if len(rows) < 2 or not np.all(np.diff(elapsed) > 0) or not np.all((memory >= 0) & (memory <= total)):
        raise ValueError("Invalid GPU sampling data")
    style = {"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none",
             "axes.spines.top": False, "axes.spines.right": False}
    with plt.rc_context(style):
        fig, axes = plt.subplots(2, 1, figsize=(9, 5.7), sharex=True, height_ratios=[2, 1], layout="constrained")
        axes[0].plot(elapsed/60, memory, color="#275C8A", lw=1.1, label="Observed whole GPU")
        axes[0].axhline(float(total.max()), color="#555555", lw=1, ls="--", label=f"Device total: {total.max():.0f} MiB")
        axes[0].set(ylabel="Whole-GPU memory (MiB)", ylim=(0, total.max()*1.06))
        axes[0].legend(frameon=False, loc="lower right")
        axes[0].text(.01, .04, f"Sampled peak: {memory.max():.0f} MiB\nIncludes desktop and other processes", transform=axes[0].transAxes, fontsize=9)
        axes[1].plot(elapsed/60, utilization, color="#AE563A", lw=.85)
        axes[1].set(xlabel="Wall time since process launch (min)", ylabel="GPU use (%)", ylim=(-2, 102))
        for ax in axes:
            ax.grid(alpha=.17, lw=.5)
        fig.suptitle(f"{args.method_label} / {out.name}", fontsize=11)
        fig.savefig(out / "gpu_memory_timeline.png", dpi=220)
        fig.savefig(out / "gpu_memory_timeline.svg")
        plt.close(fig)
    write_json(out / "gpu_memory_sampling_summary.json", {
        "source": str(out / "gpu_memory.csv"), "run_status": status["status"], "samples": len(rows),
        "median_sampling_interval_seconds": float(np.median(np.diff(elapsed))),
        "whole_gpu_peak_used_mib_sampled": float(memory.max()), "whole_gpu_total_mib": float(total.max()),
        "scope": "Whole device, including other applications. Sampled maximum is not a guaranteed transient peak or official minimum VRAM.",
        "process_allocator_stats": status.get("per_process_cuda_allocator_stats", [json.loads(p.read_text()) for p in (out / "cuda_allocator_stats").glob("*.json")])})
    print(json.dumps({"figure": str(out / "gpu_memory_timeline.png"), "samples": len(rows), "sampled_peak_mib": float(memory.max())}))


if __name__ == "__main__":
    main()

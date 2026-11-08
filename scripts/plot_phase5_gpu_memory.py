"""Phase5 resource display with explicit gaps; never interpolate missing samples."""
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

from gamecam_vo.common import sha256, write_json


def load_sampling(out):
    file = out / "gpu_memory.csv"
    with file.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    columns = ("elapsed_seconds", "whole_gpu_used_mib", "whole_gpu_total_mib", "whole_gpu_utilization_percent")
    elapsed, memory, total, utilization = values = np.array([[float(r[k]) for r in rows] for k in columns])
    if (len(rows) < 2 or not np.isfinite(values).all() or not np.all(np.diff(elapsed) > 0)
        or not np.all((memory >= 0) & (memory <= total)) or not np.all(total > 0)
        or not np.all((utilization >= 0) & (utilization <= 100))):
        raise ValueError("Invalid actual GPU samples; never repair or impute them")
    dt = np.diff(elapsed)
    median = float(np.median(dt))
    threshold = max(5., 5 * median)
    gaps = np.flatnonzero(dt > threshold)
    summary = {"source": str(file), "source_sha256": sha256(file), "samples": len(rows),
               "first_sample_seconds": float(elapsed[0]), "last_sample_seconds": float(elapsed[-1]),
               "median_sampling_interval_seconds": median, "maximum_sampling_interval_seconds": float(dt.max()),
               "display_gap_threshold_seconds": threshold, "display_gap_policy": "Break connecting lines only when delta_t > max(5 seconds, 5 * median actual sample interval); retain all samples and their original values",
               "intervals_above_gap_threshold": [{"first_sample_seconds": float(elapsed[i]), "next_sample_seconds": float(elapsed[i + 1]),
                                                  "interval_seconds": float(dt[i])} for i in gaps],
               "whole_gpu_peak_used_mib_sampled": float(memory.max()), "whole_gpu_total_mib": float(total.max()),
               "scope": "Whole device including desktop/other processes. Missing queries are not reconstructed. The sampled maximum is not a guaranteed transient peak or official minimum VRAM.",
               "sampling_or_plot_review_source_sha256": sha256(Path(__file__))}
    return (elapsed, memory, total, utilization, gaps + 1), summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--method-label", required=True)
    args = parser.parse_args()
    out = args.run_directory.resolve()
    status = json.loads((out / "status.json").read_text())
    (elapsed, memory, total, utilization, breaks), summary = load_sampling(out)
    x = np.insert(elapsed / 60, breaks, np.nan)
    memory_display = np.insert(memory, breaks, np.nan)
    utilization_display = np.insert(utilization, breaks, np.nan)
    if (not np.array_equal(x[np.isfinite(x)] * 60, elapsed) and not np.allclose(x[np.isfinite(x)] * 60, elapsed, atol=1e-10, rtol=1e-14)):
        raise AssertionError("Display must preserve actual time samples")
    if not np.array_equal(memory_display[np.isfinite(memory_display)], memory):
        raise AssertionError("Display must preserve every actual memory observation")
    style = {"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none",
             "axes.spines.top": False, "axes.spines.right": False}
    with plt.rc_context(style):
        fig, axes = plt.subplots(2, 1, figsize=(9.6, 6.1), sharex=True, height_ratios=[2, 1], layout="constrained")
        axes[0].plot(x, memory_display, color="#275C8A", lw=1.0, marker=".", ms=1.3, label="Observed device samples")
        axes[0].axhline(float(total.max()), color="#555555", lw=1, ls="--", label=f"Device total: {total.max():.0f} MiB")
        axes[0].set(ylabel="Whole-GPU memory (MiB)", ylim=(0, total.max() * 1.06))
        axes[0].legend(frameon=False, loc="lower right")
        axes[0].text(.01, .04, f"Sampled maximum: {memory.max():.0f} MiB\nIncludes desktop; transient peaks may be missed", transform=axes[0].transAxes, fontsize=8)
        axes[1].plot(x, utilization_display, color="#AE563A", lw=.8, marker=".", ms=1.2)
        axes[1].set(xlabel="Wall time since process launch (min)", ylabel="Reported GPU use (%)", ylim=(-2, 102))
        for ax in axes:
            ax.grid(alpha=.17, lw=.5)
        fig.suptitle(f"{args.method_label} / {out.name}\n"
                     f"Actual sample spacing: median {summary['median_sampling_interval_seconds']:.2f} s; maximum {summary['maximum_sampling_interval_seconds']:.1f} s\n"
                     f"{len(breaks)} line breaks at gaps > {summary['display_gap_threshold_seconds']:.2f} s; no missing values imputed", fontsize=10)
        fig.savefig(out / "gpu_memory_timeline.png", dpi=220)
        fig.savefig(out / "gpu_memory_timeline.svg")
        plt.close(fig)
    summary.update(run_status=status["status"], missing_values_imputed=False, line_breaks_used_in_this_plot=True,
                   process_allocator_stats=status.get("per_process_cuda_allocator_stats", []))
    write_json(out / "gpu_memory_sampling_summary.json", summary)
    print(json.dumps({"figure": str(out / "gpu_memory_timeline.png"), "samples": summary["samples"],
                      "sampled_peak_mib": summary["whole_gpu_peak_used_mib_sampled"],
                      "maximum_sampling_gap_seconds": summary["maximum_sampling_interval_seconds"], "line_breaks": len(breaks)}))


if __name__ == "__main__":
    main()

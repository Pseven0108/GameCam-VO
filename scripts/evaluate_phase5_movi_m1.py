"""Score actual dense signals on the common stride-8 input lattice; CPU only."""
from __future__ import annotations

import _bootstrap
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_json, run_metadata
from phase5_motion_metrics import evaluate_motion_scores, binary_statistics
from phase5_motion_support import load_movi_ground_truth, lattice, native_dense_maps, sample_resized_map, assert_movi_result
from phase5_movi_geometry import motion_labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=("DROID_W", "PI3MOS", "WILDGS"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--reference-pointer", type=Path, required=True)
    args = parser.parse_args()
    out = args.directory.resolve()
    pointer, audit, fields, motion = load_movi_ground_truth(args.reference_pointer)
    native_status = assert_movi_result(out, pointer)
    maps, evidence = native_dense_maps(args.method, out)
    trace_file = out / "frontend_frames.jsonl"
    frontend = None
    stage_note = "Native frontend initialization evidence unavailable"
    if trace_file.exists():
        trace = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines()]
        initialization_key = "initialized_after" if args.method == "PI3MOS" else "frontend_initialized"
        if trace and all(initialization_key in row for row in trace):
            count = sum(bool(row[initialization_key]) for row in trace)
            frontend = {"trace": str(trace_file), "sha256": sha256(trace_file),
                "observed_calls": len(trace), "initialized_after_calls": count,
                "all_observed_calls_uninitialized": count == 0}
            stage_note = ("Frontend never initialized; native signal evidence is separate" if count == 0 else
                f"Initialized frontend observed for {count}/{len(trace)} native calls")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    destination = out / "motion_evaluation" / (stamp+"_M1")
    destination.mkdir(parents=True, exist_ok=False)
    source_folder = destination / "executed_evaluation_source"
    source_folder.mkdir()
    source_files = []
    for name in (Path(__file__).name, "phase5_motion_metrics.py", "phase5_motion_support.py", "phase5_movi_geometry.py"):
        source = Path(__file__).with_name(name)
        snapshot = source_folder / name
        shutil.copy2(source, snapshot)
        if sha256(source) != sha256(snapshot):
            raise ValueError("Evaluation source changed while preserving its executed identity")
        source_files.append({"file": str(source), "sha256": sha256(snapshot), "executed_snapshot": str(snapshot)})
    semantics = "dynamic_sigmoid" if args.method == "PI3MOS" else "uncalibrated_uncertainty"
    report = {**run_metadata(), "status": "UNAVAILABLE", "method": args.method, "sequence": pointer["sequence"], "directory": str(destination),
        "evaluation_source_files": source_files,
        "GT_provenance": "SYNTHETIC_GROUND_TRUTH", "GT_audit_sha256": pointer["GT_audit_sha256"], "native_status": native_status["status"],
        "signal_semantics": semantics, "expected_input_frames": 24, "observed_signal_frame_ids": sorted(maps), "observed_signal_frames": len(maps),
        "native_signal_files": evidence, "common_lattice_input_uv": "u,v=3,11,...,251; 1024 distinct input pixels per observed frame",
        "camera_output_coverage_is_not_pixel_signal_coverage": True, "sensor_GT_in_model": False,
        "native_final_uncertainty_vs_online_prior_stages_differ": True, "no_sign_or_threshold_chosen_by_GT": True,
        "native_frontend_observation": frontend, "native_stage_interpretation": stage_note,
        "signal_metrics_establish_successful_camera_tracking": False,
        "sparse_BA_scores_pooled_with_dense_pixels": False, "figures_visually_reviewed": False,
        "target_event": "Frozen target-frame visible instance-motion union from actual rigid motion, not initial semantic is_dynamic",
        "calibration_scope": "Sigmoid calibration is evaluated against this independently declared motion event; the original released training-label event is not asserted to be identical"}
    if maps:
        uv = lattice()
        x, y = uv[:, 0].astype(int), uv[:, 1].astype(int)
        scores, labels, speeds, frames, transforms = [], [], [], [], []
        for frame, (array, mapping) in sorted(maps.items()):
            if mapping == "stride8_origin3":
                sampled = array.ravel().astype(float)
            elif mapping == "input_pixel_grid":
                sampled = array[y, x].astype(float)
            else:
                sampled = sample_resized_map(array, uv, (256, 256))
            if not np.isfinite(sampled).all():
                raise ValueError("Nonfinite native signals; retain failure, do not silently exclude pixels")
            scores.append(sampled); labels.append(motion["dynamic_pixel_mask"][frame, y, x])
            speeds.append(motion["GT_surface_speed_world_unit_per_second"][frame, y, x])
            frames.append(np.full(len(uv), frame))
            transforms.append({"frame": frame, "native_shape": list(array.shape), "mapping": mapping})
        score, label, speed, frame_ids = map(np.concatenate, (scores, labels, speeds, frames))
        result, curves = evaluate_motion_scores(label, score, semantics=semantics, probability_threshold=.4 if semantics == "dynamic_sigmoid" else None, continuous_speed=speed)
        sensitivity = {}
        fixed = score >= result["threshold"]
        for value in (.001, .01, .1):
            masks, _, _ = motion_labels(fields, threshold=value)
            sensitivity[str(value)] = binary_statistics(masks[frame_ids, np.tile(y, len(maps)), np.tile(x, len(maps))], fixed)
        coverage = []
        if semantics == "uncalibrated_uncertainty":
            for quantile in (0., .2, .4, .6, .8, .9, .95, 1.):
                threshold = float(np.quantile(score, quantile))
                coverage.append({"score_quantile": quantile, "threshold": threshold, **binary_statistics(label, score >= threshold)})
        samples = destination / "common_lattice_samples.npz"
        np.savez_compressed(samples, frame_index=frame_ids, input_uv=np.tile(uv, (len(maps), 1)), score=score,
            dynamic_GT=label, GT_surface_speed=speed, **curves)
        report.update(status="INDEPENDENT_M1_SCORED_ON_OBSERVED_NATIVE_SUPPORT", metrics=result, native_to_input_grid_transforms=transforms,
            GT_motion_threshold_sensitivity_fixed_predictions=sensitivity, uncertainty_coverage_curve=coverage,
            sample_archive=str(samples), sample_archive_sha256=sha256(samples),
            cross_method_support="Unrestricted method support here; compare methods only after intersecting actual observed frame IDs")
        with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False}):
            fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), layout="constrained")
            axes[0].set(xlabel="False positive rate", ylabel="True positive rate", xlim=(0, 1), ylim=(0, 1), title="a  Motion ranking")
            axes[1].set(xlabel="Recall", ylabel="Precision", xlim=(0, 1), ylim=(0, 1), title="b  Precision and recall")
            if curves:
                axes[0].plot(curves["false_positive_rate"], curves["true_positive_rate"], color="#275c8a", label=f"AUROC {result['AUROC']:.3f}")
                axes[0].plot([0, 1], [0, 1], ls="--", color=".6", lw=.8)
                axes[1].step(np.r_[0, curves["recall"]], np.r_[1., curves["precision"]], where="pre", color="#275c8a", label=f"AP {result['average_precision']:.3f}")
                axes[1].axhline(label.mean(), ls="--", color=".6", lw=.8, label="GT prevalence")
                axes[0].legend(frameon=False); axes[1].legend(frameon=False)
            else:
                for ax in axes[:2]:
                    ax.text(.5, .5, "N/A: single-class GT", ha="center", va="center", transform=ax.transAxes)
            bins = [r for r in result["reliability_bins"] if r["samples"]]
            axes[2].plot([r["mean_score"] for r in bins], [r["empirical_dynamic_frequency"] for r in bins], marker="o", color="#ae563a")
            axes[2].set(xlabel="Native sigmoid" if semantics == "dynamic_sigmoid" else "Raw uncertainty", ylabel="Empirical moving-pixel fraction", ylim=(0, 1),
                title="c  Probability calibration" if semantics == "dynamic_sigmoid" else "c  Ranking reliability (not ECE)")
            if semantics == "dynamic_sigmoid":
                axes[2].plot([0, 1], [0, 1], ls="--", color=".6", lw=.8); axes[2].set_xlim(0, 1)
            for ax in axes:
                ax.grid(alpha=.15)
            fig.suptitle(f"{args.method} / {pointer['sequence']}\nSynthetic GT; {len(maps)}/24 observed signal frames; {len(score):,} lattice pixels\n{stage_note}", fontsize=10)
            for suffix in ("png", "svg"):
                fig.savefig(destination / ("motion_ranking_reliability."+suffix), dpi=180)
            plt.close(fig)
            picks = sorted(set((0, len(maps)//2, len(maps)-1)))
            ordered_frames = sorted(maps)
            fig, axes = plt.subplots(len(picks), 4, figsize=(12, 2.8*len(picks)), layout="constrained", squeeze=False)
            lo, hi = (0., 1.) if semantics == "dynamic_sigmoid" else np.quantile(score, [.02, .98])
            if hi <= lo:
                hi = lo+max(1e-6, abs(lo)*.01)
            for row, pick in zip(axes, picks, strict=True):
                frame = ordered_frames[pick]
                signal = scores[pick].reshape(32, 32)
                row[0].imshow(fields["video"][frame]); row[0].set_title(f"RGB / input frame {frame}")
                row[1].imshow(motion["dynamic_pixel_mask"][frame], cmap="gray", vmin=0, vmax=1)
                row[1].set_title("GT moving-instance mask")
                im = row[2].imshow(signal, cmap="magma", vmin=lo, vmax=hi, interpolation="nearest")
                fig.colorbar(im, ax=row[2], fraction=.045)
                row[2].set_title("Native signal / 32x32 lattice")
                row[3].imshow(signal >= result["threshold"], cmap="gray", vmin=0, vmax=1, interpolation="nearest")
                row[3].set_title(f"Fixed threshold >= {result['threshold']:.3g}")
                for ax in row:
                    ax.set_xticks([]); ax.set_yticks([])
            fig.suptitle((f"{args.method}: first / middle / last observed signal frames\nSynthetic rigid-motion GT; uncertainty display uses 2-98% clipping only; all raw values used for scores" if semantics != "dynamic_sigmoid" else
                f"{args.method}: first / middle / last observed signal frames\nSynthetic rigid-motion GT; raw sigmoid displayed in [0,1]; probability calibration is measured separately")+"\n"+stage_note, fontsize=10)
            for suffix in ("png", "svg"):
                fig.savefig(destination / ("motion_GT_and_native_signal."+suffix), dpi=170)
            plt.close(fig)
    else:
        report["unavailable_reason"] = "No archived native dense signal; no rerun or fabricated map"
    write_json(destination / "M1_evaluation.json", report)
    write_json(out / "M1_evaluation_pointer.json", {"report": str(destination / "M1_evaluation.json"), "sha256": sha256(destination / "M1_evaluation.json"), "status": report["status"]})
    print(json.dumps({"method": args.method, "status": report["status"], "signal_frames": len(maps), "directory": str(destination)}))


if __name__ == "__main__":
    main()

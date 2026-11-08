"""Dense motion comparisons on actual common frame/pixel support; no NN calls."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
from itertools import combinations
import json

import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_csv, write_json
from phase5_motion_support import read, local
from phase5_motion_metrics import evaluate_motion_scores


def signal(job):
    if not job.get("result_directory"):
        return None
    out = local(job["result_directory"])
    pointer_file = out / "M1_evaluation_pointer.json"
    if not pointer_file.exists():
        if job.get("motion_evaluation_exit_code") == 0:
            raise ValueError("Successful signal analysis lacks its evidence pointer")
        return None
    pointer = read(pointer_file)
    report_file = local(pointer["report"])
    if sha256(report_file) != pointer["sha256"]:
        raise ValueError("Signal report changed without an updated identity pointer")
    report = read(report_file)
    if report["status"] == "UNAVAILABLE":
        return None
    source = local(report["sample_archive"])
    if sha256(source) != report["sample_archive_sha256"]:
        raise ValueError("Common-lattice archive changed")
    with np.load(source) as z:
        arrays = {key: z[key].copy() for key in ("frame_index", "input_uv", "score", "dynamic_GT", "GT_surface_speed")}
    return {"report": report, "arrays": arrays, "report_file": str(report_file), "report_sha256": sha256(report_file)}


def common_comparison(selected, label):
    common = sorted(set.intersection(*(set(s["arrays"]["frame_index"].astype(int)) for s in selected))) if all(selected) else []
    result = {"support": label, "status": "UNAVAILABLE", "common_frame_ids": common, "methods": [s["report"]["method"] if s else "UNAVAILABLE_SIGNAL" for s in selected]}
    if not common:
        result["reason"] = "No joint actual native signal frames; do not replace missing methods or invent maps"
        return result
    rows, support_reference = [], None
    for value in selected:
        arrays = value["arrays"]
        mask = np.isin(arrays["frame_index"], common)
        support = {key: arrays[key][mask] for key in arrays}
        if support_reference is None:
            support_reference = support
        elif any(not np.array_equal(support[key], support_reference[key]) for key in ("frame_index", "input_uv", "dynamic_GT", "GT_surface_speed")):
            raise ValueError("Common frame IDs do not imply the same pixels/independent labels; do not pool these signals")
        method = value["report"]["method"]
        metrics, _ = evaluate_motion_scores(support["dynamic_GT"], support["score"], semantics=value["report"]["signal_semantics"],
            probability_threshold=.4 if method == "PI3MOS" else None, continuous_speed=support["GT_surface_speed"])
        rows.append({"method": method, "metrics": metrics, "native_status": value["report"]["native_status"],
            "native_frontend_observation": value["report"].get("native_frontend_observation"),
            "native_stage_interpretation": value["report"].get("native_stage_interpretation"),
            "source_report": value["report_file"], "source_report_sha256": value["report_sha256"]})
    result.update(status="COMPUTED_ON_IDENTICAL_OBSERVED_FRAME_PIXEL_SUPPORT", evaluated_pixels=len(support_reference["score"]), metrics=rows,
        uncertainty_operating_point="Same predeclared 80th percentile, recomputed on this declared comparison support without GT threshold optimization",
        native_stage_caveat="Final optimized keyframe uncertainty and current-frame prior remain different temporal stages, even on common input pixels")
    return result


def main():
    reports = PROJECT / "reports/PHASE5"
    plan_file = local(read(reports / "active_E15_MOVIE_batch.json")["plan"])
    plan = read(plan_file)
    if plan["state"] != "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING" or len(plan["jobs"]) != 20:
        raise RuntimeError("All preregistered primary/repeat native attempts must first be terminal")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = PROJECT / "results/E15_MOVIE/cross_method_analysis" / stamp
    folder.mkdir(parents=True, exist_ok=False)
    primary = [j for j in plan["jobs"] if j["role"] == "primary"]
    dense_methods = ("DROID_W", "PI3MOS", "WILDGS")
    comparisons, flat = [], []
    for sequence in dict.fromkeys(j["sequence"] for j in primary):
        cases = {m: next(j for j in primary if j["sequence"] == sequence and j["method"] == m) for m in dense_methods}
        signals = {m: signal(job) for m, job in cases.items()}
        for methods in [dense_methods, *combinations(dense_methods, 2)]:
            compared = common_comparison([signals[m] for m in methods], "three_method_intersection" if len(methods) == 3 else "pairwise_intersection")
            compared.update(sequence=sequence, requested_methods=list(methods))
            comparisons.append(compared)
            for row in compared.get("metrics", []):
                metrics = row["metrics"]
                keys = ("samples", "GT_positive_samples", "GT_negative_samples", "GT_prevalence", "AUROC", "average_precision", "PR_AUC_trapezoidal",
                    "precision", "recall", "IoU", "threshold", "predicted_positive_fraction", "Brier_score", "probability_ECE_10_fixed_bins", "continuous_speed_Spearman_rho")
                flat.append({"sequence": sequence, "comparison_methods": "+".join(methods), "method": row["method"], **{key: metrics[key] for key in keys}})
    repeats = []
    for repeat in [j for j in plan["jobs"] if j["role"] == "preregistered_independent_repeat"]:
        original = next(j for j in primary if j["method"] == repeat["method"] and j["sequence"] == repeat["sequence"])
        row = {"method": repeat["method"], "sequence": repeat["sequence"], "original_native_status": original["native_status"],
            "repeat_native_status": repeat["native_status"], "hyperparameters_or_native_seed_changed": False,
            "repeat_clip_selected_from_GT_scene_statistics_before_prediction_scores": True, "independent_repeat_count": 1,
            "whole_pipeline_bitwise_determinism_claim": False, "broad_statistical_reproducibility_claim": False}
        if repeat["method"] in dense_methods:
            first_signal, second_signal = signal(original), signal(repeat)
            row["same_method_common_support_comparison"] = common_comparison([first_signal, second_signal], "primary_vs_preregistered_repeat_identical_lattice_support")
        for tag, job in (("primary", original), ("repeat", repeat)):
            if job.get("result_directory"):
                out = local(job["result_directory"])
                evaluation_file = out / "evaluation_summary.json"
                if evaluation_file.exists():
                    row[tag+"_camera_metrics"] = read(evaluation_file)["metrics"]
                    row[tag+"_exported_pose_CSV_sha256"] = sha256(out / "estimated_trajectory.csv")
                if repeat["method"] == "BA_TRACK" and (out / "M2_evaluation_pointer.json").exists():
                    pointer = read(out / "M2_evaluation_pointer.json")
                    report = read(local(pointer["report"]))
                    if sha256(local(pointer["report"])) != pointer["sha256"]:
                        raise ValueError("Native point comparison identity changed")
                    row[tag+"_point_evaluation"] = report
                    row["point_repeat_support_caveat"] = "Native source queries/windows may differ; unrestricted point summaries are not an identical-query causal comparison"
        repeats.append(row)
    write_csv(folder / "common_support_metrics.csv", flat)
    result = {"status": "ACTUAL_COMMON_DENSE_SUPPORT_AND_PLANNED_REPEAT_COMPARISONS_WRITTEN", "batch_plan": str(plan_file),
        "batch_plan_sha256": sha256(plan_file), "GT_provenance": "SYNTHETIC_GROUND_TRUTH", "comparisons": comparisons,
        "planned_repeats": repeats, "sparse_point_scores_pooled_with_dense_pixels": False, "whole_phase5_complete": False,
        "new_model_execution": False, "pixel_samples_are_not_independent_experimental_clips": True}
    report_file = folder / "comparison.json"
    write_json(report_file, result)
    write_json(reports / "movi_common_signal_analysis.json", {"status": result["status"], "report": str(report_file), "sha256": sha256(report_file)})
    print(json.dumps({"status": result["status"], "directory": str(folder), "comparison_groups": len(comparisons), "preplanned_repeats": len(repeats)}))


if __name__ == "__main__":
    main()

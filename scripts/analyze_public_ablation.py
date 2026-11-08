from __future__ import annotations
import _bootstrap
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

from gamecam_vo.common import PROJECT, make_run_dir, read_yaml, run_metadata, sha256, write_csv, write_json
from gamecam_vo.evaluation import evaluate, load_trajectory
from gamecam_vo.plotting import save_figure


def rows(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def finite_stat(records, key):
    values = np.array([float(row[key]) for row in records if row.get(key) not in (None, "")])
    values = values[np.isfinite(values)]
    return {"mean": float(values.mean()) if len(values) else None, "observed_frames": len(values)}


def find_runs(experiment):
    found = {}
    for path in sorted((PROJECT / "results" / experiment).rglob("run_summary.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("fatal_error") or run.get("processed_frames") != run.get("expected_frames"):
            continue
        variant = run.get("experiment_variant", "distance50_default")
        if variant in found:
            raise ValueError(f"More than one completed {variant} run: select a fixed run explicitly before comparing")
        found[variant] = path.parent
    return found


def main():
    a_runs, b_runs = find_runs("E1A_OMNI"), find_runs("E5_OMNI")
    out = make_run_dir(PROJECT / "results/E5_OMNI/analysis", "paired_ablation")
    compared, flat, sources = {}, [], {}
    variants = sorted(a_runs.keys() & b_runs.keys())
    if not variants:
        raise ValueError("No complete paired real A/B runs")
    fig, axes = plt.subplots(len(variants), 2, figsize=(11.5, 3.1 * len(variants)), squeeze=False, layout="constrained")
    for r, variant in enumerate(variants):
        a, b = a_runs[variant], b_runs[variant]
        sa = json.loads((a / "run_summary.json").read_text(encoding="utf-8"))["source_sha256"]
        sb = json.loads((b / "run_summary.json").read_text(encoding="utf-8"))["source_sha256"]
        inference_paths = [key for key in sa if key.replace("\\", "/").startswith("datasets/") or
                           key.replace("\\", "/") in ("gamecam_vo/orb.py", "gamecam_vo/geometry.py", "gamecam_vo/video.py", "gamecam_vo/evaluation.py")]
        if any(sa[key] != sb.get(key) for key in inference_paths):
            raise ValueError("A/B inference or evaluation source hashes differ")
        ca, cb = read_yaml(a / "run_config.yaml"), read_yaml(b / "run_config.yaml")
        for config in (ca, cb):
            config["experiment"].pop("experiment_id", None)
        if ca != cb:
            raise ValueError("A/B configurations differ beyond the experiment ID")
        if sha256(a / "evaluation_reference_trajectory.csv") != sha256(b / "evaluation_reference_trajectory.csv"):
            raise ValueError("A/B reference trajectories differ")
        ar, br = rows(a / "tracking_status.csv"), rows(b / "tracking_status.csv")
        if [v["frame_index"] for v in ar] != [v["frame_index"] for v in br]:
            raise ValueError("A/B expected frame sets differ")
        if [v["feature_count_before_mask"] for v in ar] != [v["feature_count_before_mask"] for v in br]:
            raise ValueError("A/B pre-mask ORB features differ")
        times, reference = load_trajectory(a / "evaluation_reference_trajectory.csv")
        ta, pa = load_trajectory(a / "estimated_trajectory.csv")
        tb, pb = load_trajectory(b / "estimated_trajectory.csv")
        if not (np.array_equal(ta, tb) and np.array_equal(ta, times)):
            raise ValueError("A/B timestamps differ")
        va, vb = np.isfinite(pa).all(axis=(1, 2)), np.isfinite(pb).all(axis=(1, 2))
        common = va & vb
        # Keep all expected rows: a missing frame remains a failure even in this conditional diagnostic.
        common_metrics = {}
        shared_pairs = [(x, y) for x, y in zip(ar, br, strict=True)
                        if x["reference_frame_index"] and x["reference_frame_index"] == y["reference_frame_index"]]
        for group, folder, pred, records, pair_records in (("A_no_mask", a, pa, ar, [p[0] for p in shared_pairs]),
                                                         ("B_dataset_mask", b, pb, br, [p[1] for p in shared_pairs])):
            masked = pred.copy()
            masked[~common] = np.nan
            metrics, details = evaluate(times, reference, times, masked, unit="reference_unit", time_axis="seconds")
            common_metrics[group] = metrics
            write_json(out / f"{variant}_{group}_common_frame_evaluation.json", {"metrics": metrics, "details": details})
            measured = next(row for row in rows(folder / "metrics.csv") if row["alignment"] == "Sim3")
            values = {"variant": variant, "group": group, "POSE_PROVENANCE": "ESTIMATED_REFERENCE",
                      "expected_frames": len(times), "valid_pose_frames": int(np.isfinite(pred).all(axis=(1, 2)).sum()),
                      "common_valid_frames": int(common.sum()), "pose_coverage": measured["pose_coverage"],
                      "tracking_pair_success": measured["tracking_pair_success"], "ATE_Sim3_own_valid_subset": measured["ATE_RMSE"],
                      "RPE_rotation_RMSE_degrees": measured["RPE_rotation_RMSE_degrees"],
                      "valid_rpe_pairs": measured["valid_rpe_pairs"], "input_fps": measured["input_fps"],
                      "conditional_common_frames_Sim3_ATE": metrics[1]["ATE_RMSE"],
                      "conditional_common_frames_alignment_status": metrics[1]["status"],
                      "result_directory": str(folder)}
            for key in ("feature_count_before_mask", "feature_count", "dynamic_mask_fraction", "inlier_ratio", "essential_ransac_inlier_ratio"):
                for field, value in finite_stat(records, key).items():
                    values[f"{key}_{field}"] = value
            for field, value in finite_stat(pair_records, "inlier_ratio").items():
                values[f"same_reference_pair_inlier_ratio_{field}"] = value
            flat.append(values)
        compared[variant] = {"expected_frames": len(times), "common_valid_frame_indices": np.flatnonzero(common),
                             "common_valid_count": int(common.sum()), "same_reference_pair_count": len(shared_pairs),
                             "configuration_identical_except_experiment_id": True, "pre_mask_ORB_counts_identical": True,
                             "inference_and_evaluation_source_hashes_identical": True,
                             "reference_sha256": sha256(a / "evaluation_reference_trajectory.csv"),
                             "common_frame_metrics": common_metrics}
        sources[variant] = {"A": str(a), "B": str(b)}
        frames = [int(v["frame_index"]) for v in ar]
        ax = axes[r, 0]
        ax.plot(frames, [int(v["feature_count"]) for v in ar], color="#356778", label="A: no mask", linewidth=1)
        ax.plot(frames, [int(v["feature_count"]) for v in br], color="#b77946", label="B: dataset mask", linewidth=1)
        ax.set(xlabel="Original frame index", ylabel="Retained ORB features", title=f"{variant}: feature counts")
        ax.legend()
        ax = axes[r, 1]
        ax.scatter(np.asarray(frames)[va], np.ones(va.sum()), color="#356778", s=20, marker="|")
        ax.scatter(np.asarray(frames)[vb], np.zeros(vb.sum()), color="#b77946", s=20, marker="|")
        ax.set(yticks=[0, 1], yticklabels=[f"B ({vb.sum()}/{len(times)})", f"A ({va.sum()}/{len(times)})"],
               ylim=(-.5, 1.5), xlim=(frames[0], frames[-1]), xlabel="Original frame index",
               title=f"Valid-pose coverage; common frames = {common.sum()}")
    fig.suptitle("OmniWorld-Game / c5e5ed9a4462: one complete 132-frame split\nESTIMATED_REFERENCE; lower error on different valid subsets is not proof of improvement", fontsize=11)
    save_figure(fig, out / "paired_ablation")
    write_csv(out / "paired_ablation.csv", flat)
    result = {**run_metadata(), "status": "COMPUTED", "result_directory": str(out), "sources": sources,
              "POSE_PROVENANCE": "ESTIMATED_REFERENCE", "variants": compared,
              "caveat": "Common-frame alignments fitted separately on the same intersection, conditional only; all expected frames retained. No independent engine GT, one scene, no significance claim. Missing older inlier diagnostics remain missing, not zero."}
    write_json(out / "ablation_analysis.json", result)
    write_json(PROJECT / "results/E5_OMNI/latest_analysis.json", {"directory": str(out)})
    print(json.dumps({"directory": str(out), "groups": flat}, ensure_ascii=False))


if __name__ == "__main__":
    main()

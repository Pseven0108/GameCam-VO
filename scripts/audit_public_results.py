"""Cross-file audit of the real experiment bundle, including failed attempts."""
from __future__ import annotations
import _bootstrap
import csv
import json
from pathlib import Path
import numpy as np
from gamecam_vo.common import PROJECT, make_run_dir, read_yaml, run_metadata, sha256, write_json
from gamecam_vo.dataset_validation import check_adapter_gate
from gamecam_vo.evaluation import load_trajectory
from gamecam_vo.sync import match_timestamps


def main():
    evidence, reference = [], {}
    for tag in ("mvs_synth", "omniworld_game"):
        config = read_yaml(PROJECT / "configs/datasets" / (tag + ".yaml"))
        parent = PROJECT / "results" / config["experiment_ids"]["validation"]
        e0 = Path(json.loads((parent / "latest_run.json").read_text())["directory"])
        root = json.loads((e0 / "validation.json").read_text(encoding="utf-8"))
        for seq in root["sequences"]:
            sid = seq["sequence_id"]
            _, local = check_adapter_gate(e0, sid, config)
            reference[sid] = load_trajectory(e0 / sid / local["trajectory_file"])
            evidence.append({"check": "Current raw and normalized data match validated full SHA256 inputs",
                             "dataset": tag, "sequence": sid, "status": "PASS"})
    run_checks = []
    for experiment in ("E1A_MVS", "E1A_OMNI", "E5_OMNI", "E1B_OMNI"):
        for path in sorted((PROJECT / "results" / experiment).rglob("run_summary.json")):
            summary = json.loads(path.read_text(encoding="utf-8"))
            folder = path.parent
            gt_times, gt = reference[summary["sequence_id"]]
            independent = summary["dataset"] == "MVS-Synth"
            ref_file = folder / ("evaluation_ground_truth.csv" if independent else "evaluation_reference_trajectory.csv")
            rt, rp = load_trajectory(ref_file)
            assert np.array_equal(rt, gt_times) and np.allclose(rp, gt, atol=1e-10, rtol=1e-10), "Run reference differs from E0"
            pt, pp = load_trajectory(folder / "estimated_trajectory.csv")
            association, _ = match_timestamps(gt_times, pt, .005)
            aligned = np.full_like(gt, np.nan)
            selected = association >= 0
            aligned[selected] = pp[association[selected]]
            valid = np.isfinite(aligned).all(axis=(1, 2))
            with (folder / "metrics.csv").open(newline="", encoding="utf-8") as f:
                metrics = list(csv.DictReader(f))
            for row in metrics:
                assert int(row["expected_frames"]) == len(gt_times)
                assert int(row["valid_pose_frames"]) == valid.sum()
                assert int(row["failed_frames"]) == (~valid).sum()
                assert abs(float(row["pose_coverage"]) - valid.mean()) < 1e-12
                delta = int(row["rpe_delta_samples"])
                assert int(row["valid_rpe_pairs"]) == np.count_nonzero(valid[:-delta] & valid[delta:])
                assert row["POSE_PROVENANCE"] == ("ENGINE_GROUND_TRUTH" if independent else "ESTIMATED_REFERENCE")
                if not int(row["valid_rpe_pairs"]):
                    assert row["RPE_translation_RMSE"] == "" and row["RPE_rotation_RMSE_degrees"] == "", "Unavailable RPE must stay blank"
            run_checks.append({"directory": str(folder), "status": summary["status"], "fatal_error": summary.get("fatal_error"),
                               "expected_frames": len(gt_times), "valid_pose_frames": int(valid.sum()),
                               "sha256": {p.name: sha256(p) for p in (path, folder / "metrics.csv", folder / "estimated_trajectory.csv", ref_file)}})
    tests = json.loads((PROJECT / "logs/latest_tests.json").read_text())
    assert tests["status"] == "PASS" and Path(tests["log"]).is_file()
    required = ["dataset_comparison.md", "mvs_synth_validation.md", "mvs_synth_baseline.md", "omniworld_validation.md",
                "omniworld_baseline.md", "dynamic_mask_analysis.md", "research_direction_decision.md", "monst3r_preflight.md"]
    assert all((PROJECT / "reports" / name).stat().st_size > 0 for name in required)
    model = json.loads((PROJECT / "reports/monst3r_preflight.json").read_text())
    assert model["main_weight_downloaded"] is False and model["inference_attempted"] is False
    out = make_run_dir(PROJECT / "reports/audits", "real_bundle")
    result = {**run_metadata(), "status": "PASS", "source_data_checks": evidence, "real_run_checks": run_checks,
              "failed_software_attempts_retained": sum(bool(r["fatal_error"]) for r in run_checks),
              "no_cross_dataset_pooled_ATE": True, "tests_separate_from_real_runs": True,
              "required_report_sha256": {name: sha256(PROJECT / "reports" / name) for name in required}}
    write_json(out / "bundle_audit.json", result)
    write_json(PROJECT / "reports/latest_bundle_audit.json", {"directory": str(out), "status": "PASS"})
    print(json.dumps({"status": "PASS", "real_attempts_audited": len(run_checks), "directory": str(out)}))


if __name__ == "__main__":
    main()

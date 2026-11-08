"""Verify completed phase-4 evidence and exported artifacts without model replay."""
from __future__ import annotations

import _bootstrap
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

from gamecam_vo.common import PROJECT, run_metadata, sha256, write_json


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Write a new verification snapshot without replacing the historical phase4 report")
    args = parser.parse_args()
    reports = PROJECT / "reports/SOTA"
    delivery = read(reports / "phase4_comparison_delivery.json")
    audit = read(reports / "E11_shared_input_audit/audit.json")
    assert delivery["bounded_E7_to_E12_delivery_complete"]
    assert set(audit["compared_methods"]) == {"DROID-W", "BA-Track", "Pi3MOS-SLAM", "ORB-SLAM3", "ORB+Essential"}
    assert audit["RGB_hashes_identical_for_all_compared_methods"] and audit["known_K_identical_for_all_compared_methods"]
    assert audit["expected_frames"] == 100 and audit["expected_adjacent_RPE_pairs"] == 99
    bundles = read(reports / "repro_bundle_integrity.json")
    assert bundles["status"] == "ALL_THREE_BUNDLE_FILE_AND_README_CHECKS_PASSED"
    for method in bundles["methods"]:
        assert method["readme_integrity"]["strip_round_trip"] == "PASS"
        for row in method["bundle_required_files"]:
            assert sha256(PROJECT / "baselines" / method["method"] / "repro_outputs" / row["file"]) == row["sha256"]
    references = {}
    for filename in ("droid_mvs_evaluation.json", "ba_track_mvs_evaluation.json", "pi3mos_mvs_evaluation.json"):
        evaluated = read(reports / filename)
        reference = Path(evaluated["reference_for_external_evaluation"])
        references[filename] = sha256(reference)
        assert references[filename] == evaluated["reference_sha256"] == audit["reference_sha256"]
        assert all(r["status"] == "COMPUTED" and r["valid_pose_frames"] == 100 and r["valid_rpe_pairs"] == 99 for r in evaluated["metrics"])
    counts = []
    for pointer, expected in (("pi3mos_official_demo_delivery.json", 458), ("pi3mos_mvs_delivery.json", 100)):
        record = read(reports / pointer)
        out = Path(record["directory"])
        assert record == read(out / "final_evidence_manifest.json")
        assert record["canonical_frames"] == expected and record["native_prior_maps"] == expected
        assert record["executed_source_files_verified"] == 117
        assert record["not_a_paper_score_match"] and not record["dynamic_segmentation_accuracy_claim"]
        for row in record["files"]:
            path = Path(row["file"])
            assert path.resolve().is_relative_to(out.resolve())
            assert path.stat().st_size == row["bytes"] and sha256(path) == row["sha256"]
        qa = record["figure_review"]
        assert qa["status"] == "VISUALLY_REVIEWED_PASS"
        for row in qa["files"]:
            figure = out / row["file"]
            assert sha256(figure) == row["sha256"]
            if figure.suffix == ".svg":
                assert ET.parse(figure).getroot().tag.endswith("svg")
        native = read(out / "status.json")
        assert native["exit_code"] == 0 and not native["CUDA_OOM_observed"]
        config = yaml.safe_load((out / "native_resolved_config.yaml").read_text())
        defaults = yaml.safe_load((PROJECT / "baselines/pi3mos/upstream/config/default.yaml").read_text())
        assert all(config[key] == value for key, value in defaults.items())
        assert config["PATCHES_PER_FRAME"] == 128 and config["PI3_FRAME_RANGE"] == 5
        assert config["OPTIMIZATION_WINDOW"] == 10 and config["PATCH_LIFETIME"] == 15
        counts.append({"target": record["target"], "frames": expected, "source_files": 117, "figure_files": len(qa["files"]), "indexed_files": len(record["files"])})
    with (reports / "E11_shared_input_audit/primary_metrics.csv").open(encoding="utf-8", newline="") as stream:
        primary = list(csv.DictReader(stream))
    assert len(primary) == 10 and {r["method"] for r in primary} == set(audit["compared_methods"])
    for name in ("DROID_W_readiness.md", "BA_TRACK_readiness.md", "PI3MOS_readiness.md", "SOTA_environment_audit.md",
                 "E8_DROID_W_report.md", "E9_BA_TRACK_report.md", "E10_PI3MOS_report.md", "E11_comparison_report.md", "E12_research_direction_status.md"):
        assert (reports / name).stat().st_size > 0
    result = {**run_metadata(), "status": "BOUNDED_PHASE4_DELIVERY_ARTIFACT_CHECKS_PASSED", "compared_methods": audit["compared_methods"],
              "same_external_reference_sha256": audit["reference_sha256"], "core_reference_checks": references, "Pi3MOS_checks": counts,
              "no_model_replay": True, "scope": "Checks small indexed artifacts, figure hashes/SVG syntax, native default config and shared external-reference hashes. Native raw prior arrays and large weights were verified by the saved export/acquisition gates; they are not rehashed by this final check. Visual approval is the explicitly recorded human-readable review, not inferred from XML parsing."}
    write_json(args.output if args.output else reports / "phase4_final_validation.json", result)
    print(json.dumps({"status": result["status"], "compared_methods": len(audit["compared_methods"]), "Pi3MOS_checks": counts}))


if __name__ == "__main__":
    main()

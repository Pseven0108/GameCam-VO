from __future__ import annotations
import _bootstrap
import json
import hashlib
from pathlib import Path
from gamecam_vo.common import PROJECT, write_json, run_metadata


def main():
    pointer = json.loads((PROJECT / "reports/SOTA/latest_readiness.json").read_text())
    reviewed = json.loads((Path(pointer["directory"]) / "readiness.json").read_text())
    source = Path(pointer["source_evidence"])
    for label, folder, target in (("DROID_W", "droid_w", "python run.py --config ./configs/Dynamic/Bonn/bonn_balloon.yaml"),
                                  ("BA_TRACK", "ba_track", "bash scripts/demo/run_mono_depth.sh → run_sparse.sh → run_dense.sh"),
                                  ("PI3MOS", "pi3mos", "python demo.py --imagedir datasets/Wild_SLAM_Mocap/scene1/umbrella/rgb --calib calib/wildgs/umbrella.txt --viz")):
        root = PROJECT / "baselines" / folder / "repro_outputs"
        root.mkdir(parents=True, exist_ok=True)
        p = reviewed["methods"][label]
        status = {"schema_version": "1.0", **run_metadata(), "user_language": "zh-CN", "target_repo": p["repository"],
                  "upstream_commit": p["commit"], "readme_first": True, "selected_goal": "inference",
                  "goal_priority": 1, "status": "partial", "documented_command_status": "not_run",
                  "documented_command": target, "documented_command_source": "official README and inspected source argparse",
                  "selection_source": "manual source review after E7; never execute incorrect automatic candidates",
                  "observed_metrics": {}, "result_match": False, "evidence_level": "direct",
                  "stage_results": {"readiness_audit": "completed", "inference": "not_run", "setup": "in_progress" if label == "DROID_W" else "not_started_by_order"},
                  "patches_applied": label == "DROID_W", "patch_branch": "repro/2026-10-31-sm120-readme" if label == "DROID_W" else None,
                  "highest_patch_risk": "low_documentation_only" if label == "DROID_W" else None,
                  "protocol_deviations": ["Proposed newer torch/CUDA compatibility stack is not the original author stack; runtime not yet validated"],
                  "human_decisions_required": [], "source_evidence": str(source / label),
                  "next_safe_action": "Validate isolated WSL sm_120 runtime before model asset acquisition" if label == "DROID_W" else "Wait until prior baseline is complete or explicitly blocked"}
        write_json(root / "status.json", status)
        files = {
            "SUMMARY.md": f"# {label} reproduction\n\nE7 source and limited asset-access audit completed. Actual Demo and GameCam inference have **not** been executed.\n\nSource: {p['repository']} at `{p['commit']}`.\n\nSelected target (reviewed, unexecuted): `{target}`.\n\nCurrent status: {p['status']}. Official minimum VRAM UNKNOWN.\n",
            "COMMANDS.md": f"# Commands\n\nExecuted: source-only Git checkout, repository inspection, GPU/WSL inventory, HTTP HEAD or 8-byte range probes. Evidence: {source}.\n\nReviewed inference, **not executed**:\n\n```text\n{target}\n```\n\nDROID Bonn `--config` and concrete example name correct its README's missing option/placeholder, confirmed against run.py. Original source README is retained. No multi-sequence downloader was executed. Runtime executable and environment must be frozen before execution.\n",
            "LOG.md": f"# Evidence log\n\n{source}: recorded source commits, full inspected-file hashes, hardware inventory and bounded public asset probes. A range response proves access to initial bytes and reported total size, not a complete checkpoint hash.\n\nE7 review: {pointer['directory']}.\n\nOnly DROID-W environment setup is being attempted; old GameCam environment and historical runs remain unchanged. All failed installer attempts are retained under logs/SOTA_setup and data/sota_toolchains.\n",
            "SCIENTIFIC_CHANGELOG.md": "# Scientific changes\n\nNo inference algorithm, checkpoint, model settings, training steps, GT, evaluation metric, dataset labels or scientific conclusions have been changed. Current edits to DROID README repair command documentation only. New dependency versions are a proposed, explicitly disclosed compatibility deviation, not a claim of paper-exact reproduction. No training is requested or started.\n",
            "COMPARABILITY_REPORT.md": "# Comparability\n\nNo new model metrics exist at this audit stage. Online SLAM, offline/window reconstruction and pairwise geometry will not be ranked together by FPS. MVS ENGINE_GROUND_TRUTH and Omni ESTIMATED_REFERENCE remain separate. All 100 MVS input frames remain the denominator; keyframe-only / filled trajectory semantics must be reported separately. One short sequence does not establish dynamic robustness or long-sequence drift.\n",
        }
        for name, text in files.items():
            (root / name).write_text(text, encoding="utf-8")
        original = (source / label / "README.md").read_bytes()
        prefix = b"<!-- GAMECAM_REPRO_AUDIT_BEGIN -->\nAudit only; inference not executed. See status.json and the E7 readiness report.\n<!-- GAMECAM_REPRO_AUDIT_END -->\n\n"
        (root / "ANNOTATED_README.md").write_bytes(prefix + original)
        assert (root / "ANNOTATED_README.md").read_bytes()[len(prefix):] == original
        write_json(root / "readme_integrity.json", {"original_sha256": hashlib.sha256(original).hexdigest(),
                   "annotation_prefix_bytes": len(prefix), "strip_round_trip": "PASS", "original_source": str(source / label / "README.md")})
    print(json.dumps({"status": "AUDIT_BUNDLES_WRITTEN", "inference_executed": False}))


if __name__ == "__main__":
    main()

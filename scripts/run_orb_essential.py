from __future__ import annotations
import _bootstrap
import argparse
import json
from pathlib import Path

from gamecam_vo.common import PROJECT, read_yaml
from gamecam_vo.orb import run_orb


def main():
    parser = argparse.ArgumentParser(description="ORB+Essential, allowed only after the same real inputs pass E0.")
    parser.add_argument("--e0-run", type=Path, required=True)
    parser.add_argument("--sequence-id")
    parser.add_argument("--dataset-config", type=Path, default=PROJECT / "configs/dataset.yaml")
    parser.add_argument("--camera-config", type=Path, default=PROJECT / "configs/camera.yaml")
    parser.add_argument("--experiment-config", type=Path, default=PROJECT / "configs/experiment.yaml")
    parser.add_argument("--result-parent", type=Path, default=PROJECT / "results/E1/orb_essential")
    args = parser.parse_args()
    validation = json.loads((args.e0_run / "validation.json").read_text(encoding="utf-8"))
    if not validation.get("e0_passed"):
        print("NOT RUN: E0 has not passed. No real-data trajectory or accuracy metrics were generated.")
        return 2
    identifiers = [entry["sequence_id"] for entry in validation["sequences"]]
    if args.sequence_id:
        if args.sequence_id not in identifiers:
            parser.error("Unknown sequence ID")
        identifiers = [args.sequence_id]
    exit_code = 0
    for identifier in identifiers:
        try:
            result = run_orb(args.e0_run, identifier, read_yaml(args.dataset_config),
                             read_yaml(args.camera_config), read_yaml(args.experiment_config), args.result_parent)
            print(json.dumps(result, ensure_ascii=False))
            exit_code = max(exit_code, 2 if result["fatal_error"] else 0)
        except Exception as exc:
            # Continue other selected sequences, while retaining the failed attempt.
            from gamecam_vo.common import make_run_dir, write_json
            failure = make_run_dir(args.result_parent / identifier, "preflight_failure")
            write_json(failure / "failure.json", {"sequence_id": identifier, "status": "FAILED",
                                                "reason": f"{type(exc).__name__}: {exc}"})
            print(json.dumps({"sequence_id": identifier, "error": str(exc), "failure_directory": str(failure)}, ensure_ascii=False))
            exit_code = 2
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

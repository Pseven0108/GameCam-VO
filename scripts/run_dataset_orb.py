from __future__ import annotations
import _bootstrap
import argparse
import json
from pathlib import Path

from gamecam_vo.common import PROJECT, read_yaml
from gamecam_vo.orb import run_orb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--e0-run", type=Path)
    parser.add_argument("--experiment-config", type=Path, default=PROJECT / "configs/experiment.yaml")
    parser.add_argument("--mask-source", choices=("none", "dataset", "predicted"), default="none")
    args = parser.parse_args()
    config = read_yaml(args.config)
    e0_id = config["experiment_ids"]["validation"]
    latest = PROJECT / "results" / e0_id / "latest_run.json"
    e0_run = args.e0_run or Path(json.loads(latest.read_text(encoding="utf-8"))["directory"])
    validation = json.loads((e0_run / "validation.json").read_text(encoding="utf-8"))
    if not validation["e0_passed"]:
        print("NOT RUN: this dataset's E0 has not passed.")
        return 2
    experiment = read_yaml(args.experiment_config)
    experiment_id = config["experiment_ids"]["baseline"]
    output_parent = PROJECT / "results" / experiment_id / "orb_essential"
    if args.mask_source != "none":
        group = "B" if args.mask_source == "dataset" else "C"
        experiment_id = config["experiment_ids"]["ablation"] + "_" + group
        output_parent = PROJECT / "results" / config["experiment_ids"]["ablation"] / (group + "_" + args.mask_source + "_mask")
    experiment["experiment_id"] = experiment_id
    summaries = []
    for sequence in validation["sequences"]:
        summary = run_orb(e0_run, sequence["sequence_id"], config, config["camera"], experiment, output_parent, args.mask_source)
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False))
    return 2 if any(summary["fatal_error"] for summary in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(main())

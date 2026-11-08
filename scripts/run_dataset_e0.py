from __future__ import annotations
import _bootstrap
import argparse
import json
from pathlib import Path

from gamecam_vo.common import PROJECT, read_yaml
from gamecam_vo.dataset_validation import run_dataset_e0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = read_yaml(args.config)
    result = run_dataset_e0(config, PROJECT / "results" / config["experiment_ids"]["validation"])
    print(json.dumps({key: result.get(key) for key in
                      ("status", "dataset", "experiment_id", "e0_passed", "POSE_PROVENANCE", "result_directory", "failure")}, ensure_ascii=False))
    return 0 if result["e0_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

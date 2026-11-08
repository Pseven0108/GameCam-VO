from __future__ import annotations
import _bootstrap
import argparse
import json
from pathlib import Path

from gamecam_vo.common import PROJECT, fresh_directory, read_yaml
from gamecam_vo.validation import inspect_dataset


def main():
    parser = argparse.ArgumentParser(description="Bounded metadata inspection; no downloads or trusted-GT assumptions.")
    parser.add_argument("--dataset-config", type=Path, default=PROJECT / "configs/dataset.yaml")
    parser.add_argument("--camera-config", type=Path, default=PROJECT / "configs/camera.yaml")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = inspect_dataset(read_yaml(args.dataset_config), read_yaml(args.camera_config), fresh_directory(args.out))
    print(json.dumps({"status": result["status"], "sequences": len(result["sequences"]),
                      "manifest": str(args.out / "data_manifest.json")}, ensure_ascii=False))
    return 0 if result["sequences"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

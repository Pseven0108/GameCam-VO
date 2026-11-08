from __future__ import annotations
import _bootstrap
import argparse
import json
from pathlib import Path

from gamecam_vo.validation import validate_dataset


def main():
    parser = argparse.ArgumentParser(description="Validate an immutable E0 inspection snapshot.")
    parser.add_argument("--inspection", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.inspection / "data_manifest.json").read_text(encoding="utf-8"))
    result = validate_dataset(args.inspection, manifest["dataset_config"], manifest["camera_config"])
    print(json.dumps({"status": result["status"], "e0_passed": result["e0_passed"],
                      "report": str(args.inspection / "E0_data_validation_report.md")}, ensure_ascii=False))
    return 0 if result["e0_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

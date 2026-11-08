from __future__ import annotations
import _bootstrap
import argparse
import json
import shutil
from pathlib import Path

from gamecam_vo.common import PROJECT, make_run_dir, read_yaml, write_json
from gamecam_vo.validation import inspect_dataset, validate_dataset


def main():
    parser = argparse.ArgumentParser(description="Run real-data E0. Exit 2 means missing data or unresolved validation.")
    parser.add_argument("--dataset-config", type=Path, default=PROJECT / "configs/dataset.yaml")
    parser.add_argument("--camera-config", type=Path, default=PROJECT / "configs/camera.yaml")
    parser.add_argument("--result-parent", type=Path, default=PROJECT / "results/E0")
    args = parser.parse_args()
    out = make_run_dir(args.result_parent, "e0")
    dataset, camera = read_yaml(args.dataset_config), read_yaml(args.camera_config)
    try:
        inspect_dataset(dataset, camera, out)
        result = validate_dataset(out, dataset, camera)
    except Exception as exc:
        write_json(out / "failure.json", {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}"})
        raise
    write_json(args.result_parent / "latest_run.json", {"directory": str(out.resolve()), "status": result["status"]})
    # These root-level files are documented latest views; the dated run is immutable.
    for name in ("data_manifest.json", "dataset_inspection.csv", "validation.json"):
        shutil.copyfile(out / name, args.result_parent / name)
    if args.result_parent.resolve() == (PROJECT / "results/E0").resolve():
        shutil.copyfile(out / "E0_data_validation_report.md", PROJECT / "reports/E0_data_validation_report.md")
    print(json.dumps({"status": result["status"], "e0_passed": result["e0_passed"],
                      "sequences": len(result["sequences"]), "result_directory": str(out.resolve())}, ensure_ascii=False))
    return 0 if result["e0_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

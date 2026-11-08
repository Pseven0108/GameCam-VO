from __future__ import annotations
import _bootstrap
import argparse
import json
from pathlib import Path

from gamecam_vo.common import fresh_directory, write_csv, write_json
from gamecam_vo.evaluation import evaluate, load_trajectory


def main():
    parser = argparse.ArgumentParser(description="SE3 and Sim3 evaluation with all expected frames and failed poses retained.")
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--gt-metadata", type=Path, required=True)
    parser.add_argument("--estimate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timestamp-tolerance", type=float, default=0.005)
    parser.add_argument("--rpe-delta", type=int, default=1)
    parser.add_argument("--scale-status", choices=("arbitrary", "metric", "dataset_native"), required=True)
    args = parser.parse_args()
    metadata = json.loads(args.gt_metadata.read_text(encoding="utf-8"))
    if not metadata.get("e0_passed"):
        raise ValueError("Unvalidated/candidate camera poses cannot be used as trusted GT")
    if args.scale_status == "metric" and metadata["length_unit"] != "meter":
        raise ValueError("Metric evaluation requires GT already expressed in documented meters")
    gt_times, gt = load_trajectory(args.ground_truth)
    pred_times, predicted = load_trajectory(args.estimate)
    metrics, details = evaluate(gt_times, gt, pred_times, predicted, args.timestamp_tolerance,
                               args.rpe_delta, args.scale_status, metadata["length_unit"],
                               time_axis="frame_index" if metadata.get("time_kind") == "frame_index" else "seconds")
    provenance = metadata.get("POSE_PROVENANCE", "UNSPECIFIED")
    independent = metadata.get("independent_engine_ground_truth", provenance == "ENGINE_GROUND_TRUTH")
    for row in metrics:
        row.update({"POSE_PROVENANCE": provenance, "independent_engine_ground_truth": independent,
                    "evaluation_reference_type": "engine_ground_truth" if independent else "reference_only"})
        if not independent:
            row["se3_has_metric_interpretation"] = False
    out = fresh_directory(args.out)
    write_csv(out / "metrics.csv", metrics)
    write_json(out / "evaluation_details.json", details)
    print(json.dumps({"metrics": str(out / "metrics.csv")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

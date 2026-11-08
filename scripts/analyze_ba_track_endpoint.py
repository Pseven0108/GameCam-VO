"""Post-hoc error localization; preserves the original full100/99 metrics."""
from __future__ import annotations

import _bootstrap
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, write_csv, write_json
from gamecam_vo.evaluation import load_trajectory
from gamecam_vo.geometry import invert_se3


def main():
    report = PROJECT / "reports/SOTA"
    result = json.loads((report / "ba_track_mvs_evaluation.json").read_text(encoding="utf-8"))
    out = Path(result["directory"])
    times, predicted = load_trajectory(out / "estimated_trajectory.csv")
    gt_times, gt = load_trajectory(Path(result["reference_for_external_evaluation"]))
    if len(times) != 100 or not np.array_equal(times, gt_times) or not np.isfinite(predicted).all():
        raise ValueError("This bounded diagnostic requires the same complete100-frame output")
    details = json.loads((out / "evaluation_details.json").read_text(encoding="utf-8"))
    alignment = details["alignments"]["Sim3"]
    rotation, translation = np.asarray(alignment["rotation"]), np.asarray(alignment["translation"])
    aligned = predicted.copy()
    aligned[:, :3, 3] = alignment["scale"] * (rotation @ predicted[:, :3, 3].T).T + translation
    aligned[:, :3, :3] = rotation @ predicted[:, :3, :3]
    rows = []
    for first in range(99):
        second = first+1
        reference_delta = invert_se3(gt[first]) @ gt[second]
        estimate_delta = invert_se3(aligned[first]) @ aligned[second]
        error = invert_se3(reference_delta) @ estimate_delta
        rows.append({"first_frame_index": first, "second_frame_index": second,
                     "RPE_translation_native_game_unit": float(np.linalg.norm(error[:3, 3])),
                     "RPE_rotation_degrees": float(np.degrees(Rotation.from_matrix(error[:3, :3]).magnitude()))})
    squared_t = np.array([r["RPE_translation_native_game_unit"]**2 for r in rows])
    squared_r = np.array([r["RPE_rotation_degrees"]**2 for r in rows])
    primary = next(r for r in result["metrics"] if r["alignment"] == "Sim3")
    if not np.isclose(np.sqrt(squared_t.mean()), primary["RPE_translation_RMSE"], atol=1e-10) or not np.isclose(np.sqrt(squared_r.mean()), primary["RPE_rotation_RMSE_degrees"], atol=1e-10):
        raise ValueError("Error localization no longer reproduces the retained aggregate")
    ate = np.asarray(alignment["per_valid_frame_ATE"])
    record = {"status": "FULL_SUPPORT_POSTHOC_ENDPOINT_DIAGNOSTIC", "directory": str(out),
              "fixed_alignment": "Existing full100-frame primary Sim3; no refit or frame exclusion", "expected_frames": 100, "adjacent_pairs": 99,
              "primary_metrics_changed": False, "last_frame_ATE_native_game_unit": float(ate[-1]),
              "largest_ATE_frame_index": int(np.argmax(ate)), "last_adjacent_pair": rows[-1],
              "last_pair_fraction_of_total_squared_RPE_translation": float(squared_t[-1]/squared_t.sum()),
              "last_pair_fraction_of_total_squared_RPE_rotation": float(squared_r[-1]/squared_r.sum()),
              "raw_tracker_prediction_missing_input_indices": result["output_review"]["motion"]["raw_maps_missing_for_input_indices"],
              "interpretation": "The endpoint has larger error. Missing a newly observed native Tracker prediction at99 is concurrent evidence only; no causal or gameplay-specific failure conclusion. All100 poses and99 pairs remain in primary scores."}
    write_csv(out / "adjacent_pair_error_diagnostic.csv", rows)
    write_json(out / "endpoint_diagnostic.json", record)
    write_json(report / "ba_track_endpoint_diagnostic.json", record)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()

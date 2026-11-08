"""Read-only posthoc diagnosis of accepted Racket cameras; never refit a subgroup."""
from __future__ import annotations

import _bootstrap
import csv
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, sha256, write_json
from gamecam_vo.evaluation import load_trajectory
from phase5_motion_support import read


def rows(file):
    with file.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main():
    reports = PROJECT / "reports/PHASE5"
    target = reports / "racket_camera_error_audit.json"
    if target.exists():
        raise FileExistsError(target)
    pointer_file = reports / "wild_racket_input.json"
    pointer = read(pointer_file)
    _, gt = load_trajectory(Path(pointer["reference"]))
    native = {
        "DROID_W": PROJECT / "results/E14_WILD_DYNAMIC/DROID_W/20261101T195211Z_racket",
        "PI3MOS": PROJECT / "results/E14_WILD_DYNAMIC/PI3MOS/20261101T195911Z_racket",
        "BA_TRACK": PROJECT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T220637Z_racket",
    }
    cases, relative = {}, {}
    for method, folder in native.items():
        evaluation = read(folder / "evaluation_summary.json")
        qa = read(folder / "figure_review.json")
        if (not evaluation["figures_visually_reviewed"] or qa["status"] != "VISUALLY_REVIEWED_PASS"
            or evaluation["expected_frames"] != 962):
            raise ValueError("Only actually reviewed full Racket cameras are diagnosed")
        trajectory = folder / "estimated_trajectory.csv"
        times, poses = load_trajectory(trajectory)
        if not np.array_equal(times, np.arange(962)):
            raise ValueError("No dropped input keys are permitted")
        relative[method] = np.swapaxes(poses[:-1, :3, :3], 1, 2) @ poses[1:, :3, :3]
        diagnostic = folder / "camera_error_diagnostic"
        position = rows(diagnostic / "Sim3_per_GT_frame.csv")
        pairs = rows(diagnostic / "Sim3_adjacent_pairs.csv")
        # The primary evaluation's full-sequence Sim3 is already frozen. Reuse
        # its position residuals; never fit separate quarters or drop startup.
        errors = np.array([float(r["aligned_position_residual"]) for r in position])
        rotation = np.array([float(r["RPE_rotation_degrees"]) for r in pairs])
        translation = np.array([float(r["RPE_translation"]) for r in pairs])
        quarters = []
        for indices in np.array_split(np.arange(962), 4):
            quarters.append({"first_input": int(indices[0]), "last_input": int(indices[-1]),
                             "frames": len(indices), "position_RMSE_same_full_Sim3_meter": float(np.sqrt(np.mean(errors[indices] ** 2))),
                             "fraction_of_full_position_SSE": float(np.sum(errors[indices] ** 2) / np.sum(errors ** 2))})
        r, t = int(rotation.argmax()), int(translation.argmax())
        cases[method] = {"directory": str(folder), "evaluation_sha256": sha256(folder / "evaluation_summary.json"),
                         "figure_review_sha256": sha256(folder / "figure_review.json"), "trajectory_sha256": sha256(trajectory),
                         "diagnostic_sha256": sha256(diagnostic / "diagnostic.json"),
                         "frozen_full_Sim3_ATE_meter": float(np.sqrt(np.mean(errors ** 2))), "quarters_no_refit": quarters,
                         "largest_translation_RPE_pair": [t, t + 1], "largest_translation_RPE_meter": float(translation[t]),
                         "largest_rotation_RPE_pair": [r, r + 1], "largest_rotation_RPE_degrees": float(rotation[r]),
                         "largest_rotation_pair_fraction_of_rotation_SSE": float(rotation[r] ** 2 / np.sum(rotation ** 2)),
                         "physical_dt_at_largest_rotation_pair_seconds": float(pairs[r]["physical_dt_seconds"]),
                         "all_adjacent_pairs_retained": len(pairs), "metrics_or_model_outputs_modified": False}
    shared_peak = all(v["largest_rotation_RPE_pair"] == [691, 692] for v in cases.values())
    gt_relative = np.swapaxes(gt[:-1, :3, :3], 1, 2) @ gt[1:, :3, :3]
    peak = {"pair": [691, 692], "posthoc_descriptive_selection": True,
            "all_three_reviewed_methods_have_their_largest_rotation_RPE_here": shared_peak,
            "GT_relative_rotation_degrees": float(np.degrees(Rotation.from_matrix(gt_relative[691]).magnitude())),
            "GT_camera_center_step_meter": float(np.linalg.norm(gt[692, :3, 3] - gt[691, :3, 3])),
            "native_estimated_relative_rotation_degrees": {m: float(np.degrees(Rotation.from_matrix(v[691]).magnitude())) for m, v in relative.items()},
            "pairwise_estimated_relative_rotation_difference_degrees": {a + "__" + b: float(np.degrees(Rotation.from_matrix(relative[a][691].T @ relative[b][691]).magnitude()))
                                                                       for a, b in (("DROID_W", "PI3MOS"), ("DROID_W", "BA_TRACK"), ("PI3MOS", "BA_TRACK"))}}
    record = {"status": "POSTHOC_FULL_SUPPORT_RACKET_CAMERA_DIAGNOSTIC_COMPLETED", "reference_pointer_sha256": sha256(pointer_file),
              "GT_provenance": "MOCAP_GROUND_TRUTH", "unit": "meter", "cases": cases, "shared_rotation_peak": peak,
              "published_timestamp_tie": pointer["timestamp_tie_diagnostic"],
              "scope": "Descriptive posthoc diagnosis of three accepted full camera outputs. All 962 poses and 961 pairs retained; quarters reuse the original full Sim3. No model repeat, subgroup fit, mask, failure threshold or primary metric change. WildGS is still running and is not silently omitted from the later four-method primary comparison.",
              "causal_limit": "A shared peak, camera acceleration or agreement between predictions does not prove GT error, motion blur, sync error, or dynamic/game-domain failure. RGB-only MoCap lacks independently labelled per-pixel/object motion here. BA dense OOM is separate from these complete sparse-camera errors."}
    write_json(target, record)
    text = ["# Racket camera posthoc diagnostic", "", record["scope"], "",
            "| Method | Frozen full Sim3 ATE m | Largest translation RPE pair | Largest rotation RPE deg | Largest rotation pair SSE share |",
            "|---|---:|---|---:|---:|"]
    for method, value in cases.items():
        text.append(f"| {method} | {value['frozen_full_Sim3_ATE_meter']:.8f} | {value['largest_translation_RPE_pair']} | {value['largest_rotation_RPE_degrees']:.8f} | {value['largest_rotation_pair_fraction_of_rotation_SSE']:.3%} |")
    text += ["", "The largest rotation residual is at 691→692 for all three reviewed methods. Its squared-error share remains small; the old MVS100 last-pair concentration is not assumed to generalize.",
             "", record["causal_limit"], "", "The published duplicate timestamp at 422→423 remains in primary camera/RPE support. Its speed is undefined and excluded only from per-second speed summaries.",
             "", "All four quarter summaries, native/GT relative motion, exact paths and source-artifact SHA values are in [the audit JSON](racket_camera_error_audit.json). No quarter was realigned or selected for a better score."]
    target.with_suffix(".md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print({"status": record["status"], "shared_peak": peak})


if __name__ == "__main__":
    main()

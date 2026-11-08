"""Analytical ties, ranking and single-class checks; no dataset/model scores."""
from __future__ import annotations

import _bootstrap
import json
import numpy as np
from gamecam_vo.common import PROJECT, write_json
from phase5_motion_metrics import evaluate_motion_scores
from phase5_motion_support import sample_resized_map, lattice
from evaluate_phase5_movi_m2 import xyz_from_z


def main():
    labels = np.array([0, 0, 1, 1], bool)
    result, _ = evaluate_motion_scores(labels, [.1, .4, .35, .8], semantics="dynamic_sigmoid", probability_threshold=.4)
    assert abs(result["AUROC"]-.75) < 1e-12 and abs(result["average_precision"]-5/6) < 1e-12
    assert abs(result["PR_AUC_trapezoidal"]-19/24) < 1e-12
    tied, _ = evaluate_motion_scores(labels, [.5]*4, semantics="uncalibrated_uncertainty")
    assert tied["AUROC"] == .5 and tied["average_precision"] == .5 and tied["predicted_positive_fraction"] == 1.
    assert tied["Brier_score"] is None and tied["probability_ECE_10_fixed_bins"] is None and len(tied["reliability_bins"]) == 1
    single, _ = evaluate_motion_scores([0, 0], [.1, .2], semantics="dynamic_sigmoid", probability_threshold=.4)
    assert single["AUROC"] is None and single["average_precision"] is None and single["recall"] is None
    strict, _ = evaluate_motion_scores([0, 1], [.9, .91], semantics="dynamic_sigmoid", probability_threshold=.9, threshold_inclusive=False)
    assert strict["true_positive"] == 1 and strict["false_positive"] == 0
    # An affine image field remains affine under half-pixel coordinates, even
    # across Pi3's two resize stages. These are evaluator checks, not NN scores.
    points = lattice()
    yy, xx = np.mgrid[:64, :64]
    affine_map = 2*((xx+.5)*4-.5)-3*((yy+.5)*4-.5)+7
    sampled = sample_resized_map(affine_map, points, (256, 256))
    assert np.max(np.abs(sampled-(2*points[:, 0]-3*points[:, 1]+7))) < 1e-10
    k = np.array([[100., 0., 127.5], [0., 120., 127.5], [0., 0., 1.]])
    xyz = xyz_from_z(np.array([[137.5, 151.5]]), np.array([2.]), k)
    assert np.allclose(xyz, [[.2, .4, 2.]])
    record = {"status": "ANALYTICAL_RANKING_TIES_CALIBRATION_AND_SINGLE_CLASS_CHECKS_PASS", "AUROC_example": .75,
        "average_precision_example": 5/6, "trapezoidal_PR_AUC_example": 19/24,
        "constant_uncertainty_has_no_probability_calibration_claim": True, "synthetic_plumbing_checks_not_real_experimental_results": True}
    record.update(native_strict_BA_threshold_boundary="PASS", half_pixel_lattice_affine_field="PASS", Z_depth_distinguished_from_range="PASS")
    write_json(PROJECT / "reports/PHASE5/motion_metric_plumbing_probe.json", record)
    print(json.dumps(record))


if __name__ == "__main__":
    main()

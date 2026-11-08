"""Convention plumbing probes against independently written official equations."""
from __future__ import annotations

import _bootstrap
import json

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, write_json
from phase5_movi_geometry import project, unproject_range, transport_object_points, wxyz_rotations, motion_labels
from phase5_camera_gauge import underconstrained_evaluation


def main():
    # These analytical probes are not MOVi samples or research observations.
    width = 256
    focal_ratio = 35./32.
    official_k = np.array([[focal_ratio, 0., -.5], [0., -focal_ratio, -.5], [0., 0., -1.]])
    r = Rotation.from_euler("zyx", [30., 15., -10.], degrees=True).as_matrix()
    gl = np.eye(4); gl[:3, :3] = r; gl[:3, 3] = [1., -2., 3.]
    local_points = np.array([[.4, .5, -2.], [-.7, .3, -3.], [.2, -.6, -4.]])
    world = local_points @ r.T+gl[:3, 3]
    homogeneous = np.c_[world, np.ones(len(world))]
    camera = (np.linalg.inv(gl) @ homogeneous.T).T[:, :3]
    expected = camera @ official_k.T
    expected = expected[:, :2]/expected[:, 2:3]
    cv = gl @ np.diag([1., -1., -1., 1.])
    k = np.array([[focal_ratio*width, 0., 127.5], [0., focal_ratio*width, 127.5], [0., 0., 1.]])
    actual, _, distance = project(world, k, cv)
    projection_error = float(np.max(np.abs((actual+.5)/width-expected)))
    restored = unproject_range(actual, distance, k, cv)
    range_error = float(np.max(np.abs(restored-world)))
    assert projection_error < 1e-12 and range_error < 1e-12
    q_xyzw = Rotation.from_matrix(r).as_quat()
    assert np.allclose(wxyz_rotations(q_xyzw[[3, 0, 1, 2]]), r, atol=1e-12)
    positions = np.array([[[1., 2., 3.], [2., -.5, 4.]]])
    rotations = np.array([[np.eye(3), Rotation.from_euler("y", 40., degrees=True).as_matrix()]])
    point = np.array([[1.4, 2.5, 3.6]])
    expected_target = (point[0]-positions[0, 0]) @ rotations[0, 1].T+positions[0, 1]
    transformed = transport_object_points(point, np.array([1]), 0, 1, positions, rotations)
    assert np.allclose(transformed[0], expected_target, atol=1e-12)
    fields = {"instances__positions": np.array([[[0., 0., 0.], [0., 0., 0.], [1., 0., 0.]]]),
        "instances__quaternions": np.tile([1., 0., 0., 0.], (1, 3, 1)),
        "instances__velocities": np.zeros((1, 3, 3)), "instances__angular_velocities": np.zeros((1, 3, 3)),
        "segmentations": np.tile(np.array([[0, 1]], dtype=np.uint8), (3, 1, 1)), "instances__is_dynamic": np.array([False])}
    masks, moving, _ = motion_labels(fields)
    assert np.array_equal(moving, [[False, True, True]])
    assert np.array_equal(masks[:, 0, 0], [False, False, False]) and np.array_equal(masks[:, 0, 1], [False, True, True])
    gt = np.broadcast_to(np.eye(4), (24, 4, 4)).copy()
    gt[:, 0, 3] = np.arange(24)/12
    gauge_rotation = Rotation.from_euler("z", 40., degrees=True).as_matrix()
    gauge_translation = np.array([1., -2., .5])
    estimated = gt.copy()
    estimated[:, :3, :3] = gauge_rotation.T @ gt[:, :3, :3]
    estimated[:, :3, 3] = (gt[:, :3, 3]-gauge_translation) @ gauge_rotation/2.5
    gauge_metrics, gauge_details = underconstrained_evaluation(gt, estimated, "analytical_test_unit", 1.)
    assert gauge_metrics[0]["ATE_RMSE"] is None and gauge_metrics[1]["ATE_RMSE"] is None
    assert abs(gauge_metrics[2]["alignment_scale"]-2.5) < 1e-12 and gauge_metrics[2]["ATE_RMSE"] < 1e-12
    static_gt = np.broadcast_to(np.eye(4), (24, 4, 4)).copy()
    wrong = static_gt.copy(); wrong[:, 0, 3] = np.arange(24)/12
    wrong[:, :3, :3] = Rotation.from_euler("z", np.arange(24), degrees=True).as_matrix()
    static_metrics, static_details = underconstrained_evaluation(static_gt, wrong, "analytical_test_unit", 1.)
    assert len(static_metrics) == 2 and static_details["orientation_anchored_diagnostic"]["status"] == "UNAVAILABLE"
    assert abs(static_metrics[0]["RPE_rotation_RMSE_degrees"]-1.) < 1e-12
    result = {"status": "ANALYTICAL_CAMERA_RANGE_OBJECT_AND_LABEL_CONVENTION_PROBES_PASS", "official_GL_vs_CV_normalized_projection_max_error": projection_error,
        "range_unprojection_world_point_max_error": range_error, "WXYZ_convention": "PASS", "rigid_object_transport": "PASS",
        "motion_from_actual_positions_even_when_initial_is_dynamic_false": "PASS", "background_ID_zero_not_object_last_index": "PASS",
        "linear_trajectory_standard_ATE_unavailable_with_separate_correct_gauge_diagnostic": "PASS",
        "static_camera_does_not_get_fictitious_zero_scale_ATE": "PASS", "relative_rotation_RPE_remains_identified": "PASS",
        "real_MOVi_sample_geometry_audit": "NOT_RUN_STAGE_GATE", "model_inference": False, "synthetic_plumbing_probe_not_experimental_result": True}
    write_json(PROJECT / "reports/PHASE5/movi_geometry_plumbing_probe.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

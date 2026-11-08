"""Synthetic clock and trajectory checks; no real-data measurements are produced."""
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from gamecam_vo.evaluation import evaluate
from gamecam_vo.sync import match_timestamps, timestamp_diagnostics


def synthetic_poses(n=12):
    times = np.arange(n) / 30
    poses = np.repeat(np.eye(4)[None], n, axis=0)
    phase = np.linspace(0, 2, n)
    poses[:, :3, 3] = np.column_stack((np.cos(phase), np.sin(phase), phase / 3))
    poses[:, :3, :3] = Rotation.from_euler("y", phase / 3).as_matrix()
    return times, poses


def test_timestamp_matching_does_not_invent_a_clock_offset():
    query = np.arange(5) / 30
    reference = query + 123.45
    wrong, _ = match_timestamps(query, reference, 0.005)
    assert (wrong == -1).all()
    correct, error = match_timestamps(query + 123.45, reference, 0.005)
    np.testing.assert_array_equal(correct, np.arange(5))
    np.testing.assert_allclose(error, 0)


@pytest.mark.parametrize("query,reference", [([0, 0], [0, 1]), ([0, 1], [0, 0]), ([0, np.nan], [0, 1])])
def test_invalid_timestamp_order_is_rejected(query, reference):
    with pytest.raises(ValueError):
        match_timestamps(query, reference, 0.02)


def test_many_to_one_and_tied_timestamp_associations_are_not_accepted():
    with pytest.raises(ValueError, match="Many-to-one"):
        match_timestamps(np.array([0, 0.01]), np.array([0, 1]), 0.02)
    association, _ = match_timestamps(np.array([0.5]), np.array([0, 1]), 0.6)
    assert association.tolist() == [-1]


def test_timestamp_gaps_and_duplicates_are_visible():
    result = timestamp_diagnostics(np.array([0, 0.03, 0.06, 0.06, 0.5]))
    assert not result["strictly_increasing"]
    assert result["duplicate_count"] == 1
    assert result["large_gap_indices"] == [3]


def test_global_sim3_and_se3_are_separate_and_orientations_align():
    times, gt = synthetic_poses()
    rotation = Rotation.from_euler("zyx", [20, 10, 5], degrees=True).as_matrix()
    translation = np.array([3, -2, 1])
    prediction = gt.copy()
    prediction[:, :3, 3] = (rotation.T @ (gt[:, :3, 3] - translation).T).T / 4.2
    prediction[:, :3, :3] = rotation.T @ gt[:, :3, :3]
    rows, _ = evaluate(times, gt, times, prediction)
    se3, sim3 = rows
    assert se3["ATE_RMSE"] > 0.1
    assert sim3["alignment_scale"] == pytest.approx(4.2)
    assert sim3["ATE_RMSE"] < 1e-10
    assert sim3["RPE_translation_RMSE"] < 1e-10
    assert sim3["RotErr_RMSE_degrees"] < 1e-5
    assert not se3["se3_has_metric_interpretation"]
    assert not sim3["sim3_is_metric_accuracy"]


@pytest.mark.parametrize("omit_row", [False, True])
def test_failed_frames_stay_in_denominator_and_rpe_does_not_bridge_them(omit_row):
    times, gt = synthetic_poses(12)
    pred = gt.copy()
    if omit_row:
        pred = np.delete(pred, 5, axis=0)
        pred_times = np.delete(times, 5)
    else:
        pred[5] = np.nan
        pred_times = times
    rows, details = evaluate(times, gt, pred_times, pred)
    for row in rows:
        assert row["expected_frames"] == 12
        assert row["failed_frames"] == 1
        assert row["pose_coverage"] == pytest.approx(11 / 12)
        assert row["expected_rpe_pairs"] == 11
        assert row["valid_rpe_pairs"] == 9
    assert [4, 6] not in details["rpe_pairs_expected_indices"]
    assert (4, 6) not in details["rpe_pairs_expected_indices"]


def test_empty_prediction_has_failure_coverage_without_fabricated_errors():
    times, gt = synthetic_poses()
    rows, _ = evaluate(times, gt, np.array([]), np.empty((0, 4, 4)))
    for row in rows:
        assert row["failed_frames"] == len(times)
        assert row["pose_coverage"] == 0
        assert row["status"] == "UNAVAILABLE"
        assert row["ATE_RMSE"] is None


def test_degenerate_alignment_is_explicitly_unavailable():
    times, poses = synthetic_poses()
    poses[:, :3, 3] = np.column_stack((np.arange(len(times)), np.zeros((len(times), 2))))
    rows, _ = evaluate(times, poses, times, poses)
    assert all(row["status"] == "UNAVAILABLE" for row in rows)
    assert all("underconstrained" in row["unavailable_reason"] for row in rows)


def test_frame_index_association_never_claims_second_based_timing_accuracy():
    _, gt = synthetic_poses()
    indices = np.arange(len(gt), dtype=float)
    rows, _ = evaluate(indices, gt, indices, gt, time_axis="frame_index")
    assert all(row["max_timestamp_error_seconds"] is None for row in rows)
    assert all(row["max_frame_index_matching_error"] == 0 for row in rows)
    assert all(row["timestamp_association_unit"] == "frame_index" for row in rows)

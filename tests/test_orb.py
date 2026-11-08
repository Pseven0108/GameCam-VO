"""Known 3D correspondences test the geometry, not real game-video accuracy."""
import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, read_yaml
from gamecam_vo.orb import MotionFailure, estimate_motion, ratio_matches


def fixture_correspondences(pure_rotation=False):
    random = np.random.default_rng(42)
    points = random.uniform([-2, -1.5, 4], [2, 1.5, 12], size=(350, 3))
    rotation = Rotation.from_euler("xyz", [1, 2, -0.5], degrees=True).as_matrix()
    translation = np.zeros(3) if pure_rotation else np.array([-0.5, 0.04, 0.02])
    current = points @ rotation.T + translation
    k1 = np.array([[700., 0, 320], [0, 710, 240], [0, 0, 1]])
    k2 = np.array([[730., 0, 320], [0, 740, 240], [0, 0, 1]])
    def project(xyz, k):
        pixel = xyz @ k.T
        return pixel[:, :2] / pixel[:, 2:]
    return project(points, k1), project(current, k2), k1, k2, rotation, translation


def test_essential_recovery_handles_per_frame_intrinsics():
    p1, p2, k1, k2, expected_r, expected_t = fixture_correspondences()
    config = read_yaml(PROJECT / "configs/experiment.yaml")
    cv2.setRNGSeed(42)
    rotation, direction, stats = estimate_motion(p1, p2, k1, k2, np.zeros(5), config)
    angular_error = Rotation.from_matrix(expected_r.T @ rotation).magnitude()
    assert np.degrees(angular_error) < 0.1
    assert np.dot(direction.ravel(), expected_t / np.linalg.norm(expected_t)) > 0.999
    assert stats["inliers"] > 300
    assert stats["median_parallax_degrees"] > 0.3


def test_pure_rotation_is_not_silently_integrated_as_unit_translation():
    p1, p2, k1, k2, _, _ = fixture_correspondences(pure_rotation=True)
    with pytest.raises(MotionFailure):
        estimate_motion(p1, p2, k1, k2, np.zeros(5), read_yaml(PROJECT / "configs/experiment.yaml"))


def test_missing_descriptors_do_not_produce_matches():
    assert ratio_matches(None, None, 0.75) == []


def test_configured_distance_cutoff_accepts_observable_finite_low_parallax():
    rng = np.random.default_rng(7)
    points = rng.uniform([-1.5, -1, 9], [1.5, 1, 11], (300, 3))
    current = points + [-0.12, 0, 0]
    k = np.array([[700., 0, 320], [0, 700, 240], [0, 0, 1]])
    def pixels(x):
        projected = x @ k.T
        return projected[:, :2] / projected[:, 2:]
    config = read_yaml(PROJECT / "configs/experiment.yaml")
    cv2.setRNGSeed(42)
    with pytest.raises(MotionFailure):
        estimate_motion(pixels(points), pixels(current), k, k, np.zeros(5), config)
    config["ransac"]["recover_pose_distance_threshold"] = 1000
    cv2.setRNGSeed(42)
    rotation, direction, stats = estimate_motion(pixels(points), pixels(current), k, k, np.zeros(5), config)
    assert stats["inliers"] > 250
    assert stats["median_parallax_degrees"] > 0.3
    assert direction[0, 0] < -0.99

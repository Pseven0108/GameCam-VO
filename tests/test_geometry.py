"""Known synthetic SE(3) fixtures; these are not WildWorld experimental results."""
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from gamecam_vo.geometry import (GL_FROM_CV, integrate_recover_pose, invert_se3,
                                parse_vector, project_world, wildworld_to_twc)
from gamecam_vo.video import intrinsic_matrix


def test_gl_to_cv_projection_has_correct_y_and_z():
    center = np.array([2.0, 3.0, 5.0])
    twc = wildworld_to_twc(center, np.array([0, 0, 0, 1]))
    world_point = center + np.array([[1.0, 2.0, -5.0]])
    uv, front = project_world(world_point, twc, np.array([500, 500, 320, 240]))
    assert front.tolist() == [True]
    np.testing.assert_allclose(uv, [[420, 40]])
    assert np.linalg.det(GL_FROM_CV) == pytest.approx(1)
    np.testing.assert_allclose(twc[:3, 3], center)


def test_xyzw_camera_rotation_is_postmultiplied_by_basis_change():
    q = Rotation.from_euler("y", 45, degrees=True).as_quat()
    pose = wildworld_to_twc(np.zeros(3), q)
    np.testing.assert_allclose(pose[:3, :3], Rotation.from_quat(q).as_matrix() @ GL_FROM_CV)


def test_recover_pose_integration_direction_with_rotated_origin():
    origin = np.eye(4)
    origin[:3, :3] = Rotation.from_euler("zyx", [20, 10, -5], degrees=True).as_matrix()
    origin[:3, 3] = [4, -2, 1]
    relative = np.eye(4)
    relative[:3, :3] = Rotation.from_euler("y", 12, degrees=True).as_matrix()
    relative[:3, 3] = [-1, 0, 0]
    current = integrate_recover_pose(origin, relative[:3, :3], relative[:3, 3])
    np.testing.assert_allclose(invert_se3(current) @ origin, relative, atol=1e-12)
    world_point = np.array([2.0, 1.0, 8.0, 1])
    np.testing.assert_allclose(invert_se3(current) @ world_point,
                               relative @ invert_se3(origin) @ world_point, atol=1e-12)
    # A forward camera-center displacement must invert recoverPose's translation.
    simple = integrate_recover_pose(np.eye(4), np.eye(3), [-1, 0, 0])
    np.testing.assert_allclose(simple[:3, 3], [1, 0, 0])


@pytest.mark.parametrize("value", ["__import__('os').system('echo unsafe')", "(True, 2, 3)", "(1, '2', 3)", "[1,2]"])
def test_vector_parser_rejects_code_and_malformed_values(value):
    with pytest.raises((ValueError, SyntaxError)):
        parse_vector(value, 3)


def test_nan_vector_is_retained_as_missing():
    vector = parse_vector("(nan, NaN, 1.0)", 3)
    assert np.isnan(vector[:2]).all()
    assert vector[2] == 1


def test_intrinsics_follow_resize_pixel_centers():
    matrix = intrinsic_matrix(np.array([500, 600, 320, 240]), 0.5, 0.5)
    np.testing.assert_allclose(matrix, [[250, 0, 159.75], [0, 300, 119.75], [0, 0, 1]])


def test_unified_intrinsic_matrix_and_legacy_four_values_have_identical_scaling():
    values = np.array([500, 600, 320, 240])
    matrix = np.array([[500, 0, 320], [0, 600, 240], [0, 0, 1]])
    np.testing.assert_allclose(intrinsic_matrix(matrix, 0.5, 0.5), intrinsic_matrix(values, 0.5, 0.5))

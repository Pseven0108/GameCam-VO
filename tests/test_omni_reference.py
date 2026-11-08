"""Synthetic schema tests: OmniWorld reference poses must never become engine GT."""
import json
import cv2
import numpy as np
import pytest

from datasets.omniworld_game.adapter import OmniWorldGameDataset
from datasets.omniworld_game.mask_loader import read_dynamic_mask
from datasets.omniworld_game.parser import read_depth, read_flow, read_fps
from datasets.omniworld_game.pose_converter import wxyz_w2c_to_twc
from gamecam_vo.common import PROJECT, read_yaml
from gamecam_vo.dataset_validation import run_dataset_e0


def test_wxyz_reference_is_w2c_not_camera_center():
    poses = wxyz_w2c_to_twc([[1, 0, 0, 0]], [[-2, 0, 0]])
    np.testing.assert_allclose(poses[0, :3, 3], [2, 0, 0])
    scaled = wxyz_w2c_to_twc([[1, 0, 0, 0]], [[-2, 0, 0]], metric_scale=3)
    np.testing.assert_allclose(scaled[0, :3, 3], [6, 0, 0])


def test_optimized_quaternion_scale_is_audited_without_changing_rotation():
    original = wxyz_w2c_to_twc([[1, 0, 0, 0]], [[-2, 0, 0]])
    scaled = wxyz_w2c_to_twc([[-8.6, 0, 0, 0]], [[-2, 0, 0]])
    np.testing.assert_allclose(scaled, original)
    with pytest.raises(ValueError):
        wxyz_w2c_to_twc([[0, 0, 0, 0]], [[0, 0, 0]])


def test_labeled_fps_does_not_parse_the_processing_time_as_frame_rate(tmp_path):
    path = tmp_path / "fps.txt"
    path.write_text("FPS: 30.0 \nProcessing time: 103.18 seconds\n")
    assert read_fps(path) == 30


def test_binary_mask_semantics_and_rejection_of_colored_labels(tmp_path):
    path = tmp_path / "binary.png"
    cv2.imwrite(str(path), np.array([[0, 255]], dtype=np.uint8))
    np.testing.assert_array_equal(read_dynamic_mask(path), [[False, True]])
    cv2.imwrite(str(path), np.array([[[0, 0, 255]]], dtype=np.uint8))
    with pytest.raises(ValueError, match="colored"):
        read_dynamic_mask(path)


def test_depth_decode_retains_invalid_mask_and_scales_only_valid_values(tmp_path):
    path = tmp_path / "depth.png"
    # The official executable threshold is <0.0015, not the prose's approximate 100.
    cv2.imwrite(str(path), np.array([[0, 98, 100, 30000, 65535]], np.uint16))
    unscaled, valid = read_depth(path)
    scaled, scaled_valid = read_depth(path, metric_scale=2)
    np.testing.assert_array_equal(valid, [[False, False, True, True, False]])
    np.testing.assert_array_equal(valid, scaled_valid)
    assert scaled[0, 3] == pytest.approx(unscaled[0, 3] * 2)
    assert (scaled[~valid] == -1).all()


def test_flow_components_use_signed_documented_range(tmp_path):
    for filename in ("flow_u_16.png", "flow_v_16.png"):
        cv2.imwrite(str(tmp_path / filename), np.array([[0, 65535]], np.uint16))
    flow = read_flow(tmp_path)
    np.testing.assert_allclose(flow, [[[-300, -300], [300, 300]]])


def test_omni_e0_output_is_labeled_reference_without_a_gt_filename(tmp_path):
    directory = tmp_path / "SYNTHETIC_OMNI_REFERENCE"
    for name in ("color", "depth", "gdino_mask", "camera"):
        (directory / name).mkdir(parents=True)
    frame_ids = [2, 5, 7]
    for frame in frame_ids:
        cv2.imwrite(str(directory / "color" / f"{frame:06d}.png"), np.full((60, 80, 3), 80, np.uint8))
        cv2.imwrite(str(directory / "depth" / f"{frame:06d}.png"), np.full((60, 80), 30000, np.uint16))
        cv2.imwrite(str(directory / "gdino_mask" / f"{frame:06d}.png"), np.zeros((60, 80), np.uint8))
    (directory / "split_info.json").write_text(json.dumps({"split": [frame_ids]}))
    (directory / "camera/split_0.json").write_text(json.dumps(
        {"focals": 60, "cx": 40, "cy": 30, "quats": [[1, 0, 0, 0]] * 3,
         "trans": [[0, 0, 0], [-0.1, 0, 0], [-0.1, -0.1, 0]]}))
    (directory / "fps.txt").write_text("24")
    config = read_yaml(PROJECT / "configs/datasets/omniworld_game.yaml")
    config.update(root=str(directory), scene_id=None)
    dataset = OmniWorldGameDataset(config, PROJECT)
    metadata = dataset.get_metadata()
    assert metadata["POSE_PROVENANCE"] == "ESTIMATED_REFERENCE"
    assert not metadata["independent_engine_ground_truth"]
    assert [frame["frame_index"] for frame in dataset.get_frames()] == frame_ids
    np.testing.assert_allclose([row["timestamp"] for row in dataset.records], np.array(frame_ids) / 24)
    result = run_dataset_e0(config, tmp_path / "SYNTHETIC_REFERENCE_E0")
    assert result["e0_passed"], result
    from pathlib import Path
    sequence_out = Path(result["result_directory"]) / metadata["sequence_id"]
    assert (sequence_out / "normalized_reference_trajectory.csv").is_file()
    assert not (sequence_out / "normalized_ground_truth.csv").exists()

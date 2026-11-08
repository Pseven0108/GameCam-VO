"""Synthetic MVS-schema fixtures ONLY; real dataset results are recorded elsewhere."""
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from datasets.mvs_synth.adapter import MVSSynthDataset
from datasets.mvs_synth.pose_converter import WORLD_REFLECTION, convert_world_to_camera
from gamecam_vo.common import PROJECT, read_yaml
from gamecam_vo.dataset_validation import check_adapter_gate, run_dataset_e0


def known_twc(index):
    pose = np.eye(4)
    pose[:3, :3] = Rotation.from_euler("y", 0.1 * index).as_matrix()
    pose[:3, 3] = [0.2 * index, (0.1 * index)**2, 0]
    return pose


def test_constant_world_reflection_preserves_relative_camera_motion():
    first, second = known_twc(0), known_twc(1)
    raw_first = np.linalg.inv(first) @ WORLD_REFLECTION
    raw_second = np.linalg.inv(second) @ WORLD_REFLECTION
    normalized_first, _ = convert_world_to_camera(raw_first)
    normalized_second, diagnostics = convert_world_to_camera(raw_second)
    np.testing.assert_allclose(normalized_first, first, atol=1e-12)
    np.testing.assert_allclose(normalized_second, second, atol=1e-12)
    np.testing.assert_allclose(raw_second @ np.linalg.inv(raw_first),
                               np.linalg.inv(normalized_second) @ normalized_first, atol=1e-12)
    assert diagnostics["normalized_determinant"] == pytest.approx(1)
    assert not diagnostics["reflection_removed_by_SVD"]
    assert not diagnostics["raw_matrix_altered"]


def test_numeric_rotation_roundoff_is_bounded_and_camera_center_preserved():
    raw = np.linalg.inv(known_twc(2)) @ WORLD_REFLECTION
    raw[0, :3] *= 1.000005
    original = raw.copy()
    expected_center = np.linalg.inv(raw @ WORLD_REFLECTION)[:3, 3]
    pose, diagnostics = convert_world_to_camera(raw)
    np.testing.assert_allclose(pose[:3, :3].T @ pose[:3, :3], np.eye(3), atol=1e-12)
    np.testing.assert_allclose(pose[:3, 3], expected_center, atol=1e-12)
    np.testing.assert_array_equal(raw, original)
    assert diagnostics["numeric_SO3_polar_correction_used"]
    assert 0 < diagnostics["numeric_rotation_max_abs_adjustment"] < 1e-4


def test_arbitrary_reflections_scales_and_wrong_homogeneous_rows_are_rejected():
    for bad in (np.eye(4), WORLD_REFLECTION * 1.1):
        with pytest.raises(ValueError):
            convert_world_to_camera(bad)
    bad = WORLD_REFLECTION.copy()
    bad[0, 0] = 2
    with pytest.raises(ValueError):
        convert_world_to_camera(bad)


def synthetic_mvs(tmp_path):
    root = tmp_path / "SYNTHETIC_NOT_MVS"
    sequence = root / "0000"
    for modality in ("images", "depths", "poses"):
        (sequence / modality).mkdir(parents=True)
    for index in range(3):
        cv2.imwrite(str(sequence / "images" / f"{index:04d}.png"), np.full((60, 80, 3), 80, np.uint8))
        cv2.imwrite(str(sequence / "depths" / f"{index:04d}.exr"), np.full((60, 80), 5, np.float32))
        twc = np.eye(4)
        twc[:3, 3] = [index / 10, (index / 10)**2, 0]
        data = {"extrinsic": (np.linalg.inv(twc) @ WORLD_REFLECTION).tolist(),
                "f_x": 60, "f_y": 60, "c_x": 40, "c_y": 30}
        (sequence / "poses" / f"{index:04d}.json").write_text(json.dumps(data), encoding="utf-8")
    config = read_yaml(PROJECT / "configs/datasets/mvs_synth.yaml")
    config.update(root=str(root), expected_frames=3, dataset="SYNTHETIC MVS UNIT FIXTURE")
    config["validation"].update(projection_pairs=2, projection_grid_stride=2)
    return config


def test_image_sequence_adapter_uses_frame_indices_without_fabricating_fps(tmp_path):
    config = synthetic_mvs(tmp_path)
    dataset = MVSSynthDataset(config, PROJECT)
    assert dataset.get_metadata()["fps"] is None
    assert dataset.get_metadata()["timestamp_kind"] == "frame_index"
    assert len(list(dataset.get_frames())) == 3
    assert dataset.get_intrinsics().shape == (3, 3, 3)
    assert dataset.get_depth(0)[1].all()


def test_generic_e0_hash_gate_and_frame_based_motion_statistics(tmp_path):
    config = synthetic_mvs(tmp_path)
    result = run_dataset_e0(config, tmp_path / "SYNTHETIC_E0_ONLY")
    assert result["e0_passed"], result
    e0_run = Path(result["result_directory"])
    entry, metadata = check_adapter_gate(e0_run, "0000", config)
    assert not metadata["physical_timestamps_available"]
    assert metadata["raw_extrinsics_preserved"]
    import csv
    with (e0_run / "0000/pose_statistics.csv").open(newline="") as handle:
        stats = list(csv.DictReader(handle))
    assert all(row["speed_dataset_units_per_second"] == "nan" for row in stats)
    # Exercise the actual shared ORB runner with the adapter's Nx3x3 intrinsics.
    from gamecam_vo.orb import run_orb
    run = run_orb(e0_run, "0000", config, config["camera"],
                  read_yaml(PROJECT / "configs/experiment.yaml"), tmp_path / "SYNTHETIC_ORB_ONLY")
    assert run["fatal_error"] is None
    assert run["processed_frames"] == 3
    changed = Path(entry["input_files"][0]["path"])
    changed.write_bytes(changed.read_bytes() + b"x")
    with pytest.raises(ValueError, match="Validated source changed"):
        check_adapter_gate(e0_run, "0000", config)

"""Synthetic files in pytest's temporary directory ONLY. Not WildWorld experiments."""
import copy
import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from gamecam_vo.common import PROJECT, read_yaml
from gamecam_vo.dataset import load_state
from gamecam_vo.orb import check_e0_gate, run_orb
from gamecam_vo.validation import inspect_dataset, validate_dataset, validate_sequence
from gamecam_vo.video import iter_frames


def configs():
    return read_yaml(PROJECT / "configs/dataset.yaml"), read_yaml(PROJECT / "configs/camera.yaml")


def make_synthetic_sequence(tmp_path, timestamps=False):
    directory = tmp_path / "SYNTHETIC_NOT_WILDWORLD"
    directory.mkdir()
    writer = cv2.VideoWriter(str(directory / "rgb.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
    assert writer.isOpened(), "The actual MP4 codec is unavailable"
    for _ in range(12):
        writer.write(np.full((240, 320, 3), 90, np.uint8))
    writer.release()
    keys = ["camera.K", "camera.pos", "camera.rot"] + (["clock"] if timestamps else [])
    with (directory / "state.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for i in range(12):
            row = {"camera.K": "(250, 250, 160, 120)", "camera.pos": str((i / 10, (i / 10)**2, 0)),
                   "camera.rot": "(0,0,0,1)"}
            if timestamps:
                row["clock"] = str(10 + i / 30)
            writer.writerow(row)
    return directory


def known_synthetic_config(tmp_path, timestamps=False):
    dataset, camera = configs()
    directory = make_synthetic_sequence(tmp_path, timestamps)
    dataset["sequences"] = [str(directory)]
    evidence = "SYNTHETIC UNIT FIXTURE ONLY: clocks and coordinates known by construction"
    dataset["validation"]["projection_review_confirmed"] = True
    dataset["validation"]["projection_review_evidence"] = evidence
    dataset["sync"]["frame_mapping_confirmed"] = True
    dataset["sync"]["frame_mapping_evidence"] = evidence
    if timestamps:
        dataset["sync"].update(timestamp_column="clock", timestamp_seconds_per_unit=1,
                               video_pts_to_state_offset_seconds=10, timestamp_clock_evidence=evidence)
    camera.update(world_axes="SYNTHETIC right/up/back", world_axes_evidence=evidence,
                  length_unit="synthetic_unit", length_unit_evidence=evidence,
                  distortion_coefficients=[0, 0, 0, 0, 0], distortion_evidence=evidence)
    return directory, dataset, camera


def test_missing_real_data_creates_blocked_manifest_and_no_fake_trajectory(tmp_path):
    dataset, camera = configs()
    manifest = inspect_dataset(dataset, camera, tmp_path)
    result = validate_dataset(tmp_path, dataset, camera)
    assert manifest["status"] == "BLOCKED_NO_DATA"
    assert result["status"] == "BLOCKED_NO_DATA"
    assert not result["downstream_allowed"]
    assert not list(tmp_path.rglob("*trajectory*.png"))
    assert not list(tmp_path.rglob("normalized_ground_truth.csv"))
    with pytest.raises(ValueError, match="E0 has not passed"):
        check_e0_gate(tmp_path, "nonexistent", dataset, camera)
    with pytest.raises(FileExistsError):
        inspect_dataset(dataset, camera, tmp_path)


def test_unconfirmed_row_index_mapping_never_passes_e0(tmp_path):
    dataset, camera = configs()
    directory = make_synthetic_sequence(tmp_path)
    dataset["sequences"] = [str(directory)]
    out = tmp_path / "inspection"
    manifest = inspect_dataset(dataset, camera, out)
    result = validate_dataset(out, dataset, camera)
    entry = result["sequences"][0]
    assert not entry["e0_passed"]
    assert any("only a candidate" in reason for reason in entry["blockers"])
    metadata = json.loads((out / manifest["sequences"][0]["sequence_id"] / "normalized_ground_truth.metadata.json").read_text())
    assert not metadata["e0_passed"]
    assert metadata["length_unit"] == "dataset_unit"


@pytest.mark.parametrize("timestamps", [False, True])
def test_synthetic_fixture_exercises_full_e0_and_failed_orb_coverage(tmp_path, timestamps):
    _, dataset, camera = known_synthetic_config(tmp_path, timestamps)
    out = tmp_path / "e0"
    manifest = inspect_dataset(dataset, camera, out)
    result = validate_dataset(out, dataset, camera)
    assert result["e0_passed"], result
    identifier = manifest["sequences"][0]["sequence_id"]
    experiment = read_yaml(PROJECT / "configs/experiment.yaml")
    run = run_orb(out, identifier, dataset, camera, experiment, tmp_path / "unit_test_orb")
    assert run["processed_frames"] == 12
    assert run["successful_motion_pairs"] == 0  # Deliberately textureless synthetic frames.
    assert run["fatal_error"] is None
    with (Path(run["result_directory"]) / "metrics.csv").open(newline="") as handle:
        metrics = list(csv.DictReader(handle))
    assert len(metrics) == 2
    assert all(int(row["failed_frames"]) == 11 for row in metrics)
    assert all(float(row["pose_coverage"]) == pytest.approx(1 / 12) for row in metrics)
    assert all(row["ATE_RMSE"] == "" for row in metrics)
    assert all(row["status"] == "UNAVAILABLE" for row in metrics)
    changed = copy.deepcopy(dataset)
    changed["clip"]["frame_stride"] = 2
    with pytest.raises(ValueError, match="configuration has changed"):
        check_e0_gate(out, identifier, changed, camera)
    gt_file = out / identifier / "normalized_ground_truth.csv"
    gt_file.write_text(gt_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ground truth/association output changed"):
        check_e0_gate(out, identifier, dataset, camera)


def test_decoder_keeps_true_frame_indices_and_pts_when_sampling(tmp_path):
    directory = make_synthetic_sequence(tmp_path)
    frames = list(iter_frames(directory / "rgb.mp4", {"start_seconds": 0.1, "duration_seconds": 0.2, "frame_stride": 2}))
    assert [f["frame_index"] for f in frames] == [3, 5, 7]
    np.testing.assert_allclose([f["video_pts_seconds"] for f in frames], np.array([3, 5, 7]) / 30)


def test_timestamp_columns_are_not_auto_trusted(tmp_path):
    directory = make_synthetic_sequence(tmp_path, timestamps=True)
    dataset, camera = configs()
    state = load_state(directory / "state.csv", dataset, camera)
    assert "clock" in state["columns"]
    assert np.isnan(state["timestamps"]).all()


def test_incorrect_metadata_fps_cannot_validate_an_index_only_clock(tmp_path):
    _, dataset, camera = known_synthetic_config(tmp_path)
    manifest = inspect_dataset(dataset, camera, tmp_path / "inspection")
    entry = manifest["sequences"][0]
    entry["fps"] = 29.0  # Deliberately inconsistent fixture metadata.
    result = validate_sequence(entry, dataset, camera, tmp_path / "check_bad_clock")
    assert not result["e0_passed"]
    assert any("disagrees with decoded PTS" in reason for reason in result["blockers"])


def test_invalid_pose_row_is_retained_and_blocks_validation(tmp_path):
    directory, dataset, camera = known_synthetic_config(tmp_path)
    state_path = directory / "state.csv"
    state_path.write_text(state_path.read_text(encoding="utf-8").replace("(0,0,0,1)", "(nan,nan,nan,nan)", 1), encoding="utf-8")
    out = tmp_path / "invalid_pose_inspection"
    manifest = inspect_dataset(dataset, camera, out)
    result = validate_dataset(out, dataset, camera)
    assert not result["e0_passed"]
    assert result["sequences"][0]["missing_pose_fraction"] == pytest.approx(1 / 12)
    with (out / manifest["sequences"][0]["sequence_id"] / "normalized_ground_truth.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 12
    assert rows[0]["pose_valid"] == "False"
    assert rows[0]["tx"] == "nan"

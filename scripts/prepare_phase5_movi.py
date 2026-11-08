"""Audit one actual held-out clip, freeze its RGB/K separately from synthetic GT."""
from __future__ import annotations

import _bootstrap
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

import numpy as np
from scipy.spatial.transform import Rotation

from gamecam_vo.common import PROJECT, POSE_COLUMNS, sha256, write_csv, write_json
from gamecam_vo.geometry import poses_to_rows
from phase5_movi_geometry import camera_parameters, camera_translation_rank, motion_labels, project, wxyz_rotations, audit_flow_and_visibility, surface_displacement_speed


def local(value):
    return Path(str(value).replace("/mnt/d/", "D:/", 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("extracted", type=Path)
    args = parser.parse_args()
    extracted = args.extracted.resolve()
    if not extracted.is_relative_to(PROJECT / "data/phase5/MOVi_E"):
        raise ValueError("Expected owned official-test extraction")
    extraction = json.loads((extracted / "extraction.json").read_text(encoding="utf-8"))
    if extraction["status"] != "OFFICIAL_TEST_TFRECORD_EXTRACTED_CRC_VERIFIED":
        raise ValueError("Require CRC-verified official test record extraction")
    archive = extracted / "sample_fields.npz"
    if sha256(archive) != extraction["field_archive_sha256"]:
        raise ValueError("Decoded source archive changed")
    with np.load(archive) as values:
        arrays = {name: values[name].copy() for name in values.files}
    native_record = local(extraction["raw_record"])
    match = re.search(r"shard_(\d+)_first_record", native_record.name)
    if not match or not re.fullmatch(r"[A-Za-z0-9_.-]+", extraction["video_name"]):
        raise ValueError("Stable safe public video/shard identifiers required")
    sequence = "movi_e_test_s"+match.group(1)+"_v"+extraction["video_name"]
    pointer = PROJECT / "reports/PHASE5" / (sequence+"_input.json")
    if pointer.exists():
        raise FileExistsError("Frozen MOVi reference already exists; do not relabel after scores")
    k, poses = camera_parameters(arrays)
    object_r = wxyz_rotations(arrays["instances__quaternions"])
    position = arrays["instances__positions"].astype(float)
    center_errors = []
    for frame in range(len(poses)):
        uv, z, _ = project(position[:, frame], k, poses[frame])
        normalized = (uv+.5)/256
        expected = arrays["instances__image_positions"][:, frame]
        valid = (z > 1e-4) & np.isfinite(normalized).all(axis=1) & np.isfinite(expected).all(axis=1)
        if not np.allclose(normalized[valid], expected[valid], atol=2e-5, rtol=2e-5):
            raise ValueError("Official camera/object-center image projection disagreement; block scoring")
        center_errors.extend(np.abs(normalized[valid]-expected[valid]).ravel())
    if not center_errors:
        raise ValueError("No independently visible object-center projection support; audit before scoring")
    bbox = arrays["instances__bboxes_3d"].astype(float)
    bbox_errors = []
    for instance in range(len(position)):
        for frame in range(len(poses)):
            relative = object_r[instance, frame] @ object_r[instance, 0].T
            predicted = (bbox[instance, 0]-position[instance, 0]) @ relative.T+position[instance, frame]
            bbox_errors.append(float(np.max(np.abs(predicted-bbox[instance, frame]))))
    if max(bbox_errors) > 1e-4:
        raise ValueError("Object quaternion/rigid bounding-box convention failed independent GT check")
    expected_fov = 2*np.arctan(float(arrays["camera__sensor_width"])/(2*float(arrays["camera__focal_length"])))
    if not np.isclose(float(arrays["camera__field_of_view"]), expected_fov, atol=1e-6):
        raise ValueError("Official scalar focal/sensor/FOV relation disagrees")
    masks, objects_moving, speeds = motion_labels(arrays)
    rank, singular = camera_translation_rank(poses)
    angle = Rotation.from_matrix(poses[0, :3, :3].T @ poses[:, :3, :3]).magnitude()
    camera_static = bool(np.max(np.linalg.norm(poses[:, :3, 3]-poses[0, :3, 3], axis=1)) <= 1e-5 and angle.max() <= 1e-5)
    scene_static = not bool(objects_moving.any())
    condition = "A" if scene_static and not camera_static else "B" if not scene_static and camera_static else "C" if not scene_static and not camera_static else "BOTH_STATIC"
    flow_review, fields = audit_flow_and_visibility(arrays, k, poses)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    inputs = PROJECT / "data/phase5_inputs/MOVi_E" / sequence / (stamp+"_RGB_K_only_256x256")
    validation = PROJECT / "results/E15_MOVIE/data_validation" / sequence / stamp
    inputs.mkdir(parents=True, exist_ok=False); (inputs / "rgb").mkdir()
    validation.mkdir(parents=True, exist_ok=False)
    rows = []
    for frame in range(24):
        source, target = extracted / "rgb" / f"{frame:06d}.png", inputs / "rgb" / f"frame_{frame:06d}.png"
        shutil.copy2(source, target)
        if sha256(source) != sha256(target):
            raise ValueError("Common native RGB byte identity failed")
        rows.append({"index": frame, "sample_key": frame, "timestamp_seconds": frame/12., "path": str(target), "sha256": sha256(target)})
    protocol = PROJECT / "docs/PHASE5_MOVI_protocol.md"
    input_manifest = {"dataset": "MOVi-E", "split": "test", "version": "1.0.0", "sequence_id": sequence, "height": 256, "width": 256,
        "fixed_K": k.tolist(), "inference_inputs": ["RGB", "camera_intrinsics"], "frames": rows, "expected_frames": 24,
        "frame_rate": 12., "source_record_sha256": extraction["raw_record_sha256"], "sensor_depth_or_reference_poses_passed": False,
        "preprocessing": "Native official 256x256 RGB bytes retained, no geometric image change"}
    write_json(inputs / "input_manifest.json", input_manifest)
    reference = validation / "reference_trajectory.csv"
    write_csv(reference, poses_to_rows(np.arange(24), poses), POSE_COLUMNS)
    fields["GT_surface_speed_world_unit_per_second"] = surface_displacement_speed(arrays, k, poses)
    motion_file = validation / "motion_ground_truth.npz"
    np.savez_compressed(motion_file, dynamic_pixel_mask=masks, moving_instances=objects_moving, **speeds, **fields)
    sensitivity = {}
    for threshold in (.001, .01, .1):
        m, _, _ = motion_labels(arrays, threshold=threshold)
        sensitivity[str(threshold)] = float(m.mean())
    report = {"status": "SYNTHETIC_CAMERA_INSTANCE_AND_MOTION_GT_AUDITED", "sequence": sequence, "condition": condition,
        "frames": 24, "camera_static": camera_static, "scene_static": scene_static, "camera_effective_translation_rank": rank,
        "camera_centered_translation_singular_values": singular.tolist(), "maximum_center_projection_normalized_error": float(max(center_errors)),
        "maximum_rigid_bbox_error_world_unit": max(bbox_errors), "native_dynamic_pixel_fraction": float(masks.mean()),
        "per_frame_dynamic_pixel_fraction": masks.mean(axis=(1, 2)).tolist(), "initial_is_dynamic_not_used_as_frame_labels": True,
        "motion_label_threshold_sensitivity": sensitivity, "depth_is_euclidean_range": True, "camera_is_T_wc_CV_basis": True,
        "FOV_field_is_scalar_constant": True, "M3_validated": False, "flow_geometry_review": flow_review,
        "pixel_motion_label_geometry_valid": True, "object_motion_geometry_validated": flow_review["object_motion_geometry_validated"],
        "original_fields": str(archive), "original_fields_sha256": sha256(archive), "input_manifest_sha256": sha256(inputs / "input_manifest.json"),
        "reference_sha256": sha256(reference), "GT_provenance": "SYNTHETIC_GROUND_TRUTH", "unit": "Kubric_world_unit",
        "motion_ground_truth": str(motion_file), "motion_ground_truth_sha256": sha256(motion_file),
        "continuous_surface_speed_semantics": "Maximum available adjacent rigid surface displacement times 12FPS; rotation included, world-static environment ID0 has zero speed",
        "protocol_file": str(protocol), "protocol_sha256": sha256(protocol), "model_predictions_used_in_GT_preparation": False}
    write_json(validation / "GT_audit.json", report)
    metadata = {"status": "PHASE5_FROZEN_RGB_K_AND_EXTERNAL_SYNTHETIC_GT_READY", "dataset": "MOVi-E", "sequence": sequence, "split": "test",
        "directory": str(inputs), "external_validation_directory": str(validation), "reference": str(reference), "reference_sha256": sha256(reference),
        "expected_frames": 24, "height": 256, "width": 256, "GT_provenance": "SYNTHETIC_GROUND_TRUTH", "unit": "Kubric_world_unit",
        "position_alignment_identifiability_rank": rank, "condition": condition, "GT_audit_sha256": sha256(validation / "GT_audit.json")}
    write_json(pointer, metadata)
    print(json.dumps({"status": metadata["status"], "sequence": sequence, "condition": condition, "rank": rank, "flow_geometry": flow_review["status"]}))


if __name__ == "__main__":
    main()

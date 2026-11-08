"""Explicit image-grid mappings and immutable synthetic GT for CPU evaluation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.ndimage import map_coordinates

from gamecam_vo.common import PROJECT, sha256


def local(value):
    return Path(str(value).replace("/mnt/d/", "D:/", 1)).resolve()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def json_lines(path):
    return [json.loads(row) for row in path.read_text(encoding="utf-8").splitlines() if row.strip()] if path.exists() else []


def load_movi_ground_truth(pointer_file):
    pointer = read(pointer_file)
    if pointer.get("dataset") != "MOVi-E" or pointer.get("GT_provenance") != "SYNTHETIC_GROUND_TRUTH":
        raise ValueError("Only the independently frozen official synthetic test GT is accepted")
    folder = local(pointer["external_validation_directory"])
    audit_file = folder / "GT_audit.json"
    if sha256(audit_file) != pointer["GT_audit_sha256"]:
        raise ValueError("Frozen GT audit changed")
    audit = read(audit_file)
    source_file, motion_file = local(audit["original_fields"]), local(audit["motion_ground_truth"])
    if sha256(source_file) != audit["original_fields_sha256"] or sha256(motion_file) != audit["motion_ground_truth_sha256"]:
        raise ValueError("Frozen independent source/motion GT changed")
    with np.load(source_file) as z:
        fields = {key: z[key].copy() for key in z.files}
    with np.load(motion_file) as z:
        motion = {key: z[key].copy() for key in z.files}
    return pointer, audit, fields, motion


def lattice(height=256, width=256):
    yy, xx = np.meshgrid(np.arange(3, height, 8), np.arange(3, width, 8), indexing="ij")
    return np.column_stack((xx.ravel(), yy.ravel())).astype(float)


def sample_resized_map(array, input_uv, input_shape):
    """Half-pixel transform used by PIL resize and align_corners=False.

    Bilinear sampling describes where an existing map is evaluated; this never
    invents additional independent pixels or changes model outputs. For Pi3 the
    composition of native model-grid and feature-grid half-pixel transforms is
    exactly this input-to-returned-map transform.
    """
    array = np.asarray(array)
    if array.ndim != 2 or not np.isfinite(array).all():
        raise ValueError("Expected one finite native map")
    ih, iw = input_shape
    h, w = array.shape
    xy = (np.asarray(input_uv)+.5)*[w/iw, h/ih]-.5
    if (xy[:, 0] < -.5).any() or (xy[:, 0] > w-.5).any() or (xy[:, 1] < -.5).any() or (xy[:, 1] > h-.5).any():
        raise ValueError("Evaluation points are outside the map's represented input area")
    return map_coordinates(array.astype(float), [xy[:, 1], xy[:, 0]], order=1, mode="nearest", prefilter=False)


def native_dense_maps(method, out, expected=24):
    """One predeclared map per observed frame, with all selected files hashed."""
    result, evidence = {}, []
    if method == "DROID_W":
        candidates = list((out / "upstream_output").rglob("video.npz"))
        if not candidates:
            return {}, [{"unavailable_reason": "NO_NATIVE_SAVED_VIDEO"}]
        if len(candidates) != 1:
            raise ValueError("Ambiguous native final video")
        path = candidates[0]
        with np.load(path) as z:
            ids, maps = z["timestamps"].copy(), z["uncertainties"].copy()
        if not np.array_equal(ids, ids.astype(int)) or len(ids) != len(maps):
            raise ValueError("Native uncertainty/keyframe support differs")
        for frame, array in zip(ids.astype(int), maps, strict=True):
            if array.shape != (32, 32) or not np.isfinite(array).all() or (array <= 0).any():
                raise ValueError("Actual DROID stride-8 uncertainty schema differs")
            result[int(frame)] = (array, "stride8_origin3")
        evidence.append({"file": str(path), "sha256": sha256(path), "stage": "Native final BA keyframe uncertainty; not per-frame online probabilities"})
    elif method == "PI3MOS":
        for call in json_lines(out / "raw_initialization/manifest.jsonl"):
            path = out / "raw_initialization" / call["file"]
            if sha256(path) != call["sha256"]:
                raise ValueError("Raw initialization archive changed")
            with np.load(path) as z:
                shape = z["local_points"].shape
                maps = z["dynamic_masks"].reshape(shape[1], shape[2], shape[3])
            for frame, array in zip(call["input_frame_indices"], maps, strict=True):
                result[int(frame)] = (array.copy(), "half_pixel_resize")
            evidence.append({"file": str(path), "sha256": call["sha256"], "stage": "Native initialization model grid"})
        # Current-frame priors take precedence exactly as in the native exporter.
        for call in json_lines(out / "native_prior_outputs/manifest.jsonl"):
            path = out / "native_prior_outputs" / call["file"]
            if sha256(path) != call["sha256"]:
                raise ValueError("Raw prior archive changed")
            with np.load(path) as z:
                array = z["dynamic_probability_fmap_current"].copy()
            result[int(call["current_input_index"])] = (array, "half_pixel_resize")
            evidence.append({"file": str(path), "sha256": call["sha256"], "stage": "Native current-frame feature-grid prior"})
    elif method == "WILDGS":
        for call in json_lines(out / "raw_uncertainty_manifest.jsonl"):
            if Path(call["plot_directory"]).name != "plots_after_refine":
                continue
            path = local(call["file"])
            if sha256(path) != call["sha256"]:
                raise ValueError("Raw final returned variance changed")
            array = np.load(path).squeeze()
            frame = int(call["frame_index"])
            if frame in result:
                raise ValueError("Duplicate final keyframe variance; inspect native call history instead of selecting by score")
            if array.shape != (256, 256):
                raise ValueError("Actual WildGS variance grid differs from full RGB grid")
            result[frame] = (array, "input_pixel_grid")
            evidence.append({"file": str(path), "sha256": call["sha256"], "stage": "Native plots_after_refine returned adjusted variance"})
    else:
        raise ValueError("Sparse BA point scores must be evaluated separately")
    if any(frame < 0 or frame >= expected for frame in result):
        raise ValueError("Observed signal refers to a non-input frame")
    return result, evidence


def assert_movi_result(out, pointer):
    if not out.is_relative_to(PROJECT / "results/E15_MOVIE") or pointer["expected_frames"] != 24:
        raise ValueError("Expected an owned new E15 result")
    native = read(out / "input_manifest.json")
    frozen = read(local(pointer["directory"]) / "input_manifest.json")
    if native != frozen or len(frozen["frames"]) != 24 or (frozen["height"], frozen["width"]) != (256, 256):
        raise ValueError("The actual model input differs from the independently frozen RGB/K view")
    return read(out / "status.json")

"""GT-only Kubric geometry, with conventions fixed from official source."""
from __future__ import annotations

import cv2
import numpy as np
from scipy.spatial.transform import Rotation


def wxyz_rotations(quaternions):
    q = np.asarray(quaternions, dtype=np.float64)
    if q.shape[-1] != 4 or not np.isfinite(q).all():
        raise ValueError("Invalid official quaternion array")
    error = np.max(np.abs(np.linalg.norm(q, axis=-1)-1))
    if error > 1e-4:
        raise ValueError("Official quaternion norm exceeds float32 tolerance")
    return Rotation.from_quat(q[..., [1, 2, 3, 0]].reshape(-1, 4)).as_matrix().reshape(*q.shape[:-1], 3, 3)


def camera_parameters(arrays):
    h, w = arrays["video"].shape[1:3]
    f = float(arrays["camera__focal_length"])/float(arrays["camera__sensor_width"])*w
    k = np.array([[f, 0., (w-1)/2], [0., f, (h-1)/2], [0., 0., 1.]])
    r = wxyz_rotations(arrays["camera__quaternions"]) @ np.diag([1., -1., -1.])
    t = np.asarray(arrays["camera__positions"], dtype=np.float64)
    poses = np.broadcast_to(np.eye(4), (len(t), 4, 4)).copy()
    poses[:, :3, :3], poses[:, :3, 3] = r, t
    return k, poses


def dequantize(array, value_range):
    lo, hi = np.asarray(value_range, dtype=np.float64)
    if not np.isfinite([lo, hi]).all() or hi < lo or np.asarray(array).dtype != np.uint16:
        raise ValueError("Expected official uint16 and finite nondecreasing range")
    return np.asarray(array, dtype=np.float64)/65535*(hi-lo)+lo


def unproject_range(uv, distance, k, camera_pose):
    uv = np.asarray(uv, dtype=np.float64)
    ray = np.column_stack(((uv[:, 0]-k[0, 2])/k[0, 0], (uv[:, 1]-k[1, 2])/k[1, 1], np.ones(len(uv))))
    ray /= np.linalg.norm(ray, axis=1, keepdims=True)
    camera = ray*np.asarray(distance).reshape(-1, 1)
    return camera @ camera_pose[:3, :3].T + camera_pose[:3, 3]


def project(world, k, camera_pose):
    camera = (np.asarray(world)-camera_pose[:3, 3]) @ camera_pose[:3, :3]
    with np.errstate(divide="ignore", invalid="ignore"):
        uv = camera[:, :2]/camera[:, 2:3]
    uv = uv*np.array([k[0, 0], k[1, 1]])+np.array([k[0, 2], k[1, 2]])
    return uv, camera[:, 2], np.linalg.norm(camera, axis=1)


def transport_object_points(world, ids, origin_frame, target_frame, object_positions, object_rotations):
    result = np.asarray(world).copy()
    for identity in np.unique(ids):
        if identity == 0:
            continue
        index = int(identity)-1
        mask = ids == identity
        relative = object_rotations[index, target_frame] @ object_rotations[index, origin_frame].T
        result[mask] = (world[mask]-object_positions[index, origin_frame]) @ relative.T+object_positions[index, target_frame]
    return result


def motion_labels(arrays, fps=12., threshold=.01):
    position = np.asarray(arrays["instances__positions"], dtype=np.float64)
    rotation = wxyz_rotations(arrays["instances__quaternions"])
    linear = np.linalg.norm(arrays["instances__velocities"], axis=-1)
    angular = np.linalg.norm(arrays["instances__angular_velocities"], axis=-1)
    linear_difference = np.linalg.norm(np.diff(position, axis=1), axis=-1)*fps
    relative = np.swapaxes(rotation[:, :-1], -1, -2) @ rotation[:, 1:]
    angular_difference = Rotation.from_matrix(relative.reshape(-1, 3, 3)).magnitude().reshape(relative.shape[:2])*fps
    adjacent_linear = np.maximum(np.pad(linear_difference, ((0, 0), (1, 0))), np.pad(linear_difference, ((0, 0), (0, 1))))
    adjacent_angular = np.maximum(np.pad(angular_difference, ((0, 0), (1, 0))), np.pad(angular_difference, ((0, 0), (0, 1))))
    moving = (linear > threshold) | (angular > threshold) | (adjacent_linear > threshold) | (adjacent_angular > threshold)
    segmentation = arrays["segmentations"]
    masks = np.stack([np.r_[False, moving[:, t]][segmentation[t]] for t in range(segmentation.shape[0])])
    return masks, moving, {"instant_linear_speed": linear, "instant_angular_speed": angular,
        "adjacent_linear_speed": adjacent_linear, "adjacent_angular_speed": adjacent_angular}


def camera_translation_rank(poses):
    position = poses[:, :3, 3]
    singular = np.linalg.svd(position-position.mean(axis=0), compute_uv=False)
    rank = 0 if singular[0] <= 1e-5*np.sqrt(len(position)) else 1 if singular[1]/singular[0] < 1e-5 else 2 if singular[2]/singular[0] < 1e-5 else 3
    return rank, singular


def surface_displacement_speed(arrays, k, camera_poses, fps=12.):
    """Visible surface-point speed from rigid poses, including rotation.

    Use the larger available adjacent interval, matching the frame-label union.
    This is a finite-displacement speed, not an instantaneous angular-velocity
    convention assumption. ID-zero environment points remain world-static.
    """
    t, h, w = arrays["video"].shape[:3]
    yy, xx = np.mgrid[:h, :w]
    uv = np.column_stack((xx.ravel(), yy.ravel()))
    ranges = dequantize(arrays["depth"], arrays["metadata__depth_range"])
    position = np.asarray(arrays["instances__positions"], float)
    rotations = wxyz_rotations(arrays["instances__quaternions"])
    result = []
    for frame in range(t):
        world = unproject_range(uv, ranges[frame].ravel(), k, camera_poses[frame])
        ids = arrays["segmentations"][frame].ravel()
        speed = np.zeros(h*w)
        for target in (frame-1, frame+1):
            if 0 <= target < t:
                moved = transport_object_points(world, ids, frame, target, position, rotations)
                speed = np.maximum(speed, np.linalg.norm(moved-world, axis=-1)*fps)
        result.append(speed.reshape(h, w).astype(np.float32))
    return np.stack(result)


def audit_flow_and_visibility(arrays, k, camera_poses):
    t, h, w = arrays["video"].shape[:3]
    yy, xx = np.mgrid[:h, :w]
    uv0 = np.column_stack((xx.ravel(), yy.ravel())).astype(np.float64)
    depth = dequantize(arrays["depth"], arrays["metadata__depth_range"])
    flow_rc = dequantize(arrays["forward_flow"], arrays["metadata__forward_flow_range"])
    positions = np.asarray(arrays["instances__positions"], dtype=np.float64)
    rotations = wxyz_rotations(arrays["instances__quaternions"])
    dynamic_mask, _, _ = motion_labels(arrays)
    records, errors, dynamic_errors, static_errors = [], [], [], []
    camera_flows, total_flows, occluded, offscreen, valid_interior = [], [], [], [], []
    for frame in range(t-1):
        ids = arrays["segmentations"][frame].ravel()
        interior = np.zeros((h, w), dtype=bool)
        for identity in np.unique(ids):
            if identity:
                interior |= cv2.erode((arrays["segmentations"][frame] == identity).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        world = unproject_range(uv0, depth[frame].ravel(), k, camera_poses[frame])
        future = transport_object_points(world, ids, frame, frame+1, positions, rotations)
        total, z, expected_range = project(future, k, camera_poses[frame+1])
        fixed, _, _ = project(world, k, camera_poses[frame+1])
        in_view = np.isfinite(total).all(axis=1) & (z > 0) & (total[:, 0] >= 0) & (total[:, 0] <= w-1) & (total[:, 1] >= 0) & (total[:, 1] <= h-1)
        safe = np.rint(np.clip(np.nan_to_num(total, nan=0, posinf=w-1, neginf=0), [0, 0], [w-1, h-1])).astype(int)
        future_depth = depth[frame+1, safe[:, 1], safe[:, 0]]
        quantum = np.diff(arrays["metadata__depth_range"])[0]/65535
        tolerance = 2*quantum+.005*expected_range
        hidden = in_view & (future_depth > 0) & (expected_range > future_depth+tolerance)
        interior = interior.ravel() & (ids > 0) & np.isfinite(total).all(axis=1)
        flow_error = np.linalg.norm((total-uv0)-flow_rc[frame].reshape(-1, 2)[:, ::-1], axis=1)
        measured = flow_error[interior & in_view]
        moving = dynamic_mask[frame].ravel()
        dynamic_errors.append(flow_error[interior & in_view & moving])
        static_errors.append(flow_error[interior & in_view & ~moving])
        if len(measured):
            errors.append(measured)
        records.append({"origin_frame": frame, "interior_foreground_pixels": int(interior.sum()),
            "median_total_flow_geometry_error_pixels": float(np.median(measured)) if len(measured) else None,
            "p95_total_flow_geometry_error_pixels": float(np.quantile(measured, .95)) if len(measured) else None,
            "occluded_in_view_foreground_pixels": int((hidden & interior).sum()), "offscreen_foreground_pixels": int((~in_view & interior).sum())})
        camera_flows.append((fixed-uv0).reshape(h, w, 2).astype(np.float32))
        total_flows.append((total-uv0).reshape(h, w, 2).astype(np.float32))
        occluded.append(hidden.reshape(h, w)); offscreen.append((~in_view).reshape(h, w)); valid_interior.append(interior.reshape(h, w))
    all_errors = np.concatenate(errors) if errors else np.array([])
    dynamic_errors, static_errors = np.concatenate(dynamic_errors), np.concatenate(static_errors)
    median = float(np.median(all_errors)) if all_errors.size else None
    strata = {name: {"pixels": int(values.size), "median_error_pixels": float(np.median(values)) if values.size else None,
        "validated": bool(values.size >= 100 and np.median(values) <= .25)} for name, values in (("moving_foreground", dynamic_errors), ("static_foreground", static_errors))}
    supported_ok = all(row["validated"] for row in strata.values() if row["pixels"] >= 100)
    report = {"status": "PASS" if median is not None and median <= .25 and supported_ok else "GEOMETRY_FLOW_CHECK_FAILED_BLOCK_M2",
        "predeclared_median_tolerance_pixels": .25, "measured_pixels": int(all_errors.size), "median_error_pixels": median,
        "strata": strata, "minimum_stratum_pixels": 100, "object_motion_geometry_validated": strata["moving_foreground"]["validated"],
        "p95_error_pixels": float(np.quantile(all_errors, .95)) if all_errors.size else None, "per_pair": records,
        "scope": "GT range+rigid object/camera projection versus official forward flow; foreground eroded interiors, no predictions involved"}
    fields = {"GT_camera_flow_uv": np.stack(camera_flows), "GT_total_flow_uv": np.stack(total_flows),
        "GT_occluded_in_view": np.stack(occluded), "GT_offscreen": np.stack(offscreen), "GT_foreground_interior": np.stack(valid_interior)}
    fields["GT_object_residual_flow_uv"] = fields["GT_total_flow_uv"]-fields["GT_camera_flow_uv"]
    return report, fields


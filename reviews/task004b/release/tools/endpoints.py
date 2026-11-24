"""Offline evaluation only. Nothing here is imported by the model runner."""
from pathlib import Path

import numpy as np

from contracts import GT_SHA, IDS, ORDER, S_REF, TARGET, need, read_json, stat_sha, write_csv
from trace_audit import pose_index


RETENTION_FIELDS = (
    'arm', 'attempt_id', 'status', 'rgb312_retained_kf', 'rgb328_retained_kf', 'endpoint_kf_retention_rate',
    'keyframe_count', 'keyframe_retention_rate', 'joint_local_ba_return', 'joint_local_ba_return_count',
    'both_in_pose_window_count', 'both_in_window_and_observed_count', 'direct_edge_count',
    'retained_pair_comparable', 'rgb312_export_valid', 'rgb328_export_valid', 'rgb312_export_origin', 'rgb328_export_origin',
    'rgb312_filler_temp_valid', 'rgb328_filler_temp_valid', 'rgb312_filler_batch', 'rgb328_filler_batch',
    'final_kf_snapshot_event', 'export_event', 'reason',
)
METRIC_FIELDS = (
    'arm', 'attempt_id', 'status', 'source', 'rgb_start', 'rgb_end', 'camera_start', 'camera_end',
    's_ref', 'gt_length_game_units', 'estimate_raw_length', 'estimate_scaled_length_game_units',
    'displacement_ratio_pct', 'absolute_gap_from_100_pct_points', 'translation_rpe_game_units',
    'rotation_rpe_deg', 'world_direction_error_deg', 'global_fit_scale_diagnostic', 'direction_status', 'reason',
)
MIN_GT = 1e-6


def quat_xyzw(q):
    q = np.asarray(q, dtype=float)
    need(q.shape == (4,) and np.isfinite(q).all(), 'quaternion shape or finiteness')
    norm = np.linalg.norm(q)
    need(abs(norm - 1.0) < 2e-3, 'non-unit quaternion')
    x, y, z, w = q / norm
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ])


def pose_matrix(row, convention):
    v = np.asarray(row, dtype=float)
    need(v.shape == (7,) and np.isfinite(v).all(), 'pose shape or finiteness')
    r = quat_xyzw(v[3:])
    p = np.eye(4)
    if convention == 'W2C':
        p[:3, :3], p[:3, 3] = r.T, -(r.T @ v[:3])
    elif convention == 'C2W':
        p[:3, :3], p[:3, 3] = r, v[:3]
    else:
        raise ValueError('unsupported pose convention')
    return p


def rigid(m):
    m = np.asarray(m, dtype=float)
    need(m.shape[-2:] == (4, 4) and np.isfinite(m).all(), 'pose matrix shape or finiteness')
    r = m[..., :3, :3]
    need(np.allclose(m[..., 3, :], [0, 0, 0, 1], atol=1e-6, rtol=0)
         and np.allclose(r.swapaxes(-1, -2) @ r, np.eye(3), atol=2e-3, rtol=0)
         and np.allclose(np.linalg.det(r), 1, atol=2e-3, rtol=0), 'non-rigid pose matrix')
    return m


def read_gt(path):
    need(stat_sha(path) == GT_SHA, 'GT identity mismatch')
    with np.load(path, allow_pickle=False) as z:
        need(np.array_equal(z['rgb_ids'], IDS) and np.array_equal(z['camera_frame_ids'], np.array(IDS) - 1),
             'GT RGB-to-camera mismatch')
        gt = rigid(z['c2w'])
    need(gt.shape == (len(IDS), 4, 4), 'GT coverage mismatch')
    return gt


def read_export(npz, text, keyframes):
    kfs = read_json(keyframes)
    keys, local = kfs['rgb_ids'], kfs['local_indices']
    need(type(kfs['final_count']) is int and kfs['final_count'] == len(keys) and bool(keys)
         and keys == sorted(set(keys)) and all(type(k) is int and k in IDS for k in keys)
         and [k-1 for k in keys] == local, 'invalid native keyframe index')
    rows = np.loadtxt(text, ndmin=2)
    with np.load(npz, allow_pickle=False) as z:
        need(np.array_equal(z['rgb_ids'], IDS) and np.array_equal(z['keyframe_rgb_ids'], keys)
             and np.array_equal(z['keyframe_local_indices'], local), 'trajectory/index ID mismatch')
        data, valid = z['c2w_xyzw'], z['valid']
    need(rows.shape == (len(IDS), 8) and np.array_equal(rows[:, 0], np.arange(len(IDS)))
         and data.shape == (len(IDS), 7) and valid.shape == (len(IDS),) and valid.dtype == np.bool_, 'native export format mismatch')
    need(np.allclose(rows[:, 1:], data, rtol=1e-7, atol=1e-7, equal_nan=True), 'NPZ and text export disagree')
    mats = {i: pose_matrix(data[i-1], 'C2W') for i in IDS if valid[i-1]}
    return mats, keys


def alignment_rotation(mats, gt):
    ids = sorted(mats)
    if len(ids) < 3:
        return None, None
    x = np.stack([mats[i][:3, 3] for i in ids])
    y = gt[np.asarray(ids) - 1, :3, 3]
    x, y = x - x.mean(axis=0), y - y.mean(axis=0)
    h = x.T @ y
    need(np.isfinite(h).all(), 'nonfinite alignment covariance')
    u, s, vt = np.linalg.svd(h)
    if s[0] <= 0 or s[1] <= s[0] * 1e-10:
        return None, None
    fix = np.diag([1.0, 1.0, np.sign(np.linalg.det(vt.T @ u.T))])
    return vt.T @ fix @ u.T, float(np.dot(s, np.diag(fix)) / np.sum(x*x))


def degrees(a):
    return float(np.degrees(np.arccos(np.clip(a, -1, 1))))


def metric(arm, attempt_id, source, poses, gt, align=(None, None), reason=None, status=None):
    a, b = TARGET
    base = dict(arm=arm, attempt_id=attempt_id, source=source, rgb_start=a, rgb_end=b,
                camera_start=a-1, camera_end=b-1, s_ref=S_REF, reason=reason)
    if not set(TARGET) <= poses.keys():
        return dict(base, status=status or 'ENDPOINT_UNAVAILABLE')
    p, q = poses[a], poses[b]
    g, h = gt[a-1], gt[b-1]
    rot, scale = align
    d, dg = q[:3, 3] - p[:3, 3], h[:3, 3] - g[:3, 3]
    length, glen = float(np.linalg.norm(d)), float(np.linalg.norm(dg))
    ratio = 100 * S_REF * length / glen if glen > MIN_GT else None
    rpe = float(np.linalg.norm(S_REF * (p[:3, :3].T @ d) - g[:3, :3].T @ dg))
    r_gt, r_est = g[:3, :3].T @ h[:3, :3], p[:3, :3].T @ q[:3, :3]
    angle = degrees((np.trace(r_gt.T @ r_est) - 1) / 2)
    angle_reason = ('DEGENERATE_GT_DISPLACEMENT' if glen <= MIN_GT else
                    'DEGENERATE_EST_DISPLACEMENT' if S_REF * length <= MIN_GT else
                    'DEGENERATE_GLOBAL_ALIGNMENT' if rot is None else 'VALID')
    direction = degrees((rot @ d) @ dg / (length * glen)) if angle_reason == 'VALID' else None
    return dict(base, status='VALID' if ratio is not None else 'PARTIAL_GT_DISPLACEMENT_DEGENERATE',
                gt_length_game_units=glen, estimate_raw_length=length,
                estimate_scaled_length_game_units=S_REF*length, displacement_ratio_pct=ratio,
                absolute_gap_from_100_pct_points=None if ratio is None else abs(ratio-100),
                translation_rpe_game_units=rpe, rotation_rpe_deg=angle, world_direction_error_deg=direction,
                global_fit_scale_diagnostic=scale, direction_status=angle_reason)


def observed(rows, ids):
    out = {}
    for i in ids:
        if i in rows:
            try:
                out[i] = pose_matrix(rows[i]['w2c_xyzw'], 'W2C')
            except (TypeError, ValueError):
                pass
    return out


def evaluate(arm, attempt, trace, poses, keys, gt):
    a, b = TARGET
    event = trace.export
    need(event is not None and event['rgb_ids'] == list(IDS) and event['anchor_rgb_ids'] == keys,
         'observer export IDs differ from native export')
    export = rigid(event['c2w'])
    need(export.shape == (len(IDS), 4, 4), 'wrong observer export shape')
    for i, p in poses.items():
        need(np.allclose(p, export[i-1], atol=2e-4, rtol=1e-5), f'RGB {i}: matrix and native pose disagree')

    snapshot = trace.boundaries['final_phase_2_done']
    rows = pose_index(snapshot, 'KEYFRAME_CACHE')
    need(list(rows) == keys, 'post-Final BA keyframe retention differs from export')
    direct = observed(rows, [i for i in TARGET if i in keys])
    filler = observed(trace.filler, TARGET)
    for i in TARGET:
        if i in poses:
            native = (direct if i in keys else filler).get(i)
            need(native is not None and np.allclose(native, poses[i], atol=2e-4, rtol=1e-5), f'RGB {i}: export source mismatch')

    local = [row for row, _ in trace.common]
    retention = dict(arm=arm, attempt_id=attempt, status='OBSERVED', rgb312_retained_kf=a in keys, rgb328_retained_kf=b in keys,
                     endpoint_kf_retention_rate=sum(i in keys for i in TARGET)/len(TARGET),
                     keyframe_count=len(keys), keyframe_retention_rate=len(keys)/len(IDS),
                     joint_local_ba_return=bool(local), joint_local_ba_return_count=len(local),
                     both_in_pose_window_count=sum(x['both_in_pose_window'] for x in local),
                     both_in_window_and_observed_count=sum(x['both_in_pose_window'] and x['both_observed_in_edges'] for x in local),
                     direct_edge_count=sum(x['direct_edge'] for x in local), retained_pair_comparable=set(TARGET) <= direct.keys(),
                     rgb312_export_valid=a in poses, rgb328_export_valid=b in poses,
                     rgb312_export_origin=origin(a, poses, keys), rgb328_export_origin=origin(b, poses, keys),
                     rgb312_filler_temp_valid=a in filler, rgb328_filler_temp_valid=b in filler,
                     rgb312_filler_batch=trace.filler[a].get('audit_batch') if a in trace.filler else None,
                     rgb328_filler_batch=trace.filler[b].get('audit_batch') if b in trace.filler else None,
                     final_kf_snapshot_event=snapshot['event'], export_event=event['event'], reason=None)
    alignment = alignment_rotation(poses, gt)
    metrics = [metric(arm, attempt, 'FIXED_RGB_FINAL_EXPORT', poses, gt, alignment, reason=None if set(TARGET) <= poses.keys() else 'FINAL_POSE_MISSING'),
               metric(arm, attempt, 'DIRECT_RETAINED_KEYFRAME_POST_FINAL_BA', direct, gt, alignment,
                      reason=None if set(TARGET) <= direct.keys() else 'AT_LEAST_ONE_RETAINED_KEYFRAME_ENDPOINT_UNAVAILABLE')]
    diagnostics = [metric(arm, attempt, 'FILLER_TEMPORARY_BATCH_RESULT', filler, gt, alignment,
                          reason=None if set(TARGET) <= filler.keys() else 'FILLER_POSE_MISSING')]
    comparison = []
    if trace.common:
        for phase, (call, stages) in (('FIRST', trace.common[0]), ('LAST', trace.common[-1])):
            for label, points in stages.items():
                pr = observed(points, TARGET)
                comparison.append(dict(anchor=phase, call=call, metric=metric(arm, attempt, label, pr, gt, alignment)))
    return retention, metrics, diagnostics, comparison


def origin(i, poses, keys):
    return None if i not in poses else 'REINSERTED_KEYFRAME' if i in keys else 'FILLER_RESULT'


def prepare_pending_tables(root):
    reason = 'CPU_PREPARATION_ONLY_NO_AUTHORIZED_GPU_RESULT'
    retention = [dict(arm=a, status='NOT_RUN', reason=reason) for a in ORDER]
    fixed = [metric(a, None, 'FIXED_RGB_FINAL_EXPORT', {}, None, reason=reason, status='NOT_RUN') for a in ORDER]
    direct = [metric(a, None, 'DIRECT_RETAINED_KEYFRAME_POST_FINAL_BA', {}, None, reason=reason, status='NOT_RUN') for a in ORDER]
    write_csv(Path(root) / 'TASK004_ENDPOINT_RETENTION.csv', RETENTION_FIELDS, retention)
    write_csv(Path(root) / 'TASK004_FIXED_RGB_ENDPOINT_METRICS.csv', METRIC_FIELDS, fixed)
    write_csv(Path(root) / 'TASK004_DIRECT_KEYFRAME_ENDPOINT_METRICS.csv', METRIC_FIELDS, direct)

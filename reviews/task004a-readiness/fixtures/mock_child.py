"""Emit deliberately synthetic receipts and poses. No SLAM, GPU, images or weights."""
import argparse
import json
import os
from pathlib import Path
import sys

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from contracts import BITS, IDS, INPUT_SHA, R2_K, TENSOR_SHA, need, new_json, stat_sha, verify_policy
from trace_audit import BEFORE, CANDIDATE, CLAMP, NATIVE


def synthetic_gt():
    gt = np.repeat(np.eye(4)[None, :, :], len(IDS), axis=0)
    x = np.linspace(0, 1, len(IDS))
    gt[:, :3, 3] = np.column_stack((80*x, 10*x**2, 3*np.sin(x*4)))
    return gt


def create(out, config, arm, selected, process_failure=False, bad_trace=False):
    need(os.environ.get('CUDA_VISIBLE_DEVICES', '') == '', 'CPU-only environment required')
    verify_policy(out/'policy.json', arm)
    pid = os.getpid()
    events = 0
    bcount = 0
    offsets = []
    trace = (out/'observer.jsonl').open('xb')

    def log(kind, stage, trigger=None, step=None, batch=None, **more):
        nonlocal events
        events += 1
        line = json.dumps(dict(schema=CANDIDATE, event=events, type=kind, stage=stage, pid=pid,
                               trigger_rgb_id=trigger, outer_iteration=step, filler_batch=batch, **more),
                          allow_nan=False, separators=(',', ':')) + '\n'
        trace.write(line.encode('ascii'))

    keep = dict(E0=(312,328), E1=(328,), E2=(312,328), E3=(312,), E4=(312,328), E6=(328,), E7=(), E8=(312,))[arm]
    keys = [1, 101, 229, *keep, 430]
    gt = synthetic_gt()
    p = gt.copy()
    p[:, :3, 3] /= 23 + sum(BITS[arm])
    q = p.copy()
    # Use different offsets at different retained anchors so relative motion also differs.
    q[[i-1 for i in keys], 1, 3] += np.asarray(keys) * 0.0001

    def row(index, slot, pool='KEYFRAME_CACHE', trajectory=p):
        return dict(slot=slot, rgb_id=index, pool=pool, w2c_xyzw=[*map(float, -trajectory[index-1, :3, 3]), 0, 0, 0, 1])

    def rows(ids, start=0, pool='KEYFRAME_CACHE', trajectory=p):
        return [row(i, start+off, pool, trajectory) for off, i in enumerate(ids)]

    def call(stage, items, flags, trigger=None, step=None, batch=None, t0=0, corrupt=False):
        nonlocal bcount
        bcount += 1
        d,w,u,m = [bool(x) for x in flags]
        take = d if not m else True
        n = len(items)
        counters = dict(scope='ALL_PIXELS_ACTIVE_SLOT_PREFIX', active_slots=n, total=80*45*n,
                        negative=0, nonfinite=0, float32_floor_count=0)
        area = [(i, i+1) for i in range(n-1)]
        common = dict(trigger=trigger, step=step, batch=batch)
        active = stage in ('frontend_local_predecision', 'frontend_local_retained')
        log(BEFORE, stage, **common, ba_id=bcount, rows=items, t0=t0, t1=n, edge_slots=area,
            metric_depth_prior_selected=take, metric_depth_branch_active=d, metric_depth_configured=True,
            source_uba=w, update_u=u, motion_only=m, target_uba=False, gamma_depth=0.01,
            task004_local_phase=stage if active else None, metric_depth_positive_support=4 if d else 0,
            cached_prior_positive_support=4)
        if corrupt:
            return
        log(NATIVE, stage, **common, ba_id=bcount, rows=items, full_disparity_grid=counters)
        log(CLAMP, stage, **common, ba_id=bcount, full_disparity_grid=counters)

    log('tracking_start', 'startup', enable_online_ba=False, enable_loop=False, mapping_enabled=False, droidvis=True, backend_stride=8)
    for i in IDS:
        if i == 328:
            common_keys = sorted(set([k for k in keys if k <= i] + [312,328]))
            call('frontend_local_predecision', rows(common_keys), (*BITS[arm], 0), trigger=i, step=1,
                 t0=(len(common_keys)-1 if arm == 'E3' else 0), corrupt=bad_trace or process_failure)
            if process_failure:
                trace.close()
                print('synthetic native pre-return failure', file=sys.stderr)
                return 31
            if 328 in keys and not bad_trace:
                call('frontend_local_retained', rows(common_keys), (*BITS[arm], 0), trigger=i, step=1)
        decision = ('RETAINED' if i in keys else 'LOCAL_BA_REJECTED' if i == 328 else 'MOTION_FILTER_REJECTED')
        log('keyframe_decision', 'frontend_input', trigger=i, outcome=decision)

    final = rows(keys)
    log('stage_boundary', 'final_pre', rows=final)
    for stage, count in ((1, 7), (2, 12)):
        log('stage_boundary', f'final_ba_phase_{stage}', rows=final)
        for k in range(1, count+1):
            call(f'final_ba_phase_{stage}', final, (0,1,0,0), step=k)
        log('stage_boundary', f'final_phase_{stage}_done', rows=final)
    for batch, off in enumerate(range(0, len(IDS), 16), 1):
        frames = IDS[off:off+16]
        temp = rows(frames, len(keys), 'FILLER_TEMP', q)
        log('filler_interpolated', 'filler_interpolated', batch=batch, rows=temp)
        for k in range(1, 13):
            call('filler_pose_only', final+temp, (0,1,0,1), step=k, batch=batch, t0=len(keys))
            log('filler_pose_update', 'filler_pose_only', step=k, batch=batch, rows=temp, ba_id=bcount, update_number=k)
        log('filler_batch_result', 'filler_pose_only', step=12, batch=batch, rows=temp)
    log('export_matrix', 'export_matrix_after_anchor_reinsertion', c2w=p.tolist(), rgb_ids=list(IDS), anchor_rgb_ids=keys)
    log('observer_overhead', 'export_matrix_after_anchor_reinsertion', events_before_summary=events, bytes_before_summary=trace.tell())
    trace.close()

    local = [i-1 for i in keys]
    cfg = yaml.safe_load(config.read_bytes())
    cfg['data'].update(output=str(out), input_folder='CPU_MOCK_NO_IMAGES')
    (out/'native_config.yaml').write_text(yaml.safe_dump(cfg), encoding='utf-8')
    new_json(out/'keyframes.json', dict(final_count=len(keys), peak_tracking_count=len(keys), rgb_ids=keys, local_indices=local))
    new_json(out/'task004_policy_receipt.json', dict(arm=arm, campaign='FACTORIAL', local_dwu=list(BITS[arm]),
                                             final_phases=2, policy_sha256=selected))
    new_json(out/'model_input.json', dict(manifest_sha256=INPUT_SHA, actual_loader_k=R2_K, rgb_ids=list(IDS), stride=1,
                                        size=[640,360], branch='FIXED_K_NATIVE_RESIZE', pose_inputs=0, multiprocessing='spawn'))
    child = dict(pid=pid, read_frames=len(IDS), filler_frames=len(IDS), scaled_rgb_tensor_sha256=TENSOR_SHA)
    new_json(out/'tracking_child_ok.json', child)
    new_json(out/'native_camera_stream.json', dict(pid=pid+1000, frustum_messages=1))
    new_json(out/'progress.json', dict(phase='complete', done=len(IDS), n=len(IDS), keyframes=len(keys)))
    (out/'native/traj').mkdir(parents=True)
    est = np.column_stack((p[:, :3, 3], np.repeat([[0,0,0,1]], len(IDS), axis=0)))
    txt = out/'native/traj/est_poses_full.txt'
    np.savetxt(txt, np.column_stack((np.arange(len(IDS)), est)))
    np.savez_compressed(out/'trajectory.npz', rgb_ids=IDS, c2w_xyzw=est, valid=np.ones(len(IDS), dtype=bool),
                        keyframe_rgb_ids=keys, keyframe_local_indices=local)
    np.savez(out/'native/video.npz', synthetic=np.ones(1), timestamps=local)
    new_json(out/'model_result.json', dict(child, input_frames=len(IDS), poses_exported=len(IDS), valid_poses=len(IDS),
             keyframes=len(keys), native_viewer_exit=0, native_viewer_pid=pid+1000, native_camera_messages=1,
             trajectory_sha256=stat_sha(out/'trajectory.npz'), upstream_text_sha256=stat_sha(txt)))
    print(f'{arm}: SYNTHETIC_ONLY, no model, no images, no GPU')
    return 0


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('out', type=Path)
    cli.add_argument('config', type=Path)
    cli.add_argument('arm')
    cli.add_argument('policy_sha')
    cli.add_argument('--process-failure', action='store_true')
    cli.add_argument('--bad-trace', action='store_true')
    opt = cli.parse_args()
    raise SystemExit(create(opt.out, opt.config, opt.arm, opt.policy_sha, opt.process_failure, opt.bad_trace))

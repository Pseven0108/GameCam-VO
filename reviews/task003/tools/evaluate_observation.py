"""Evaluate the single Task 003 trace using the sealed, local-only GT."""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation
import yaml

from offline_task003 import PAIRS, degrees, dump, read, read_track, score, sha, table
from process_runtime import check

ROOT = Path(__file__).resolve().parents[1]
R2 = ROOT.parent / 'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1'
SRC = ROOT.parent / 'DROID_W_TASK003_VAL007_RUNTIME_LOCALIZATION'
CAP = ROOT / 'remote/capture'
EVD = ROOT / 'evidence'
IDS = np.arange(1, 488)
INTEREST = set(sum(PAIRS, ()))
INIT = ('frontend_init_begin', 'frontend_init_first_done', 'frontend_init_second_begin', 'frontend_init_second_done')
FINAL = ('final_pre', 'final_phase_1_done', 'final_phase_2_done')
ORDERED = (*INIT, 'first_colocated_frontend_before', 'first_colocated_frontend_after',
           'last_colocated_frontend_after', *FINAL, 'filler_interpolated', 'filler_batch_result', 'exported')


def c2w(row):
    aa = np.asarray(row['w2c_xyzw'], dtype=np.float64)
    assert np.isfinite(aa).all() and abs(np.linalg.norm(aa[3:]) - 1) < 2e-3
    r = Rotation.from_quat(aa[3:]).as_matrix().T
    m = np.eye(4)
    m[:3, :3], m[:3, 3] = r, -(r @ aa[:3])
    return m


def poses_of(event, pool=None):
    return {r['rgb_id']: c2w(r) for r in event.get('rows', []) if r['rgb_id'] in INTEREST
            and (pool is None or r['pool'] == pool)}


def kv(config, prefix=()):
    if isinstance(config, dict):
        return {k: v for name, value in config.items() for k, v in kv(value, (*prefix, name)).items()}
    return {'.'.join(prefix): config}


def config_check():
    sealed = ROOT / 'remote/incoming/native_config.yaml'
    actual = CAP / 'native_config.yaml'
    cfg, observed = (kv(yaml.safe_load(x.read_text(encoding='utf-8'))) for x in (sealed, actual))
    changes = {k: {'sealed': cfg.get(k), 'actual': observed.get(k)} for k in sorted(cfg.keys() | observed.keys())
               if type(cfg.get(k)) is not type(observed.get(k)) or cfg.get(k) != observed.get(k)}
    assert set(changes) == {'data.input_folder', 'data.output'}, changes
    man = read(CAP/'model_input.json')
    assert man['rgb_ids'] == IDS.tolist() and man['pose_inputs'] == 0 and man['multiprocessing'] == 'spawn'
    assert man['size'] == [640, 360] and man['stride'] == 1
    assert man['actual_loader_k'] == [386.01129150390625, 386.01129150390625, 319.5, 179.5]
    dump(EVD / 'CONFIG_EFFECTIVE_DIFF.json', dict(status='PASS_ONLY_TWO_IO_PATHS', sealed_sha256=sha(sealed),
         actual_sha256=sha(actual), changes=changes, loader=man))


def plots(rows, perframe, group_steps):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    dst = ROOT / 'figures'
    dst.mkdir(exist_ok=True)
    labels = dict(first_colocated_frontend_before='Insert / before local BA',
        first_colocated_frontend_after='First local BA', last_colocated_frontend_after='Last local BA',
        final_pre='Before global BA', final_phase_1_done='Global BA pass 1', final_phase_2_done='Global BA pass 2',
        filler_interpolated='Filler interpolation', filler_batch_result='Filler optimized', exported='Export')
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), layout='constrained')
    for ax, pair in zip(axes, PAIRS):
        observed = [r for r in rows if (r['first_rgb'], r['last_rgb']) == pair and r['status'] == 'OBSERVED'
                    and r['stage'] in labels]
        x = np.arange(len(observed))
        y = [100*r['length_ratio'] for r in observed]
        ax.plot(x, y, color='#176e86', marker='o', lw=1.6, ms=4)
        ax.axhline(100, color='#626d73', lw=1, ls='--', label='GT = 100%')
        ax.set_xticks(x, [labels[r['stage']] for r in observed], rotation=48, ha='right', fontsize=8)
        ax.set_title(f'RGB {pair[0]} to {pair[1]}')
        ax.set_ylabel('Endpoint displacement (% of GT)')
        ax.grid(axis='y', alpha=.2)
        ax.set_ylim(bottom=0)
    fig.suptitle('Task 003 / Stage localization with one fixed global Sim(3)')
    fig.savefig(dst/'TASK003_STAGE_DISPLACEMENT.png', dpi=175)
    plt.close(fig)

    gp = np.array([r['gt_xyz'] for r in perframe])
    ep = np.array([r['est_xyz'] for r in perframe])
    keys = np.array([r['keyframe'] for r in perframe])
    fig, axs = plt.subplots(2, 1, figsize=(9, 8), layout='constrained', height_ratios=[3, 2])
    ii, jj = sorted(np.argsort(np.ptp(gp, axis=0))[-2:])
    axs[0].plot(gp[:, ii], gp[:, jj], color='#23272a', lw=1.5, label='VIPER camera GT')
    axs[0].plot(ep[:, ii], ep[:, jj], color='#176e86', lw=1.5, label='DROID-W export')
    axs[0].plot(ep[keys, ii], ep[keys, jj], '.', color='#176e86', ms=3, label='Exported keyframes')
    for rgbid in sorted(INTEREST):
        x, y = ep[rgbid-1, [ii, jj]]
        axs[0].scatter(x, y, s=12, c='#bd563a')
    axs[0].set(xlabel=f'{"XYZ"[ii]} (game units)', ylabel=f'{"XYZ"[jj]} (game units)', aspect='equal')
    axs[0].legend(frameon=False)
    axs[1].plot(IDS, [r['position_error'] for r in perframe], color='#176e86', lw=1.35)
    axs[1].axvspan(min(INTEREST), max(INTEREST), color='#bd563a', alpha=.12, label='Target range')
    axs[1].set(xlabel='RGB ID', ylabel='Position error (game units)', xlim=(1, 487))
    axs[1].legend(frameon=False)
    for ax in axs:
        ax.grid(alpha=.2)
    fig.suptitle('val_007 / Full export and per-frame error')
    fig.savefig(dst/'TASK003_FINAL_TRAJECTORY.png', dpi=175)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), layout='constrained')
    for ax, pair in zip(axes, PAIRS):
        for group, name, color in [('filler', 'Filler pose updates', '#af4d35'), ('final', 'Final BA updates', '#176e86')]:
            grp = [r for r in group_steps if (r['first_rgb'], r['last_rgb']) == pair and r['group'] == group]
            if grp:
                ax.plot([r['step'] for r in grp], [100*r['length_ratio'] for r in grp], '.-', color=color, label=name)
        ax.axhline(100, lw=1, ls='--', color='#626d73')
        ax.set(xlabel='Update within stage', ylabel='Endpoint displacement (% GT)', title=f'{pair[0]} to {pair[1]}')
        ax.grid(alpha=.2)
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle('Native updates at observed endpoints / stages shown only where available')
    fig.savefig(dst/'TASK003_OPTIMIZATION_STEPS.png', dpi=175)
    plt.close(fig)


def main():
    lock = read(SRC/'evidence/sealed_r2/PROTOCOL_LOCK.json')
    evaluator = R2/'pipeline/offline_evaluation.py'
    assert sha(evaluator) == lock['evaluation']['source_sha256']
    sys.path.insert(0, str(evaluator.parent))
    import offline_evaluation as ev
    ev.selfcheck()
    config_check()
    gt_path = R2/'offline_gt/val_007.npz'
    gt_sha = sha(gt_path)
    assert gt_sha == '91fb149c066bb488ac6071602a4b50fe1540243f2db3369a3706f63b705d7008'
    with np.load(gt_path, allow_pickle=False) as z:
        np.testing.assert_array_equal(z['rgb_ids'], IDS)
        np.testing.assert_array_equal(z['camera_frame_ids'], IDS-1)
        gt = z['c2w']
    assert gt.shape == (487, 4, 4) and np.isfinite(gt).all()
    assert np.max(np.abs(np.linalg.det(gt[:, :3, :3])-1)) < 2e-3
    attempt = read(CAP/'attempt.json')
    path = CAP/'trajectory.npz'
    trace = CAP/'observer.jsonl'
    assert attempt['exit_code'] == 0 and attempt['attempts_consumed'] == 1
    assert sha(path) == attempt['model']['trajectory_sha256'] and sha(trace) == attempt['trace_sha256']
    assert sha(CAP/'est_poses_full.txt') == attempt['model']['upstream_text_sha256']
    pred, keys = read_track(path, IDS)
    frozen = SRC/'evidence/sealed_r2/wild_reference/val_007_full_00001-00487/trajectory.npz'
    assert sha(frozen) == '7db5457fd92a43e6f3bd4408c4f7f14e84c53c0449a2b51e7dd756894a03054a'
    historical, oldkeys = read_track(frozen, IDS)
    pr = Rotation.from_quat(pred[:, 3:]).as_matrix()
    fit = ev.align(pred[:, :3], gt[:, :3, 3], True)
    full, rpe, _ = ev.metrics(pred, gt, IDS, np.ones(len(IDS), dtype=bool))
    oldfull, _, _ = ev.metrics(historical, gt, IDS, np.ones(len(IDS), dtype=bool))
    assert full['scale_est_to_gt'] == fit[2]

    first, last, bounds, inserts, fill, fillsteps, fsteps = {}, {}, {}, {}, defaultdict(dict), defaultdict(dict), []
    counts, decisions, mechanisms, depth_focus = Counter(), Counter(), Counter(), []
    before_ids, exported, overhead, pid = {}, None, None, None
    with trace.open('rb') as f:
        for idx, line in enumerate(f, 1):
            d = check(line, idx, pid)
            pid = d['pid']
            kind, stage = d['type'], d['stage']
            counts[(kind, stage)] += 1
            if kind == 'keyframe_candidate_inserted' and d['row']['rgb_id'] in INTEREST:
                inserts[d['row']['rgb_id']] = (idx, c2w(d['row']))
                depth_focus.append(dict(event=idx, rgb_id=d['row']['rgb_id'], pose_init=d['pose_init'],
                    predicted_depth=d['predicted_depth'], native_mono_prior=d['native_mono_prior'], disparity=d['disparity']))
            if kind == 'keyframe_decision':
                decisions[d['outcome']] += 1
            if kind == 'stage_boundary' and stage in (*INIT, *FINAL, 'filler_anchors'):
                bounds[stage] = (idx, poses_of(d, 'KEYFRAME_CACHE'))
            if kind == 'ba_before':
                mechanisms[(stage, d['metric_depth_branch_active'], d['source_uba'], d['update_u'], d['motion_only'])] += 1
            if stage.startswith('frontend_') and kind in ('ba_before', 'ba_after_native'):
                p = poses_of(d, 'KEYFRAME_CACHE')
                for pair in PAIRS:
                    if all(k in p for k in pair):
                        if kind == 'ba_before' and pair not in first:
                            first[pair] = (idx, p)
                            before_ids[pair] = d['ba_id']
                        elif kind == 'ba_after_native':
                            if before_ids.get(pair) == d['ba_id']:
                                first[(pair, 'after')] = (idx, p)
                            last[pair] = (idx, p)
            if stage.startswith('final_ba_phase_') and kind == 'ba_after_native':
                fsteps.append((idx, stage, d['outer_iteration'], poses_of(d, 'KEYFRAME_CACHE')))
            if kind in ('filler_interpolated', 'filler_batch_result', 'filler_pose_update'):
                p = poses_of(d, 'FILLER_TEMP')
                sink = fillsteps[d['update_number']] if kind == 'filler_pose_update' else fill[kind]
                for k, m in p.items():
                    assert k not in sink
                    sink[k] = (idx, m, d['filler_batch'])
            if kind == 'export_matrix':
                assert d['anchor_rgb_ids'] == keys.tolist()
                exported = idx, np.array(d['c2w'])
            if kind == 'observer_overhead':
                overhead = d

    assert overhead and exported and counts[('tracking_start', 'startup')] == 1
    exp_id, exp = exported
    # Native matrix and text/quaternion export are different serializations of the same poses.
    np.testing.assert_allclose(exp[:, :3, 3], pred[:, :3], atol=5e-5, rtol=0)
    np.testing.assert_allclose(exp[:, :3, :3], pr, atol=5e-5, rtol=0)
    aligned = fit[2] * (pred[:, :3] @ fit[0].T) + fit[1]
    perframe = [dict(rgb_id=int(rid), camera_id=int(rid-1), keyframe=bool(rid in keys),
        est_xyz=aligned[i].tolist(), gt_xyz=gt[i, :3, 3].tolist(),
        position_error=float(np.linalg.norm(aligned[i] - gt[i, :3, 3])),
        rotation_error_deg=float(degrees(gt[i, :3, :3].T @ fit[0] @ pr[i]))) for i, rid in enumerate(IDS)]
    rows, iter_rows = [], []

    def evaluate(pair, tag, left, right, note=None):
        a, b = pair
        row = dict(stage=tag, first_rgb=a, last_rgb=b, first_camera=a-1, last_camera=b-1,
                   endpoint_roles='->'.join('K' if k in keys else 'F' for k in pair), note=note)
        if left is None or right is None:
            return dict(row, status='ENDPOINT_UNAVAILABLE', missing_rgb_ids=','.join(str(k) for k,v in zip(pair,(left,right)) if v is None))
        ep, er = (np.stack([m[1][:3, p] for m in (left, right)]) for p in (3, slice(0, 3)))
        return dict(row, status='OBSERVED', first_event=left[0], last_event=right[0],
                    length_est_native_units=float(np.linalg.norm(ep[1]-ep[0])),
                    **score(ep, er, gt[np.array(pair)-1], fit, a, b))

    for pair in PAIRS:
        shared = {**bounds, 'first_colocated_frontend_before': first.get(pair),
                  'first_colocated_frontend_after': first.get((pair, 'after')), 'last_colocated_frontend_after': last.get(pair),
                  'exported': (exp_id, {x: exp[x-1] for x in INTEREST})}
        for stage in ORDERED:
            if stage in fill:
                l, r = (fill[stage].get(k) for k in pair)
                note = (f'Filler temporary poses; batches {l[2]} and {r[2]}. Export reinserts any keyframes.' if l and r else 'Filler temporary poses only.')
            else:
                entry = shared.get(stage)
                l, r = ((entry[0],entry[1][k]) if entry and k in entry[1] else None for k in pair)
                note = 'Common state in one event.'
                if stage in INIT:
                    note = 'Global warmup; endpoints are later in the sequence.'
                if stage == 'first_colocated_frontend_before':
                    note = 'First local BA with both endpoints, using a common pre-update state.'
            rows.append(evaluate(pair, stage, l, r, note))
        rows.append(evaluate(pair, 'separate_insert_events', *(inserts.get(k) for k in pair),
                             'Separate keyframe insertion events; earlier endpoint may move between insertions.'))
        for idx, stage, step, pp in fsteps:
            if all(k in pp for k in pair):
                iter_rows.append(dict(group='final', step=step+(7 if stage.endswith('_2') else 0),
                                      **evaluate(pair, stage, *((idx, pp[k]) for k in pair))))
        for step, pp in sorted(fillsteps.items()):
            if all(k in pp for k in pair):
                iter_rows.append(dict(group='filler',step=step,**evaluate(pair,'filler_pose_update', *(pp[k] for k in pair))))

    table(ROOT/'TASK003_VAL007_INTERVAL_ANALYSIS.csv', rows)
    table(ROOT/'TASK003_TARGET_OPTIMIZATION_STEPS.csv', iter_rows)
    table(ROOT/'TASK003_EXPORTED_PER_FRAME.csv', perframe)
    table(ROOT/'TASK003_EXPORTED_RPE_OFFSETS.csv', rpe)
    table(ROOT/'TASK003_ACTIVE_MECHANISMS_BY_STAGE.csv', [dict(stage=s, metric_depth=md, source_uba=u, update_u=up,
          motion_only=mo, calls=n) for (s, md, u, up, mo),n in sorted(mechanisms.items())])
    with (CAP/'resource_samples.csv').open(newline='') as f:
        samples = list(csv.DictReader(f))
    summary = dict(attempt=attempt, gt_path=str(gt_path), gt_sha256=gt_sha, evaluator_sha256=sha(evaluator),
         rgb_to_camera='camera_frame_id = rgb_id - 1; 487/487', sim3_alignment=dict(R=fit[0].tolist(), t=fit[1].tolist(),
         scale=fit[2], rank=fit[3], fit_to='entire Task003 final export, reused at every observed stage'),
         metrics=full, historical_r2=oldfull, stage_counts={f'{a}/{b}': n for (a,b),n in counts.items()},
         keyframes_overlap=dict(old_count=len(oldkeys), new_count=len(keys), common_count=len(set(keys)&set(oldkeys)),
            added=sorted(set(keys.tolist())-set(oldkeys.tolist())), removed=sorted(set(oldkeys.tolist())-set(keys.tolist()))),
         choices=dict(decisions), target_depth_inserts=depth_focus, overhead=overhead,
         host_peak_gpu_mib=max(int(r['gpu_used_mib']) for r in samples),
         min_shm_free_bytes=min(int(r['shm_free_bytes']) for r in samples),
         min_disk_free_bytes=min(int(r['disk_free_bytes']) for r in samples),
         peak_cgroup_memory_bytes=max(int(r['cgroup_memory_bytes']) for r in samples),
         interval_rows=rows)
    dump(EVD/'TASK003_RUNTIME_EVALUATION.json', summary)
    plots(rows, perframe, iter_rows)
    print('PASS: trace and trajectory SHA; configuration diff; camera correspondence; native matrix equals exported poses.')
    for row in rows:
        if row['status'] == 'OBSERVED':
            print(row['first_rgb'], row['last_rgb'], row['stage'], row['endpoint_roles'],
                  f"ratio={row['length_ratio']:.7f} RPEt={row['translation_rpe_game_units']:.4f} RPErot={row['rotation_rpe_deg']:.3f}",
                  row.get('first_event'), row.get('last_event'))


if __name__ == '__main__':
    main()

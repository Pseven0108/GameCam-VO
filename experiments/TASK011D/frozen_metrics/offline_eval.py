"""Score sealed full trajectories locally, with one alignment per sequence."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from fullseq_common import ROOT, atomic_json, sha_file

ENV_BY_VAL = {**dict.fromkeys([1,2,3,4,29,30,31,32,41,42,43,44],'Day'),
              **dict.fromkeys([5,6,7,33,34,35,36,45,46,47],'Night'),
              **dict.fromkeys(range(8,18),'Sunset'),
              **dict.fromkeys([18,19,20,37,38,39,40],'Rain'),
              **dict.fromkeys(range(21,29),'Snow')}


def fit_alignment(est, gt, scale_free):
    a, b = est - est.mean(0), gt - gt.mean(0)
    variance = np.sum(a*a) / len(a)
    if variance <= 1e-14 or np.sum(b*b) <= 1e-12:
        raise ValueError('degenerate estimated or reference translation')
    u, d, vt = np.linalg.svd(b.T @ a / len(a))
    # Rotation is underconstrained for a line, so do not emit aligned orientation errors there.
    rank = int(np.sum(d > max(d[0]*1e-10,1e-14)))
    sign = np.array([1,1,np.linalg.det(u @ vt)])
    rot = (u * sign) @ vt
    scale = float(d @ sign / variance) if scale_free else 1.
    if scale <= 0 or not np.isfinite(scale):
        raise ValueError('nonpositive or invalid alignment scale')
    return rot, gt.mean(0) - scale * rot @ est.mean(0), scale, rank


def norm_rmse(x):
    return float(np.sqrt(np.mean(np.sum(x*x,axis=-1))))


def rpe(est_p, est_r, gt_p, gt_r, ids, offset):
    by_id = {v:i for i,v in enumerate(ids)}
    pairs = [(i,by_id[f+offset]) for i,f in enumerate(ids) if f+offset in by_id]
    if not pairs:
        return {'pairs':0, 'translation_rmse':None, 'rotation_rmse_deg':None,
                'translation_relative_pct_median':None,'nonzero_displacement_pairs':0}
    i,j = np.asarray(pairs).T
    rel = lambda pos, rot: ((rot[i].transpose(0,2,1) @ (pos[j]-pos[i])[:,:,None])[:,:,0],
                            rot[i].transpose(0,2,1) @ rot[j])
    e,Er = rel(est_p,est_r)
    g,Gr = rel(gt_p,gt_r)
    angle = np.degrees(Rotation.from_matrix(Gr.transpose(0,2,1) @ Er).magnitude())
    disp = np.linalg.norm(g,axis=1)
    good = disp > 1e-8
    pct = np.linalg.norm(e-g,axis=1)[good]/disp[good]*100
    return {'pairs':len(i),'translation_rmse':norm_rmse(e-g), 'rotation_rmse_deg':float(np.sqrt(np.mean(angle**2))),
            'translation_relative_pct_median':float(np.median(pct)) if good.any() else None,
            'nonzero_displacement_pairs':int(np.sum(good))}


def pose_metrics(pred, truth, ids, stride):
    est_p, est_r = pred[:,:3], Rotation.from_quat(pred[:,3:]).as_matrix()
    gt_p, gt_r = truth[:,:3,3], truth[:,:3,:3]
    path_len = float(np.linalg.norm(np.diff(gt_p,axis=0),axis=1).sum())
    stats = {'gt_path_length':path_len, 'raw_est_path_length':float(np.linalg.norm(np.diff(est_p,axis=0),axis=1).sum())}
    for mode in ('se3','sim3'):
        q,t,s,rank = fit_alignment(est_p,gt_p,mode=='sim3')
        aligned = s * (est_p @ q.T) + t
        ate = norm_rmse(aligned-gt_p)
        stats[f'ate_{mode}_rmse'] = ate
        stats[f'ate_{mode}_path_pct'] = 100*ate/path_len if path_len>1e-12 else None
        if mode=='sim3':
            stats['scale_est_to_gt'] = s
            stats['alignment_translation_covariance_rank'] = rank
            scopes = {'full':np.arange(len(ids)), **dict(zip(('early','middle','late'),np.array_split(np.arange(len(ids)),3)))}
            relative = [{'alignment':'sim3_global','segment':seg,'delta_rgb_frames':off,
                        **rpe(aligned[ix], (q @ est_r)[ix], gt_p[ix], gt_r[ix], ids[ix], off)}
                        for seg,ix in scopes.items() for off in sorted({stride,60,120})]
    return stats, relative


def csv_write(path, rows):
    with path.open('w',newline='',encoding='utf-8-sig') as stream:
        columns = list(dict.fromkeys(k for row in rows for k in row))
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        writer.writerows(rows)


def score(result_root, out):
    locked = json.loads((result_root/'evidence/validation-complete.json').read_text())
    index = json.loads((ROOT/'evidence/viper_input_index.json').read_text())
    vals = {f"val_{x['sequence']}":x for x in index['cases'] if x['split']=='val'}
    assert locked['terminal']==locked['planned']==94
    expected = {(x,m) for x in vals for m in ('slam','wild')}
    rows, intervals, seen = [], [], set()
    stride = locked['stride']
    for rec in locked['results']:
        case, model = rec['case'], rec['model']
        assert (case,model) in expected and (case,model) not in seen
        seen.add((case,model))
        meta = vals[case]
        rgb_total = meta['count']
        expected_input = (rgb_total + stride - 1)//stride
        row = {'case':case,'model':model,'environment':ENV_BY_VAL[int(meta['sequence'])],
               'variable_intrinsics':meta['variable_K_stratum'],'status':rec['status'],'stride':stride,
               'original_frames':rgb_total,'scheduled_input':expected_input,
               'processed_frames_last_audit':rec.get('last_progress',{}).get('done'),
               'valid_poses':rec.get('valid_poses',0),'pose_coverage':rec.get('valid_poses',0)/expected_input,
               'duration_seconds':rec['elapsed_sec'],'keyframes':rec.get('native_final_keyframes'),
               'peak_tracking_gpu_mib':rec.get('phase_sampled_peak_gpu_mib',{}).get('tracking'),
               'peak_final_BA_gpu_mib':rec.get('phase_sampled_peak_gpu_mib',{}).get('final_backend'),
               'score_status':'RUN_NOT_COMPLETE'}
        if rec['status']=='COMPLETE':
            attempt = result_root / rec['attempt']
            traj_path = attempt/'trajectory.npz'
            assert attempt.resolve().is_relative_to(result_root.resolve())
            assert sha_file(traj_path)==rec['trajectory_sha256']
            with np.load(traj_path,allow_pickle=False) as ts, np.load(ROOT/'offline_gt'/f'{case}.npz',allow_pickle=False) as gt:
                ids = gt['rgb_ids'][::stride]
                assert len(ids)==expected_input and np.array_equal(ts['rgb_ids'],ids) and ts['finite_valid'].all()
                try:
                    metrics, rel = pose_metrics(ts['c2w_xyzw'],gt['gt_c2w'][::stride],ids,stride)
                    row.update(metrics,score_status='SCORED')
                    intervals.extend({'case':case,'model':model,**r} for r in rel)
                except ValueError as e:
                    row.update(score_status='DEGENERATE_ALIGNMENT',score_reason=str(e))
        rows.append(row)
    assert seen==expected
    by_key = {(x['case'],x['model']):x for x in rows}
    paired = {c for c in vals if all(by_key[c,m]['score_status']=='SCORED' for m in ('slam','wild'))}
    env_summary = []
    for model in ('slam','wild'):
        for category in ('ALL','Day','Sunset','Rain','Night','Snow'):
            group = [r for r in rows if r['model']==model and (category=='ALL' or r['environment']==category)]
            for var in (False,True):
                part = [r for r in group if r['variable_intrinsics']==var]
                shared = [x for x in part if x['case'] in paired]
                env_summary.append({'model':model,'group':category,'variable_intrinsics':var,'planned':len(part),
                                    'completed':sum(r['status']=='COMPLETE' for r in part),
                                    'scored':sum(r['score_status']=='SCORED' for r in part), 'paired_scored':len(shared),
                                    'mean_valid_pose_coverage':float(np.mean([r['pose_coverage'] for r in part])) if part else None,
                                    'paired_median_sim3_ate_rmse':float(np.median([r['ate_sim3_rmse'] for r in shared])) if shared else None,
                                    'paired_median_sim3_ate_percent_gt_path':float(np.median([r['ate_sim3_path_pct'] for r in shared])) if shared else None})
    out.mkdir(exist_ok=False)
    csv_write(out/'validation_sequence_scores.csv', rows)
    csv_write(out/'validation_segment_rpe.csv', intervals)
    csv_write(out/'validation_environment_summary.csv', env_summary)
    atomic_json(out/'validation_evaluation.json', {'results':rows,'summary':env_summary,'stride':stride,'attempted':94,
                 'scored':len([x for x in rows if x['score_status']=='SCORED']),'paired_scored_sequences':len(paired),
                 'protocol': {'coordinates':'OpenCV camera-to-world after official View Matrix conversion',
                              'units':'VIPER game units, meters not asserted','primary':'global Sim3 per complete sequence',
                              'SE3':'diagnostic, scale not fit','rpe':'same global Sim3; early/middle/late time order thirds',
                              'pose_coverage':'numerical validity, not guaranteed tracking accuracy',
                              'scale_direction':'multiply estimated translation to align to GT',
                              'K':'common fixed Train-only prior; Day 042/043 separately stratified',
                              'truth_scope':'local offline scores; frame ID minus one, physical clock unverified'}})


def selfcheck():
    # Reference curve and rotations are independent of the fit; get exact known Sim(3).
    tt = np.arange(130) * .03
    gt_pos = np.stack([tt, .3*np.sin(tt), .2*np.cos(tt)],axis=-1)
    gt_r = Rotation.from_euler('z',.3*tt).as_matrix()
    rot = Rotation.from_euler('xy',[.2,-.4]).as_matrix()
    truth = np.broadcast_to(np.eye(4),(len(tt),4,4)).copy()
    truth[:,:3,:3],truth[:,:3,3] = gt_r, gt_pos
    pred = np.column_stack([(gt_pos - [1,-2,.4]) @ rot / 3.5, Rotation.from_matrix(rot.T @ gt_r).as_quat()])
    m, r = pose_metrics(pred,truth,np.arange(1,len(tt)+1),1)
    assert abs(m['scale_est_to_gt']-3.5)<1e-10 and m['ate_sim3_rmse']<1e-10
    assert m['ate_se3_rmse']>.5 and r[0]['pairs']==129 and r[0]['translation_rmse']<1e-10
    assert r[0]['rotation_rmse_deg']<1e-9 and rpe(gt_pos,gt_r,gt_pos,gt_r,np.arange(130)*3,1)['pairs']==0
    try:
        fit_alignment(np.zeros_like(gt_pos),gt_pos,True)
    except ValueError:
        pass
    else:
        raise AssertionError('degenerate fit was accepted')
    print('offline_eval self-check passed: scale, ATE, RPE, gaps, degenerate alignment')


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--result-root',type=Path)
    ap.add_argument('--out',type=Path)
    ap.add_argument('--selfcheck',action='store_true')
    args=ap.parse_args()
    if args.selfcheck:
        selfcheck()
    else:
        score(args.result_root,args.out)

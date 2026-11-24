"""Checked loaders and numerical functions for the local VIPER R2 audit."""
import io
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='2',
                  OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parents[1]
EXP = OUT.parent
PARENT = EXP / 'DROID_W_TASK002B_R2_INPUT_PARITY_OFFLINE_MOTION_AUDIT'
sys.path.insert(0, str(PARENT / 'analysis_only'))
from audit_common import COMMITS, R2, exact_member, require, sha
import numpy as np
import yaml
from scipy.spatial.transform import Rotation

MODELS = ('DROID-SLAM', 'DROID-W')
CLASSES = ('KEYFRAME', 'FILLED_FRAME')
PAIR_TYPES = tuple(f'{a}->{b}' for a in CLASSES for b in CLASSES)
THIRDS = ('early', 'middle', 'late')
CASE = 'val_007_full_00001-00487'
CASE_INTERVALS = ((309, 325), (301, 353))
FLOOR = 1e-6


def close(actual, expected, message, atol=1e-7, rtol=1e-7):
    if actual is None or expected in (None, ''):
        require(actual is None and expected in (None, ''), message)
    else:
        require(np.isclose(actual, float(expected), rtol=rtol, atol=atol),
                f'{message}: {actual} vs {expected}')


def classify_frames(ids, rgb, pred, flags, local, keys):
    require(ids.ndim == rgb.ndim == local.ndim == keys.ndim == 1 and
            all(a.dtype.kind in 'iu' for a in (ids, rgb, local, keys)) and
            len(local) == len(keys) > 0 and np.all(np.diff(ids) > 0) and
            np.all(np.diff(rgb) > 0) and np.all(np.diff(local) > 0) and
            (local >= 0).all() and (local < len(ids)).all() and
            np.array_equal(ids[local], keys) and np.isin(rgb, ids).all(), 'unusable RGB/keyframe identities')
    require(flags.dtype == bool and flags.shape == rgb.shape and pred.shape == (len(rgb), 7), 'bad pose schema')
    at = np.searchsorted(ids, rgb)
    status = np.full(len(ids), 'MISSING', dtype='<U12')
    good = flags & np.isfinite(pred).all(axis=1) & (np.abs(np.linalg.norm(pred[:, 3:], axis=1) - 1) < .002)
    status[at] = np.where(good, 'VALID', 'INVALID')
    slots = np.full(len(ids), -1, dtype=int)
    slots[at] = np.arange(len(rgb))
    return np.isin(ids, keys), slots, status


def load_export(z, plan, model, ids, protected):
    sid = plan['id']
    base = f'results/{sid}/attempt_001' if model == MODELS[0] else f'wild_reference/{sid}'

    def check(name):
        p = f'{base}/{name}'
        data = exact_member(z, p)
        protected[R2/p] = sha(data)
        return data

    receipt = json.loads(check('attempt.json'))
    blob = check('trajectory.npz')
    h = sha(blob)
    require(h == receipt['trajectory_sha256'] and receipt['segment'] == sid and
            receipt['status'] == 'COMPLETE' and receipt['stride'] == 1 and
            receipt['upstream_commit'] == COMMITS[model] and
            receipt['input_manifest_sha256'] == plan['input_manifest_sha256'], f'receipt mismatch: {model} {sid}')
    with np.load(io.BytesIO(blob), allow_pickle=False) as a:
        fields = ','.join(a.files)
        pred, rgb, flags, local, keys = (a[k] for k in
            ('c2w_xyzw', 'rgb_ids', 'valid', 'keyframe_local_indices', 'keyframe_rgb_ids'))
        direct = a['keyframe_ba_c2w_xyzw'] if 'keyframe_ba_c2w_xyzw' in a else None
    is_kf, slots, status = classify_frames(ids, rgb, pred, flags, local, keys)
    mask = status == 'VALID'
    require(len(pred) == receipt['poses_exported'] and mask.sum() == receipt['valid_poses'] and
            len(keys) == receipt['keyframes'], f'pose count mismatch: {model} {sid}')
    if model == MODELS[0]:
        res = json.loads(check('model_result.json'))
        require(res['keyframes'] == len(keys) and res['trajectory_sha256'] == h and
                res['non_keyframe_filled'] == len(ids)-len(keys), f'model_result mismatch: {sid}')
        check('model_config.json')
        require(direct is not None and direct.shape == (len(keys),7) and np.isfinite(direct).all() and
                np.all(np.abs(np.linalg.norm(direct[:, 3:], axis=1)-1) < .002), f'invalid SLAM BA anchors: {sid}')
        config = dict(final_ba='Droid.terminate.backend(7),backend(12)',
                      pre_final_diagnostic=False, filler_use_dino_features=None,
                      filler_uncertainty_activate=None, filler_bidirectional_u=None)
        names = 'attempt.json;model_result.json;model_config.json'
    else:
        k = json.loads(check('keyframes.json'))
        cfgblob = check('native_config.yaml')
        cfg = yaml.safe_load(cfgblob)
        track = json.loads(check('tracking_child_ok.json'))
        require(h == plan['wild_trajectory_sha256'] and sha(cfgblob) == plan['wild_config_sha256'] and
                track['read_frames'] == track['filler_frames'] == len(ids) and
                k['final_count'] == len(keys) and k['rgb_ids'] == keys.tolist() and
                k['local_indices'] == local.tolist() and direct is None, f'W receipts/schema differ: {sid}')
        u = cfg['tracking']['uncertainty_params']
        config = dict(final_ba=cfg['tracking']['backend']['final_ba'],
                      pre_final_diagnostic=cfg['mapping']['eval_before_final_ba'],
                      filler_use_dino_features=cfg['traj_filler']['use_dino_features'],
                      filler_uncertainty_activate=u['activate'], filler_bidirectional_u=u['enable_bidirectional_uncer'])
        names = 'attempt.json;keyframes.json;tracking_child_ok.json;native_config.yaml'
    rot = np.full((len(ids),3,3), np.nan)
    full = np.full((len(ids), 7), np.nan, dtype=pred.dtype)
    full[slots >= 0] = pred
    rot[mask] = Rotation.from_quat(full[mask, 3:]).as_matrix()
    return dict(pred=full, rot=rot, valid=mask, source=is_kf, slot=slots, status=status, keys=keys,
                direct=direct, member=f'{base}/trajectory.npz', trajectory_sha256=h,
                export_schema=fields, verified_receipts=names, **config)


def angles(mat):
    return np.degrees(Rotation.from_matrix(mat).magnitude()) if len(mat) else np.empty(0)


def pose_errors(pred, rot, truth, r, t, s):
    pts = s * (pred[:, :3] @ r.T) + t
    err = np.linalg.norm(pts - truth[:, :3, 3], axis=1)
    ang = angles(truth[:, :3, :3].transpose(0,2,1) @ (r @ rot))
    return pts, err, ang


def align_once(ev, d, truth, score):
    pred, rot, ok = (d[k] for k in ('pred','rot','valid'))
    r,t,s,rank = ev.align(pred[ok,:3],truth[ok,:3,3],True)
    pts = np.full((len(ok),3),np.nan); te = np.full(len(ok),np.nan); ae = te.copy()
    pts[ok],te[ok],ae[ok] = pose_errors(pred[ok],rot[ok],truth[ok],r,t,s)
    close(s,score['scale_est_to_gt'],'official scale')
    close(rank,score['alignment_rank'],'alignment rank')
    close(ev.rmse(pts[ok]-truth[ok,:3,3]),score['ate_sim3_game_units'],'official ATE')
    d.update(point=pts,translation=te,angle=ae,r=r,t=t,scale=s,rank=rank)


def endpoint_type(kf, i, j):
    return np.where(kf[i],0,2) + np.where(kf[j],0,1)


def relative(ev, d, truth, i, j):
    ep,eq = ev.rel_pose(d['pred'][:,:3],d['rot'],i,j)
    gp,gq = ev.rel_pose(truth[:,:3,3],truth[:,:3,:3],i,j)
    sq = np.sum((d['scale']*ep-gp)**2,axis=1)
    ang = angles(gq.transpose(0,2,1)@eq)
    gt = np.linalg.norm(gp,axis=1)
    ratio = np.full(len(i),np.nan)
    valid = gt > FLOOR
    ratio[valid] = (np.linalg.norm(ep[valid],axis=1)/gt[valid]) * d['scale']
    return np.c_[sq,ang,gt,ratio]


def pair_pack(ev, d, ids, truth, i, j, off):
    ci,cj = ev.pairs(ids,off,d['valid'])
    ok = np.zeros(len(i),dtype=bool); ok[ci] = True
    require(np.array_equal(ci,i[ok]) and np.array_equal(cj,j[ok]),'R2 complete-interval gate')
    v = np.full((len(i),4),np.nan); v[ok] = relative(ev,d,truth,ci,cj)
    return endpoint_type(d['source'],i,j),ok,v


def quantiles(v, prefix):
    return {prefix+'_'+k:x for k,x in zip(('p10','median','p90','p95'),
        map(float,np.quantile(v,[.1,.5,.9,.95])) if len(v) else [None]*4)}


def stats(sq, rot, expected):
    n=len(sq); a=float(sq.sum(dtype=float)); b=float(np.sum(rot**2,dtype=float))
    return dict(expected_count=int(expected),valid_count=n,invalid_or_missing_count=int(expected)-n,
                coverage=n/expected if expected else None,translation_sse=a,rotation_sse=b,
                translation_rmse=float(np.sqrt(a/n)) if n else None,rotation_rmse_deg=float(np.sqrt(b/n)) if n else None,
                **quantiles(np.sqrt(sq),'translation'),**quantiles(rot,'rotation_deg'),
                support='EMPTY' if not n else ('SPARSE_LT10' if n<10 else 'AT_LEAST_10_ROWS'))


def pair_stats(v, ok, sel, screened):
    take=ok&sel; e=v[take]
    ratios=e[np.isfinite(e[:,3]),3]; good=v[take&screened,3]
    return dict(**stats(e[:,0],e[:,1],sel.sum()),ratio_count=len(ratios),**quantiles(ratios,'scaled_ratio'),
                screened_ratio_count=len(good),screened_compression_lt_half_count=int((good<.5).sum()))


def fmt(x):
    return format(x,'.12g') if np.isfinite(x) else ''

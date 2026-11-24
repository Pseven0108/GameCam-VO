"""Recompute the three val_007 intervals from sealed stride-1 exports (CPU)."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
R1 = ROOT.parent / 'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1'
SEG = 'val_007_full_00001-00487'
PAIRS = [(309, 325), (301, 353), (312, 328)]
STAGES = ['inserted', 'frontend_local', 'final_pre', 'final_phase_1_done',
          'final_phase_2_done', 'filler_interpolated', 'filler_updates_done', 'exported']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def table(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8', newline='') as file:
        out = csv.DictWriter(file, fields)
        out.writeheader()
        out.writerows(rows)


def degrees(matrix):
    return np.rad2deg(Rotation.from_matrix(matrix).magnitude())


def score(ep, er, gt, alignment, a, b):
    gp, gr = gt[:, :3, 3], gt[:, :3, :3]
    r, t, s, rank = alignment
    p, q = s * (ep @ r.T) + t, r @ er
    ed, gd = p[1] - p[0], gp[1] - gp[0]
    d, g = np.linalg.norm(ed), np.linalg.norm(gd)
    direction = np.rad2deg(np.arccos(np.clip(ed @ gd / (d * g), -1., 1.))) if min(d, g) > 1e-6 else None
    erel, grel = q[0].T @ q[1], gr[0].T @ gr[1]
    return dict(first_rgb=a, last_rgb=b, first_camera=a-1, last_camera=b-1, alignment_scale=s,
                alignment_rank=rank, length_est_game_units=float(d), length_gt_game_units=float(g),
                length_ratio=float(d/g) if g > 1e-6 else None,
                direction_error_deg=float(direction) if direction is not None else None,
                translation_rpe_game_units=float(np.linalg.norm(q[0].T @ ed - gr[0].T @ gd)),
                rotation_rpe_deg=float(degrees(grel.T @ erel)),
                first_position_error=float(np.linalg.norm(p[0] - gp[0])),
                last_position_error=float(np.linalg.norm(p[1] - gp[1])),
                first_rotation_error_deg=float(degrees(gr[0].T @ q[0])),
                last_rotation_error_deg=float(degrees(gr[1].T @ q[1])),
                estimates_xyz=json.dumps(p.tolist()), gt_xyz=json.dumps(gp.tolist()))


def read_track(path, ids):
    with np.load(path, allow_pickle=False) as z:
        assert np.array_equal(z['rgb_ids'], ids) and z['valid'].all()
        pred, keys = z['c2w_xyzw'].astype(np.float64), z['keyframe_rgb_ids']
        assert np.array_equal(ids[z['keyframe_local_indices']], keys)
        assert pred.shape == (len(ids), 7) and np.isfinite(pred).all()
        assert np.max(np.abs(np.linalg.norm(pred[:, 3:], axis=1)-1)) < 2e-3
        assert np.all(np.diff(keys) > 0)
        return pred, keys


def plots(ids, gt, models, result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    dest = ROOT/'figures'
    dest.mkdir(exist_ok=True)

    def save(fig, name):
        fig.savefig(dest/f'TASK003_{name}.png', dpi=150, bbox_inches='tight')
        plt.close(fig)

    for name, metric, units in [('TRANSLATION', 'translation_rpe_game_units', 'Relative translation error (game units)'),
                                ('ROTATION', 'rotation_rpe_deg', 'Relative rotation error (degrees)')]:
        fig, axs = plt.subplots(1, 3, figsize=(11, 3.5), layout='constrained', sharey=True)
        for ax, (a, b) in zip(axs, PAIRS):
            rows = [r for r in result if (r['first_rgb'],r['last_rgb'],r['stage']) == (a,b,'r2_exported')]
            bars = ax.bar(['DROID-W', 'DROID-SLAM'], [r[metric] for r in rows], color=['#c35134','#4476a5'])
            ax.bar_label(bars, fmt='%.3g', padding=2)
            ax.set_title(f'RGB {a} to {b}')
            ax.grid(axis='y', alpha=.24)
            ax.margins(y=.15)
        axs[0].set_ylabel(units)
        fig.suptitle('Sealed R2 export (stride 1) | Task 003 internal stages were not observed')
        save(fig, f'STAGE_{name}_AVAILABLE_EVIDENCE')

    for kind, title in [('KEYFRAME', 'R2 exported keyframes (W: final BA anchors)'),
                        ('FILLER', 'R2 exported non-keyframes; internal filler poses unavailable'),
                        ('EXPORT', 'Sealed R2 exported trajectories')]:
        view = (ids>=289)&(ids<=363) if kind!='EXPORT' else np.ones(len(ids),dtype=bool)
        fig, ax = plt.subplots(figsize=(7, 4.9), layout='constrained')
        p = gt[:, :3, 3]
        axes = sorted(np.argsort(np.ptp(p[view],axis=0))[-2:])
        ix,iy = axes
        ax.plot(p[view,ix],p[view,iy],color='#20252a',lw=1.4,label='GT')
        for name,color,point,keys in models:
            mask = np.isin(ids,keys)
            keep = view & (mask if kind=='KEYFRAME' else ~mask if kind=='FILLER' else view)
            if kind=='FILLER':
                ax.scatter(point[keep,ix],point[keep,iy],s=13,color=color,label=name)
            else:
                ax.plot(point[keep,ix],point[keep,iy],'.-' if kind=='KEYFRAME' else '-',
                        ms=4,lw=1.3,color=color,label=name)
            if name=='DROID-W' and kind=='KEYFRAME':
                for j in (311,327):
                    ax.annotate(str(ids[j]),point[j,axes],xytext=(4,6+(j==327)*8),textcoords='offset points',fontsize=8)
        ax.set(xlabel=f'{"XYZ"[ix]} (game units)',ylabel=f'{"XYZ"[iy]} (game units)',title=title)
        ax.set_aspect('equal',adjustable='datalim')
        ax.grid(alpha=.25)
        ax.legend(loc='best')
        save(fig,f'{kind}_TRAJECTORY_COMPARISON')


def main():
    seal = ROOT/'evidence/sealed_r2'
    ident = read(ROOT/'evidence/SEALED_IDENTITY_VERIFICATION.json')
    lock = read(seal/'PROTOCOL_LOCK.json')
    evaluator = R1/'pipeline/offline_evaluation.py'
    assert sha(evaluator)==lock['evaluation']['source_sha256']
    sys.path.insert(0,str(evaluator.parent))
    import offline_evaluation as ev
    ev.selfcheck()
    gt_file = R1/'offline_gt/val_007.npz'
    assert sha(gt_file)=='91fb149c066bb488ac6071602a4b50fe1540243f2db3369a3706f63b705d7008'
    ids = np.arange(1,488)
    with np.load(gt_file,allow_pickle=False) as z:
        assert np.array_equal(z['rgb_ids'],ids) and np.array_equal(z['camera_frame_ids'],ids-1)
        gt = z['c2w']
    assert gt.shape==(487,4,4) and np.isfinite(gt).all()
    # Use the preceding Task 002B admission rule on the unchanged GT matrices.
    gr = gt[:,:3,:3]
    defects = dict(det=float(np.max(np.abs(np.linalg.det(gr)-1))),
                   orthogonality=float(np.max(np.abs(gr.transpose(0,2,1)@gr-np.eye(3)))),
                   last_row=float(np.max(np.abs(gt[:,3]-[0,0,0,1]))))
    assert max(defects.values()) <= 2e-3
    w = seal/'wild_reference'/SEG
    assert sha(w/'trajectory.npz')==read(w/'attempt.json')['trajectory_sha256']
    paths = [w/'trajectory.npz',seal/'results'/SEG/'attempt_001/trajectory.npz']
    results,models,perframe,inputs,official = [],[],[],[],[]
    gp,gr = gt[:,:3,3],gt[:,:3,:3]
    for name,color,path in zip(('DROID-W','DROID-SLAM'),('#c35134','#4476a5'),paths):
        pred,keys = read_track(path,ids)
        if name=='DROID-W':
            assert keys.tolist()==read(w/'keyframes.json')['rgb_ids']
        ep,er = pred[:,:3],Rotation.from_quat(pred[:,3:]).as_matrix()
        fit = ev.align(ep,gp,True)
        r,t,s,_ = fit
        point,rot = s*(ep@r.T)+t,r@er
        e = np.linalg.norm(point-gp,axis=1)
        angles = degrees(gr.transpose(0,2,1)@rot)
        m,rpe,_ = ev.metrics(pred,gt,ids,np.ones(len(ids),dtype=bool))
        assert abs(m['scale_est_to_gt']-s)<1e-12
        models.append((name,color,point,keys))
        inputs.append(dict(model=name,archive_member=path.relative_to(seal).as_posix(),sha256=sha(path),
                           keys=len(keys),fit_R=r.tolist(),fit_t=t.tolist(),**m))
        official.extend(dict(model=name,**row) for row in rpe)
        for i,rgb in enumerate(ids):
            perframe.append(dict(model=name,rgb_id=int(rgb),camera_id=int(rgb-1),keyframe=bool(rgb in keys),
                                 x=float(point[i,0]),y=float(point[i,1]),z=float(point[i,2]),
                                 translation_error=float(e[i]),rotation_error_deg=float(angles[i])))
        for a,b in PAIRS:
            ix = np.asarray((a-1,b-1))
            results.append(dict(model=name,stage='r2_exported',evidence_status='CONFIRMED_HISTORICAL_STRIDE1',
                                endpoints='->'.join('K' if x in keys else 'F' for x in (a,b)),
                                **score(ep[ix],er[ix],gt[ix],fit,a,b)))
        if name=='DROID-W':
            a,b=312,328
            assert np.flatnonzero(keys==b)[0]-np.flatnonzero(keys==a)[0]==1
            ix=np.asarray((a-1,b-1))
            results.append(dict(model=name,stage='r2_final_ba_anchor_reinserted',
                                evidence_status='CONFIRMED_FROM_FROZEN_REINSERTION_PATH',endpoints='K->K',
                                **score(ep[ix],er[ix],gt[ix],fit,a,b)))
    for a,b in PAIRS:
        for stage in STAGES:
            results.append(dict(model='DROID-W',stage=f'task003_{stage}',evidence_status='UNVERIFIED_RUN_NOT_STARTED',
                                endpoints='UNKNOWN_FOR_TASK003',first_rgb=a,last_rgb=b,first_camera=a-1,last_camera=b-1))
    table(ROOT/'TASK003_VAL007_INTERVAL_ANALYSIS.csv',results)
    table(ROOT/'evidence/R2_EXPORT_PER_FRAME.csv',perframe)
    table(ROOT/'evidence/R2_OFFICIAL_OFFSETS.csv',official)
    dump(ROOT/'evidence/TASK003_OFFLINE_RECOMPUTATION.json',dict(gt_file=str(gt_file),gt_sha256=sha(gt_file),
         gt_pairing='487 IDs checked: Camera ID = RGB ID - 1',gt_max_defects=defects,metric_sha256=sha(evaluator),
         sealed_archive_sha256=ident['zip_sha256'],models=inputs,stage_onset='UNVERIFIED',gpu_started=False,
         requested_interval_rows=results[:7]))
    plots(ids,gt,models,results)
    for row in results[:7]:
        print(row['model'],row['stage'],row['first_rgb'],row['last_rgb'],row['endpoints'],
              'EST/GT',round(row['length_est_game_units'],6),round(row['length_gt_game_units'],6),
              'ratio',round(row['length_ratio'],6),'rot RPE',round(row['rotation_rpe_deg'],6))
    print('PASS: 487 GT IDs, two sealed exports, three exact intervals, no local refits')


if __name__=='__main__':
    main()

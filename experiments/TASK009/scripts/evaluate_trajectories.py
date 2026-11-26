"""Offline-only common-GT scoring with one global similarity per run.

VIPER distances are native game units. No metric depth GT is assumed.
"""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def alignment(estimate,truth,scale=True):
    x=np.asarray(estimate,dtype=np.float64);y=np.asarray(truth,dtype=np.float64)
    xm=x.mean(0);ym=y.mean(0);xc=x-xm;yc=y-ym
    u,s,vt=np.linalg.svd(yc.T@xc/len(x))
    fix=np.ones(3);fix[-1]=np.linalg.det(u@vt)
    rotation=(u*fix)@vt
    variance=(xc**2).sum()/len(x)
    if variance<1e-16:raise ValueError('No estimated translation: Sim3 scale unobservable')
    factor=float(s@fix/variance) if scale else 1.
    if factor<=0:raise ValueError('Nonpositive similarity scale')
    translation=ym-factor*rotation@xm
    return factor,rotation,translation


def transform(poses,scale,rotation,translation):
    out=np.array(poses,dtype=np.float64,copy=True)
    out[:,:3,:3]=rotation@out[:,:3,:3]
    out[:,:3,3]=scale*(out[:,:3,3]@rotation.T)+translation
    return out


def rotation_angle(rotation):
    return np.degrees(np.arccos(np.clip((np.trace(rotation,axis1=-2,axis2=-1)-1)/2,-1,1)))


def rmse(x):return float(np.sqrt(np.mean(np.square(x))))


def score(poses,truth,ids):
    estimate=np.asarray(poses,dtype=np.float64);gt=np.asarray(truth,dtype=np.float64)
    if estimate.shape!=gt.shape or not np.isfinite(estimate).all():raise ValueError('Invalid trajectory')
    s,r,t=alignment(estimate[:,:3,3],gt[:,:3,3])
    aligned=transform(estimate,s,r,t)
    s0,r0,t0=alignment(estimate[:,:3,3],gt[:,:3,3],scale=False)
    rigid=transform(estimate,s0,r0,t0)
    errors=np.linalg.norm(aligned[:,:3,3]-gt[:,:3,3],axis=1)
    row={'frames':len(ids),'coverage':1.,'sim3_scale':s,'sim3_ate_game_units':rmse(errors),
         'se3_ate_game_units':rmse(np.linalg.norm(rigid[:,:3,3]-gt[:,:3,3],axis=1)),
         'absolute_rotation_rmse_deg':rmse(rotation_angle(np.swapaxes(gt[:,:3,:3],1,2)@aligned[:,:3,:3])),
         'raw_path_length':float(np.linalg.norm(np.diff(estimate[:,:3,3],axis=0),axis=1).sum()),
         'gt_path_length_game_units':float(np.linalg.norm(np.diff(gt[:,:3,3],axis=0),axis=1).sum()),
         'gt_position_rank':int(np.linalg.matrix_rank(gt[:,:3,3]-gt[:,:3,3].mean(0))),
         'alignment':'One global Sim3 per trajectory; no per-segment refitting'}
    for offset in (1,5,15):
        if len(ids)<=offset:continue
        expected=np.linalg.inv(gt[:-offset])@gt[offset:]
        predicted=np.linalg.inv(aligned[:-offset])@aligned[offset:]
        residual=np.linalg.inv(expected)@predicted
        row[f'rpe_translation_offset{offset}_game_units']=rmse(np.linalg.norm(residual[:,:3,3],axis=1))
        row[f'rpe_rotation_offset{offset}_deg']=rmse(rotation_angle(residual[:,:3,:3]))
    for a,b in ((309,325),(312,328),(301,332)):
        if a not in ids or b not in ids:continue
        i,j=list(ids).index(a),list(ids).index(b)
        actual=estimate[j,:3,3]-estimate[i,:3,3]
        target=gt[j,:3,3]-gt[i,:3,3]
        denominator=np.linalg.norm(target)
        prefix=f'{a}_{b}'
        row[f'{prefix}_raw_displacement_ratio']=float(np.linalg.norm(actual)/denominator) if denominator>1e-12 else None
        row[f'{prefix}_global_scaled_displacement_ratio']=float(s*np.linalg.norm(actual)/denominator) if denominator>1e-12 else None
        aligned_vector=s*r@actual
        row[f'{prefix}_translation_vector_error_game_units']=float(np.linalg.norm(aligned_vector-target))
        denom=np.linalg.norm(aligned_vector)*denominator
        row[f'{prefix}_direction_error_deg']=float(np.degrees(np.arccos(np.clip(aligned_vector@target/denom,-1,1)))) if denom>1e-12 else None
    return row,aligned,errors


def main():
    p=argparse.ArgumentParser();p.add_argument('--priors',type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs='+',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    with np.load(a.priors/'offline_gt.npz',allow_pickle=False) as z:
        ids=z['rgb_ids'];truth=z['c2w']
    rows=[];curves=[];errors=[]
    for folder in a.runs:
        receipt=json.loads((folder/'receipt.json').read_text())
        if receipt['status']!='COMPLETE':raise ValueError(f'Cannot score failed run {folder}')
        with np.load(folder/'trajectory.npz',allow_pickle=False) as z:
            if not np.array_equal(z['rgb_ids'],ids):raise ValueError('RGB/GT identity mismatch')
            result,aligned,error=score(z['c2w'],truth,ids)
        result.update(run=folder.name,gate=receipt['gate'],static_tracks=bool(receipt.get('static_tracks')),
                      total_seconds=receipt['total_seconds'],tracking_seconds=receipt['tracking_seconds'],
                      peak_allocated_bytes=receipt['peak_allocated_bytes'],native_ba_calls=receipt['native_ba_calls'],
                      gate_calls=receipt['gate_calls'],static_calls=receipt.get('static_calls',0),keyframes=receipt['keyframes'])
        rows.append(result);curves.append(aligned)
        errors.append(error)
        np.savez_compressed(a.output/f'{folder.name}_aligned.npz',rgb_ids=ids,c2w=aligned,per_frame_position_error=error)
    (a.output/'results.json').write_text(json.dumps({'unit':'VIPER native game units, not verified meters','results':rows,
        'limits':'32 frames / one seed / one Night window; no generalization or accuracy significance claim'},indent=2))
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (a.output/'metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    axes[0].plot(truth[:,0,3],truth[:,2,3],color='black',label='GT')
    for row,curve,error in zip(rows,curves,errors):
        axes[0].plot(curve[:,0,3],curve[:,2,3],label=row['run'])
        axes[1].plot(ids,error,label=row['run'])
    axes[0].set(xlabel='World X (game units)',ylabel='World Z (game units)',title='One global Sim3 per run')
    axes[0].axis('equal');axes[0].legend(fontsize=6)
    axes[1].set(xlabel='Original RGB ID',ylabel='Position error (game units)',title='Matched 32-frame local exploration')
    axes[1].legend(fontsize=6)
    fig.savefig(a.output/'trajectory_comparison.png',dpi=160)
    plt.close(fig)
    print(json.dumps(rows,indent=2))


if __name__=='__main__':main()

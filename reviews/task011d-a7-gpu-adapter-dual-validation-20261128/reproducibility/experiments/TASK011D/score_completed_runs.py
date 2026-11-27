"""Offline GT scorer for future complete E2E trajectories. No model imports."""
import argparse,csv,importlib.util,json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from common import TASK,csvwrite,dump,sha

def metrics_module():
    path=TASK/'frozen_metrics/offline_eval.py'
    sys.path.insert(0,str(path.parent))
    spec=importlib.util.spec_from_file_location('task011d_frozen_metrics',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def score_trajectory(pred,truth,ids):
    m=metrics_module()
    metrics=dict(gt_path_length=float(np.linalg.norm(np.diff(truth[:,:3,3],axis=0),axis=1).sum()),
        raw_est_path_length=float(np.linalg.norm(np.diff(pred[:,:3],axis=0),axis=1).sum()))
    if metrics['gt_path_length']<=.0001:raise ValueError('Unadmitted GT path')
    metrics['raw_path_ratio']=metrics['raw_est_path_length']/metrics['gt_path_length']
    metrics['raw_path_ratio_abs_error']=abs(metrics['raw_path_ratio']-1)
    p=pred[:,:3];r=Rotation.from_quat(pred[:,3:]).as_matrix()
    try:
        frozen,_=m.pose_metrics(pred,truth,ids,1);metrics.update(frozen)
        q,t,s,_=m.fit_alignment(p,truth[:,:3,3],True);aligned=True
    except ValueError as e:
        metrics.update(ate_sim3_path_pct=None,ate_sim3_rmse=None,ate_se3_rmse=None,alignment_error=str(e));aligned=False
    rows=[]
    for offset in (1,15,60):
        for mode in ('raw','single_global_sim3'):
            if mode!='raw' and not aligned:continue
            pp=s*(p@q.T)+t if mode!='raw' else p;rr=q@r if mode!='raw' else r
            a=m.rpe(pp,rr,truth[:,:3,3],truth[:,:3,:3],ids,offset)
            rows.append(dict(alignment=mode,offset=offset,**a))
            if offset==1:metrics[mode+'_RPE_translation']=a['translation_rmse'];metrics[mode+'_RPE_rotation_deg']=a['rotation_rmse_deg']
    return metrics,rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--output');a=p.parse_args()
    if not a.output:print('VALIDATE_ONLY_NO_TRAJECTORIES_SCORED');return
    plan=list(csv.DictReader((TASK/'configs/EXECUTION_ORDER.csv').open()))
    windows={x['window_id']:x for x in json.loads((TASK/'configs/GPU_INPUTS.json').read_text())['windows']}
    rows=[];rel=[]
    for job in plan:
        receipt=TASK/'execution_ledger'/job['job_key']/'TERMINAL.json'
        if not receipt.exists():continue
        row=json.loads(receipt.read_text());root=TASK/'runs'/str(job['seed'])/job['window']/job['arm']
        if row['status']!='COMPLETE':rows.append(row);continue
        w=windows[job['window']]
        with np.load(TASK/w['raw_GT'],allow_pickle=False) as z:ids=z['rgb_ids'].copy();gt=z['gt_c2w'].copy()
        with np.load(root/'trajectory.npz',allow_pickle=False) as z:
            if not np.array_equal(z['rgb_ids'],ids):raise ValueError('GT/trajectory frame identity mismatch')
            pred=z['c2w_xyzw'].copy()
        if pred.shape!=(64,7) or not np.isfinite(pred).all():raise ValueError('Incomplete or corrupt supposedly complete trajectory')
        child=json.loads((root/'TRACKING_CHILD_COMPLETE.json').read_text())
        row.update(runtime_tracking_child_seconds=child['seconds'],peak_allocated_bytes=child['peak_allocated_bytes'],keyframes=child['keyframes'])
        try:
            metrics,rpe=score_trajectory(pred,gt,ids);row.update(metrics)
            if metrics.get('alignment_error'):row['status']='COMPLETE_ALIGNMENT_DEGENERATE'
            rel.extend([{**job,**r} for r in rpe])
        except ValueError as e:row.update(status='COMPLETE_ALIGNMENT_DEGENERATE',ate_sim3_path_pct=None,alignment_error=str(e))
        row['A0_capture_overhead_included']=job['arm']=='A0'
        if job['arm']=='A0':
            index=TASK/'fixed_state/snapshots'/str(job['seed'])/job['window']/'SNAPSHOT_INDEX.jsonl'
            records=[json.loads(line) for line in index.read_text().splitlines()] if index.exists() else []
            row['snapshot_observer_wall_seconds']=sum(r['observer_wall_seconds'] for r in records)
            row['snapshot_bytes']=sum(r['bytes'] for r in records)
            check=root/'NATIVE_CACHE_EQUIVALENCE.json'
            row['cache_extra_validation_seconds']=json.loads(check.read_text())['extra_validation_seconds'] if check.exists() else None
            row['observer_time_subtraction_not_a_clean_runtime_certificate']=True
        rows.append(row)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    dump(out/'OUTCOMES.json',rows);csvwrite(out/'TRAJECTORY_METRICS.csv',rows);csvwrite(out/'RPE_OFFSETS.csv',rel)

if __name__=='__main__':main()

"""Offline paired evaluation only. Camera poses never enter GPU inference."""
import argparse,csv,importlib.util,json,sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from common import TASK,dump,csvwrite

PIPE=Path('D:/aaa/GameCam-VO/experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/pipeline')
sys.path.insert(0,str(PIPE))
spec=importlib.util.spec_from_file_location('frozen_viper_offline_eval',PIPE/'offline_eval.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)


def relative_metrics(pred,truth,ids,offset,scale_free):
    pos=pred[:,:3];rot=Rotation.from_quat(pred[:,3:]).as_matrix()
    if scale_free:
        q,t,s,_=legacy.fit_alignment(pos,truth[:,:3,3],True)
        pos=s*(pos@q.T)+t;rot=q@rot
    return legacy.rpe(pos,rot,truth[:,:3,3],truth[:,:3,:3],ids,offset)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');a=parser.parse_args()
    out=TASK/'evaluation';out.mkdir(exist_ok=True)
    inputs=json.loads((TASK/'private/VIPER_INPUTS.json').read_text())['windows']
    local=TASK/'gpu_results';rows=[];relative=[];timelines=[]
    for window in inputs:
        with np.load(window['offline_gt'],allow_pickle=False) as z:
            ids=z['rgb_ids'].copy();gt=z['gt_c2w'].copy()
        for arm in range(7):
            label='window_'+window['window_id']+'_A'+str(arm)
            root=local/'raw'/label/'result'
            if not root.exists():continue
            meta=dict(window=window['window_id'],sequence=window['sequence'],environment=window['environment'],arm='A'+str(arm),
                requested_frames=64,units='NATIVE_CAMERA_REFERENCE_UNITS_NOT_NEW_METRE_CERTIFICATE')
            complete=root/'COMPLETE.json'
            if not complete.exists():
                failure=root/'ALGORITHM_FAILURE.json'
                rows.append(dict(**meta,status=json.loads(failure.read_text())['status'] if failure.exists() else 'ENGINEERING_FAILURE',success=False))
                continue
            receipt=json.loads(complete.read_text());child=json.loads((root/'TRACKING_CHILD_COMPLETE.json').read_text())
            with np.load(root/'trajectory.npz',allow_pickle=False) as z:
                if not np.array_equal(z['rgb_ids'],ids):raise RuntimeError('Predicted/GT RGB identities differ')
                pred=z['c2w_xyzw'].copy()
            if pred.shape!=(64,7) or not np.isfinite(pred).all():raise RuntimeError('Invalid saved complete trajectory')
            row=dict(**meta,status='COMPLETE',success=True,runtime_model_run_seconds=receipt['seconds'],
                runtime_tracking_child_seconds=child['seconds'],peak_allocated_bytes=child['peak_allocated_bytes'],
                peak_reserved_bytes=child['peak_reserved_bytes'],keyframes=child['keyframes'])
            try:
                metric,rel=legacy.pose_metrics(pred,gt,ids,1);row.update(metric)
                row['raw_path_ratio']=metric['raw_est_path_length']/metric['gt_path_length'] if metric['gt_path_length']>1e-12 else None
                row['raw_path_ratio_abs_error']=abs(row['raw_path_ratio']-1) if row['raw_path_ratio'] is not None else None
                pos=pred[:,:3];rot=Rotation.from_quat(pred[:,3:]).as_matrix()
                q,t,s,rank=legacy.fit_alignment(pos,gt[:,:3,3],True);aligned=s*(pos@q.T)+t
                for offset in (1,15,60):
                    for mode,scale_free in [('raw',False),('single_global_sim3',True)]:
                        r=relative_metrics(pred,gt,ids,offset,scale_free)
                        relative.append(dict(**meta,alignment=mode,offset=offset,**r))
                        if offset==1:
                            row[mode+'_RPE_translation']=r['translation_rmse'];row[mode+'_RPE_rotation_deg']=r['rotation_rmse_deg']
                for name,part in [('early',slice(0,16)),('middle',slice(24,40)),('late',slice(48,64))]:
                    pp=aligned[part];gg=gt[part,:3,3]
                    length=float(np.linalg.norm(np.diff(gg,axis=0),axis=1).sum())
                    row['single_scale_'+name+'_path_ratio']=float(np.linalg.norm(np.diff(pp,axis=0),axis=1).sum()/length) if length>1e-12 else None
            except ValueError as e:row.update(status='COMPLETE_ALIGNMENT_DEGENERATE',alignment_error=str(e))
            ba_path=root/'native_ba_calls.jsonl';calls=[json.loads(line) for line in ba_path.read_text().splitlines()] if ba_path.exists() else []
            for call in calls:timelines.append({**meta,**call})
            row.update(BA_calls=len(calls),controlled_BA_calls=sum(c['intervention'] for c in calls),
                negative_disparity_events=sum(c.get('negative_before_native_outer_clamp',0)>0 for c in calls),
                U_median_across_BA=float(np.median([c['U_median'] for c in calls])) if calls else None)
            rows.append(row)
    measures=['ate_sim3_rmse','ate_sim3_path_pct','ate_se3_rmse','ate_se3_path_pct','single_global_sim3_RPE_translation','single_global_sim3_RPE_rotation_deg',
              'raw_path_ratio_abs_error','runtime_model_run_seconds','runtime_tracking_child_seconds','peak_allocated_bytes','keyframes']
    summaries=[]
    for env in ['ALL','Day','Sunset','Rain','Snow','Night']:
        for arm in range(7):
            own=[r for r in rows if r['arm']=='A'+str(arm) and (env=='ALL' or r['environment']==env)]
            if not own:continue
            row=dict(environment=env,arm='A'+str(arm),terminal=len(own),planned=20 if env=='ALL' else 4,
                completed=sum(r['success'] for r in own),failure_count=sum(not r['success'] for r in own))
            row['success_rate']=row['completed']/len(own)
            for key in measures:
                v=[r[key] for r in own if r.get(key) is not None]
                row[key+'_n']=len(v);row[key+'_mean']=float(np.mean(v)) if v else None;row[key+'_median']=float(np.median(v)) if v else None
            summaries.append(row)
    pairs=[];by={(r['window'],r['arm']):r for r in rows}
    for base in ('A0','A1'):
        for arm in ('A1','A2','A3','A4','A5','A6'):
            if base==arm:continue
            for key in measures:
                diffs=[]
                for window in inputs:
                    x,y=by.get((window['window_id'],arm)),by.get((window['window_id'],base))
                    if x and y and x.get(key) is not None and y.get(key) is not None:diffs.append(float(x[key]-y[key]))
                if not diffs:continue
                d=np.array(diffs);rng=np.random.default_rng(43)
                interval=np.quantile(d[rng.integers(0,len(d),size=(3000,len(d)))].mean(1),[.025,.975]) if len(d)>=2 else [None,None]
                pairs.append(dict(arm=arm,reference=base,metric=key,paired_sequences=len(d),mean_difference=float(d.mean()),
                    median_difference=float(np.median(d)),lower95=interval[0],upper95=interval[1],
                    lower_is_better=key!='keyframes',wins=int((d<0).sum()) if key!='keyframes' else None,
                    losses=int((d>0).sum()) if key!='keyframes' else None,ties=int((d==0).sum()),
                    incomplete_pairs_not_imputed=True,bootstrap_unit='SOURCE_SEQUENCE_ONE_WINDOW_EACH',exploratory_not_blind=True))
    csvwrite(out/'VIPER_TRAJECTORY_METRICS.csv',rows);csvwrite(out/'VIPER_ENVIRONMENT_METRICS.csv',summaries)
    csvwrite(out/'VIPER_METHOD_COMPARISON.csv',pairs);csvwrite(out/'VIPER_RPE_OFFSETS.csv',relative)
    csvwrite(out/'VIPER_BA_TIMELINE.csv',timelines)
    dump(out/'EVALUATION_STATE.json',dict(terminal=len(rows),planned=140,complete_batch=len(rows)==140,
        valid_trajectories=sum(r['success'] for r in rows),original_metrics_implementation=str(PIPE/'offline_eval.py'),
        new_truth_fitting=False,Sim3_is_not_metric_scale_certificate=True))
    if not a.partial and len(rows)!=140:raise RuntimeError('Full results not yet available; partial tables labelled incomplete')
    print('EVALUATED',len(rows),'/140',flush=True)


if __name__=='__main__':main()

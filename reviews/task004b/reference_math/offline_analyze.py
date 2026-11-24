"""CPU-only analysis of sealed Task004A results. Never imported by model execution."""
import csv,json,sys,pathlib,math,hashlib,itertools,time,os
from datetime import datetime,timezone
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'release/tools'))
import contracts as c
import endpoints as e
import trace_audit as ta
OUT=ROOT/'evaluation'
GT=ROOT.parent/'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/offline_gt/val_007.npz'
CFG=ROOT.parent/'DROID_W_TASK003_VAL007_OBSERVATION_R1/remote/incoming/native_config.yaml'
utc=lambda:datetime.now(timezone.utc).isoformat()
def clean(v):
 if isinstance(v,np.ndarray):return clean(v.tolist())
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,float) and not math.isfinite(v):return None
 if isinstance(v,dict):return {str(k):clean(w) for k,w in v.items()}
 if isinstance(v,(list,tuple)):return [clean(w) for w in v]
 return v
def put(name,doc):
 with (OUT/name).open('x',encoding='utf-8') as f:json.dump(clean(doc),f,indent=2,ensure_ascii=False,allow_nan=False)
def csvout(name,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (OUT/name).open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(clean(v)) if isinstance(v,(dict,list,tuple)) else clean(v) for k,v in r.items()})
def rmse(x):return float(np.sqrt(np.mean(np.sum(x*x,axis=-1))))
def align(x,y,scaled=True):
 xa=x-x.mean(0);ya=y-y.mean(0);u,d,vt=np.linalg.svd(ya.T@xa/len(x))
 variance=np.mean(np.sum(xa*xa,axis=1))
 if variance<1e-14:raise ValueError('DEGENERATE_ESTIMATED_TRAJECTORY')
 signs=np.ones(3);signs[-1]=np.linalg.det(u@vt);r=(u*signs)@vt;s=float(d@signs/variance) if scaled else 1.
 if s<=0 or not math.isfinite(s):raise ValueError('UNUSABLE_ALIGNMENT_SCALE')
 return r,y.mean(0)-s*(r@x.mean(0)),s,int(sum(d>max(1e-14,d[0]*1e-10)))
def rot_angle(r):return np.degrees(np.arccos(np.clip((np.trace(r,axis1=-2,axis2=-1)-1)/2,-1,1)))
def endpoint(arm,source,a,b,poses,gt,align_r,scale):
 r=dict(arm=arm,source=source,rgb_start=a,rgb_end=b,camera_start=a-1,camera_end=b-1,s_ref=c.S_REF)
 if a not in poses or b not in poses:return dict(r,status='ENDPOINT_UNAVAILABLE',reason='REAL_ENDPOINT_NOT_PRESENT_NO_INTERPOLATION')
 p,q=poses[a],poses[b];g,h=gt[a-1],gt[b-1];d=q[:3,3]-p[:3,3];dg=h[:3,3]-g[:3,3];dl=float(np.linalg.norm(d));gl=float(np.linalg.norm(dg))
 ratio=100*c.S_REF*dl/gl if gl>1e-6 else None
 direction=float(np.degrees(np.arccos(np.clip((align_r@d)@dg/(dl*gl),-1,1)))) if dl>1e-12 and gl>1e-6 and align_r is not None else None
 return dict(r,status='VALID' if ratio is not None else 'DEGENERATE_GT',gt_length_game_units=gl,estimate_raw_length=dl,estimate_scaled_length_game_units=c.S_REF*dl,displacement_ratio_pct=ratio,absolute_gap_from_100_pct_points=abs(ratio-100) if ratio is not None else None,translation_rpe_game_units=float(np.linalg.norm(c.S_REF*(p[:3,:3].T@d)-g[:3,:3].T@dg)),rotation_rpe_deg=float(rot_angle((g[:3,:3].T@h[:3,:3]).T@(p[:3,:3].T@q[:3,:3]))),world_direction_error_deg=direction,global_fit_scale_diagnostic=scale)
def effects(rows):
 by={r['arm']:r for r in rows};out=[]
 for metric in ('displacement_ratio_pct','absolute_gap_from_100_pct_points','ate_sim3_game_units','ate_se3_game_units','keyframes'):
  values={a:by[a].get(metric) for a in c.ORDER}
  if any(v is None for v in values.values()):
   out.append(dict(metric=metric,status='UNAVAILABLE_MISSING_ARM_OUTCOME'));continue
  for n in (1,2,3):
   for ix in itertools.combinations(range(3),n):
    contrast=sum(np.prod([2*c.BITS[a][i]-1 for i in ix])*values[a] for a in c.ORDER)/4
    out.append(dict(metric=metric,factor=':'.join('DWU'[i] for i in ix),effect_on_minus_off=float(contrast),regression_coefficient=float(contrast)/2,status='SINGLE_SEQUENCE_SINGLE_SEED_DESCRIPTIVE_CONTRAST',p_value=None,replicate_n=1))
 return out

def tests():
 rng=np.random.default_rng(917);x=rng.normal(size=(20,3));r0=np.array([[0,-1,0],[1,0,0],[0,0,1.]]);y=3*(x@r0.T)+np.array([2,5,-1]);r,t,s,rank=align(x,y)
 checks=[]
 def ck(name,ok):
  assert bool(ok),name;checks.append(dict(name=name,status='PASS'))
 ck('analytic_90deg_rotation_scale3_translation_recovered',np.max(abs(3*(x@r.T)+t-y))<1e-12 and abs(s-3)<1e-12)
 ck('SE3_alignment_does_not_rescale',align(x,y,False)[2]==1)
 ident=np.repeat(np.eye(4)[None],487,axis=0);g=ident.copy();g[:,0,3]=np.arange(487);pred={i:g[i-1] for i in c.IDS}
 old=c.S_REF;c.S_REF=1
 q=endpoint('SYNTHETIC','ANALYTIC',312,328,pred,g,np.eye(3),1);c.S_REF=old
 ck('known_16unit_endpoint_ratio100_rpe0',q['displacement_ratio_pct']==100 and q['translation_rpe_game_units']==0 and q['rotation_rpe_deg']==0)
 ck('missing_real_keyframe_is_not_interpolated',endpoint('SYNTHETIC','NO_DATA',312,328,{},g,None,None)['status']=='ENDPOINT_UNAVAILABLE')
 rows=[]
 for a in c.ORDER:
  d,w,u=[2*n-1 for n in c.BITS[a]];rows.append(dict(arm=a,displacement_ratio_pct=10+3*d+5*w*u))
 eff=effects(rows);ef={z.get('factor'):z.get('effect_on_minus_off') for z in eff if z['metric']=='displacement_ratio_pct'}
 ck('factorial_analytic_main_effect6_interaction10',abs(ef['D']-6)<1e-12 and abs(ef['W:U']-10)<1e-12 and abs(ef['U'])<1e-12)
 ck('unit_xyzw_quaternion_identity',np.array_equal(e.quat_xyzw([0,0,0,1]),np.eye(3)))
 OUT.mkdir(exist_ok=True);put('CPU_ANALYSIS_SELFCHECK.json',dict(synthetic_only=True,checks=checks,passed=len(checks),failed=0,utc=utc()));print('CPU_ANALYSIS_SELFCHECK',len(checks),'PASS')

def run():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU-only environment required'
 assert (ROOT/'evidence/ALL_LOCAL_ARCHIVES_VERIFIED.json').is_file(),'wait for all raw archives'
 gt=e.read_gt(GT);gtsha=c.stat_sha(GT);assert c.stat_sha(CFG)==c.CONFIG_SHA
 OUT.mkdir(exist_ok=True);allmetrics=[];fixed=[];retentions=[];directm=[];stages=[];ba=[];urows=[];grids=[];decisions=[];validated=[];perframe=[];rpes=[];positions={};armrows=[]
 for arm in c.ORDER:
  t0=time.monotonic();folder=ROOT/'results'/arm;attempts=list(folder.glob('attempt_*'));assert len(attempts)==1;at=attempts[0]
  done=c.read_json(folder/'COMPLETE.json');assert done['status']=='COMPLETE';assert c.stat_sha(at/'policy.json')==c.POLICY_SHA[arm]
  inv=c.read_json(at/'OUTPUT_INTEGRITY.json')['files']
  for n,entry in inv.items():assert c.stat_sha(at/n)==entry['sha256'] and (at/n).stat().st_size==entry['bytes'],n
  child=c.read_json(at/'tracking_child_ok.json');receipt=c.read_json(at/'PROCESS_RECEIPT.json');model=c.read_json(at/'model_result.json');launch=c.read_json(at/'LAUNCH_RECEIPT.json')
  assert receipt['exit_code']==0 and model['valid_poses']==487 and model['scaled_rgb_tensor_sha256']==c.TENSOR_SHA
  assert c.read_json(at/'task004_policy_receipt.json')['local_dwu']==list(c.BITS[arm]);assert c.read_json(at/'model_input.json')['pose_inputs']==0
  trace=ta.parse(at/'observer.jsonl',arm=arm,complete=True,expected_pid=child['pid']);poses,keys=e.read_export(at/'trajectory.npz',at/'native/traj/est_poses_full.txt',at/'keyframes.json')
  assert len(poses)==487 and trace.sha256==done['observer_sha256']
  retention,canonical,fillercanonical,local=e.evaluate(arm,at.name,trace,poses,keys,gt);retentions.append(retention)
  p=np.stack([poses[i] for i in c.IDS]);ep=p[:,:3,3];gp=gt[:,:3,3];r,t,scale,rank=align(ep,gp);rs,ts,_,_=align(ep,gp,False);sim=scale*(ep@r.T)+t;se3=ep@rs.T+ts;positions[arm]=sim
  path=float(np.linalg.norm(np.diff(gp,axis=0),axis=1).sum());primary=endpoint(arm,'FIXED_RGB_FINAL_EXPORT',312,328,poses,gt,r,scale)
  assert abs(primary['estimate_raw_length']-canonical[0]['estimate_raw_length'])<1e-12
  summary=dict(arm=arm,D=c.BITS[arm][0],W=c.BITS[arm][1],U=c.BITS[arm][2],status='COMPLETE',input_frames=487,valid_poses=487,keyframes=len(keys),model_elapsed_s=receipt['elapsed_s'],peak_gpu_used_mib=receipt['peak_gpu_used_mib'],ba_calls=len(trace.calls),ate_sim3_game_units=rmse(sim-gp),ate_se3_game_units=rmse(se3-gp),global_fit_scale=scale,alignment_rank=rank,gt_path_game_units=path,ate_sim3_path_pct=100*rmse(sim-gp)/path,displacement_ratio_pct=primary['displacement_ratio_pct'],absolute_gap_from_100_pct_points=primary['absolute_gap_from_100_pct_points'],rgb312_retained_kf=312 in keys,rgb328_retained_kf=328 in keys,attempt_id=at.name)
  for delta in (1,15,60,150):
   i=np.arange(487-delta);j=i+delta;predrel=np.einsum('nij,nj->ni',p[i,:3,:3].transpose(0,2,1),ep[j]-ep[i]);gtrel=np.einsum('nij,nj->ni',gt[i,:3,:3].transpose(0,2,1),gp[j]-gp[i]);pe=np.einsum('nij,njk->nik',p[i,:3,:3].transpose(0,2,1),p[j,:3,:3]);ge=np.einsum('nij,njk->nik',gt[i,:3,:3].transpose(0,2,1),gt[j,:3,:3]);angles=rot_angle(ge.transpose(0,2,1)@pe)
   rr=dict(arm=arm,delta_rgb_frames=delta,pairs=len(i),translation_rpe_raw_game_units=rmse(predrel-gtrel),translation_rpe_sref_game_units=rmse(c.S_REF*predrel-gtrel),translation_rpe_sim3_game_units=rmse(scale*predrel-gtrel),rotation_rpe_rmse_deg=float(np.sqrt(np.mean(angles**2))))
   rpes.append(rr)
   if delta==1:summary.update(rpe1_sim3_game_units=rr['translation_rpe_sim3_game_units'],rpe1_rotation_deg=rr['rotation_rpe_rmse_deg'])
  allmetrics.append(summary)
  finalrows=ta.pose_index(trace.boundaries['final_phase_2_done'],'KEYFRAME_CACHE')
  finaldirect=e.observed(finalrows,keys)
  for a,b in ((312,328),(309,325),(301,353)):
   fixed.append(endpoint(arm,'FIXED_RGB_FINAL_EXPORT',a,b,poses,gt,r,scale));directm.append(endpoint(arm,'DIRECT_RETAINED_KEYFRAME_POST_FINAL_BA',a,b,finaldirect,gt,r,scale))
   for name,bound in trace.boundaries.items():
    by=e.observed(ta.pose_index(bound,'KEYFRAME_CACHE'),[i for i in (a,b) if i in [v['rgb_id'] for v in bound['rows']]])
    stages.append(dict(stage=name,**endpoint(arm,'KEYFRAME_STAGE_BOUNDARY',a,b,by,gt,r,scale)))
  for call in trace.calls:ba.append(dict(arm=arm,**call))
  for (pid,frame),decision in trace.decisions.items():decisions.append(dict(arm=arm,pid=pid,rgb_id=frame,decision=decision,retained_in_final_keyframe_cache=frame in keys))
  for line in (at/'observer.jsonl').open(encoding='utf-8'):
   row=json.loads(line)
   if row['type']=='ba_before':
    rec={k:row[k] for k in ('event','ba_id','stage','trigger_rgb_id','source_uba','target_uba','update_u','metric_depth_branch_active','metric_depth_positive_support','cached_prior_positive_support','gamma_depth','t0','t1')};rec['arm']=arm
    for field in ('uncertainty','eta_sample'):
     for n,v in row.get(field,{}).items():
      if isinstance(v,(int,float)):rec[field+'_'+n]=v
    for sub,stats in row.get('geometry',{}).items():
     if isinstance(stats,dict):
      for n,v in stats.items():
       if isinstance(v,(int,float)):rec['geometry_'+sub+'_'+n]=v
    rec['geometry_scope']='RECORDED_CPU_EDGE_PIXEL_SUBSAMPLE_NOT_FULL_NATIVE';urows.append(rec)
   if row['type'] in ('ba_after_native','ba_after_clamp'):
    grids.append(dict(arm=arm,event=row['event'],ba_id=row['ba_id'],stage=row['stage'],type=row['type'],trigger_rgb_id=row['trigger_rgb_id'],**row['full_disparity_grid']))
  for idx in range(487):perframe.append(dict(arm=arm,rgb_id=idx+1,camera_id=idx,is_keyframe=idx+1 in keys,origin='REINSERTED_KEYFRAME' if idx+1 in keys else 'FILLER_RESULT',error_sim3_game_units=float(np.linalg.norm(sim[idx]-gp[idx])),error_se3_game_units=float(np.linalg.norm(se3[idx]-gp[idx])),**{f'raw_{a}':ep[idx,k] for k,a in enumerate('xyz')},**{f'aligned_{a}':sim[idx,k] for k,a in enumerate('xyz')}))
  validated.append(dict(arm=arm,trace=trace.summary(),trajectory_sha256=c.stat_sha(at/'trajectory.npz'),observer_sha256=trace.sha256,elapsed_cpu_s=time.monotonic()-t0,remote_model_validation='PASS',local_receipt_trace_export_validation='PASS'))
  print(json.dumps(dict(event='ARM_OFFLINE_EVALUATED',**summary)),flush=True)
 csvout('TASK004A_ATE_RPE_COMPARISON.csv',allmetrics);csvout('TASK004A_RPE_BY_INTERVAL.csv',rpes);csvout('TASK004A_ENDPOINT_COMPARISON.csv',fixed);csvout('TASK004_FIXED_RGB_ENDPOINT_METRICS.csv',fixed);csvout('TASK004_DIRECT_KEYFRAME_ENDPOINT_METRICS.csv',directm);csvout('TASK004_ENDPOINT_RETENTION.csv',retentions);csvout('TASK004A_KEYFRAME_SELECTION_COMPARISON.csv',decisions);csvout('TASK004A_LOCAL_BA_TIMELINE_COMPARISON.csv',ba);csvout('TASK004A_UNCERTAINTY_ANALYSIS.csv',urows);csvout('TASK004A_DISPARITY_DIAGNOSTICS.csv',grids);csvout('TASK004A_FINAL_BA_STAGE_COMPARISON.csv',stages);csvout('TASK004A_PER_FRAME_TRAJECTORY_ERRORS.csv',perframe);csvout('TASK004A_FACTORIAL_RESULTS.csv',effects(allmetrics));put('OFFLINE_ANALYSIS_VALIDATION.json',dict(utc=utc(),ground_truth_path=str(GT),ground_truth_sha256=gtsha,s_ref=c.S_REF,arms=validated,cpu_only=True,torch_imported='torch' in sys.modules));assert c.stat_sha(GT)==gtsha
 put('RESULTS_SUMMARY.json',dict(arms=allmetrics,source_commit=c.COMMIT,seed=43,replicates_per_arm=1,s_ref=c.S_REF,all_poses=3896,causal_scope='OBSERVED_TOTAL_PIPELINE_INTERVENTION_ON_ONE_SEQUENCE_NO_GENERALIZATION_OR_SIGNIFICANCE_CLAIM'))
 print('CPU_OFFLINE_ANALYSIS_COMPLETE',flush=True)

if __name__=='__main__':
 if '--selfcheck' in sys.argv:tests()
 else:run()
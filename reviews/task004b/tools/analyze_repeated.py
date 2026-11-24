"""Task004B CPU evaluation; reuses Task004A math/trace contracts, never starts a model."""
import os,sys,pathlib,json,csv,math,time,hashlib,importlib.util,collections,itertools,statistics
from datetime import datetime,timezone
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
AROOT=ROOT.parent/'DROID_W_TASK004A_GPU_SCREENING_20261123T082038066Z'
sys.path.insert(0,str(AROOT/'release/tools'))
import contracts as c, endpoints as e, trace_audit as ta
spec=importlib.util.spec_from_file_location('validated_A_math',AROOT/'tools/offline_analyze.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
GT=ROOT.parent/'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/offline_gt/val_007.npz'
OUT=ROOT/'evaluation';OUT.mkdir(exist_ok=True)
T975_DF2=math.sqrt(2*.95**2/(1-.95**2))
ARMS=tuple(sorted(c.BITS,key=lambda a:int(a[1:])))
UTC=lambda:datetime.now(timezone.utc).isoformat()
def sha(p):return c.stat_sha(p)
def put(p,d):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(m.clean(d),f,ensure_ascii=False,indent=2,allow_nan=False)
def csvout(p,rows):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with p.open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(m.clean(v)) if isinstance(v,(dict,list,tuple)) else m.clean(v) for k,v in r.items()})
def numeric_summary(values):
 x=np.asarray([v for v in values if v is not None and math.isfinite(v)],float);n=len(x)
 return dict(n=n,mean=float(x.mean()) if n else None,median=float(np.median(x)) if n else None,sd=float(x.std(ddof=1)) if n>1 else None,minimum=float(x.min()) if n else None,maximum=float(x.max()) if n else None,ci95_low=float(x.mean()-T975_DF2*x.std(ddof=1)/math.sqrt(3)) if n==3 else None,ci95_high=float(x.mean()+T975_DF2*x.std(ddof=1)/math.sqrt(3)) if n==3 else None,ci_method='STUDENT_T_DF2_ACROSS_THREE_SEED_BLOCKS_APPROXIMATE' if n==3 else 'NOT_THREE_BLOCKS')
def describe(vals):
 x=np.asarray([v for v in vals if v is not None and math.isfinite(v)],float)
 return dict(n=len(x),mean=float(x.mean()) if len(x) else None,median=float(np.median(x)) if len(x) else None,p05=float(np.quantile(x,.05)) if len(x) else None,p90=float(np.quantile(x,.9)) if len(x) else None,p95=float(np.quantile(x,.95)) if len(x) else None,minimum=float(x.min()) if len(x) else None,maximum=float(x.max()) if len(x) else None)
def flatten(d,prefix=''):
 return {(prefix+'_'+k if prefix else k):v for k,v in d.items()}
def analyze(seed,arm):
 source=AROOT if seed==43 else ROOT
 folder=source/'results'/('seed'+str(seed) if seed!=43 else '')/arm
 dest=OUT/'runs'/('seed'+str(seed)+'_'+arm)
 if (dest/'COMPLETE.json').exists():return json.loads((dest/'SUMMARY.json').read_text(encoding='utf-8'))
 if seed!=43 and not (ROOT/'evidence'/('LOCAL_ARCHIVE_seed'+str(seed)+'_'+arm+'.json')).is_file():return None
 if not (folder/'COMPLETE.json').is_file():return None
 assert not dest.exists(),'partial CPU analysis exists; inspect instead of overwriting'
 dest.mkdir(parents=True)
 atts=list(folder.glob('attempt_*'));assert len(atts)==1;at=atts[0]
 done=c.read_json(folder/'COMPLETE.json');assert done['status']=='COMPLETE'
 assert sha(at/'policy.json')==c.POLICY_SHA[arm]
 inv=c.read_json(at/'OUTPUT_INTEGRITY.json')['files']
 proof=None
 if seed!=43:
  proof=c.read_json(ROOT/'evidence'/('LOCAL_ARCHIVE_seed'+str(seed)+'_'+arm+'.json'))
  assert proof['crc']=='PASS' and proof['internal_sha256_matches']==len(proof['files'])
 for name,entry in inv.items():
  p=at/name
  if p.is_file():assert sha(p)==entry['sha256'] and p.stat().st_size==entry['bytes'],name
  else:assert proof and name in proof['archive_only_members'] and proof['files'][name]==entry,name
 receipt=c.read_json(at/'PROCESS_RECEIPT.json');child=c.read_json(at/'tracking_child_ok.json');model=c.read_json(at/'model_result.json')
 assert receipt['exit_code']==0 and model['valid_poses']==487 and model['scaled_rgb_tensor_sha256']==c.TENSOR_SHA
 assert c.read_json(at/'task004_policy_receipt.json')['local_dwu']==list(c.BITS[arm])
 assert c.read_json(at/'model_input.json')['pose_inputs']==0
 seed_receipts={}
 if seed!=43:
  for scope,file in [('main','seed_receipt_main.json'),('tracking_spawn_entry','seed_receipt_tracking_spawn_entry.json')]:
   sr=c.read_json(at/file);assert sr['configured_seed']==seed and sr['extra_rng_draws']==0;seed_receipts[scope]=sr
  assert seed_receipts['main']['torch_initial_seed']==seed
 trace=ta.parse(at/'observer.jsonl',arm=arm,complete=True,expected_pid=child['pid'])
 assert trace.sha256==done['observer_sha256']
 poses,keys=e.read_export(at/'trajectory.npz',at/'native/traj/est_poses_full.txt',at/'keyframes.json')
 assert len(poses)==487 and sha(GT)==c.GT_SHA
 gt=e.read_gt(GT);ret,canonical,filler_diag,localdiag=e.evaluate(arm,at.name,trace,poses,keys,gt)
 p=np.stack([poses[i] for i in c.IDS]);ep=p[:,:3,3];gp=gt[:,:3,3];r,t,scale,rank=m.align(ep,gp);rs,ts,_,_=m.align(ep,gp,False)
 sim=scale*(ep@r.T)+t;se3=ep@rs.T+ts
 primary=m.endpoint(arm,'FIXED_RGB_FINAL_EXPORT',312,328,poses,gt,r,scale)
 base=dict(seed=seed,arm=arm,D=c.BITS[arm][0],W=c.BITS[arm][1],U=c.BITS[arm][2],attempt_id=at.name)
 summary=dict(base,status='COMPLETE',input_frames=487,valid_poses=487,keyframes=len(keys),model_elapsed_s=receipt['elapsed_s'],peak_gpu_used_mib=receipt['peak_gpu_used_mib'],peak_shm_used_bytes=receipt.get('peak_shm_used_bytes'),ba_calls=len(trace.calls),ate_sim3_game_units=m.rmse(sim-gp),ate_se3_game_units=m.rmse(se3-gp),global_fit_scale=scale,alignment_rank=rank,gt_path_game_units=float(np.linalg.norm(np.diff(gp,axis=0),axis=1).sum()),displacement_ratio_pct=primary['displacement_ratio_pct'],absolute_gap_from_100_pct_points=primary['absolute_gap_from_100_pct_points'],endpoint_translation_rpe_game_units=primary['translation_rpe_game_units'],endpoint_rotation_rpe_deg=primary['rotation_rpe_deg'],endpoint_direction_error_deg=primary['world_direction_error_deg'],rgb312_retained_kf=312 in keys,rgb328_retained_kf=328 in keys,retained_kf_rgb_ids=keys,estimand='TOTAL_FRONTEND_EFFECT')
 fixed=[];direct=[];stage=[];rpes=[];timeline=[];decisions=[];scores=[];unc=[];grids=[];firstlast=[]
 directposes=e.observed(ta.pose_index(trace.boundaries['final_phase_2_done'],'KEYFRAME_CACHE'),keys)
 for a,b in ((312,328),(309,325),(301,353)):
  fixed.append(dict(base,**{k:v for k,v in m.endpoint(arm,'FIXED_RGB_FINAL_EXPORT',a,b,poses,gt,r,scale).items() if k!='arm'}))
  direct.append(dict(base,**{k:v for k,v in m.endpoint(arm,'DIRECT_RETAINED_KEYFRAME_POST_FINAL_BA',a,b,directposes,gt,r,scale).items() if k!='arm'}))
  for name,bound in trace.boundaries.items():
   ids=[q['rgb_id'] for q in bound['rows']];by=e.observed(ta.pose_index(bound,'KEYFRAME_CACHE'),[i for i in (a,b) if i in ids])
   stage.append(dict(base,stage=name,**{k:v for k,v in m.endpoint(arm,'KEYFRAME_STAGE_BOUNDARY',a,b,by,gt,r,scale).items() if k!='arm'}))
 for delta in (1,15,60,150):
  i=np.arange(487-delta);j=i+delta;predrel=np.einsum('nij,nj->ni',p[i,:3,:3].transpose(0,2,1),ep[j]-ep[i]);gtrel=np.einsum('nij,nj->ni',gt[i,:3,:3].transpose(0,2,1),gp[j]-gp[i])
  pr=p[i,:3,:3].transpose(0,2,1)@p[j,:3,:3];gr=gt[i,:3,:3].transpose(0,2,1)@gt[j,:3,:3];angles=m.rot_angle(gr.transpose(0,2,1)@pr)
  rr=dict(base,delta_rgb_frames=delta,pairs=len(i),translation_rpe_raw_game_units=m.rmse(predrel-gtrel),translation_rpe_sref_game_units=m.rmse(c.S_REF*predrel-gtrel),translation_rpe_sim3_game_units=m.rmse(scale*predrel-gtrel),rotation_rpe_rmse_deg=float(np.sqrt(np.mean(angles**2))))
  rpes.append(rr)
  for name in ('translation_rpe_raw_game_units','translation_rpe_sref_game_units','translation_rpe_sim3_game_units','rotation_rpe_rmse_deg'):summary['offset'+str(delta)+'_'+name]=rr[name]
 for call in trace.calls:
  timeline.append(dict(base,**call))
  if call['stage'] in c.LOCAL_STAGES:
   # Target pair poses come only from genuine observed keyframes; no interpolation.
   pass
 for call,phases in trace.common:
  rec=dict(base,ba_id=call['ba_id'],stage=call['stage'],trigger_rgb_id=call['trigger_rgb_id'],candidate_decision=call['candidate_decision'],both_in_pose_window=call['both_in_pose_window'],both_observed_in_edges=call['both_observed_in_edges'],direct_edge=call['direct_edge'])
  vals={}
  for name,rows in phases.items():
   val=m.endpoint(arm,name,312,328,e.observed(rows,(312,328)),gt,r,scale);vals[name]=val
   for k in ('displacement_ratio_pct','estimate_raw_length','translation_rpe_game_units','world_direction_error_deg'):rec[name+'_'+k]=val.get(k)
  rec['native_minus_before_ratio_pct_points']=vals['native'].get('displacement_ratio_pct',0)-vals['before'].get('displacement_ratio_pct',0)
  firstlast.append(rec)
 counts=collections.Counter(trace.decisions.values());calls=collections.Counter(x['stage'] for x in trace.calls)
 summary.update(motion_filter_rejected=counts['MOTION_FILTER_REJECTED'],local_ba_rejected=counts['LOCAL_BA_REJECTED'],retained_decisions=counts['RETAINED']+counts['RETAINED_WARMUP_PENDING'],predecision_ba_calls=calls['frontend_local_predecision'],retained_ba_calls=calls['frontend_local_retained'],local_ba_rejection_rate=counts['LOCAL_BA_REJECTED']/max(1,487-counts['MOTION_FILTER_REJECTED']))
 for (pid,i),outcome in trace.decisions.items():decisions.append(dict(base,pid=pid,rgb_id=i,decision=outcome,retained_in_final_keyframe_cache=i in keys))
 with (at/'observer.jsonl').open(encoding='utf-8') as f:
  for line in f:
   row=json.loads(line);kind=row['type']
   if kind in ('motion_filter_score','frontend_distance'):
    rec={k:row.get(k) for k in ('event','stage','trigger_rgb_id','score','threshold','forced','native_decision_proxy')};scores.append(dict(base,type=kind,**rec))
   if kind=='ba_before':
    rec={k:row[k] for k in ('event','ba_id','stage','trigger_rgb_id','source_uba','target_uba','update_u','metric_depth_branch_active','metric_depth_positive_support','cached_prior_positive_support','gamma_depth','t0','t1')}
    for field in ('uncertainty','eta_sample'):
     for k,v in row.get(field,{}).items():
      if isinstance(v,(int,float)):rec[field+'_'+k]=v
    for field,v in row.get('geometry',{}).items():
     if isinstance(v,dict):
      for k,x in v.items():
       if isinstance(x,(int,float)):rec['geometry_'+field+'_'+k]=x
    unc.append(dict(base,geometry_scope='CPU_EDGE_PIXEL_SUBSAMPLE_NOT_FULL_NATIVE',**rec))
   if kind in ('ba_after_native','ba_after_clamp'):grids.append(dict(base,event=row['event'],ba_id=row['ba_id'],stage=row['stage'],type=kind,trigger_rgb_id=row['trigger_rgb_id'],**row['full_disparity_grid']))
 for kind,label in [('motion_filter_score','motion_filter_proxy'),('frontend_distance','local_motion_distance')]:summary.update(flatten(describe([q['score'] for q in scores if q['type']==kind]),label))
 ul=[q for q in unc if q['stage'] in c.LOCAL_STAGES]
 for k,label in [('uncertainty_median','U_event_medians'),('uncertainty_p90','U_event_p90s'),('uncertainty_p95','U_event_p95s'),('geometry_effective_weight_mean','effective_weight_event_means'),('geometry_source_uncertainty_multiplier_mean','source_U_multiplier_event_means')]:summary.update(flatten(describe([q.get(k) for q in ul]),label))
 for phase in ('ba_after_native','ba_after_clamp'):
  gs=[q for q in grids if q['type']==phase];summary[phase+'_negative_pixel_events']=sum(q['negative'] for q in gs);summary[phase+'_max_negative_in_call']=max(q['negative'] for q in gs);summary[phase+'_floor_pixel_events']=sum(q['float32_floor_count'] for q in gs)
 summary['local_ba_native_negative_pixel_events']=sum(q['negative'] for q in grids if q['type']=='ba_after_native' and q['stage'] in c.LOCAL_STAGES)
 summary['clamp_calls_changing_grid']=sum(q['native_grid']!=q['clamp_grid'] for q in trace.calls)
 perframe=[dict(base,rgb_id=i+1,camera_id=i,is_keyframe=i+1 in keys,origin='REINSERTED_KEYFRAME' if i+1 in keys else 'FILLER_RESULT',error_sim3_game_units=float(np.linalg.norm(sim[i]-gp[i])),error_se3_game_units=float(np.linalg.norm(se3[i]-gp[i])),**{f'raw_{a}':ep[i,k] for k,a in enumerate('xyz')},**{f'aligned_{a}':sim[i,k] for k,a in enumerate('xyz')}) for i in range(487)]
 for name,rows in [('FIXED_ENDPOINTS',fixed),('DIRECT_KEYFRAME_ENDPOINTS',direct),('STAGE_ENDPOINTS',stage),('RPE',rpes),('BA_TIMELINE',timeline),('KEYFRAME_DECISIONS',decisions),('MOTION_DISTANCE',scores),('UNCERTAINTY_EVENTS',unc),('DISPARITY_EVENTS',grids),('LOCAL_PAIR_UPDATES',firstlast),('PER_FRAME',perframe)]:csvout(dest/(name+'.csv'),rows)
 put(dest/'RETENTION.json',dict(seed=seed,**ret));put(dest/'SUMMARY.json',summary)
 put(dest/'VALIDATION.json',dict(utc=UTC(),trace=trace.summary(),gt_sha256=sha(GT),trajectory_sha256=sha(at/'trajectory.npz'),policy_sha256=sha(at/'policy.json'),source_attempt=str(at),seed_receipts=seed_receipts,original_math_module_sha256=sha(AROOT/'tools/offline_analyze.py'),archive_proof=str(ROOT/'evidence'/('LOCAL_ARCHIVE_seed'+str(seed)+'_'+arm+'.json')) if proof else 'TASK004A_PREVIOUS_COMPLETE_VALIDATED_ARCHIVE',torch_imported='torch' in sys.modules))
 put(dest/'COMPLETE.json',dict(seed=seed,arm=arm,status='CPU_ANALYSIS_COMPLETE',utc=UTC()))
 print(json.dumps(dict(event='OFFLINE_RUN_EVALUATED',seed=seed,arm=arm,ate_sim3=summary['ate_sim3_game_units'],endpoint_ratio_pct=summary['displacement_ratio_pct'],keyframes=len(keys))),flush=True)
 return summary

def selfcheck():
 checks=[]
 def ck(n,ok):assert bool(ok),n;checks.append(dict(name=n,status='PASS'))
 ck('df2_student_t_975_analytic',abs(T975_DF2-4.302652729749)<1e-10)
 q=numeric_summary([1,2,3]);ck('sample_mean_sd_df2_ci',q['mean']==2 and q['sd']==1 and abs(q['ci95_high']-(2+T975_DF2/math.sqrt(3)))<1e-12)
 ck('CI_absent_for_two_blocks',numeric_summary([1,2])['ci95_low'] is None)
 rows=[]
 for a in c.ORDER:
  d,w,u=[2*x-1 for x in c.BITS[a]];rows.append(dict(arm=a,displacement_ratio_pct=17+3*d+5*d*u+7*d*w*u))
 f={x['factor']:x['effect_on_minus_off'] for x in m.effects(rows) if x['metric']=='displacement_ratio_pct'}
 ck('factorial_main_and_threeway',abs(f['D']-6)<1e-10 and abs(f['D:U']-10)<1e-10 and abs(f['D:W:U']-14)<1e-10)
 ck('null_missing_ci_not_zero',numeric_summary([None])['mean'] is None)
 old=m.OUT;m.OUT=OUT/'legacy_math_selfcheck';m.OUT.mkdir(exist_ok=False);m.tests();m.OUT=old
 put(OUT/'B_ANALYSIS_SELFCHECK.json',dict(utc=UTC(),checks=checks,passed=len(checks),failed=0,legacy_checks=6,torch_imported='torch' in sys.modules))
 print('B_ANALYSIS_SELFCHECK',len(checks),'PASS',flush=True)

def main():
 assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
 if '--selfcheck' in sys.argv:selfcheck();return
 for seed in (43,44,45):
  for arm in ARMS:analyze(seed,arm)
 print('AVAILABLE_OFFLINE_ANALYSES_COMPLETE',flush=True)
if __name__=='__main__':main()

"""Additional offline conditional-effect, prefix and source-provenance analysis."""
import os,sys,json,csv,pathlib,collections,hashlib,subprocess
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
import numpy as np
from task005a_analysis import ROOT,OLD,RECEIVER,ARMS,GT,OUT,stage,align,geometryposes,sha,dump,writecsv,verify_seal

def readcsv(name):
 with (OUT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
 scores=readcsv('TASK005A_MATCHED_SUPPORT_STAGE_SCORES.csv');effects=[]
 for st,support in [('FRONTEND','COMMON_ALL_FOUR_KF'),('POST_FINAL_BA','COMMON_ALL_FOUR_KF'),('EXPORTED','COMMON_ALL_FOUR_KF'),('EXPORTED','ALL_487')]:
  by={r['arm']:float(r['ate_sim3']) for r in scores if r['stage']==st and r['support']==support}
  s1=by['B1']-by['B2'];s0=by['B3']-by['B4']
  effects.append(dict(stage=st,support=support,D_on_minus_off_S1=s1,D_on_minus_off_S0=s0,difference_of_D_effects=s1-s0,estimation='DESCRIPTIVE_SINGLE_SEQUENCE_SINGLE_SEED_NOT_POPULATION_EFFECT'))
 writecsv('TASK005A_CONDITIONAL_D_EFFECTS.csv',effects)
 gt=np.load(GT,allow_pickle=False)['c2w'];pred={};struct={};trace={}
 for arm in ARMS:
  latest={};before={};structures=[]
  with (stage(arm)/'observer.jsonl').open(encoding='utf-8') as inp:
   for line in inp:
    obj=json.loads(line);typ=obj['type']
    if typ=='ba_before':
     if obj['stage'] in ('frontend_local_predecision','frontend_local_retained'):
      structures.append(dict(ba_id=obj['ba_id'],rgb=obj['trigger_rgb_id'],stage=obj['stage'],t0=obj['t0'],t1=obj['t1'],iters=obj['native_iterations_requested'],edges=obj['edge_slots'],slots=[(r['slot'],r['rgb_id'],r['pool']) for r in obj['rows']]))
     before[obj['ba_id']]=obj
    elif typ=='ba_after_native':
     pre=before.pop(obj['ba_id'])
     if pre['stage']=='frontend_local_predecision':latest[pre['trigger_rgb_id']]=obj['rows']
  assert not before
  pred[arm]=latest;struct[arm]=structures
  traced=[]
  with (stage(arm)/'native_trace.jsonl').open(encoding='utf-8') as inp:
   for line in inp:
    obj=json.loads(line)
    if obj['kind'] in ('ba.continuous.before','ba.continuous.after'):traced.append(obj)
  trace[arm]=traced
  print('STREAMED',arm,'prefix_candidates',len(latest),'local_calls',len(structures),flush=True)
 controls=[]
 for schedule,on,off in [('S1','B1','B2'),('S0','B3','B4')]:
  left,right=struct[on],struct[off];assert left==right
  tleft,tright=trace[on],trace[off];assert len(tleft)==len(tright)
  counts=collections.defaultdict(collections.Counter);first_diff={}
  for l,r in zip(tleft,tright):
   assert (l['kind'],l['call'],l['phase'],l['rgb'])==(r['kind'],r['call'],r['phase'],r['rgb'])
   for key,value in l['tensor_sha256'].items():
    eq=value==r['tensor_sha256'][key];counts[l['kind']][key+'_equal']+=int(eq);counts[l['kind']][key+'_total']+=1
    if not eq and (l['kind'],key) not in first_diff:first_diff[(l['kind'],key)]={'call':l['call'],'rgb':l['rgb'],'phase':l['phase']}
  controls.append({'schedule':schedule,'arms':[on,off],'local_discrete_structure_exact_match':True,'local_calls':len(left),'trace_records':len(tleft),'continuous_hash_equality_counts':dict(counts),'first_continuous_divergence':{':'.join(k):v for k,v in first_diff.items()},'continuous_state_NOT_frozen':True})
 hashes=json.loads((OUT/'FIRST_BA_TENSOR_HASHES.json').read_text());initials=[x['first_BA_before']['tensor_sha256'] for x in hashes];assert all(x==initials[0] for x in initials)
 dump(OUT/'TASK005A_SAME_SCHEDULE_CONTROL_CHECKS.json',{'checks':controls,'all_four_first_BA_six_tensor_hashes_equal':True,'first_BA_rgb':19,'first_BA_native_call':25,'hash_keys':list(initials[0]),'not_full_residual_or_Hessian_checkpoint':True})
 prefix=[];peffects=[]
 rgbs=sorted(set.intersection(*(set(pred[a]) for a in ARMS)))
 for rgb in rgbs:
  poses={a:geometryposes(pred[a][rgb]) for a in ARMS};common=sorted(set.intersection(*(set(poses[a]) for a in ARMS)))
  if len(common)<10:continue
  res={}
  for a in ARMS:
   x=np.array([poses[a][i][:3,3] for i in common]);y=gt[np.array(common)-1,:3,3]
   rot,t,s=align(x,y);err=np.linalg.norm(s*x@rot.T+t-y,axis=-1);res[a]=float(np.sqrt(np.mean(err**2)))
   prefix.append(dict(arm=a,D=ARMS[a][0],schedule=ARMS[a][1],trigger_rgb=rgb,n_common=len(common),common_ids=';'.join(map(str,common)),ate_sim3=res[a],fit_scale=s,boundary='AFTER_LAST_PREDECISION_BA_BEFORE_FORCED_DROP',alignment='ONE_FIT_PER_CURRENT_COMMON_PREFIX_NOT_FINAL_487_FIT'))
  peffects.append(dict(trigger_rgb=rgb,n_common=len(common),D_on_minus_off_S1=res['B1']-res['B2'],D_on_minus_off_S0=res['B3']-res['B4'],reversal_observed=(res['B1']>res['B2'] and res['B3']<res['B4'])))
 writecsv('TASK005A_PREFIX_COMMON_KF.csv',prefix);writecsv('TASK005A_PREFIX_CONDITIONAL_EFFECTS.csv',peffects)
 decisions=readcsv('TASK005A_FORCED_VS_NATURAL_DECISIONS.csv');mismatch=[]
 for a in ARMS:
  rs=[r for r in decisions if r['arm']==a];dif=[r for r in rs if r['disagrees']=='True']
  mismatch.append(dict(arm=a,schedule=ARMS[a][1],D=ARMS[a][0],decisions=len(rs),mismatches=len(dif),would_keep_but_forced_drop=sum(r['natural_drop']=='False' and r['scheduled_drop']=='True' for r in dif),would_drop_but_forced_keep=sum(r['natural_drop']=='True' and r['scheduled_drop']=='False' for r in dif),first_mismatch_rgb=min(int(r['rgb']) for r in dif) if dif else None,interpretation='CURRENT_STATE_DECISION_VS_FORCED_SCHEDULE_NOT_FREE_RUNNING_COUNTERFACTUAL'))
 writecsv('TASK005A_MISMATCH_DIRECTION.csv',mismatch)
 common=json.loads((OUT/'COMMON_SUPPORT.json').read_text())['common_rgb_ids'];depth=[]
 for a in ARMS:
  with np.load(stage(a)/'native/video.npz',allow_pickle=False) as z:
   ids=np.rint(z['timestamps']).astype(int)+1;prior=z['mono_disps'][:,3::8,3::8];disp=z['droid_disps'];uncer=z['uncertainties']
  for n,rgb in enumerate(ids):
   p=prior[n].astype(float);d=disp[n].astype(float);v=np.isfinite(p)&np.isfinite(d)&(p>0)&(d>0)
   lr=np.log(d[v]/p[v]);shift=np.median(lr)
   depth.append(dict(arm=a,D=ARMS[a][0],schedule=ARMS[a][1],rgb=int(rgb),on_common_support=int(rgb) in common,n=int(v.sum()),log_ratio_gauge_shift=shift,gauge_removed_log_shape_MAD=float(np.median(np.abs(lr-shift))),source_U_gate_less_than_one_fraction=float(np.mean(uncer[n]>.8)),scope='FINAL_SAVED_MAP_NOT_GROUND_TRUTH_DEPTH_OR_NATIVE_OBJECTIVE'))
 writecsv('TASK005A_GAUGE_NORMALIZED_MAP_DIAGNOSTICS.csv',depth)
 depthsummary=[]
 for a in ARMS:
  rs=[r for r in depth if r['arm']==a and r['on_common_support']]
  depthsummary.append(dict(arm=a,common_frames=len(rs),median_frame_log_gauge_shift=float(np.median([r['log_ratio_gauge_shift'] for r in rs])),median_frame_gauge_removed_shape_MAD=float(np.median([r['gauge_removed_log_shape_MAD'] for r in rs])),median_frame_U_gated_fraction=float(np.median([r['source_U_gate_less_than_one_fraction'] for r in rs]))))
 writecsv('TASK005A_MAP_DIAGNOSTIC_SUMMARY.csv',depthsummary)
 sources=[ROOT.parent/'VIPER_VAL007_STAGE_OBSERVABILITY_R2/review/frozen_source/DROID-W/src/lib/droid_kernels.cu',ROOT.parent/'DROID_W_TASK004C_B_NATIVE_INTEGRATION_20261124_R1/source_candidate/src/lib/droid_kernels.cu',OLD/'raw_evidence/R3_OFFLINE/additional_source_reference/src/depth_video.py',OLD/'raw_evidence/R3_OFFLINE/additional_source_reference/task003_observer.py']
 inventory=[]
 for p in sources:
  assert p.is_file();inventory.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
 assert inventory[0]['sha256']==inventory[1]['sha256']
 repo=ROOT.parent/'VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_20261120_034750/fresh_official_source/DROID-W'
 q=subprocess.run(['git','-C',str(repo),'rev-parse','c3414af6047d06bafc1a6645d09f23247f3b2cdc:src/lib/droid_kernels.cu'],capture_output=True,text=True)
 if q.returncode==0:
  blob=hashlib.sha1(b'blob '+str(sources[0].stat().st_size).encode()+bytes([0])+sources[0].read_bytes()).hexdigest()
  assert blob==q.stdout.strip();baseline=dict(status='GIT_OBJECT_MATCH',commit='c3414af6047d06bafc1a6645d09f23247f3b2cdc',blob_sha1=blob,checkout=str(repo))
 else:baseline=dict(status='GIT_OBJECT_UNAVAILABLE_SOURCE_COPIES_MATCH',stderr=q.stderr.strip())
 dump(ROOT/'01_source_audit/SOURCE_PROVENANCE.json',dict(sources=inventory,baseline=baseline,kernel_source_copies_equal=True,no_source_execution=True))
 verify_seal()
 print('CONDITIONAL_EFFECTS',json.dumps(effects),flush=True)
 print('MISMATCH',json.dumps(mismatch),flush=True)
 print('MAP_SUMMARY',json.dumps(depthsummary),flush=True)
 print('PREFIX_REVERSAL_COUNT',sum(x['reversal_observed'] for x in peffects),'of',len(peffects),flush=True)
 print('SOURCE',baseline['status'],flush=True)
if __name__=='__main__':main()

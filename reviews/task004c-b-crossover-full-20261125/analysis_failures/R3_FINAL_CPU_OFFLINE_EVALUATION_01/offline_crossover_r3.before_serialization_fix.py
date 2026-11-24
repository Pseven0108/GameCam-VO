"""CPU-only offline evaluation; GT is never passed to any tracking process."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import csv,hashlib,json,math,pathlib,sys,time
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'raw_evidence'/'R3_OFFLINE'/'attempts'
sys.path.insert(0,str(ROOT/'tools'))
from evidence_locations import stage_dir
OUT=ROOT/'evaluation'
GT=ROOT.parent/'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/offline_gt/val_007.npz'
GT_SHA='91fb149c066bb488ac6071602a4b50fe1540243f2db3369a3706f63b705d7008'
C0_SHA='18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92'
S_REF=19.1341794347
BITS={'B1':(1,'S1'),'B2':(0,'S1'),'B4':(0,'S0'),'B3':(1,'S0')}
PAIRS=((312,328),(309,325),(301,353))
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def jsonout(name,value):
 (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def csvout(name,rows):
 keys=list(dict.fromkeys(k for row in rows for k in row))
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader()
  for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict,tuple)) else v for k,v in row.items()})
def rows(path):return [json.loads(x) for x in pathlib.Path(path).read_text().splitlines() if x.strip()]
def quat(q):
 q=np.asarray(q,dtype=np.float64);norm=np.linalg.norm(q)
 assert q.shape==(4,) and np.isfinite(q).all() and abs(norm-1)<2e-3,'Invalid XYZW quaternion'
 x,y,z,w=q/norm
 return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def pose(v,convention):
 v=np.asarray(v,dtype=float);assert v.shape==(7,) and np.isfinite(v).all()
 r=quat(v[3:]);m=np.eye(4)
 if convention=='W2C':m[:3,:3]=r.T;m[:3,3]=-r.T@v[:3]
 elif convention=='C2W':m[:3,:3]=r;m[:3,3]=v[:3]
 else:raise ValueError(convention)
 return m
def rmse(x):return float(np.sqrt(np.mean(np.sum(np.asarray(x)**2,axis=-1))))
def angles(r):return np.degrees(np.arccos(np.clip((np.trace(r,axis1=-2,axis2=-1)-1)/2,-1,1)))
def align(x,y,scaled=True):
 x=np.asarray(x);y=np.asarray(y);xc=x-x.mean(0);yc=y-y.mean(0)
 u,d,vt=np.linalg.svd(yc.T@xc/len(x));sign=np.ones(3);sign[-1]=np.linalg.det(u@vt)
 var=np.mean(np.sum(xc*xc,axis=1));assert var>1e-14
 r=(u*sign)@vt;s=float(d@sign/var) if scaled else 1.
 assert s>0 and math.isfinite(s)
 return r,y.mean(0)-s*r@x.mean(0),s

def endpoint(arm,stage,a,b,poses,gt,rotation=None,scale=None):
 row={'arm':arm,'stage':stage,'rgb_start':a,'rgb_end':b,'camera_start':a-1,'camera_end':b-1,'no_interpolation':True}
 if a not in poses or b not in poses:return dict(row,status='ENDPOINT_UNAVAILABLE')
 p,q=poses[a],poses[b];g,h=gt[a-1],gt[b-1];d=q[:3,3]-p[:3,3];dg=h[:3,3]-g[:3,3]
 dl=float(np.linalg.norm(d));gl=float(np.linalg.norm(dg));assert gl>1e-6
 direction=float(np.degrees(np.arccos(np.clip((rotation@d)@dg/(dl*gl),-1,1)))) if rotation is not None and dl>1e-12 else None
 return dict(row,status='VALID',estimate_raw_length=dl,gt_length_game_units=gl,raw_numeric_length_ratio=dl/gl,
  inherited_sref=S_REF,inherited_sref_displacement_ratio_pct=100*S_REF*dl/gl,
  global_sim3_fit_scale=scale,global_sim3_displacement_ratio_pct=100*scale*dl/gl if scale else None,
  translation_rpe_inherited_sref_game_units=float(np.linalg.norm(S_REF*(p[:3,:3].T@d)-g[:3,:3].T@dg)),
  translation_rpe_global_sim3_game_units=float(np.linalg.norm(scale*(p[:3,:3].T@d)-g[:3,:3].T@dg)) if scale else None,
  camera_relative_direction_error_deg=float(np.degrees(np.arccos(np.clip((p[:3,:3].T@d)@(g[:3,:3].T@dg)/(dl*gl),-1,1)))) if dl>1e-12 else None,
   direction_error_deg=direction,rotation_rpe_deg=float(angles((g[:3,:3].T@h[:3,:3]).T@(p[:3,:3].T@q[:3,:3]))))

def read_keyframes(path):
 with np.load(path,allow_pickle=False) as z:
  ids=np.rint(z['timestamps']).astype(int)+1;data=z['poses']
 assert len(ids)==len(set(ids)) and np.all(np.diff(ids)>0) and data.shape==(len(ids),7)
 return {int(i):pose(v,'W2C') for i,v in zip(ids,data)}
def schedule_check(producer,consumer):
 sys.path.insert(0,str(ROOT/'source_reference'))
 from native_control.runtime import read_schedule
 a=read_schedule(stage_dir(producer)/'schedule.jsonl');b=read_schedule(stage_dir(consumer)/'schedule.jsonl')
 assert len(a['events'])==len(b['events'])
 for x,y in zip(a['events'],b['events']):
  for key in ('index','kind','rgb','context','payload'):assert x[key]==y[key],(producer,consumer,x['index'],key)
 return {'producer':producer,'consumer':consumer,'events':len(a['events']),'exact_discrete_events_and_contexts':True,
 'producer_schedule_sha256':sha(stage_dir(producer)/'schedule.jsonl'),'consumer_schedule_sha256':sha(stage_dir(consumer)/'schedule.jsonl'),
 'independent_continuous_optimization':True,'continuous_states_not_replayed':True}

def selfcheck():
 rng=np.random.default_rng(917);x=rng.normal(size=(40,3));r0=np.array([[0,-1,0],[1,0,0],[0,0,1.]])
 y=3*(x@r0.T)+np.array([2,5,-1]);r,t,s=align(x,y);tests=[]
 def ck(n,ok):assert bool(ok),n;tests.append({'name':n,'status':'PASS'})
 ck('known_Sim3_rotation_translation_scale3',rmse(s*x@r.T+t-y)<1e-12 and abs(s-3)<1e-12)
 rs,ts,ss=align(x,x@r0.T+4,False);ck('SE3_has_no_scale',ss==1 and rmse(x@rs.T+ts-(x@r0.T+4))<1e-12)
 v=[1.,2.,3.,0.,0.,math.sqrt(.5),math.sqrt(.5)];c2w=pose(v,'C2W');w2c=pose(v,'W2C')
 ck('XYZW_90deg_Z_rotation',np.allclose(c2w[:3,:3],r0,atol=1e-12))
 ck('W2C_inversion_translation_rotated',np.allclose(c2w@w2c,np.eye(4),atol=1e-12))
 g=np.repeat(np.eye(4)[None],4,axis=0);g[:,0,3]=np.arange(4);p={i+1:m for i,m in enumerate(g)}
 e=endpoint('TEST','identity',1,4,p,g,np.eye(3),1)
 ck('identity_endpoint_zero_RPE',e['translation_rpe_global_sim3_game_units']==0 and e['rotation_rpe_deg']==0)
 ck('missing_endpoint_not_interpolated',endpoint('TEST','missing',1,4,{1:g[0]},g)['status']=='ENDPOINT_UNAVAILABLE')
 i=np.arange(3);j=i+1;rel=np.einsum('nij,nj->ni',g[i,:3,:3].transpose(0,2,1),g[j,:3,3]-g[i,:3,3])
 ck('identity_relative_motion',np.allclose(rel,[1,0,0]))
 ck('reflection_not_allowed',np.linalg.det(r)>0.999999999)
 ck('rotation_angle_90deg',abs(float(angles(r0))-90)<1e-10)
 # A change of monocular gauge must not change aligned endpoint or shape metrics.
 changed={i+1:m.copy() for i,m in enumerate(g)}
 for m in changed.values():m[:3,3]=4*m[:3,3]+np.array([8.,-2.,1.])
 ax=np.array([m[:3,3] for m in changed.values()]);ay=g[:,:3,3];ar,at,ascale=align(ax,ay)
 eg=endpoint('TEST','changed_gauge',1,4,changed,g,ar,ascale)
 ck('stage_global_alignment_recovers_gauge_scale',abs(ascale-.25)<1e-12)
 ck('stage_global_alignment_preserves_endpoint_length_ratio',abs(eg['global_sim3_displacement_ratio_pct']-100)<1e-10)
 ck('stage_global_alignment_preserves_shape_RMSE',rmse(ascale*ax@ar.T+at-ay)<1e-12)
 OUT.mkdir(exist_ok=True);jsonout('CPU_EVALUATION_SELFCHECK.json',{'passed':len(tests),'failed':0,'seed':917,'CUDA_VISIBLE_DEVICES':'','tests':tests})
 print(json.dumps({'selfcheck_passed':len(tests),'failed':0}))

def evaluate():
 assert sha(GT)==GT_SHA
 with np.load(GT,allow_pickle=False) as z:
  assert np.array_equal(z['rgb_ids'],np.arange(1,488)) and np.array_equal(z['camera_frame_ids'],np.arange(487))
  gt=z['c2w'].copy()
 assert gt.shape==(487,4,4) and np.isfinite(gt).all()
 summary=[];endpoints=[];rp=[];retention=[];perframe=[];mechanisms=[];comparisons=[];positions={};anchors=[];stage_scores=[]
 for arm,(D,S) in BITS.items():
  at=stage_dir(arm);success=json.loads((at/'SUCCESS.json').read_text());receipt=json.loads((at/'PROCESS_RECEIPT.json').read_text())
  assert success['pose_rows']==487 and success['c0_sha256']==C0_SHA and receipt['exit_code']==0
  native=at/'native';data=np.loadtxt(native/'traj/est_poses_full.txt',ndmin=2)
  assert data.shape==(487,8) and np.array_equal(data[:,0],np.arange(487))
  poses={i+1:pose(row[1:],'C2W') for i,row in enumerate(data)}
  front=read_keyframes(at/'FRONTEND_KEYFRAMES.npz');final=read_keyframes(at/'FINAL_BA_KEYFRAMES.npz')
  assert sorted(front)==sorted(final)
  ids=sorted(final);tp=np.array([np.linalg.norm(final[i][:3,3]-poses[i][:3,3]) for i in ids])
  rr=angles(np.stack([final[i][:3,:3].T@poses[i][:3,:3] for i in ids]))
  max_coord=max(1.,max(float(np.linalg.norm(final[i][:3,3])) for i in ids))
  precision_bound=2e-6+32*np.finfo(np.float32).eps*max_coord
  assert tp.max()<precision_bound and rr.max()<0.001,'Retained KF/export mismatch exceeds stated precision bound'
  anchors.append({'arm':arm,'retained_keyframes':len(ids),'translation_max_abs_norm_raw':float(tp.max()),'rotation_max_deg':float(rr.max()),'translation_check_bound_raw':precision_bound,'rotation_check_bound_deg':0.001,'bit_exact':False,'source':'src/utils/eval_traj.py full_traj_fill overwrites filled poses at retained KF timestamps before six-decimal TUM export','status':'CONSISTENT_WITH_FLOAT32_AND_TEXT_EXPORT'})
  p=np.stack(list(poses.values()));x=p[:,:3,3];y=gt[:,:3,3]
  r,t,s=align(x,y);rs,ts,_=align(x,y,False);aligned=s*x@r.T+t;positions[arm]=aligned
  err=aligned-y;rot_err=angles(gt[:,:3,:3].transpose(0,2,1)@(r[None]@p[:,:3,:3]))
  primary=endpoint(arm,'FINAL_EXPORT',312,328,poses,gt,r,s)
  row={'arm':arm,'D':D,'schedule':S,'frames':487,'keyframes':len(front),'runtime_s':receipt['runtime_seconds'],
   'ate_sim3_game_units':rmse(err),'ate_se3_raw_numeric_diagnostic':rmse(x@rs.T+ts-y),
   'ate_se3_inherited_sref_game_units':rmse((S_REF*x)@rs.T+(y.mean(0)-rs@(S_REF*x.mean(0)))-y),
   'global_sim3_fit_scale':s,'orientation_rmse_sim3_deg':float(np.sqrt(np.mean(rot_err**2))),
   'rgb312_retained':312 in front,'rgb328_retained':328 in front,
   'endpoint312_328_raw_length':primary['estimate_raw_length'],
   'endpoint312_328_inherited_sref_ratio_pct':primary['inherited_sref_displacement_ratio_pct'],
   'endpoint312_328_global_sim3_ratio_pct':primary['global_sim3_displacement_ratio_pct']}
  summary.append(row)
  for stage,stage_poses in (('FRONTEND_DIRECT_KEYFRAME',front),('POST_FINAL_BA_DIRECT_KEYFRAME',final)):
   stage_ids=sorted(stage_poses);stage_x=np.array([stage_poses[i][:3,3] for i in stage_ids]);stage_y=gt[np.array(stage_ids)-1,:3,3]
   sr,st,ss=align(stage_x,stage_y)
   stage_scores.append({'arm':arm,'stage':stage,'aligned_keyframe_count':len(stage_ids),'global_stage_sim3_fit_scale':ss,'ate_sim3_keyframes_game_units':rmse(ss*stage_x@sr.T+st-stage_y),'scope':'All retained keyframes of this stage, single global scale; no segment scale fitting','raw_lengths_across_stages_gauge_dependent':True})
  for a,b in PAIRS:
   for stage,stage_poses in (('FINAL_EXPORT',poses),('FRONTEND_DIRECT_KEYFRAME',front),('POST_FINAL_BA_DIRECT_KEYFRAME',final)):
    if stage=='FINAL_EXPORT':er,es=r,s;alignment_source='ALL_487_FINAL_EXPORT_POSES'
    else:
     stage_ids=sorted(stage_poses);stage_x=np.array([stage_poses[i][:3,3] for i in stage_ids]);stage_y=gt[np.array(stage_ids)-1,:3,3]
     er,et,es=align(stage_x,stage_y);alignment_source='ALL_RETAINED_KEYFRAMES_AT_THIS_STAGE'
    row_endpoint=endpoint(arm,stage,a,b,stage_poses,gt,er,es)
    row_endpoint['alignment_source']=alignment_source
    row_endpoint['stage_gauge_independently_aligned']=True
    endpoints.append(row_endpoint)
   retention.append({'arm':arm,'a':a,'b':b,'a_retained_keyframe':a in front,'b_retained_keyframe':b in front,'a_final_export_valid':a in poses,'b_final_export_valid':b in poses,'a_filler_participation':a not in front,'b_filler_participation':b not in front})
  for delta in (1,15,60,150):
   i=np.arange(487-delta);j=i+delta
   pred=np.einsum('nij,nj->ni',p[i,:3,:3].transpose(0,2,1),x[j]-x[i]);truth=np.einsum('nij,nj->ni',gt[i,:3,:3].transpose(0,2,1),y[j]-y[i])
   er=angles((gt[i,:3,:3].transpose(0,2,1)@gt[j,:3,:3]).transpose(0,2,1)@(p[i,:3,:3].transpose(0,2,1)@p[j,:3,:3]))
   rp.append({'arm':arm,'offset_rgb':delta,'pairs':len(i),'translation_rmse_raw_numeric_diagnostic':rmse(pred-truth),'translation_rmse_inherited_sref_game_units':rmse(S_REF*pred-truth),'translation_rmse_global_sim3_game_units':rmse(s*pred-truth),'rotation_rmse_deg':float(np.sqrt(np.mean(er**2)))})
  for k in range(487):perframe.append({'arm':arm,'rgb_id':k+1,'sim3_error_game_units':float(np.linalg.norm(err[k])),'sim3_rotation_error_deg':float(rot_err[k]),'retained_keyframe':k+1 in front,'raw_x':float(x[k,0]),'raw_y':float(x[k,1]),'raw_z':float(x[k,2]),'aligned_x':float(aligned[k,0]),'aligned_y':float(aligned[k,1]),'aligned_z':float(aligned[k,2])})
  obs=rows(at/'observer.jsonl')
  calls={};decisions=[]
  for q in obs:
   if q['type'] in ('ba_before','ba_after_native','ba_after_clamp'):calls.setdefault(q['ba_id'],{})[q['type']]=q
   if q['type']=='keyframe_decision':decisions.append(q)
  for bid,v in calls.items():
   assert set(v)=={'ba_before','ba_after_native','ba_after_clamp'},(arm,bid)
   bef,nat,cl=v['ba_before'],v['ba_after_native'],v['ba_after_clamp']
   mechanisms.append({'arm':arm,'ba_id':bid,'rgb_id':bef['trigger_rgb_id'],'stage':bef['stage'],'metric_depth_selected':bef.get('metric_depth_prior_selected'),'native_negative_sample_count':nat.get('disparity',{}).get('negative'),'native_sample_size':nat.get('disparity',{}).get('n'),'clamp_floor_count_all_active_pixels':cl.get('full_disparity_grid',{}).get('float32_floor_count'),'uncertainty_median':nat.get('uncertainty',{}).get('median'),'uncertainty_p90':nat.get('uncertainty',{}).get('p90'),'sample_effective_weight_median':bef.get('geometry',{}).get('effective_weight',{}).get('median')})
  row['ba_calls_observed_since_C0']=len(calls)
  row['motion_filter_rejected']=sum(x['outcome']=='MOTION_FILTER_REJECTED' for x in decisions)
  row['local_ba_rejected']=sum(x['outcome']=='LOCAL_BA_REJECTED' for x in decisions)
  row['retained_decisions']=sum(x['outcome']=='RETAINED' for x in decisions)
  for item in retention:
   if item['arm']!=arm:continue
   a,b=item['a'],item['b'];joint=[]
   for bid,v in calls.items():
    bef=v['ba_before'];active={x['rgb_id'] for x in bef.get('rows',[]) if bef['t0']<=x['slot']<bef['t1']}
    if {a,b}.issubset(active):joint.append(bid)
   item['common_optimized_BA_call_count']=len(joint)
   item['common_optimized_BA_call_ids']=joint
   item['common_BA_definition']='Both endpoint slots in [t0,t1); not merely present in keyframe cache'
   item['filler_calculated_all_frames_but_retained_KF_overwritten']=True
 for a,b in (('B1','B2'),('B4','B3')):comparisons.append(schedule_check(a,b))
 csvout('CROSSOVER_SUMMARY.csv',summary);csvout('FIXED_ENDPOINT_AND_DIRECT_KEYFRAME.csv',endpoints);csvout('RPE_OFFSETS.csv',rp);csvout('ENDPOINT_RETENTION.csv',retention);csvout('PER_FRAME_ERRORS.csv',perframe);csvout('BA_MECHANISM_TIMELINE.csv',mechanisms)
 jsonout('SCHEDULE_REPLAY_COMPARISON.json',comparisons)
 jsonout('RETAINED_KEYFRAME_EXPORT_CONSISTENCY.json',anchors)
 contrasts=[];by={x['arm']:x for x in summary}
 for name,a,b in (('D_on_minus_off_fixed_S1','B1','B2'),('D_on_minus_off_fixed_S0','B3','B4'),('S1_minus_S0_fixed_D1','B1','B3'),('S1_minus_S0_fixed_D0','B2','B4')):
  for metric in ('ate_sim3_game_units','endpoint312_328_raw_length','endpoint312_328_inherited_sref_ratio_pct','endpoint312_328_global_sim3_ratio_pct','keyframes'):
   contrasts.append({'contrast':name,'metric':metric,'value':float(by[a][metric]-by[b][metric]),'arm_plus':a,'arm_minus':b,'replicate_n':1,'statistical_inference':'DESCRIPTIVE_SINGLE_SEQUENCE_SINGLE_SEED_NO_PVALUE'})
 csvout('CONTROLLED_CONTRASTS.csv',contrasts);csvout('KEYFRAME_STAGE_SCORES.csv',stage_scores)
 ds_contrasts=[]
 for metric in ('ate_sim3_game_units','endpoint312_328_global_sim3_ratio_pct','endpoint312_328_raw_length','keyframes'):
  d_s1=by['B1'][metric]-by['B2'][metric];d_s0=by['B3'][metric]-by['B4'][metric]
  ds_contrasts.append({'metric':metric,'D_on_minus_off_at_S1':d_s1,'D_on_minus_off_at_S0':d_s0,'mean_D_effect':.5*(d_s1+d_s0),'mean_S1_minus_S0_effect':.5*((by['B1'][metric]-by['B3'][metric])+(by['B2'][metric]-by['B4'][metric])),'difference_of_D_effects_S1_minus_S0':d_s1-d_s0,'replicate_n_per_cell':1,'CI_or_pvalue':'NOT_ESTIMATED_SINGLE_REPLICATE','schedules_are_endogenous_historical_producer_paths':True})
 csvout('DESCRIPTIVE_D_S_CONTRASTS.csv',ds_contrasts)
 aggregate=[]
 for arm in BITS:
  for stage in sorted({x['stage'] for x in mechanisms if x['arm']==arm}):
   calls_here=[x for x in mechanisms if x['arm']==arm and x['stage']==stage]
   out={'arm':arm,'stage':stage,'observed_BA_calls':len(calls_here),'calls_with_sampled_negative_disparity':sum((x['native_negative_sample_count'] or 0)>0 for x in calls_here),'negative_counts_are_sampled_not_full_pixel_census':True,'floor_counts_are_grid_at_floor_not_new_clamp_events':True}
   for key in ('native_negative_sample_count','clamp_floor_count_all_active_pixels','uncertainty_median','uncertainty_p90','sample_effective_weight_median'):
    vals=[x[key] for x in calls_here if x[key] is not None]
    out[key+'_max']=max(vals) if vals else None
    out[key+'_median_over_events']=float(np.median(vals)) if vals else None
   aggregate.append(out)
 csvout('BA_STAGE_DIAGNOSTIC_SUMMARY.csv',aggregate)
 jsonout('EVALUATION_IDENTITY.json',{'GT_SHA256':GT_SHA,'GT_used_offline_only':True,'RGB_to_camera':'camera_frame=rgb_id-1','C0_SHA256':C0_SHA,'S_REF':S_REF,'S_REF_provenance':'Inherited historical Task004A E0 GT-derived alignment; diagnostic, not recovered metric scale','all_formal_arms_complete':True,'sequence':'val_007','seed':43,'CUDA_VISIBLE_DEVICES':'','no_per_segment_scale_fit':True})
 # Scientific plots use standard matplotlib; input RGB and GT arrays stay local.
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 fig,axs=plt.subplots(2,2,figsize=(11,8),constrained_layout=True)
 for ax,(arm,xyz) in zip(axs.flat,positions.items()):
  ax.plot(gt[:,0,3],gt[:,2,3],color='black',lw=1.3,label='GT');ax.plot(xyz[:,0],xyz[:,2],lw=1.1,label=arm)
  ax.scatter(xyz[[311,327],0],xyz[[311,327],2],s=22);ax.set_title(arm+' single global Sim3');ax.set_xlabel('World X (game units)');ax.set_ylabel('World Z (game units)');ax.axis('equal');ax.legend()
 fig.savefig(OUT/'GLOBAL_SIM3_TRAJECTORIES.png',dpi=160);plt.close(fig)
 print(json.dumps({'arms':len(summary),'summary':summary},ensure_ascii=False,indent=2))
if __name__=='__main__':
 if '--selfcheck' in sys.argv:selfcheck()
 else:selfcheck();evaluate()

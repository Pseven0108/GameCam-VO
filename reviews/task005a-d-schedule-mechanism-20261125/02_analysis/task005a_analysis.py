"""TASK005A: seal Task004C-B without modifying it, then explain existing D x S results."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import csv,datetime,hashlib,json,math,pathlib,sys,collections
sys.dont_write_bytecode=True
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'DROID_W_TASK004C_B_IO_COMPAT_20261124_R1'
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125')
OUT=ROOT/'03_evaluation'
ARMS={'B1':(1,'S1'),'B2':(0,'S1'),'B4':(0,'S0'),'B3':(1,'S0')}
GT=ROOT.parent/'DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/offline_gt/val_007.npz'
GT_SHA='91fb149c066bb488ac6071602a4b50fe1540243f2db3369a3706f63b705d7008'
PAIRS=((312,328),(309,325),(301,353))
LOCAL={'frontend_local_predecision','frontend_local_retained'}
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def stage(arm):
 p=OLD/'raw_evidence/R3_OFFLINE/attempts'/arm
 return p if p.exists() else RECEIVER/'raw_evidence/R3_OFFLINE/attempts'/arm
def dump(path,obj):
 def enc(x):
  if isinstance(x,np.generic):return x.item()
  if isinstance(x,np.ndarray):return x.tolist()
  raise TypeError(type(x).__name__)
 pathlib.Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,default=enc)+'\n',encoding='utf-8')
def writecsv(name,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def seal():
 p=ROOT/'00_seal/TASK004CB_IMMUTABLE_SEAL.json'
 if p.exists():return
 pub=json.loads((OLD/'GITHUB_R3_PUBLICATION_RECEIPT.json').read_text())
 package=json.loads((OLD/'COMPLETED_PACKAGE_VALIDATION.json').read_text())
 assert sha(package['ZIP_path'])==pub['ZIP_SHA256']
 inventory={}
 for base in (OLD,RECEIVER/'raw_evidence/R3_OFFLINE'):
  for q in base.rglob('*'):
   if q.is_file():
    st=q.stat();inventory[str(q)]={'bytes':st.st_size,'mtime_ns':st.st_mtime_ns}
 selected={}
 paths=list((OLD/'final_reports').glob('*'))+list((OLD/'evaluation').glob('*'))
 paths+=list((OLD/'analysis').glob('*.py'))+list((OLD/'source_reference').rglob('*.py'))
 paths+=[OLD/'GITHUB_R3_PUBLICATION_RECEIPT.json',OLD/'GITHUB_R3_SHUTDOWN_PUBLICATION_RECEIPT.json',OLD/'COMPLETED_PACKAGE_VALIDATION.json']
 for arm in ARMS:
  for name in ('observer.jsonl','native_trace.jsonl','FRONTEND_KEYFRAMES.npz','FINAL_BA_KEYFRAMES.npz','PROCESS_RECEIPT.json','SUCCESS.json','STAGE_RESUME_INPUT.json','RESTORE_RECEIPT.json','native/traj/est_poses_full.txt'):
   paths.append(stage(arm)/name)
 for q in paths:
  if q.is_file():selected[str(q)]={'bytes':q.stat().st_size,'sha256':sha(q)}
 dump(p,{'status':'FORMALLY_SEALED_FIRST_COMPLETE_FOUR_ARM_CONTROLLED_CROSSOVER',
  'sealed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'experiment_id':'Task004C-B',
  'review_commit':pub['commit'],'closeout_commit':json.loads((OLD/'GITHUB_R3_SHUTDOWN_PUBLICATION_RECEIPT.json').read_text())['final_closeout_commit'],
  'review_ZIP':package['ZIP_path'],'review_ZIP_SHA256':pub['ZIP_SHA256'],'original_manifest_entries':653,
  'no_rewrites_or_reanalysis_outputs_inside_original':True,'new_analysis_workspace':str(ROOT),
  'complete_metadata_inventory':inventory,'selected_content_hashes':selected,
  'claim':'First complete four-arm controlled crossover in this project; not a first-in-literature claim.'})
 print(json.dumps({'seal':'PASS','files_metadata':len(inventory),'files_hashed':len(selected)},ensure_ascii=False),flush=True)
def quat(q):
 q=np.asarray(q,dtype=np.float64);assert np.isfinite(q).all();q=q/np.linalg.norm(q);x,y,z,w=q
 return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def transform(v,w2c=False):
 m=np.eye(4);r=quat(v[3:]);t=np.asarray(v[:3]);m[:3,:3]=r.T if w2c else r;m[:3,3]=-r.T@t if w2c else t;return m
def align(x,y):
 xc=x-x.mean(0);yc=y-y.mean(0);u,d,vt=np.linalg.svd(yc.T@xc/len(x));sgn=np.ones(3);sgn[-1]=np.linalg.det(u@vt)
 r=(u*sgn)@vt;var=np.mean(np.sum(xc*xc,axis=-1));assert var>1e-14
 s=float(d@sgn/var);t=y.mean(0)-s*r@x.mean(0);assert s>0;return r,t,s

def stageposes(path):
 with np.load(path,allow_pickle=False) as z:
  ids=np.rint(z['timestamps']).astype(int)+1;poses=z['poses']
 assert len(set(ids))==len(ids) and np.all(np.diff(ids)>0)
 return {int(i):transform(v,True) for i,v in zip(ids,poses)}
def angle(a,b):
 na=np.linalg.norm(a);nb=np.linalg.norm(b)
 return float(np.degrees(np.arccos(np.clip(np.dot(a,b)/(na*nb),-1,1)))) if na>1e-12 and nb>1e-12 else None
def pstat(x,key,sub='median'):
 v=x.get(key) or {};return v.get(sub)
def geostat(x,key,sub='median'):return ((x.get('geometry') or {}).get(key) or {}).get(sub)
def geometryposes(rows):return {int(r['rgb_id']):transform(r['w2c_xyzw'],True) for r in rows if r.get('pool')=='KEYFRAME_CACHE'}
def dist(poses,a,b):return float(np.linalg.norm(poses[b][:3,3]-poses[a][:3,3])) if a in poses and b in poses else None

def analyze():
 seal();assert sha(GT)==GT_SHA
 with np.load(GT,allow_pickle=False) as z:
  assert np.array_equal(z['rgb_ids'],np.arange(1,488));gt=z['c2w'].copy()
 states={}
 for a in ARMS:
  b=stage(a);f=stageposes(b/'FRONTEND_KEYFRAMES.npz');k=stageposes(b/'FINAL_BA_KEYFRAMES.npz')
  data=np.loadtxt(b/'native/traj/est_poses_full.txt');assert data.shape==(487,8) and np.array_equal(data[:,0],np.arange(487))
  e={i+1:transform(r[1:]) for i,r in enumerate(data)};states[a]={'FRONTEND':f,'POST_FINAL_BA':k,'EXPORTED':e}
 common=sorted(set.intersection(*(set(states[a]['FRONTEND'])&set(states[a]['POST_FINAL_BA']) for a in ARMS)))
 assert len(common)>10
 scoring=[];endpoints=[];segments=[];perframe=[]
 for a in ARMS:
  D,S=ARMS[a]
  for st,poses in states[a].items():
   supports={'COMMON_ALL_FOUR_KF':common,'OWN_SUPPORT':sorted(poses)}
   if st=='EXPORTED':supports['ALL_487']=list(range(1,488))
   for support,ids in supports.items():
    x=np.array([poses[i][:3,3] for i in ids]);y=gt[np.array(ids)-1,:3,3];r,t,s=align(x,y);aligned=s*x@r.T+t;error2=np.sum((aligned-y)**2,axis=-1)
    scoring.append({'arm':a,'D':D,'schedule':S,'stage':st,'support':support,'n':len(ids),'ate_sim3':float(np.sqrt(np.mean(error2))),'fit_scale':s})
    if support=='COMMON_ALL_FOUR_KF' or (st=='EXPORTED' and support=='ALL_487'):
     for start,end in PAIRS:
      row={'arm':a,'stage':st,'fit_support':support,'start':start,'end':end,'status':'AVAILABLE' if start in poses and end in poses else 'ENDPOINT_UNAVAILABLE'}
      if row['status']=='AVAILABLE':
       delta=poses[end][:3,3]-poses[start][:3,3];dg=gt[end-1,:3,3]-gt[start-1,:3,3]
       row.update(ratio_pct=100*s*np.linalg.norm(delta)/np.linalg.norm(dg),world_direction_error_deg=angle(r@delta,dg),relative_direction_error_deg=angle(poses[start][:3,:3].T@delta,gt[start-1,:3,:3].T@dg))
      endpoints.append(row)
    if st=='EXPORTED' and support=='ALL_487':
     for i,e in zip(ids,error2):perframe.append({'arm':a,'D':D,'schedule':S,'rgb':i,'squared_error':e,'error':math.sqrt(e)})
     for lo,hi in ((1,120),(121,240),(241,360),(361,487),(301,353),(309,325),(312,328)):
      mask=(np.array(ids)>=lo)&(np.array(ids)<=hi)
      segments.append({'arm':a,'start':lo,'end':hi,'n':int(mask.sum()),'rmse_under_whole_487_alignment':float(np.sqrt(np.mean(error2[mask]))),'fraction_whole_trajectory_SSE':float(error2[mask].sum()/error2.sum()),'no_segment_scale_fit':True})
 writecsv('TASK005A_MATCHED_SUPPORT_STAGE_SCORES.csv',scoring)
 writecsv('TASK005A_STAGE_ENDPOINTS.csv',endpoints);writecsv('TASK005A_SEGMENT_ERROR_CONTRIBUTIONS.csv',segments);writecsv('TASK005A_PER_FRAME_GLOBAL_ERRORS.csv',perframe)
 dump(OUT/'COMMON_SUPPORT.json',{'common_rgb_ids':common,'count':len(common),'S1_only':sorted(set(states['B1']['FRONTEND'])-set(common)),'S0_only':sorted(set(states['B4']['FRONTEND'])-set(common))})
 print('MATCHED_SUPPORT',len(common),json.dumps([r for r in scoring if r['support']=='COMMON_ALL_FOUR_KF']),flush=True)

 # Full observer summaries: pair each native call; never run BA or reconstruct unobserved tensors.
 ba=[];pair_updates=[];stage_boundaries=[];decisions=[];native_decisions=[];hash_checks=[]
 for a in ARMS:
  b=stage(a);before={};native={};boundaries=[];types=collections.Counter()
  with (b/'observer.jsonl').open(encoding='utf-8') as f:
   for line in f:
    o=json.loads(line);typ=o['type'];types[typ]+=1
    if typ=='ba_before':before[o['ba_id']]=o
    elif typ=='ba_after_native':native[o['ba_id']]=o
    elif typ=='ba_after_clamp':
     bid=o['ba_id'];pre=before.pop(bid);nat=native.pop(bid);D,S=ARMS[a];poses=geometryposes(pre.get('rows',[]));after=geometryposes(nat.get('rows',[]))
     edges=np.array(pre['edge_slots'],dtype=int).reshape(-1,2);rgbids=[r['rgb_id'] for r in pre['rows']];gaps=[abs(rgbids[i]-rgbids[j]) for i,j in edges]
     grid=nat['full_disparity_grid'];clamp=o['full_disparity_grid'];geom=pre.get('geometry') or {};ng=nat.get('geometry') or {}
     weights_n=(geom.get('effective_weight') or {}).get('n')
     eta=pstat(pre,'eta_sample');row={'arm':a,'D':D,'schedule':S,'ba_id':bid,'rgb':pre['trigger_rgb_id'],'stage':pre['stage'],
      'D_selected':pre['metric_depth_prior_selected'],'source_UBA':pre['source_uba'],'update_U':pre['update_u'],'edge_count':len(edges),'edge_rgb_gap_median':float(np.median(gaps)) if gaps else None,
      'edge_rgb_gap_p90':float(np.quantile(gaps,.9)) if gaps else None,'active_KF':len(poses),'pose_window':pre['t1']-pre['t0'],
      'eta_median':eta,'alpha_over_eta_median_diagnostic':pre['gamma_depth']/eta if eta and eta>0 else None,
      'cached_prior_support_fraction':pre['cached_prior_positive_support']/pre['cached_prior_total'] if pre['cached_prior_total'] else None,
      'native_full_negative_fraction':grid['negative']/grid['total'],'native_full_negative_count':grid['negative'],'native_full_nonfinite':grid['nonfinite'],
      'clamp_grid_floor_fraction':clamp['float32_floor_count']/clamp['total'],'native_sample_negative_fraction':nat['disparity']['negative']/nat['disparity']['n'],
      'before_disparity_median':pstat(pre,'disparity'),'after_disparity_median':pstat(nat,'disparity'),'U_before_median':pstat(pre,'uncertainty'),'U_after_median':pstat(nat,'uncertainty'),
      'U_after_p90':pstat(nat,'uncertainty','p90'),'effective_weight_before_median':geostat(pre,'effective_weight'),'raw_weight_before_median':geostat(pre,'raw_weight'),
      'source_U_multiplier_mean':geostat(pre,'source_uncertainty_multiplier','mean'),'source_U_multiplier_median':geostat(pre,'source_uncertainty_multiplier'),
      'residual_before_median_lowres_px':geostat(pre,'residual_lowres_px'),'residual_after_median_lowres_px':geostat(nat,'residual_lowres_px'),
      'valid_projection_fraction_before':geom.get('valid_fraction'),'valid_projection_fraction_after':ng.get('valid_fraction'),
      'weighted_SSE_before':geom.get('weighted_residual_sse'),'weighted_SSE_after':ng.get('weighted_residual_sse'),
      'weighted_SSE_before_per_valid_observation':geom.get('weighted_residual_sse',0)/geom['valid_projection_samples'] if geom.get('valid_projection_samples') else None,
      'weighted_SSE_after_per_valid_observation':ng.get('weighted_residual_sse',0)/ng['valid_projection_samples'] if ng.get('valid_projection_samples') else None}
     ba.append(row)
     anchor_pre=dist(poses,1,18);anchor_after=dist(after,1,18)
     for start,end in PAIRS:
      d0=dist(poses,start,end);d1=dist(after,start,end)
      if d0 is not None and d1 is not None:
       pair_updates.append({'arm':a,'D':D,'schedule':S,'ba_id':bid,'rgb':pre['trigger_rgb_id'],'stage':pre['stage'],'start':start,'end':end,
        'pre_raw_length':d0,'native_after_raw_length':d1,'within_call_length_ratio':d1/d0 if d0>1e-15 else None,
        'pre_length_over_fixed_anchor1_18':d0/anchor_pre if anchor_pre and anchor_pre>1e-15 else None,
        'after_length_over_fixed_anchor1_18':d1/anchor_after if anchor_after and anchor_after>1e-15 else None,
        'direction_turn_within_call_deg':angle(poses[end][:3,3]-poses[start][:3,3],after[end][:3,3]-after[start][:3,3])})
    elif typ=='stage_boundary':
     poses=geometryposes(o.get('rows',[]));ids=sorted(set(poses)&set(common))
     if len(ids)>10:
      x=np.array([poses[i][:3,3] for i in ids]);y=gt[np.array(ids)-1,:3,3];r,t,s=align(x,y)
      stage_boundaries.append({'arm':a,'stage':o['stage'],'common_support_n':len(ids),'ate_sim3':float(np.sqrt(np.mean(np.sum((s*x@r.T+t-y)**2,axis=-1)))),'fit_scale':s})
    elif typ=='frontend_distance':
     decisions.append({'arm':a,'rgb':o['trigger_rgb_id'],'distance':o['score'],'threshold':o['threshold']})
  assert not before and not native
  trace_first={}
  with (b/'native_trace.jsonl').open(encoding='utf-8') as f:
   for line in f:
    o=json.loads(line)
    if o['kind']=='keyframe.natural':native_decisions.append({'arm':a,'rgb':o['rgb'],'natural_drop':o['drop'],'scheduled_drop':o['scheduled_drop'],'distance':o['distance'],'threshold':o['threshold'],'disagrees':o['drop']!=o['scheduled_drop']})
    if o['kind'] in ('ba.continuous.before','ba.continuous.after') and o['kind'] not in trace_first:trace_first[o['kind']]=o
  hash_checks.append({'arm':a,'first_BA_before':trace_first['ba.continuous.before'],'first_BA_after':trace_first['ba.continuous.after']})
  print('OBSERVER_COMPLETE',a,dict(types),flush=True)
 writecsv('TASK005A_BA_MECHANISM_TIMELINE.csv',ba);writecsv('TASK005A_TARGET_PAIR_BA_UPDATES.csv',pair_updates)
 writecsv('TASK005A_FINAL_BA_STAGE_COMMON_SUPPORT.csv',stage_boundaries);writecsv('TASK005A_PREDECISION_DISTANCE.csv',decisions);writecsv('TASK005A_FORCED_VS_NATURAL_DECISIONS.csv',native_decisions)
 dump(OUT/'FIRST_BA_TENSOR_HASHES.json',hash_checks)
 agg=[]
 numeric=[k for k,v in ba[0].items() if isinstance(v,(int,float)) and not isinstance(v,bool) and k not in ('D','ba_id','rgb')]
 for a in ARMS:
  phases=sorted({r['stage'] for r in ba if r['arm']==a})+['ALL_FRONTEND_LOCAL']
  for phase in phases:
   rs=[r for r in ba if r['arm']==a and (r['stage'] in LOCAL if phase=='ALL_FRONTEND_LOCAL' else r['stage']==phase)]
   out={'arm':a,'D':ARMS[a][0],'schedule':ARMS[a][1],'stage':phase,'calls':len(rs)}
   for key in numeric:
    v=[r[key] for r in rs if r.get(key) is not None and np.isfinite(r[key])]
    out[key+'_event_median']=float(np.median(v)) if v else None
    out[key+'_event_p90']=float(np.quantile(v,.9)) if v else None
   agg.append(out)
 writecsv('TASK005A_BA_PHASE_SUMMARY.csv',agg)
 mismatch=[]
 for a in ARMS:
  rs=[r for r in native_decisions if r['arm']==a]
  mismatch.append({'arm':a,'D':ARMS[a][0],'schedule':ARMS[a][1],'candidate_decisions':len(rs),'natural_vs_forced_mismatches':sum(r['disagrees'] for r in rs),'natural_drop_count':sum(r['natural_drop'] for r in rs),'scheduled_drop_count':sum(r['scheduled_drop'] for r in rs)})
 writecsv('TASK005A_DECISION_MISMATCH_SUMMARY.csv',mismatch);print('DECISION_MISMATCH',json.dumps(mismatch),flush=True)

 # Final native maps only, with the original documented sampling [3::8,3::8].
 depthrows=[];prior_hashes={};native_inputs=[]
 for a in ARMS:
  p=stage(a)/'native/video.npz'
  with np.load(p,allow_pickle=False) as z:
   ts=z['timestamps'];ids=np.rint(ts).astype(int)+1;mono=z['mono_disps'];disp=z['droid_disps'];u=z['uncertainties']
  assert mono.ndim==3 and disp.ndim==3 and disp.shape==u.shape
  low=mono[:,3::8,3::8]
  assert low.shape==disp.shape and list(ids)==list(states[a]['POST_FINAL_BA'])
  prior_hashes[a]={}
  for j,rgb in enumerate(ids):
   d=disp[j].astype(np.float64);m=low[j].astype(np.float64);valid=np.isfinite(d)&np.isfinite(m)&(d>0)&(m>0);ratio=d[valid]/m[valid]
   prior_hashes[a][int(rgb)]=hashlib.sha256(low[j].tobytes()).hexdigest()
   depthrows.append({'arm':a,'D':ARMS[a][0],'schedule':ARMS[a][1],'rgb':int(rgb),'full_grid_pixels':d.size,'positive_joint_valid_pixels':int(valid.sum()),
    'disparity_over_prior_median':float(np.median(ratio)),'abs_log_disparity_prior_median':float(np.median(np.abs(np.log(ratio)))),
    'disparity_median':float(np.median(d)),'prior_median':float(np.median(m)),
    'floor_fraction':float(np.mean(d==float(np.float32(1e-5)))),'U_median':float(np.median(u[j])),'U_p90':float(np.quantile(u[j],.9)),
    'diagnostic_scope':'POST_FINAL_BA_AND_FILLER_SAVED_MAP_NOT_FRONTEND_PRIOR_ERROR_GT'})
  native_inputs.append({'arm':a,'video_path':str(p),'video_bytes':p.stat().st_size,'array_keys_read':['timestamps','mono_disps','droid_disps','uncertainties'],'images_not_loaded':True,'no_checkpoint_deserialization':True})
 writecsv('TASK005A_FINAL_DEPTH_PRIOR_DIAGNOSTICS.csv',depthrows)
 prior_match={str(i):len({prior_hashes[a][i] for a in ARMS})==1 for i in common}
 dump(OUT/'DEPTH_PRIOR_INPUT_IDENTITY.json',{'comparison':'downsampled native mono prior at common retained frames','common_count':len(common),'all_equal':all(prior_match.values()),'per_rgb_equal':prior_match,'native_inputs':native_inputs,'not_independent_depth_GT':True})
 # Gauge-invariant map shape mismatch: remove one median log ratio per map; not a physical scale estimate.
 print('ANALYSIS_COMPLETE',{'BA_calls':len(ba),'pair_updates':len(pair_updates),'common_KF':len(common),'prior_same':all(prior_match.values())},flush=True)

def verify_seal():
 s=json.loads((ROOT/'00_seal/TASK004CB_IMMUTABLE_SEAL.json').read_text())
 changes=[]
 current=set()
 for base in (OLD,RECEIVER/'raw_evidence/R3_OFFLINE'):
  current.update(str(q) for q in base.rglob('*') if q.is_file())
 expected_paths=set(s['complete_metadata_inventory'])
 for extra in sorted(current-expected_paths):changes.append({'path':extra,'change':'NEW_FILE_IN_SEALED_TREE'})
 for p,expected in s['complete_metadata_inventory'].items():
  q=pathlib.Path(p)
  if not q.exists():changes.append({'path':p,'change':'MISSING'});continue
  st=q.stat()
  if st.st_size!=expected['bytes'] or st.st_mtime_ns!=expected['mtime_ns']:changes.append({'path':p,'change':'METADATA_CHANGED'})
 for p,expected in s['selected_content_hashes'].items():
  if pathlib.Path(p).is_file() and sha(p)!=expected['sha256']:changes.append({'path':p,'change':'CONTENT_HASH_CHANGED'})
 assert sha(s['review_ZIP'])==s['review_ZIP_SHA256']
 dump(ROOT/'00_seal/TASK004CB_SEAL_REVERIFICATION.json',{'status':'PASS' if not changes else 'FAIL','metadata_entries_checked':len(s['complete_metadata_inventory']),'selected_hashes_checked':len(s['selected_content_hashes']),'changes':changes,'original_review_ZIP_unchanged':True})
 assert not changes
 print('SEAL_RECHECK_PASS',flush=True)
if __name__=='__main__':
 analyze();verify_seal()

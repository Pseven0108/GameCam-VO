"""Blocked factorial statistics over three observed run blocks; no GPU execution."""
import pathlib,sys,json,csv,math,itertools,collections
import numpy as np
from analyze_repeated import ROOT,AROOT,OUT,c,m,ARMS,numeric_summary,csvout,put,sha,UTC
METRICS=['displacement_ratio_pct','absolute_gap_from_100_pct_points','endpoint_translation_rpe_game_units','endpoint_direction_error_deg','endpoint_rotation_rpe_deg','ate_sim3_game_units','ate_se3_game_units','global_fit_scale','keyframes','predecision_ba_calls','retained_ba_calls','motion_filter_rejected','local_ba_rejected','local_candidate_rejection_rate','local_motion_distance_median','U_event_medians_median','U_event_p90s_median','U_event_p95s_median','effective_weight_event_means_median','source_U_multiplier_event_means_median','ba_after_native_negative_pixel_events','ba_after_native_max_negative_in_call','ba_after_clamp_floor_pixel_events','clamp_pixel_events_from_new_floor','model_elapsed_s','peak_gpu_used_mib','peak_shm_used_bytes']+[f'offset{delta}_{q}' for delta in (1,15,60,150) for q in ('translation_rpe_raw_game_units','translation_rpe_sref_game_units','translation_rpe_sim3_game_units','rotation_rpe_rmse_deg')]

def readcsv(path):
 with pathlib.Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def fitblocked(rows,metric):
 # Seven factorial coefficients plus intercept and two seed-block offsets.
 X=[];Y=[]
 for r in rows:
  v=r.get(metric)
  if v is None or not math.isfinite(v):return dict(status='MISSING_OUTCOME',metric=metric)
  d,w,u=(2*r[k]-1 for k in ('D','W','U'))
  X.append([1,int(r['seed']==44),int(r['seed']==45),d,w,u,d*w,d*u,w*u,d*w*u]);Y.append(v)
 X=np.asarray(X,float);Y=np.asarray(Y);beta,res,rank,sv=np.linalg.lstsq(X,Y,rcond=None);err=Y-X@beta
 return dict(status='DESCRIPTIVE_SEED_BLOCKED_LINEAR_FIT',metric=metric,n_observations=len(Y),design_rank=int(rank),residual_df=len(Y)-int(rank),residual_sse=float(err@err),coefficients=dict(zip(['intercept_seed43','block44_minus43','block45_minus43','D','W','U','D:W','D:U','W:U','D:W:U'],beta.tolist())),uncertainty_method='USE_THREE_SEEDWISE_CONTRASTS_T_DF2_NOT_BA_EVENTS',no_pooled_event_significance=True)
def effects(rows):
 out=[]
 for seed in (43,44,45):
  by={r['arm']:r for r in rows if r['seed']==seed};assert set(by)==set(ARMS)
  for metric in METRICS:
   vals=[by[a].get(metric) for a in ARMS]
   if any(v is None or not math.isfinite(v) for v in vals):continue
   for n in (1,2,3):
    for ix in itertools.combinations(range(3),n):
     effect=sum(np.prod([2*c.BITS[a][i]-1 for i in ix])*by[a][metric] for a in ARMS)/4
     out.append(dict(seed=seed,metric=metric,factor=':'.join('DWU'[i] for i in ix),effect_on_minus_off=float(effect),regression_coefficient=float(effect)/2,statistical_unit='ONE_COMPLETE_SEED_BLOCK',estimand='TOTAL_FRONTEND_EFFECT'))
 return out

def run():
 assert (ROOT/'evidence/ALL_LOCAL_ARCHIVES_VERIFIED.json').is_file(),'await all16 sealed archives'
 rows=[];merged=collections.defaultdict(list);ret=[];orig=[]
 for seed in (43,44,45):
  for arm in ARMS:
   d=OUT/'runs'/('seed'+str(seed)+'_'+arm);assert (d/'COMPLETE.json').is_file()
   r=json.loads((d/'SUMMARY.json').read_text());ts=readcsv(d/'BA_TIMELINE.csv')
   candidateids={int(x['trigger_rgb_id']) for x in ts if x['stage']=='frontend_local_predecision'}
   floor_increments=[json.loads(x['clamp_grid'])['float32_floor_count']-json.loads(x['native_grid'])['float32_floor_count'] for x in ts]
   assert all(x>=0 for x in floor_increments),'unexpected reduction in clamp-floor count'
   r['clamp_pixel_events_from_new_floor']=sum(floor_increments)
   r['local_predecision_candidate_frames']=len(candidateids)
   r['local_candidate_rejection_rate']=r['local_ba_rejected']/len(candidateids) if candidateids else None
   r['local_rejected_fraction_all_motion_passed_frames']=r.pop('local_ba_rejection_rate')
   rows.append(r);ret.append(json.loads((d/'RETENTION.json').read_text()))
   for name in ('FIXED_ENDPOINTS','DIRECT_KEYFRAME_ENDPOINTS','STAGE_ENDPOINTS','RPE','BA_TIMELINE','KEYFRAME_DECISIONS','MOTION_DISTANCE','UNCERTAINTY_EVENTS','DISPARITY_EVENTS','LOCAL_PAIR_UPDATES','PER_FRAME'):merged[name].extend(readcsv(d/(name+'.csv')))
 # E0 overlap within its own run block. No cross-run KF interpolation.
 for r in rows:
  b=next(x for x in rows if x['seed']==r['seed'] and x['arm']=='E0');a=set(r['retained_kf_rgb_ids']);bkeys=set(b['retained_kf_rgb_ids']);r['common_kf_with_E0']=len(a&bkeys);r['common_kf_fraction_of_E0']=len(a&bkeys)/len(bkeys);r['common_kf_jaccard_E0']=len(a&bkeys)/len(a|bkeys)
  q=next(x for x in ret if x['seed']==r['seed'] and x['arm']==r['arm'])
  for field in ('joint_local_ba_return','joint_local_ba_return_count','both_in_pose_window_count','both_in_window_and_observed_count','direct_edge_count','rgb312_export_origin','rgb328_export_origin','rgb312_filler_temp_valid','rgb328_filler_temp_valid'):r[field]=q[field]
 # Exact reuse audit of Seed43 (re-evaluation only, no new inference).
 aold={r['arm']:r for r in json.loads((AROOT/'evaluation/RESULTS_SUMMARY.json').read_text())['arms']};reuse=[]
 for r in rows:
  if r['seed']!=43:continue
  for metric in ('ate_sim3_game_units','ate_se3_game_units','global_fit_scale','displacement_ratio_pct','absolute_gap_from_100_pct_points','keyframes'):
   gap=abs(r[metric]-aold[r['arm']][metric]);assert gap<1e-9
   reuse.append(dict(arm=r['arm'],metric=metric,previous=aold[r['arm']][metric],recomputed=r[metric],difference=gap,status='MATCH'))
 csvout(OUT/'TASK004B_SEED43_REUSE_VERIFICATION.csv',reuse)
 for seed in (44,45):csvout(OUT/('TASK004B_SEED'+str(seed)+'_RESULTS.csv'),[r for r in rows if r['seed']==seed])
 csvout(OUT/'TASK004B_24_RUN_MASTER_TABLE.csv',rows)
 csvout(OUT/'TASK004B_KEYFRAME_RETENTION_ANALYSIS.csv',[{k:v for k,v in r.items() if k in ('seed','arm','D','W','U','attempt_id','keyframes','predecision_ba_calls','retained_ba_calls','local_ba_rejected','motion_filter_rejected','local_predecision_candidate_frames','local_candidate_rejection_rate','common_kf_with_E0','common_kf_fraction_of_E0','common_kf_jaccard_E0','retained_kf_rgb_ids','rgb312_retained_kf','rgb328_retained_kf','joint_local_ba_return','joint_local_ba_return_count','both_in_pose_window_count','both_in_window_and_observed_count','direct_edge_count','rgb312_export_origin','rgb328_export_origin','rgb312_filler_temp_valid','rgb328_filler_temp_valid','local_motion_distance_median','local_motion_distance_p90','local_motion_distance_p95')} for r in rows])
 mapping=dict(FIXED_ENDPOINTS='TASK004B_FIXED_ENDPOINT_COMPARISON.csv',DIRECT_KEYFRAME_ENDPOINTS='TASK004B_DIRECT_KEYFRAME_ENDPOINTS.csv',STAGE_ENDPOINTS='TASK004B_FINAL_BA_STAGE_COMPARISON.csv',RPE='TASK004B_RPE_BY_INTERVAL.csv',BA_TIMELINE='TASK004B_LOCAL_BA_TIMELINE_COMPARISON.csv',KEYFRAME_DECISIONS='TASK004B_FRAMEWISE_KEYFRAME_DECISIONS.csv',MOTION_DISTANCE='TASK004B_FRAMEWISE_MOTION_DISTANCE.csv',UNCERTAINTY_EVENTS='TASK004B_UNCERTAINTY_EVENTS.csv',DISPARITY_EVENTS='TASK004B_DISPARITY_EVENTS.csv',LOCAL_PAIR_UPDATES='TASK004B_LOCAL_TARGET_PAIR_BA_UPDATES.csv',PER_FRAME='TASK004B_PER_FRAME_TRAJECTORY_ERRORS.csv')
 for name,filename in mapping.items():csvout(OUT/filename,merged[name])
 csvout(OUT/'TASK004B_ATE_RPE_COMPARISON.csv',[{k:v for k,v in r.items() if k in ('seed','arm','D','W','U','global_fit_scale','ate_sim3_game_units','ate_se3_game_units','gt_path_game_units','model_elapsed_s','peak_gpu_used_mib','peak_shm_used_bytes') or k.startswith('offset')} for r in rows])
 csvout(OUT/'TASK004B_UNCERTAINTY_INTERACTION_ANALYSIS.csv',[{k:v for k,v in r.items() if k in ('seed','arm','D','W','U','keyframes','ba_after_native_negative_pixel_events','ba_after_native_max_negative_in_call','ba_after_clamp_floor_pixel_events','local_ba_native_negative_pixel_events','clamp_calls_changing_grid','clamp_pixel_events_from_new_floor') or k.startswith(('U_event','effective_weight_event','source_U_multiplier_event'))} for r in rows])
 ef=effects(rows);csvout(OUT/'TASK004B_SEEDWISE_FACTORIAL_EFFECTS.csv',ef)
 summaries=[]
 for metric in METRICS:
  for arm in ARMS:
   ss=numeric_summary([r.get(metric) for r in rows if r['arm']==arm]);summaries.append(dict(arm=arm,metric=metric,**ss))
 csvout(OUT/'TASK004B_ARM_DESCRIPTIVE_STATISTICS.csv',summaries)
 aggregate=[]
 for metric,factor in sorted({(r['metric'],r['factor']) for r in ef}):
  er=[r for r in ef if r['metric']==metric and r['factor']==factor];sv={r['seed']:r['effect_on_minus_off'] for r in er};v=list(sv.values());ss=numeric_summary(v)
  aggregate.append(dict(metric=metric,factor=factor,**ss,seed43_effect=sv.get(43),seed44_effect=sv.get(44),seed45_effect=sv.get(45),same_nonzero_direction=(all(x>0 for x in v) or all(x<0 for x in v)) if len(v)==3 else None,contrast_definition='sum_product_coded_levels_times_outcome_divided_by4',statistical_unit='SEED_BLOCK',multiplicity='UNADJUSTED_DESCRIPTIVE_95CI',no_full_child_seed_control=True))
 csvout(OUT/'TASK004B_FACTORIAL_EFFECTS.csv',aggregate)
 paired=[]
 for seed in (43,44,45):
  by={r['arm']:r for r in rows if r['seed']==seed}
  for on,off in [('E0','E1'),('E2','E4'),('E3','E6'),('E7','E8')]:
   for metric in METRICS:
    x,y=by[on].get(metric),by[off].get(metric)
    if x is not None and y is not None:paired.append(dict(seed=seed,comparison='D_ON_MINUS_D_OFF',on_arm=on,off_arm=off,W=c.BITS[on][1],U=c.BITS[on][2],metric=metric,on_value=x,off_value=y,paired_difference=x-y))
  for arm in ARMS:
   if arm=='E0':continue
   for metric in METRICS:
    x,y=by[arm].get(metric),by['E0'].get(metric)
    if x is not None and y is not None:paired.append(dict(seed=seed,comparison='ARM_MINUS_E0',on_arm=arm,off_arm='E0',metric=metric,on_value=x,off_value=y,paired_difference=x-y))
 csvout(OUT/'TASK004B_SEEDWISE_PAIRED_DIFFERENCES.csv',paired)
 ps=[]
 for group in sorted({(p['comparison'],p['on_arm'],p['off_arm'],p['metric']) for p in paired}):
  rs=[p for p in paired if (p['comparison'],p['on_arm'],p['off_arm'],p['metric'])==group];pv={r['seed']:r['paired_difference'] for r in rs};v=list(pv.values())
  ps.append(dict(comparison=group[0],on_arm=group[1],off_arm=group[2],metric=group[3],**numeric_summary(v),seed43_difference=pv.get(43),seed44_difference=pv.get(44),seed45_difference=pv.get(45)))
 csvout(OUT/'TASK004B_PAIRED_DIFFERENCES_SUMMARY.csv',ps)
 fits=[fitblocked(rows,metric) for metric in METRICS];put(OUT/'TASK004B_SEED_BLOCKED_LINEAR_FIT.json',dict(models=fits,observations=24,unit='RUN',blocks=3,full_child_seed_control=False))
 # Check blocked LS factorial coefficients equal averaged seedwise contrasts / 2.
 checks=[]
 for f in fits:
  if f['status']=='MISSING_OUTCOME':continue
  for label in ('D','W','U','D:W','D:U','W:U','D:W:U'):
   q=next(x for x in aggregate if x['metric']==f['metric'] and x['factor']==label);err=abs(f['coefficients'][label]*2-q['mean']);assert err<max(1e-7,abs(q['mean'])*1e-9);checks.append(dict(metric=f['metric'],factor=label,absolute_difference=err,status='PASS'))
 put(OUT/'TASK004B_FACTORIAL_CROSSCHECK.json',dict(utc=UTC(),checks=checks,passed=len(checks),statistical_unit='THREE_COMPLETE_SEED_BLOCKS',naive_event_pseudoreplication=False))
 put(OUT/'TASK004B_RESULTS.json',dict(utc=UTC(),status='ALL_24_RUNS_EVALUATED',additional_gpu_runs=16,total_runs=24,blocks=[43,44,45],runs=rows,effects=aggregate,arm_summaries=summaries,s_ref=c.S_REF,unit='GAME_UNITS_NOT_ASSUMED_METERS',estimand='TOTAL_FRONTEND_EFFECT',randomization_limit='MAIN_SEEDED_TRACKING_SPAWN_NOT_EXTRA_RESEEDED',browser_rendering='NOT_VERIFIED_NOT_REQUIRED_BY_USER'))
 print('ALL24_CPU_STATISTICS_COMPLETE',flush=True)
if __name__=='__main__':run()

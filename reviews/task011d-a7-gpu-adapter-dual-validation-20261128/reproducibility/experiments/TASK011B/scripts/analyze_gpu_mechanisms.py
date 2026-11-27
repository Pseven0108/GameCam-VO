"""Offline trace summaries; BA calls are not independent statistical samples."""
import json
from pathlib import Path
import numpy as np
from common import TASK,csvwrite,dump

MAIN='FRONTEND_MAIN_LOOP_LOCAL_BA'


def describe(values,prefix):
    a=np.asarray(values,dtype=np.float64)
    a=a[np.isfinite(a)]
    if not len(a):return {prefix+'_n':0}
    return {prefix+'_n':len(a),prefix+'_mean':float(a.mean()),
            prefix+'_median':float(np.median(a)),prefix+'_min':float(a.min()),
            prefix+'_P90':float(np.quantile(a,.9)),prefix+'_P95':float(np.quantile(a,.95)),
            prefix+'_max':float(a.max())}


def main():
    windows=json.loads((TASK/'private/VIPER_INPUTS.json').read_text())['windows']
    base=TASK/'gpu_results/raw';out=TASK/'evaluation';out.mkdir(exist_ok=True)
    rows=[];retention=[];comparison=[];scopes=[];native_cache=[]
    for w in windows:
        sets={}
        for arm in range(7):
            aid='A'+str(arm);root=base/('window_'+w['window_id']+'_'+aid)/'result'
            if not root.exists():continue
            identity=dict(window=w['window_id'],sequence=w['sequence'],environment=w['environment'],arm=aid)
            p=root/'native_ba_calls.jsonl'
            calls=[json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
            main=[r for r in calls if r['phase']==MAIN and not r['motion_only']]
            wrong=[r for r in calls if r['intervention'] and (r['phase']!=MAIN or r['motion_only'])]
            if wrong:raise RuntimeError('Intervention escaped the approved phase')
            row=dict(**identity,BA_calls=len(calls),local_joint_calls=len(main),
                controlled_calls=sum(r['intervention'] for r in calls),
                negative_disparity_event_calls=sum(r.get('negative_before_native_outer_clamp',0)>0 for r in calls),
                negative_values_sum_over_calls=sum(r.get('negative_before_native_outer_clamp',0) for r in calls),
                exact_native_clamp_count='UNOBSERVED_NEGATIVE_VALUES_ARE_ONLY_A_LOWER_BOUND',
                BA_objective_residual_convergence='NOT_EXPORTED_UPDATE_NORMS_ARE_NOT_OBJECTIVE_VALUES')
            for field in ('U_median','U_mean','dx_l2','dz_l2','relative_reliability_mean',
                          'geometry_g_mean','geometry_g_min','geometry_g_max','geometry_u_median'):
                row.update(describe([r[field] for r in main if field in r],field))
            row.update(describe([x for r in main for x in r.get('effective_prior_mean_by_iteration',[])],
                                'local_effective_prior_mean'))
            ratios=[r['prior_effective_positive_pixels']/r['depth_variables'] for r in main if r.get('depth_variables',0)]
            row.update(describe(ratios,'local_prior_positive_fraction'))
            eligible=[r['prior_eligible_native_pixels']/r['depth_variables'] for r in main if r.get('depth_variables',0)]
            row.update(describe(eligible,'local_native_eligible_fraction'))
            vid=root/'native/video.npz'
            if vid.exists():
                with np.load(vid,allow_pickle=False) as z:
                    ts=z['timestamps'].copy();U=z['uncertainties'].copy();d=z['droid_disps'].copy()
                if not np.equal(ts,np.round(ts)).all() or not ((ts>=0)&(ts<64)).all():
                    raise RuntimeError('Invalid retained timestamp')
                sets[aid]=set(map(int,ts))
                row['retained_keyframes']=len(ts)
                row.update(describe(U.ravel(),'final_U'))
                row['final_nonpositive_disparity_pixels']=int((d<=0).sum())
                row['final_floor_value_pixels']=int((d==np.float32(1e-5)).sum())
                row['final_floor_pixels_not_total_clamp_count']=True
                for i,f in enumerate(w['rgb_frames'] if 'rgb_frames' in w else range(w['rgb_start'],w['rgb_end']+1)):
                    retention.append(dict(**identity,input_index=i,rgb_id=f,retained_final_keyframe=i in sets[aid],
                        reason_if_not_retained='NOT_SEPARATED_MOTION_FILTER_VS_LOCAL_REJECTION'))
            proof=root/'NATIVE_CACHE_EQUIVALENCE.json'
            if proof.exists():native_cache.append(dict(**identity,**json.loads(proof.read_text())))
            for phase in sorted(set(r['phase'] for r in calls)):
                own=[r for r in calls if r['phase']==phase]
                scopes.append(dict(**identity,phase=phase,calls=len(own),interventions=sum(r['intervention'] for r in own),
                    U_update_calls=sum(r['enable_update_uncer'] for r in own),UBA_calls=sum(r['enable_udba'] for r in own)))
            rows.append(row)
        for arm,own in sets.items():
            for reference in ('A0','A1'):
                if reference not in sets or arm==reference:continue
                other=sets[reference]
                comparison.append(dict(window=w['window_id'],environment=w['environment'],arm=arm,reference=reference,
                    retained_own=len(own),retained_reference=len(other),common=len(own&other),
                    union=len(own|other),jaccard=len(own&other)/len(own|other) if own|other else None,
                    own_only=sorted(own-other),reference_only=sorted(other-own)))
    csvwrite(out/'VIPER_PRIOR_U_GEOMETRY_SUMMARY.csv',rows)
    csvwrite(out/'VIPER_KEYFRAME_RETENTION.csv',retention)
    csvwrite(out/'VIPER_KEYFRAME_COMPARISON.csv',comparison)
    csvwrite(out/'VIPER_PHASE_SCOPE_AUDIT.csv',scopes)
    csvwrite(out/'VIPER_NATIVE_CACHE_EQUIVALENCE.csv',native_cache)
    metrics_path=out/'VIPER_TRAJECTORY_METRICS.csv'
    if metrics_path.exists():
        import csv
        with metrics_path.open(encoding='utf-8-sig',newline='') as f:
            metrics=list(csv.DictReader(f))
        by={(r['window'],r['arm']):r for r in metrics};controls=[]
        keys=('ate_sim3_path_pct','ate_se3_path_pct','single_global_sim3_RPE_translation',
              'single_global_sim3_RPE_rotation_deg','raw_path_ratio_abs_error','keyframes')
        for w in windows:
            a,b=by.get((w['window_id'],'A0')),by.get((w['window_id'],'A1'))
            if not a or not b:continue
            for key in keys:
                if a.get(key) in ('',None) or b.get(key) in ('',None):continue
                x,y=float(a[key]),float(b[key])
                controls.append(dict(window=w['window_id'],environment=w['environment'],metric=key,
                    original_installed_A0=x,candidate_D1_endpoint_A1=y,
                    candidate_minus_original=y-x,absolute_difference=abs(y-x),
                    mathematically_equivalent_intended_algorithms=True,
                    not_a_direct_measure_of_identical_binary_repeat_noise=True))
        csvwrite(out/'VIPER_A0_A1_CONTROL_VARIABILITY.csv',controls)
    dump(out/'MECHANISM_ANALYSIS_STATUS.json',dict(
        actual_window_results=len(rows),planned=140,all_controlled_calls_in_approved_scope=True,
        BA_calls_not_independent_repeats=True,native_live_cache_checks=len(native_cache),
        all_observed_live_cache_checks_pass=all(r['status']=='PASS' for r in native_cache),
        limitation='Residual objectives, exact below-floor clamp counts and per-rejection reasons not captured.'))
    print('ACTUAL_MECHANISM_SUMMARIES',len(rows),flush=True)


if __name__=='__main__':main()

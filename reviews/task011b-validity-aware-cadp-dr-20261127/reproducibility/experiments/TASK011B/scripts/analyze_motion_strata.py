"""Transparent GT-only sensitivity strata, never changing primary metrics.

Midpoint sampling deliberately did not use GT motion. A nearly static camera
can therefore be selected; dividing error by its roundoff-scale path is not a
meaningful accuracy claim. Retain all20 planned inputs and all original score
rows, while providing a labelled exploratory motion-stratum sensitivity table.
"""
import csv,json
import numpy as np
from common import TASK,csvwrite,dump,sha

THRESHOLD=1e-4  # native Camera units; descriptive, not an asserted physical metre


def main():
    plan=TASK/'configs/POST_SELECTION_MOTION_SENSITIVITY_AMENDMENT.json'
    if not plan.exists():raise RuntimeError('Freeze descriptive sensitivity before executing this analysis')
    config=json.loads(plan.read_text())
    if config['GT_path_threshold_native_units']!=THRESHOLD:raise RuntimeError('Sensitivity rule changed')
    with (TASK/'evaluation/VIPER_INPUT_MOTION_AND_FILE_IDENTITY.csv').open(encoding='utf-8-sig',newline='') as f:
        motion={r['window']:r for r in csv.DictReader(f)}
    with (TASK/'evaluation/VIPER_TRAJECTORY_METRICS.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=140:raise RuntimeError('Final sensitivity table requires all140 outcomes')
    tagged=[]
    for r in rows:
        path=float(motion[r['window']]['GT_path_native_units'])
        tagged.append(dict(**r,GT_path_descriptive_native_units=path,
            motion_stratum='NEAR_ZERO_TRANSLATION' if path<=THRESHOLD else 'TRANSLATING',
            original_primary_row_unchanged=True))
    measures=('ate_sim3_path_pct','ate_se3_path_pct','ate_sim3_rmse','ate_se3_rmse',
              'single_global_sim3_RPE_translation','single_global_sim3_RPE_rotation_deg',
              'raw_path_ratio_abs_error','runtime_tracking_child_seconds','keyframes')
    summaries=[];paired=[]
    for stratum in ('TRANSLATING','NEAR_ZERO_TRANSLATION'):
        windows=[w for w,x in motion.items() if (float(x['GT_path_native_units'])>THRESHOLD)==(stratum=='TRANSLATING')]
        if not windows:continue
        by={(r['window'],r['arm']):r for r in tagged if r['window'] in windows}
        for arm in ('A0','A1','A2','A3','A4','A5','A6'):
            own=[by[(w,arm)] for w in windows]
            row=dict(motion_stratum=stratum,arm=arm,planned_windows=len(windows),
                completed=sum(r['success']=='True' for r in own),failures=sum(r['success']!='True' for r in own),
                exploratory_post_selection_sensitivity=True)
            for key in measures:
                values=[float(r[key]) for r in own if r.get(key) not in ('',None)]
                row[key+'_n']=len(values);row[key+'_mean']=float(np.mean(values)) if values else None
                row[key+'_median']=float(np.median(values)) if values else None
            summaries.append(row)
        for arm,reference in [(a,b) for b in ('A0','A1') for a in ('A2','A3','A4','A5','A6')]+[('A6','A4')]:
            for key in measures:
                d=[]
                for w in windows:
                    x,y=by[(w,arm)],by[(w,reference)]
                    if x.get(key) in ('',None) or y.get(key) in ('',None):continue
                    d.append(float(x[key])-float(y[key]))
                if not d:continue
                delta=np.asarray(d);rng=np.random.default_rng(43)
                ci=np.quantile(delta[rng.integers(0,len(d),size=(3000,len(d)))].mean(1),[.025,.975]) if len(d)>1 else [None,None]
                paired.append(dict(motion_stratum=stratum,arm=arm,reference=reference,metric=key,
                    paired_sequences=len(d),mean_difference=float(delta.mean()),median_difference=float(np.median(delta)),
                    lower95=ci[0],upper95=ci[1],exploratory_post_selection_sensitivity=True,
                    original_completion_denominator_20_unchanged=True))
    csvwrite(TASK/'evaluation/VIPER_MOTION_STRATIFIED_RUNS.csv',tagged)
    csvwrite(TASK/'evaluation/VIPER_MOTION_STRATIFIED_SUMMARY.csv',summaries)
    csvwrite(TASK/'evaluation/VIPER_MOTION_STRATIFIED_PAIRED.csv',paired)
    dump(TASK/'evaluation/MOTION_SENSITIVITY_STATUS.json',dict(
        status='EXPLORATORY_GT_ONLY_SENSITIVITY_ORIGINAL_PRIMARY_PRESERVED',
        rule_sha256=sha(plan),GT_path_threshold_native_units=THRESHOLD,
        translating_windows=sum(float(x['GT_path_native_units'])>THRESHOLD for x in motion.values()),
        near_zero_translation_windows=sum(float(x['GT_path_native_units'])<=THRESHOLD for x in motion.values()),
        windows_replaced=0,additional_GPU_runs=0,all_original_primary_scores_retained=True,
        decision_not_a_preregistered_confirmatory_endpoint=True,
        strict_geometry_synergy_identifiable=False))
    print('ACTUAL_MOTION_STRATIFIED_SENSITIVITY',len(tagged),len(summaries),flush=True)


if __name__=='__main__':main()

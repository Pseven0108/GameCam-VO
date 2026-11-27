"""Descriptive paired shape/scale/rotation signs, without a new score or run."""
import csv,json
from common import TASK,csvwrite,dump


def main():
    with (TASK/'evaluation/VIPER_TRAJECTORY_METRICS.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=140:raise RuntimeError('Describe tradeoffs only after all140 outcomes')
    with (TASK/'evaluation/VIPER_INPUT_MOTION_AND_FILE_IDENTITY.csv').open(encoding='utf-8-sig',newline='') as f:
        motion={r['window']:r for r in csv.DictReader(f)}
    threshold=json.loads((TASK/'configs/POST_SELECTION_MOTION_SENSITIVITY_AMENDMENT.json').read_text())['GT_path_threshold_native_units']
    by={(r['window'],r['arm']):r for r in rows};pairs=[];summaries=[]
    fields=('ate_sim3_path_pct','raw_path_ratio_abs_error','single_global_sim3_RPE_rotation_deg')
    for arm in ('A2','A3','A4','A5','A6'):
        for reference in ('A0','A1'):
            for window in sorted(motion):
                a,b=by[(window,arm)],by[(window,reference)]
                item=dict(window=window,environment=a['environment'],arm=arm,reference=reference,
                    translating=float(motion[window]['GT_path_native_units'])>threshold,
                    both_completed=a['success']=='True' and b['success']=='True',
                    all_three_metrics_available=all(a.get(k) not in ('',None) and b.get(k) not in ('',None) for k in fields))
                if item['all_three_metrics_available']:
                    delta={k:float(a[k])-float(b[k]) for k in fields}
                    item.update({k+'_difference':v for k,v in delta.items()})
                    item.update(shape_lower=delta[fields[0]]<0,raw_scale_error_lower=delta[fields[1]]<0,
                        rotation_error_lower=delta[fields[2]]<0,
                        shape_lower_but_scale_error_higher=delta[fields[0]]<0 and delta[fields[1]]>0,
                        all_three_lower=all(v<0 for v in delta.values()))
                pairs.append(item)
            for scope in ('ALL_PRESELECTED','TRANSLATING_EXPLORATORY'):
                eligible=[r for r in pairs if r['arm']==arm and r['reference']==reference and
                    (scope=='ALL_PRESELECTED' or r['translating'])]
                available=[r for r in eligible if r['all_three_metrics_available']]
                item=dict(arm=arm,reference=reference,population=scope,planned_windows=len(eligible),
                    paired_three_metric_windows=len(available),not_a_new_composite_score=True,
                    exploratory_descriptive_signs_not_significance_test=True)
                for key in ('shape_lower','raw_scale_error_lower','rotation_error_lower',
                            'shape_lower_but_scale_error_higher','all_three_lower'):
                    item[key+'_windows']=sum(bool(r[key]) for r in available)
                summaries.append(item)
    csvwrite(TASK/'evaluation/VIPER_MULTIMETRIC_TRADEOFF_WINDOWS.csv',pairs)
    csvwrite(TASK/'evaluation/VIPER_MULTIMETRIC_TRADEOFF_SUMMARY.csv',summaries)
    dump(TASK/'evaluation/MULTIMETRIC_TRADEOFF_SCOPE.json',dict(status='DESCRIPTIVE_PAIRED_SIGNS',
        new_metric_or_hypothesis_test=False,original_scores_unchanged=True,
        failed_trajectories_not_imputed=True,near_zero_motion_stratum_not_used_to_claim_scale_improvement=True,
        no_new_GPU_runs=True))
    print('ACTUAL_MULTIMETRIC_TRADEOFFS',len(pairs),len(summaries),flush=True)


if __name__=='__main__':main()

"""Secondary paired comparison: A6 versus A4, without any new GPU run.

Both arms use the same reliability rule. This estimates the total addition of
geometry gating under tracking feedback, not a fixed-state direct effect and
not an identified geometry-by-reliability interaction (no geometry-only arm).
"""
import csv,json
import numpy as np
from common import TASK,csvwrite,dump

METRICS=(
    'ate_sim3_path_pct','ate_se3_path_pct',
    'single_global_sim3_RPE_translation','single_global_sim3_RPE_rotation_deg',
    'raw_path_ratio_abs_error','runtime_tracking_child_seconds',
    'peak_allocated_bytes','keyframes')


def main():
    with (TASK/'evaluation/VIPER_TRAJECTORY_METRICS.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=140:raise RuntimeError('Run this final secondary comparison only after all140 outcomes')
    by={(r['window'],r['arm']):r for r in rows}
    windows=json.loads((TASK/'private/VIPER_INPUTS.json').read_text())['windows']
    pairs=[];summaries=[]
    for w in windows:
        a,b=by[(w['window_id'],'A6')],by[(w['window_id'],'A4')]
        for key in METRICS:
            if a.get(key) in ('',None) or b.get(key) in ('',None):continue
            pairs.append(dict(window=w['window_id'],sequence=w['sequence'],environment=w['environment'],
                metric=key,A6=float(a[key]),A4=float(b[key]),difference_A6_minus_A4=float(a[key])-float(b[key]),
                lower_is_better=key!='keyframes',same_reliability_rule=True,
                total_geometry_gating_effect_not_fixed_state_direct_effect=True))
    for env in ('ALL','Day','Sunset','Rain','Snow','Night'):
        for key in METRICS:
            own=[r for r in pairs if r['metric']==key and (env=='ALL' or r['environment']==env)]
            if not own:continue
            delta=np.array([r['difference_A6_minus_A4'] for r in own],dtype=np.float64)
            if not np.isfinite(delta).all():raise RuntimeError('Nonfinite paired secondary metric')
            rng=np.random.default_rng(43)
            ci=np.quantile(delta[rng.integers(0,len(delta),size=(3000,len(delta)))].mean(1),[.025,.975]) if len(delta)>1 else [None,None]
            summaries.append(dict(environment=env,metric=key,paired_sequences=len(delta),
                mean_difference=float(delta.mean()),median_difference=float(np.median(delta)),
                lower95=ci[0],upper95=ci[1],wins=int((delta<0).sum()) if key!='keyframes' else None,
                losses=int((delta>0).sum()) if key!='keyframes' else None,ties=int((delta==0).sum()),
                bootstrap_unit='SOURCE_SEQUENCE_ONE_WINDOW_EACH',exploratory_not_blind=True,
                no_geometry_only_arm=True,synergy_not_identified=True))
    csvwrite(TASK/'evaluation/VIPER_A6_VS_A4_PAIRED_WINDOWS.csv',pairs)
    csvwrite(TASK/'evaluation/VIPER_A6_VS_A4_GEOMETRY_INCREMENT.csv',summaries)
    dump(TASK/'evaluation/GEOMETRY_INCREMENT_ANALYSIS_STATUS.json',dict(
        status='ACTUAL_PAIRED_SECONDARY_ANALYSIS',formal_outcomes=140,paired_rows=len(pairs),
        new_GPU_runs=0,geometry_reliability_interaction_identified=False,
        reason='No geometry-only arm; A6 versus A4 is the total effect of adding g under feedback, not a fixed-state mechanism test.'))
    print('ACTUAL_A6_A4_GEOMETRY_INCREMENT',len(pairs),len(summaries),flush=True)


if __name__=='__main__':main()

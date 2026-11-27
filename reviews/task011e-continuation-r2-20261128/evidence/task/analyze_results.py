"""Sequence-clustered paired inference and explicit failure accounting.

No embedded outcome data. Unit-test fixtures are not scientific observations.
"""
import argparse,csv,json
from collections import defaultdict
from pathlib import Path
import numpy as np
from common import TASK,csvwrite,dump

METRIC='ate_sim3_path_pct'
def failure_accounting(plan,outcomes):
    expected={(r['sequence'],int(r['seed']),r['arm']) for r in plan}
    by={}
    for r in outcomes:
        key=(r['sequence'],int(r['seed']),r['arm'])
        if key not in expected or key in by:raise ValueError('Unplanned or duplicate outcome')
        by[key]=r
    result=[]
    for arm in ('A0','A1','A4','A5','A7'):
        keys=[k for k in expected if k[2]==arm];rows=[by[k] for k in keys if k in by]
        complete=sum(r.get('status') in ('COMPLETE','COMPLETE_ALIGNMENT_DEGENERATE') for r in rows)
        initialized=sum(r.get('initialized') is True for r in rows)
        score=sum(r.get('status')=='COMPLETE' and r.get(METRIC) is not None and np.isfinite(float(r[METRIC])) for r in rows)
        result.append(dict(arm=arm,planned=len(keys),terminal=len(rows),missing=len(keys)-len(rows),
            completed=complete,initialized=initialized,ATE_scorable=score,completion_rate=complete/len(keys) if keys else None))
        result[-1].update(initialization_failed=sum(r.get('status') in ('INITIALIZATION_FAILED','TRACKING_INITIALIZATION_FAILED') for r in rows),
                          initialization_unknown=sum(r.get('initialized') is None for r in rows))
    return result

def paired_bootstrap(rows,n=10000,seed=20261128,strict=False):
    by={}
    for r in rows:
        if r['arm'] not in ('A5','A7'):continue
        key=(r['sequence'],int(r['seed']),r['arm'])
        if key in by:raise ValueError('Duplicate paired seed')
        if r.get('status')=='COMPLETE' and r.get(METRIC) is not None and np.isfinite(float(r[METRIC])):
            by[key]=float(r[METRIC])
    sequences=sorted({k[0] for k in by});pairs=[]
    for sequence in sequences:
        seeds=[s for s in (43,44,45) if (sequence,s,'A5') in by and (sequence,s,'A7') in by]
        if not seeds or (strict and len(seeds)!=3):continue
        delta=[by[sequence,s,'A5']-by[sequence,s,'A7'] for s in seeds]
        pairs.append(dict(sequence=sequence,common_seeds=seeds,paired_seed_differences=delta,
                          sequence_mean_difference=float(np.mean(delta))))
    if len(pairs)<2:return dict(status='INSUFFICIENT_SEQUENCE_CLUSTERS',sequence_pairs=pairs,independent_clusters=len(pairs),CI95=None)
    values=np.array([p['sequence_mean_difference'] for p in pairs]);rng=np.random.default_rng(seed)
    samples=values[rng.integers(0,len(values),(n,len(values)))].mean(1)
    return dict(status='CONDITIONAL_ON_COMMON_SCORABLE_SEEDS',independent_clusters=len(values),sequence_pairs=pairs,
        difference_mean=float(values.mean()),difference_median=float(np.median(values)),SD=float(values.std(ddof=1)),
        CI95=np.quantile(samples,[.025,.975]).tolist(),bootstrap_repetitions=n,bootstrap_seed=seed,
        strict_all_three_seeds=strict,negative_favours='A5',failed_errors_imputed=False)

def fsr_sequence_summary(rows):
    own=defaultdict(list)
    for r in rows:
        if r.get('experiment')!='FIXED_STATE_REPLAY':raise ValueError('Do not mix FSR with E2E')
        own[r['sequence']].append(r)
    return [dict(sequence=k,nested_BA_calls=len(v),independent_sequence_clusters=1,
        median_dx_contrast=float(np.median([r['contrasts']['dx']['A5_A7_l2'] for r in v])),
        median_dx_noise=float(np.median([r['contrasts']['dx']['A5_A5_l2'] for r in v]))) for k,v in sorted(own.items())]

def descriptive_tables(rows):
    metrics=[METRIC,'ate_sim3_rmse','ate_se3_rmse','raw_RPE_translation','raw_RPE_rotation_deg',
             'single_global_sim3_RPE_translation','single_global_sim3_RPE_rotation_deg',
             'raw_path_ratio_abs_error','runtime_tracking_child_seconds','peak_allocated_bytes']
    summary=[]
    for weather in ('ALL','Day','Sunset','Rain','Snow','Night'):
        for arm in ('A0','A1','A4','A5','A7'):
            own=[r for r in rows if r['arm']==arm and (weather=='ALL' or r.get('environment')==weather)]
            if not own:continue
            for metric in metrics:
                values=[float(r[metric]) for r in own if r.get(metric) is not None and np.isfinite(float(r[metric]))]
                summary.append(dict(environment=weather,arm=arm,metric=metric,observations=len(values),
                    independent_source_sequences=len({r['sequence'] for r in own}),
                    mean=float(np.mean(values)) if values else None,median=float(np.median(values)) if values else None,
                    SD=float(np.std(values,ddof=1)) if len(values)>1 else None,
                    minimum=min(values) if values else None,maximum=max(values) if values else None,
                    repeated_seed_descriptors_not_independent_inference=True))
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--outcomes');p.add_argument('--output');a=p.parse_args()
    if not a.outcomes:print('VALIDATE_ONLY_NO_RESULTS');return
    rows=json.loads(Path(a.outcomes).read_text());plan=list(csv.DictReader((TASK/'configs/EXECUTION_ORDER.csv').open()))
    if any(r.get('synthetic',False) for r in rows):raise ValueError('Synthetic test outcomes are not formal results')
    accounting=failure_accounting(plan,rows)
    if any(r['missing'] for r in accounting):raise ValueError('Incomplete planned study: no confirmatory aggregate on partial outcomes')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    dump(out/'FAILURE_ACCOUNTING.json',accounting)
    dump(out/'PRIMARY_PAIRED_BOOTSTRAP.json',paired_bootstrap(rows))
    dump(out/'STRICT_THREE_SEEDS_SENSITIVITY.json',paired_bootstrap(rows,strict=True))
    csvwrite(out/'DESCRIPTIVE_METHOD_WEATHER_TABLE.csv',descriptive_tables(rows))
    dump(out/'PER_WEATHER_FAILURE_ACCOUNTING.json',{w:failure_accounting([p for p in plan if p['environment']==w],[r for r in rows if r['environment']==w]) for w in ('Day','Sunset','Rain','Snow','Night')})

if __name__=='__main__':main()

"""Seed-paired pilot summaries; scenes, not BA events, are the transfer units."""
import csv
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def main():
    rows=json.loads((TASK/'07_cross_scene_evaluation/ALL_RUN_METRICS.json').read_text())
    complete=[r for r in rows if r['status']=='COMPLETE' and r['run']!='night007_dev_baseline_s43_r1']
    grouped={}
    for r in complete:grouped.setdefault((r['dataset'],r['method']),[]).append(r)
    summaries=[];pairs=[]
    metrics=['sim3_ate_native_reference_units','rpe_translation_offset1_native_reference_units',
        'rpe_rotation_offset1_deg','normalized_sim3_ate','runtime_seconds','keyframes']
    for (dataset,method),runs in sorted(grouped.items()):
        summary={'dataset':dataset,'method':method,'n_runs':len(runs),'seeds':';'.join(str(r['seed']) for r in runs)}
        for metric in metrics:
            x=np.array([r[metric] for r in runs],float)
            summary.update({metric+'_mean':float(x.mean()),metric+'_median':float(np.median(x)),
                            metric+'_sd':float(x.std(ddof=1)) if len(x)>1 else None,
                            metric+'_min':float(x.min()),metric+'_max':float(x.max())})
        base={r['seed']:r for r in grouped.get((dataset,'baseline'),[])}
        deltas=[]
        for r in runs:
            if method=='baseline' or r['seed'] not in base:continue
            b=base[r['seed']];difference=r['sim3_ate_native_reference_units']-b['sim3_ate_native_reference_units']
            deltas.append(difference)
            pairs.append({'dataset':dataset,'seed':r['seed'],'method':method,
                'baseline_ate':b['sim3_ate_native_reference_units'],'method_ate':r['sim3_ate_native_reference_units'],
                'paired_ate_difference':difference,'relative_ate_change':difference/max(b['sim3_ate_native_reference_units'],1e-12),
                'rpe_t_difference':r['rpe_translation_offset1_native_reference_units']-b['rpe_translation_offset1_native_reference_units'],
                'both_poses_complete':r['coverage']==1 and b['coverage']==1})
        if deltas:summary.update(paired_ate_difference_mean=float(np.mean(deltas)),paired_ate_wins=int(np.sum(np.array(deltas)<0)))
        summaries.append(summary)
    write_csv(TASK/'07_cross_scene_evaluation/METHOD_WINDOW_SUMMARY.csv',summaries)
    write_csv(TASK/'07_cross_scene_evaluation/SEED_PAIRED_DIFFERENCES.csv',pairs)
    (TASK/'07_cross_scene_evaluation/METHOD_WINDOW_SUMMARY.json').write_text(json.dumps(summaries,indent=2))
    gate=[]
    for run in sorted((TASK/'outputs/droid').glob('*')):
        log=run/'dynamic_fusion.jsonl'
        if not log.exists():continue
        calls=[json.loads(line) for line in log.read_text().splitlines()]
        phases=sorted(set(c.get('phase','UNVERIFIED') for c in calls))
        for phase in phases:
            subset=[c for c in calls if c.get('phase','UNVERIFIED')==phase]
            weights=[c['edges'] for c in subset]
            gate.append({'run':run.name,'phase':phase,'calls':len(subset),
                'edge_weighted_gate_mean':float(np.average([c['mean_gate'] for c in subset],weights=weights)),
                'neutral_fraction':float(np.average([c['neutral_fraction'] for c in subset],weights=weights)),
                'source_UBA_mean':float(np.average([c['source_uba_mean'] for c in subset],weights=weights)),
                'native_U_mutated_by_hook':False})
    write_csv(TASK/'01_failure_diagnosis/NEW_GATE_PHASE_SUMMARY.csv',gate)
    print(json.dumps([{'method':r['method'],'n':r['n_runs'],'ATE_mean':r['sim3_ate_native_reference_units_mean'],
        'ATE_sd':r['sim3_ate_native_reference_units_sd'],'paired_wins':r.get('paired_ate_wins')} for r in summaries if r['dataset']=='night007_dev'],indent=2))


if __name__=='__main__':main()

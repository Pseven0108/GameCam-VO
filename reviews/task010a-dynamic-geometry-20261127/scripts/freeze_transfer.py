"""Select exclusively on development, then seal every held-out run before execution."""
import hashlib
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def linux(path):return str(path).replace('D:','/mnt/d').replace(chr(92),'/')


def main():
    roster=json.loads((TASK/'private/DATA_MANIFEST.json').read_text())
    rows=json.loads((TASK/'07_cross_scene_evaluation/ALL_RUN_METRICS.json').read_text())
    if any(r.get('dataset') not in [None,'night007_dev'] for r in rows):
        raise RuntimeError('Held-out native result already present; selection must not be revised')
    source=[r for r in rows if r.get('status')=='COMPLETE' and r['run']!='night007_dev_baseline_s43_r1']
    grouped={}
    for r in source:grouped.setdefault(r['method'],[]).append(r)
    expected={'baseline','legacy','legacy_mean','neutral','gmos','geomotion','geometry','fusion','static','fusion_static','depth','depth_static','depth_fusion','geomotion_full'}
    for method in expected:
        if len(grouped.get(method,[]))!=3 or {r['seed'] for r in grouped[method]}!={43,44,45}:
            raise RuntimeError('Missing complete three-seed development method '+method)
    means={m:sum(r['sim3_ate_native_reference_units'] for r in rr)/len(rr) for m,rr in grouped.items()}
    dynamic=min(['neutral','gmos','geomotion','geomotion_full','geometry','fusion'],key=means.get)
    fused=min(['fusion_static','depth_static','depth_fusion'],key=means.get)
    candidates=['neutral','gmos','geomotion','geomotion_full','geometry','fusion','static','fusion_static','depth','depth_static','depth_fusion']
    main_candidate=min(candidates,key=means.get)
    methods=list(dict.fromkeys(['baseline','legacy',dynamic,'depth','static',fused,main_candidate]))
    datasets=[d for d in roster if d['name'] not in ['night007_dev','wildworld_thirdperson_qual']]
    jobs=[]
    def job(d,method,seed):
        jid=f"{d['name']}_{method}_s{seed}_r1"
        prior=TASK/'outputs'/('priors_blend' if method.startswith('depth') else 'priors')/d['name']
        if not (prior/'receipt.json').exists():raise RuntimeError('Missing prior cache '+str(prior))
        args=['--dataset',d['name'],'--method',method,'--seed',str(seed),'--priors',linux(prior),
            '--output',f'experiments/TASK010-A/outputs/droid/{jid}']
        if method in ('static','fusion_static','depth_static'):
            tracks=TASK/'outputs/static'/(d['name']+'_r2')
            required=['statistics.json','input_manifest.json','predictions.npz']
            if not all((tracks/name).exists() for name in required):raise RuntimeError('Missing static cache files')
            if json.loads((tracks/'statistics.json').read_text())['status']!='INDEPENDENT_INFERENCE_COMPLETE':
                raise RuntimeError('Static cache inference incomplete')
            args.extend(['--static-tracks',linux(tracks)])
        return {'id':jid,'script':'experiments/TASK010-A/scripts/run_window_v2.py','args':args}
    # Balanced repetitions for every frozen arm/window, never only winners.
    # The bounded matrix is fixed before any held-out native run or score.
    for seed in [43,44,45]:
        order_d=datasets if seed!=45 else list(reversed(datasets))
        base_order=methods if seed!=44 else list(reversed(methods))
        for index,d in enumerate(order_d):
            shift=(index+seed-43)%len(methods)
            order=base_order[shift:]+base_order[:shift]
            jobs.extend(job(d,m,seed) for m in order)
    identities={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [TASK/'scripts/run_window_v2.py',TASK/'scripts/task010_fusion_v2.py',TASK/'scripts/native_holdout_controller.py',
         TASK/'scripts/task010_native_preload.py',TASK/'scripts/run_native.sh']}
    selection={'status':'FROZEN_BEFORE_HELDOUT_NATIVE_RUNS','selection_metric':'Mean development whole-window globally Sim3-aligned ATE; seeds43/44/45',
        'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'development_means':means,'best_dynamic_candidate':dynamic,'best_fusion_candidate':fused,
        'main_confirmatory_candidate':main_candidate,'main_candidate_beats_development_baseline':means[main_candidate]<means['baseline'],
        'heldout_primary_methods':methods,'heldout_windows':[d['name'] for d in datasets],
        'all_methods_and_windows_seeds':[43,44,45],'balanced_full_matrix':True,
        'planned_native_runs':len(jobs),'heldout_metrics_read_before_selection':False,
        'source_sha256':identities,'no_parameter_changes_after_selection':True,
        'dataset_manifest_sha256':hashlib.sha256((TASK/'private/DATA_MANIFEST.json').read_bytes()).hexdigest(),
        'candidate_output_validation_sha256':hashlib.sha256((TASK/'09_reproducibility/CANDIDATE_OUTPUT_VALIDATION.json').read_bytes()).hexdigest(),
        'pilot_GO_rule':{
            'scope':'GO only for a separate future formal validation, never production acceptance',
            'all_five_game_windows_mean_ATE_lower':True,'both_real_windows_mean_ATE_lower':True,
            'main_candidate_and_baseline_all_three_seeds_complete':True,
            'mean_translation_RPE1_no_worse_in_each_domain':True,
            'mean_rotation_RPE1_no_worse_in_each_domain':True,
            'otherwise':'NO_GO_FOR_GENERALIZED_IMPROVEMENT; report local gains and regressions separately'},
        'stop_rule':'Complete this fixed comparison, include all failures, then stop tuning. No selection or parameter refit on held-out scores.'}
    public=TASK/'09_reproducibility/TRANSFER_SELECTION_FROZEN.json'
    private=TASK/'private/FORKSERVER_HOLDOUT_READY.json'
    if public.exists() or private.exists():raise RuntimeError('Selection already sealed; never overwrite')
    public.write_text(json.dumps(selection,indent=2))
    plan={'selection_record_sha256':hashlib.sha256(public.read_bytes()).hexdigest(),
        'engineering_probe_jobs':1,'jobs':[{'id':'observer_readonly_probe_holdout_r1',
            'script':'experiments/TASK010-A/scripts/observer_readonly_probe.py','args':[]},*jobs]}
    private.write_text(json.dumps(plan,indent=2))
    print(json.dumps(selection,indent=2))


if __name__=='__main__':main()

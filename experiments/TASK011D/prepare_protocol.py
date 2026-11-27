"""Freeze independent FSR/E2E designs; generate no runtime authorization."""
import ast,csv,difflib,json,shutil
from pathlib import Path
import numpy as np
from common import BASE,ROOT,TASK,csvwrite,dump,sha

def generate_driver():
    source=ROOT/'experiments/TASK011B/gpu/run_window.py';raw=source.read_text();text=raw
    changes={
      'from controller import arm_config,coefficient_map,install,MAIN':'from uniform_control import arm_config,coefficient_map,install,MAIN',
      'coefficients={}':'coefficients={};native_valid={};shadow_a5={}',
      "coefficients[r['timestamp']]=s":"coefficients[r['timestamp']]=s\n                native_valid[r['timestamp']]=np.isfinite(z['native_depth']) & (z['native_depth']>1e-6)\n                if arm=='A0':shadow_a5[r['timestamp']]=coefficient_map(z['native_depth'],z['flip_depth'][:,::-1],z['native_confidence'],z['tta_valid'],arm_config('A5'))[0]",
      "str(TASK/'build_001/task011b_cadp_dr_c3414af6.so')":"str(__import__('native_binding').verify_candidate_identity())",
      "install(self.video,candidate,arm_config(arm),coefficients,out/'native_ba_calls.jsonl',regression)":
       "if arm=='A0':\n            from collect_snapshots import SnapshotCollector,install_native_collector\n            collector=SnapshotCollector(TASK/'fixed_state/snapshots'/str(self.task_seed)/window,inputs(window)['sequence'],self.task_seed)\n            install_native_collector(self.video,collector,shadow_a5,native_valid)\n        install(self.video,candidate,arm_config(arm),coefficients,out/'native_ba_calls.jsonl',None,native_valid_by_timestamp=native_valid)",
      "p.add_argument('--arm',required=True);a=p.parse_args()":"p.add_argument('--arm',required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--approval',required=True);p.add_argument('--job-key',required=True);a=p.parse_args()\n    from authorization import require_approved_runtime\n    require_approved_runtime(a.approval,'END_TO_END',a.job_key)\n    if a.seed not in (43,44,45):raise ValueError('Unregistered seed')",
      "out=TASK/'runs'/a.window/a.arm":"out=TASK/'runs'/str(a.seed)/a.window/a.arm",
      'setup_seed(43)':'setup_seed(a.seed)',
      'model.task_arm=a.arm':'model.task_arm=a.arm;model.task_seed=a.seed',
    }
    for before,after in changes.items():
        if text.count(before)!=1:raise RuntimeError('Frozen native driver source drift at '+before[:50])
        text=text.replace(before,after)
    # Endpoint diagnostics are a separately approved future preflight, not
    # hidden extra solver calls inside A0's actual-call snapshot stream.
    begin=text.index('        regression=None\n');end=text.index("        if arm=='A0':\n            from collect_snapshots",begin)
    text=text[:begin]+text[end:]
    gate="""import argparse as _approval_argparse,os as _approval_os
from authorization import require_approved_runtime as _require_runtime
_gate_parser=_approval_argparse.ArgumentParser(add_help=False)
_gate_parser.add_argument('--approval',default=_approval_os.environ.get('TASK011D_RUNTIME_APPROVAL'))
_gate_parser.add_argument('--job-key',default=_approval_os.environ.get('TASK011D_RUNTIME_JOB'))
_gate_parser.add_argument('--window')
_gate_parser.add_argument('--arm')
_gate_parser.add_argument('--seed',type=int)
_gate_args,_=_gate_parser.parse_known_args()
_require_runtime(_gate_args.approval,'END_TO_END',_gate_args.job_key)
from authorization import verify_requested_job as _verify_requested_job
_verify_requested_job('END_TO_END',_gate_args.job_key,_gate_args.window,_gate_args.arm,_gate_args.seed)
from native_binding import verify_upstream_source as _verify_upstream
_verify_upstream()
"""
    text=gate+text
    ast.parse(text)
    (TASK/'native_driver.py').write_text(text,encoding='utf-8')
    (TASK/'reports/NATIVE_DRIVER_ADAPTER_DIFF.patch').write_text(''.join(difflib.unified_diff(raw.splitlines(True),text.splitlines(True),fromfile='TASK011B frozen run_window.py',tofile='TASK011D native_driver.py')),encoding='utf-8')
    # The optional prior-cache command is also guarded and otherwise uses the
    # exact frozen native preprocessing/autocast and no-RNG-advance contract.
    p=ROOT/'experiments/TASK011B/gpu/cache_priors.py';text=p.read_text()
    text=text.replace("p.add_argument('--window',required=True);a=p.parse_args()",
        "p.add_argument('--window',required=True);p.add_argument('--approval',required=True);p.add_argument('--job-key',required=True);a=p.parse_args()\n    from authorization import require_approved_runtime\n    require_approved_runtime(a.approval,'PRIOR_CACHE',a.job_key)")
    text=gate.replace("'END_TO_END'","'PRIOR_CACHE'")+text
    ast.parse(text);(TASK/'cache_priors.py').write_text(text,encoding='utf-8')
    dump(TASK/'configs/NATIVE_DRIVER_PROVENANCE.json',dict(source=str(source.relative_to(ROOT)),source_sha256=sha(source),
        candidate_sha256=sha(TASK/'native_driver.py'),native_driver_executed=False,CUDA_or_Cpp_changed=False,
        changes='Task-local inputs/output paths, seed argument, A7 routing, A0 read-only snapshot observer, explicit authorization; separate endpoint diagnostics'))

def threshold_proposals():
    root=Path('D:/aaa/GameCam-VO-TASK011B/experiments/TASK011B/evaluation')
    rows=list(csv.DictReader((root/'VIPER_TRAJECTORY_METRICS.csv').open()))
    by={(r['window'],r['arm']):r for r in rows};output=[]
    for metric,unit,floor in [('raw_path_ratio_abs_error','dimensionless absolute difference',.10),
            ('single_global_sim3_RPE_translation','native camera units',.01),
            ('single_global_sim3_RPE_rotation_deg','degrees',.10),
            ('runtime_tracking_child_seconds','relative overhead fraction',.20)]:
        diffs=[]
        for window in sorted({r['window'] for r in rows}):
            a,b=by.get((window,'A0')),by.get((window,'A1'))
            if not a or not b or not a.get(metric) or not b.get(metric):continue
            if not a.get('gt_path_length') or float(a['gt_path_length'])<=.0001:continue
            v=abs(float(b[metric])-float(a[metric]))
            if metric=='runtime_tracking_child_seconds':v/=max(float(a[metric]),1e-12)
            diffs.append(v)
        q=float(np.quantile(diffs,.95)) if diffs else None
        output.append(dict(metric=metric,unit=unit,paired_baseline_sequences=len(diffs),historical_A0_A1_abs_diff_P95=q,
            proposed_margin=max(floor,2*q) if q is not None else floor,practical_floor_proposal=floor,
            rule='max(proposed practical floor, 2 * historical endpoint-control P95)',approved=False,
            caveat='Endpoint implementation/trajectory variability, not identical-binary repeat noise; proposal only'))
    csvwrite(TASK/'reports/SECONDARY_THRESHOLD_PROPOSALS.csv',output)
    dump(TASK/'reports/THRESHOLD_SOURCE_PROVENANCE.json',dict(source_sha256=sha(root/'VIPER_TRAJECTORY_METRICS.csv'),
        TASK011D_results_used=False,thresholds_approved=False,runtime_A0_validation_and_capture_costs_require_separate_reporting=True))
    return output

def main():
    if json.loads((TASK/'data/DATA_ADMISSION_DECISION.json').read_text())['status']!='PASS_WITH_HISTORICAL_EXPOSURE':raise RuntimeError('Stage2 not accepted')
    master=json.loads((TASK/'configs/GPU_INPUTS.json').read_text())
    rgb=[]
    for w in master['windows']:
        rgb.append({k:v for k,v in w.items() if k not in ('raw_GT','frames_manifest','frames')})
        rgb[-1]['frames']=w['frames_manifest']
    dump(TASK/'configs/GPU_RGB_INPUTS.json',dict(windows=rgb,pose_GT_input=False,depth_GT_input=False))
    jobs=[];rng=np.random.default_rng(20261128)
    for seed in (43,44,45):
        for index in rng.permutation(len(rgb)):
            w=rgb[int(index)]
            for arm in rng.permutation(['A0','A1','A4','A5','A7']):
                jobs.append(dict(order=len(jobs)+1,sequence=w['sequence'],window=w['window_id'],environment=w['environment'],
                    seed=seed,arm=str(arm),job_key=f"s{seed}_{w['window_id']}_{arm}"))
    csvwrite(TASK/'configs/EXECUTION_ORDER.csv',jobs)
    for arm in ('A0','A1','A4','A5'):
        dest=TASK/'configs/arms'/f'{arm}.json';dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'experiments/TASK011B/CADP_DR_CONFIGS'/dest.name,dest)
    shutil.copy2(ROOT/'experiments/TASK011C/configs/arms/A7.json',TASK/'configs/arms/A7.json')
    binary=Path('D:/aaa/GameCam-VO-TASK011B/experiments/TASK011B/intake/CANDIDATE_BINARY_MIDBATCH_IDENTITY.json')
    dump(TASK/'configs/NATIVE_EXTENSION_IDENTITY.json',json.loads(binary.read_text()))
    import subprocess,hashlib
    upstream=Path('D:/aaa/GameCam-VO-TASK009/external/DROID-W');commit='c3414af6047d06bafc1a6645d09f23247f3b2cdc'
    paths=subprocess.check_output(['git','-C',str(upstream),'ls-tree','-r','--name-only',commit,'src','configs'],text=True).splitlines()
    files=[]
    for rel in paths:
        if not rel.endswith(('.py','.yaml','.yml')):continue
        raw=subprocess.check_output(['git','-C',str(upstream),'show',commit+':'+rel])
        files.append(dict(path=rel,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    dump(TASK/'configs/UPSTREAM_PYTHON_IDENTITY.json',dict(commit=commit,files=files,model_not_loaded=True))
    shared=dict(seeds=[43,44,45],arms=['A0','A1','A4','A5','A7'],windows=19,frames=64,stride=1,
        buffer=500,input_hw=[360,640],alpha=.01,mean_absolute_tolerance=1e-6,
        original_R2_yaml_sha256=sha(TASK/'configs/frozen_r2.yaml'),geometry_need=False,
        route='A',historical_full_sequence_baseline_exposure=True,blind_validation=False)
    dump(TASK/'configs/FIXED_STATE_PROTOCOL.json',dict(**shared,reference_arm='A0',
        reference_runs=57,reference_runs_are_subset_of_285=True,all_eligible_local_BA_calls=True,
        phases=['FRONTEND_MAIN_LOOP_LOCAL_BA'],exclude_motion_only=True,require_metric_depth_reg=True,
        branches=['A5_first','A7','A5_repeat'],independent_30_argument_clones=True,preserve_alias_layout=True,
        restore_all_RNG_before_each_branch=True,native_U_updates_preserved=True,produce_full_trajectory=False,
        numerical_noise_near_contrast_warning_ratio=.5,noise_warning_not_a_significance_threshold=True,
        ATE_RPE=False,BA_calls_are_nested=True,local_smaller_update_is_not_accuracy=True,
        snapshot_allocation='full native 30 arguments; unique-storage preflight before every write',
        snapshot_safety_free_bytes=10*1024**3,real_snapshot_sizes_and_call_counts='UNKNOWN_UNTIL_APPROVED_A0_CAPTURE'))
    dump(TASK/'configs/END_TO_END_PROTOCOL.json',dict(**shared,planned_runs=285,
        independent_initialization=True,independent_keyframes_and_BA_history=True,shared_intermediate_states=False,
        cross_trajectory_callwise_means_equal=False,primary_metric='100 * global Sim3 ATE_RMSE / offline GT path length',
        contrast='A5 minus A7; negative favours A5',bootstrap_cluster='SOURCE_SEQUENCE',bootstrap_repetitions=10000,
        bootstrap_seed=20261128,confidence_level=.95,within_sequence='mean paired differences on common scorable seeds',
        strict_sensitivity='all three common seeds',failure_errors_imputed=False,
        completion_noninferiority_margin_percentage_points=5,secondary_thresholds_approved=False,
        A0_capture_and_cache_validation_overhead_separately_logged=True,serial=True,no_automatic_retries=True))
    proposals=threshold_proposals();generate_driver()
    configs=[p for p in sorted((TASK/'configs').rglob('*')) if p.is_file() and p.name!='FROZEN_EXPERIMENT_PROTOCOL.json']
    dump(TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json',dict(task='TASK011D',status='PREREGISTRATION_FROZEN_REVIEW_REQUIRED',
        **shared,planned_E2E_runs=285,formal_SLAM_runs_authorized_now=0,
        bootstrap_seed=20261128,execution_order_seed=20261128,secondary_thresholds_approved=False,
        future_runtime_requires_explicit_user_authorization=True,
        files=[dict(path=p.relative_to(TASK).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in configs]))
    print(json.dumps(dict(status='PROTOCOL_FROZEN_FOR_REVIEW',jobs=len(jobs),FSR_reference_runs=57,
        native_BA_calls_now=0,secondary_thresholds='PROPOSED_NOT_APPROVED')))

if __name__=='__main__':main()

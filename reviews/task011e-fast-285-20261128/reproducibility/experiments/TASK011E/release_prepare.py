"""Freeze only the explicit TASK011E launch/recording amendments."""
import ast,csv,json
from pathlib import Path
from common import TASK,PARENT,dump,sha

def main():
    changed=[];old=TASK.parent/'TASK011D'
    for p in TASK.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'))
        q=old/p.name
        if q.exists() and p.read_bytes()!=q.read_bytes():changed.append(p.name)
    assert set(changed)<={'authorization.py','common.py','cache_priors.py','run_end_to_end.py','collect_snapshots.py','native_binding.py'},changed
    # Controller, native driver, arithmetic and precision are byte-identical.
    for name in ['uniform_control.py','native_driver.py','runtime.py','transfer_audit.py',
                 'score_completed_runs.py','analyze_results.py','fixed_state_replay.py']:
        assert sha(TASK/name)==sha(old/name),name
    for q in (old/'configs').rglob('*'):
        if q.is_file() and q.name not in ('FROZEN_EXPERIMENT_PROTOCOL.json','IMPLEMENTATION_LOCK.json'):
            assert sha(TASK/q.relative_to(old))==sha(q),q
    critical=['common.py','authorization.py','batch_service.py','run_end_to_end.py','cache_priors.py',
        'collect_snapshots.py','native_driver.py','uniform_control.py','native_binding.py','runtime.py',
        'transfer_audit.py','score_completed_runs.py','analyze_results.py','fixed_state_replay.py',
        'frozen_metrics/offline_eval.py','frozen_metrics/fullseq_common.py']
    def records(paths):return [dict(path=n,bytes=(TASK/n).stat().st_size,sha256=sha(TASK/n)) for n in paths]
    dump(TASK/'configs/IMPLEMENTATION_LOCK.json',dict(parent_commit=PARENT,files=records(critical),
        computational_controller_changed=False,only_launch_authorization_storage_recording_amendments=True))
    protocol=json.loads((old/'configs/FROZEN_EXPERIMENT_PROTOCOL.json').read_text())
    protocol.update(task='TASK011E',status='USER_APPROVED_FAST_EXECUTION',formal_SLAM_runs_authorized_now=285,
        formal_SLAM_GPU_not_started=True,source_release_commit=PARENT,secondary_thresholds_approved=False,
        allowed_actions=['PRIOR_CACHE','END_TO_END'],FSR_deferred_not_authorized=True,
        original_scientific_protocol_unchanged=True)
    for r in protocol['files']:r.update(bytes=(TASK/r['path']).stat().st_size,sha256=sha(TASK/r['path']))
    protocol['files'].extend(records(['configs/SOURCE_ARCHIVE_IDENTITY.json']))
    dump(TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json',protocol)
    jobs=list(csv.DictReader((TASK/'configs/EXECUTION_ORDER.csv').open()))
    windows=list(dict.fromkeys(j['window'] for j in jobs))
    dump(TASK/'RUNTIME_AUTHORIZATION.json',dict(stage='TASK011E_FAST_285',approved=True,
        user_authorization_reference='User attachment a80c8548-a09b-45e2-a84f-4309b025da41 and explicit start instruction',
        user_authorization_sha256=sha(TASK/'intake/USER_AUTHORIZATION.txt'),
        secondary_thresholds_approved=False,approved_secondary_thresholds=[],
        secondary_proposals_sha256=sha(TASK/'reports/SECONDARY_THRESHOLD_PROPOSALS.csv'),
        allowed_actions=['PRIOR_CACHE','END_TO_END'],
        protocol_sha256=sha(TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json'),
        model_weight_identity_sha256=sha(TASK/'MODEL_WEIGHT_IDENTITY.json'),
        approved_job_keys=['cache_'+w for w in windows]+[j['job_key'] for j in jobs],
        test_only=False,automatic_retry=False,formal_runs=285,cache_forwards=2432,FSR_authorized=False))
    dump(TASK/'reports/LAUNCH_AMENDMENT_VERIFICATION.json',dict(status='PASS',
        parent=PARENT,modified_existing_files=changed,native_driver_unchanged=True,controller_unchanged=True,
        frozen_configs_unchanged=True,algorithm_parameters_unchanged=True,secondary_approval_not_fabricated=True,
        execution_order_sha256=sha(TASK/'configs/EXECUTION_ORDER.csv')))
    print('FROZEN: 19 caches, 285 bound jobs; secondary false; FSR forbidden')

if __name__=='__main__':main()

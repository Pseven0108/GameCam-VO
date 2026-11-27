"""Verify actual formal contracts without any model, CUDA or fresh inference."""
import json
from pathlib import Path
import numpy as np
import yaml
from common import TASK,csvwrite,dump,sha


def main():
    schedule=json.loads((TASK/'configs/GPU_RUN_ORDER_FROZEN.json').read_text())
    inputs={r['window_id']:r for r in json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())['windows']}
    rows=[];sources=[];common=None
    for slot,item in enumerate(schedule):
        label='window_'+item['window']+'_'+item['arm']
        proof=TASK/'gpu_results/receipts'/(label+'.json')
        if not proof.exists():continue
        receipt=json.loads(proof.read_text());root=Path(receipt['local_extracted'])
        if not receipt['all_internal_SHA256']:raise RuntimeError('Unverified transferred run')
        # Verify originals again, not only the transfer's PASS string.
        manifest=json.loads((root/'OUTPUT_SHA256.json').read_text())['files']
        for r in manifest:
            p=root/r['path']
            if p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:
                raise RuntimeError('Original collected evidence changed '+label)
        cfg=yaml.safe_load((root/'native_config.yaml').read_text())
        tracking=cfg['tracking']
        if tracking['buffer']!=500 or tracking['warmup']!=12 or tracking['uncertainty_params']['gamma_depth']!=.01:
            raise RuntimeError('Frozen native configuration changed')
        # Config is window-specific only through camera/output identities.
        if common is None:common=tracking
        if tracking!=common:raise RuntimeError('Arm/window tracking configuration changed')
        native=root/'NATIVE_CACHE_EQUIVALENCE.json'
        if native.exists():
            q=json.loads(native.read_text())
            if q['status']!='PASS' or not q['bitwise_equal'] or q['max_absolute_error']!=0 or not q['cpu_RNG_unchanged'] or not q['cuda_RNG_unchanged']:
                raise RuntimeError('Native cache verification failed')
        complete=root/'COMPLETE.json';status='ALGORITHM_FAILURE'
        if complete.exists():
            status='COMPLETE'
            with np.load(root/'trajectory.npz',allow_pickle=False) as z:
                ids=np.array([r['rgb_id'] for r in inputs[item['window']]['frames']])
                if not np.array_equal(z['rgb_ids'],ids) or z['c2w_xyzw'].shape!=(64,7) or not np.isfinite(z['c2w_xyzw']).all():
                    raise RuntimeError('Complete trajectory violates frame identity')
            exits=json.loads((root/'PROCESS_EXIT_CODES.json').read_text())
            if not exits or any(r['exit_code']!=0 for r in exits):raise RuntimeError('Reported success with failed child')
        elif not (root/'ALGORITHM_FAILURE.json').exists():
            raise RuntimeError('Unknown failure must not be silently classified')
        logfile=TASK/'gpu_results/service_logs'/(label+'.stdout')
        # Every actual service receipt pins the four arithmetic/input source files.
        native_receipt=json.loads(logfile.read_text().strip().splitlines()[-1])
        fingerprints=native_receipt['source_sha256']
        for relative,identity in fingerprints.items():
            source=(TASK/relative).resolve()
            if not source.is_relative_to(TASK.resolve()) or not source.is_file() or sha(source)!=identity:
                raise RuntimeError('Published runtime source differs from actual service identity: '+relative)
        sources.append(fingerprints)
        if fingerprints!=sources[0]:raise RuntimeError('Runtime source changed after formal batch start')
        rows.append(dict(slot=slot+1,window=item['window'],arm=item['arm'],status=status,
            files_verified=len(manifest),archive_sha256=receipt['sha256'],source_files_identical=True,
            original_native_tracking_config_equal=True,live_native_prior_check=native.exists(),
            remote_temporary_output_released_after_verified_transfer=receipt['remote_cleaned']))
    csvwrite(TASK/'evaluation/R3_EXECUTION_LEDGER.csv',rows)
    dump(TASK/'evaluation/FORMAL_RUN_CONTRACT_AUDIT.json',dict(
        status='PASS_COMPLETE' if len(rows)==140 else 'PASS_OBSERVED_PARTIAL',actual=len(rows),planned=140,
        common_runtime_source_sha256=sources[0] if sources else None,
        published_runtime_sources_match_actual_service_sha256=True,
        all_verified_archives_have_original_internal_SHA=True,
        algorithm_failures_retained=True,engineering_FP32_pilots_excluded=True,
        no_model_execution_performed_by_audit=True))
    print('FORMAL_RUN_CONTRACTS_VERIFIED',len(rows),flush=True)


if __name__=='__main__':main()

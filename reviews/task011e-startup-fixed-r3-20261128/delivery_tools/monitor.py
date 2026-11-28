"""Compact read-only observation; no launch, retry, or process signalling."""
import datetime
import json
from pathlib import Path
from remote_control import BASE,REMOTE,remote

CODE=r'''
from pathlib import Path
import json,shutil,subprocess,time
root=Path(REMOTE);task=root/'repo/experiments/TASK011E'
result=dict(when_unix=time.time(),disk_free_bytes=shutil.disk_usage(task).free)
for name in ('BATCH_CHECKPOINT.json','BATCH_STOPPED.json','BATCH_TERMINAL.json','CANARY_ENGINEERING_HEALTH.json','CACHE_REUSE_RECEIPT.json'):
    path=task/name
    if path.exists():result[name]=json.loads(path.read_text())
result['service_tail']=(root/'SERVICE.log').read_text()[-1800:]
attempts=sorted((task/'execution_ledger').glob('*/ATTEMPT.json'),key=lambda path:path.stat().st_mtime)
terminals=[json.loads(path.read_text()) for path in (task/'execution_ledger').glob('*/TERMINAL.json')]
result['attempted']=len(attempts);result['terminal']=len(terminals)
result['complete']=sum(row['status']=='COMPLETE' for row in terminals)
result['initialization_failed']=sum(row['status']=='INITIALIZATION_FAILED' for row in terminals)
result['engineering_failed']=sum(row['status']=='ENGINEERING_FAILURE' for row in terminals)
if attempts:
    latest=json.loads(attempts[-1].read_text());result['latest_job']=latest
    out=task/'runs'/str(latest['seed'])/latest['window']/latest['arm']
    result['latest_files']=[p.name for p in out.iterdir()] if out.exists() else []
    for name in ('CHILD_STAGE.json','CHILD_ENTERED.json','CHILD_EXCEPTION.json','CHILD_PROCESS_FAILURE.json','TRACKING_CHILD_COMPLETE.json'):
        path=out/name
        if path.exists():result[name]=json.loads(path.read_text())
    result['native_ba_calls']=sum(1 for _ in (out/'native_ba_calls.jsonl').open()) if (out/'native_ba_calls.jsonl').exists() else 0
    error=attempts[-1].parent/'stderr.txt';result['latest_stderr_tail']=error.read_text()[-4500:] if error.exists() else None
    std=attempts[-1].parent/'stdout.txt';result['latest_stdout_tail']=std.read_text()[-1800:] if std.exists() else None
snapshots=list((task/'fixed_state').rglob('*.pt')) if (task/'fixed_state').exists() else []
result['snapshots']=len(snapshots);result['snapshot_bytes']=sum(p.stat().st_size for p in snapshots)
result['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.free','--format=csv,noheader'],text=True).strip()
result['gpu_apps']=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader'],text=True).strip()
print(json.dumps(result))
'''.replace('REMOTE',repr(REMOTE))


def main():
    data=remote(CODE,timeout=50);value=json.loads(data)
    (BASE/'progress').mkdir(exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (BASE/'progress'/f'{stamp}.json').write_bytes(data)
    (BASE/'LATEST_PROGRESS.json').write_bytes(data)
    path=Path('D:/aaa/GameCam-VO/experiments/TASK011E_CURRENT_STATUS.json')
    state=json.loads(path.read_text(encoding='utf-8'))
    state.update(status='RUNNING_R3' if not value.get('BATCH_STOPPED.json') else 'STOPPED_R3',
        attempt='GAMECAM_TASK011E_FAST_20261128_R3',remote_root=REMOTE,local_operation_directory=str(BASE),
        current_experiment_running=not(value.get('BATCH_STOPPED.json') or value.get('BATCH_TERMINAL.json')),
        E2E_attempted=value['attempted'],E2E_terminal=value['terminal'],E2E_complete=value['complete'],
        E2E_engineering_failed=value['engineering_failed'],E2E_initialization_failed=value['initialization_failed'],
        E2E_not_attempted=285-value['attempted'],automatic_retries=0,
        CPU_candidate_applied=True,CPU_candidate_tests_passed=11,explicit_retry_approved=True,
        resume_requires_runtime_fix_and_explicit_retry_approval=False,server_shutdown_command_executed=False,
        server_shutdown_pending=True,server_shutdown_status='REOPENED_RUNNING_R3',
        server_ssh_connection_closed=False,disk_free_bytes=value['disk_free_bytes'],last_verified_unix=value['when_unix'])
    path.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(value,ensure_ascii=True,indent=2))


if __name__=='__main__':main()

"""Create an isolated explicitly approved retry; preserve sealed R1/R2."""
import ast
import hashlib
import json
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
OLD = BASE.parent/'TASK011E_CONTINUATION_R2_20261128'
ORIGINAL = OLD/'repo/experiments/TASK011E'
TASK = BASE/'repo/experiments/TASK011E'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    if TASK.exists():
        raise FileExistsError('Do not replace an existing prepared retry')
    TASK.mkdir(parents=True)
    for folder in ('configs', 'reports', 'intake', 'frozen_metrics'):
        shutil.copytree(ORIGINAL/folder, TASK/folder,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for path in ORIGINAL.glob('*.py'):
        shutil.copy2(path, TASK/path.name)
    shutil.copy2(ORIGINAL/'MODEL_WEIGHT_IDENTITY.json', TASK/'MODEL_WEIGHT_IDENTITY.json')
    for path in (OLD/'startup_import_fix_candidate').glob('*.py'):
        shutil.copy2(path, TASK/path.name)
    for name in ('spawn_supervisor.py', 'process_launcher.py'):
        shutil.copy2(BASE/name, TASK/name)

    auth = (TASK/'authorization.py').read_text(encoding='utf-8')
    auth = auth.replace('TASK011E_FAST_285_CONTINUATION_R2', 'TASK011E_FAST_285_CONTINUATION_R3')
    marker = "x.get('cache_continuation_state_sha256')==sha(TASK/'configs/CACHE_CONTINUATION_STATE.json'),"
    assert auth.count(marker) == 1
    auth = auth.replace(marker, marker+"\n        x.get('retry_authorization_sha256')==sha(TASK/'intake/RETRY_AUTHORIZATION.txt'),")
    (TASK/'authorization.py').write_text(auth, encoding='utf-8')

    driver = (TASK/'native_driver.py').read_text(encoding='utf-8')
    marker = '    torch.multiprocessing.Process=remember_process\n    try:model.run()\n    finally:\n        torch.multiprocessing.Process=old_process'
    assert driver.count(marker) == 1
    driver = driver.replace(marker,
        '    torch.multiprocessing.Process=remember_process\n'
        '    from spawn_supervisor import start_child_watchdog\n'
        '    child_watch_stop,child_watch_thread=start_child_watchdog(processes,out)\n'
        '    try:model.run()\n'
        '    finally:\n'
        '        child_watch_stop.set();child_watch_thread.join(timeout=2)\n'
        '        torch.multiprocessing.Process=old_process')
    (TASK/'native_driver.py').write_text(driver, encoding='utf-8')

    runner = (TASK/'run_end_to_end.py').read_text(encoding='utf-8')
    marker = "            code=subprocess.run(command,stdout=stdout,stderr=stderr,env=env,\n                cwd='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/source/DROID-W').returncode"
    assert runner.count(marker) == 1
    runner = runner.replace(marker,
        "            from process_launcher import run_native\n"
        "            code=run_native(command,stdout,stderr,env,\n"
        "                cwd='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/source/DROID-W',\n"
        "                audit=out/'PROCESS_GROUP_RECEIPT.json')")
    (TASK/'run_end_to_end.py').write_text(runner, encoding='utf-8')

    # All priors are reused as immutable evidence; no more model forwards.
    service = '''"""Validate 19 sealed common caches, then run the frozen E2E order."""
import argparse,json,os,subprocess,sys,time,traceback
from pathlib import Path
from common import TASK,dump,csvwrite
from run_end_to_end import validate_plan
from cache_validation import validate_cache

def main(approval):
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        HF_HOME='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/huggingface',
        HUGGINGFACE_HUB_CACHE='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/huggingface/hub',
        TORCH_HOME='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub',
        OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',MPLBACKEND='Agg',
        MPLCONFIGDIR=str(TASK/'tmp/matplotlib'),TMPDIR=str(TASK/'tmp'))
    (TASK/'tmp').mkdir(exist_ok=True);os.environ.update(env)
    complete=[]
    for window in dict.fromkeys(j['window'] for j in validate_plan()):
        complete.append(validate_cache(window));print('CACHE_REUSED',window,flush=True)
    assert len(complete)==19
    csvwrite(TASK/'CACHE_MANIFEST.csv',complete)
    dump(TASK/'CACHE_REUSE_RECEIPT.json',dict(status='ALL_19_REVERIFIED',frames=1216,
        model_forwards_this_attempt=0,source_attempt='GAMECAM_TASK011E_FAST_20261128_R2'))
    result=subprocess.run([sys.executable,'-B',str(TASK/'run_end_to_end.py'),'--execute','--approval',approval],cwd=TASK,env=env)
    if result.returncode:raise RuntimeError('E2E stopped; preserve failure, no automatic retry or skip')
    dump(TASK/'BATCH_TERMINAL.json',dict(status='ALL_285_TERMINAL',caches=19,E2E=285,FSR=0,finished_unix=time.time()))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--approval',required=True);args=parser.parse_args()
    try:main(str(Path(args.approval).resolve()))
    except BaseException as error:
        dump(TASK/'BATCH_STOPPED.json',dict(status='STOPPED',error=str(error),traceback=traceback.format_exc(),
             automatic_retry=False,history_deleted=False,when_unix=time.time()))
        traceback.print_exc();sys.exit(1)
'''
    (TASK/'batch_service.py').write_text(service, encoding='utf-8')
    original_service = (ORIGINAL/'batch_service.py').read_text(encoding='utf-8')
    validation = original_service[original_service.index('def validate_cache('):original_service.index('\ndef main(')]
    (TASK/'cache_validation.py').write_text('import json\nfrom common import TASK,sha\n\n'+validation, encoding='utf-8')

    (TASK/'intake/RETRY_AUTHORIZATION.txt').write_text(
        '2026-11-28 Asia/Shanghai\nUser: 修复，然后自己重跑实验\n'
        'Scope: repair the TASK011E spawn import collision and owned-child failure handling; '
        'explicitly retry the first engineering-failed job in a new isolated attempt; '
        'continue the existing frozen 285-job serial order. '
        'Preserve sealed R1/R2, weights, source, parameters, cache and all failures. '
        'No automatic retry of a new engineering failure.\n', encoding='utf-8')

    changed=[]
    for path in TASK.rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'))
        old = ORIGINAL/path.relative_to(TASK)
        if not old.exists() or sha(old)!=sha(path):changed.append(path.relative_to(TASK).as_posix())
    allowed={'authorization.py','native_binding.py','native_driver.py','run_end_to_end.py','batch_service.py',
             'task011e_io.py','spawn_supervisor.py','process_launcher.py','cache_validation.py'}
    assert set(changed)==allowed, changed
    for name in ('runtime.py','uniform_control.py','collect_snapshots.py','score_completed_runs.py','analyze_results.py'):
        assert sha(TASK/name)==sha(ORIGINAL/name)
    lock=json.loads((TASK/'configs/IMPLEMENTATION_LOCK.json').read_text(encoding='utf-8'))
    paths=list(dict.fromkeys([r['path'] for r in lock['files']]+sorted(allowed)))
    lock['files']=[dict(path=n,bytes=(TASK/n).stat().st_size,sha256=sha(TASK/n)) for n in paths]
    lock.update(retry_stage='R3',changes_are_startup_supervision_only=True,original_BA_changed=False)
    dump(TASK/'configs/IMPLEMENTATION_LOCK.json',lock)
    protocol_path=TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json'
    protocol=json.loads(protocol_path.read_text(encoding='utf-8'))
    for entry in protocol['files']:
        entry.update(bytes=(TASK/entry['path']).stat().st_size,sha256=sha(TASK/entry['path']))
    protocol.update(status='USER_APPROVED_ENGINEERING_RETRY_R3',scientific_protocol_changed=False)
    dump(protocol_path,protocol)
    authorization=json.loads((ORIGINAL/'RUNTIME_AUTHORIZATION.json').read_text(encoding='utf-8'))
    authorization.update(stage='TASK011E_FAST_285_CONTINUATION_R3',
        user_authorization_reference='Original frozen TASK011E + explicit user 2026-11-28: 修复，然后自己重跑实验',
        retry_authorization_sha256=sha(TASK/'intake/RETRY_AUTHORIZATION.txt'),
        protocol_sha256=sha(protocol_path),explicit_retry_of_sealed_engineering_failure=True,
        sealed_previous_attempt='GAMECAM_TASK011E_FAST_20261128_R2')
    dump(TASK/'RUNTIME_AUTHORIZATION.json',authorization)
    dump(BASE/'PREPARATION_RECEIPT.json',dict(status='PREPARED_NOT_LAUNCHED',modified_or_new=sorted(changed),
        execution_order_sha256=sha(TASK/'configs/EXECUTION_ORDER.csv'),
        runtime_approval_sha256=sha(TASK/'RUNTIME_AUTHORIZATION.json'),
        original_extension_or_baseline_changed=False,prior_attempt_preserved=True))
    print(json.dumps(dict(status='PREPARED',startup_changes=sorted(changed))))


if __name__=='__main__':main()

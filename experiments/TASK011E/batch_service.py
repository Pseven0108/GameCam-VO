"""Serial cache -> frozen 15-job canary -> remaining 270. No automatic retries."""
import argparse,json,os,subprocess,sys,time,traceback,shutil
from pathlib import Path
from common import TASK,dump,sha,csvwrite
from authorization import require_approved_runtime
from run_end_to_end import validate_plan

def validate_cache(window):
    root=TASK/'cache'/window;p=root/'CACHE_RECEIPT.json'
    if not p.is_file():raise RuntimeError('UNFINISHED_CACHE_ATTEMPT: '+window)
    m=json.loads(p.read_text())
    if not(m['status']=='COMPLETE' and m['frames']==64 and m['model_forwards']==128 and m['native_forward_RNG_unchanged']
           and m['precision_protocol']=='NATIVE_MOTION_FILTER_AUTOCAST_V2' and m['autocast_enabled']
           and m['autocast_dtype']=='torch.float16' and m['input_preprocess_device']=='cpu'):
        raise RuntimeError('Cache precision/RNG contract mismatch')
    if [r['timestamp'] for r in m['records']]!=list(range(64)):raise RuntimeError('Cache incomplete')
    for r in m['records']:
        q=root/f"{r['timestamp']:05d}.npz"
        if q.stat().st_size!=r['bytes'] or sha(q)!=r['sha256']:raise RuntimeError('Cache SHA mismatch')
    return dict(window=window,status='COMPLETE',frames=64,model_forwards=128,
                bytes=sum(r['bytes'] for r in m['records']),receipt_sha256=sha(p),seconds=m['seconds'])

def main(approval):
    jobs=validate_plan();windows=list(dict.fromkeys(j['window'] for j in jobs));complete=[]
    continuation=json.loads((TASK/'configs/CACHE_CONTINUATION_STATE.json').read_text())
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        HF_HOME='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/huggingface',
        HUGGINGFACE_HUB_CACHE='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/huggingface/hub',
        TORCH_HOME='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data/torch_hub',
        OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',MPLBACKEND='Agg',
        MPLCONFIGDIR=str(TASK/'tmp/matplotlib'),TMPDIR=str(TASK/'tmp'))
    (TASK/'tmp').mkdir(exist_ok=True)
    os.environ.update(env)
    logs=TASK/'cache_execution';logs.mkdir(exist_ok=True)
    for window in windows:
        key='cache_'+window;require_approved_runtime(approval,'PRIOR_CACHE',key)
        attempt=logs/(key+'_ATTEMPT.json');terminal=logs/(key+'_TERMINAL.json')
        if attempt.exists():
            if not terminal.exists() or json.loads(terminal.read_text())['status']!='COMPLETE':
                raise RuntimeError('UNFINISHED/FAILED_CACHE_ATTEMPT: no automatic retry')
        elif window in continuation['complete_receipt_sha256']:
            m=validate_cache(window)
            if m['receipt_sha256']!=continuation['complete_receipt_sha256'][window]:raise RuntimeError('Reused complete cache receipt drift')
            dump(attempt,dict(status='REUSED_VERIFIED_COMPLETE_CACHE',window=window,source=continuation['source_root'],model_forwards_this_attempt=0))
            dump(terminal,dict(**m,source_attempt_preserved=True,model_forwards_this_attempt=0))
            print('CACHE_REUSED',window,flush=True)
        else:
            if shutil.disk_usage(TASK).free<10*1024**3:raise RuntimeError('STORAGE_BLOCKED')
            resume=window==continuation['partial_window']
            if (TASK/'cache'/window).exists() and not resume:raise RuntimeError('Unregistered existing cache')
            dump(attempt,dict(status='STARTED',window=window,started_unix=time.time(),automatic_retry=False))
            print('CACHE_START',window,flush=True)
            with (logs/(key+'_stdout.txt')).open('wb') as out,(logs/(key+'_stderr.txt')).open('wb') as err:
                cmd=[sys.executable,'-B',str(TASK/'cache_priors.py'),'--window',window,'--approval',approval,'--job-key',key]
                if resume:cmd+=['--resume-prefix']
                code=subprocess.run(cmd,stdout=out,stderr=err,env=env,
                    cwd='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/source/DROID-W').returncode
            if code:
                dump(terminal,dict(status='ENGINEERING_FAILURE',window=window,exit_code=code,automatic_retry=False))
                raise RuntimeError('Cache failed; entire batch stopped: '+window)
            m=validate_cache(window);dump(terminal,dict(**m,finished_unix=time.time()))
        complete.append(validate_cache(window));csvwrite(TASK/'CACHE_MANIFEST.csv',complete)
        dump(TASK/'BATCH_CHECKPOINT.json',dict(status='GENERATING_CACHES',complete_caches=len(complete),
            planned_caches=19,planned_E2E=285,terminal=0,updated_unix=time.time()))
        print('CACHE_COMPLETE',len(complete),window,flush=True)
    assert len(complete)==19
    code=subprocess.run([sys.executable,'-B',str(TASK/'run_end_to_end.py'),'--execute','--approval',approval],
        cwd=TASK,env=env).returncode
    if code:raise RuntimeError('E2E stopped; no retry/skip')
    dump(TASK/'BATCH_TERMINAL.json',dict(status='ALL_285_TERMINAL',caches=19,E2E=285,FSR=0,finished_unix=time.time()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--approval',required=True);a=p.parse_args()
    try:main(str(Path(a.approval).resolve()))
    except BaseException as error:
        dump(TASK/'BATCH_STOPPED.json',dict(status='STOPPED',error=str(error),traceback=traceback.format_exc(),
            automatic_retry=False,history_deleted=False,when_unix=time.time()))
        traceback.print_exc();sys.exit(1)

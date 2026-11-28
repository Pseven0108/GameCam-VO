"""Validate 19 sealed common caches, then run the frozen E2E order."""
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

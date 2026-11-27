"""One serial GPU job, with persistent receipt even if SSH disconnects."""
import argparse,json,os,shutil,subprocess,time
from pathlib import Path
from runtime import TASK,FRESH,write,sha


def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['cache','window']);p.add_argument('window');p.add_argument('--arm');a=p.parse_args()
    label=a.kind+'_'+a.window+('_'+a.arm if a.arm else '')
    source_record={n:sha(TASK/n) for n in ['gpu/run_window.py','gpu/cache_priors.py','gpu/runtime.py','CADP_DR_EXPERIMENTAL_BRANCH/controller.py']}
    receipt=TASK/'job_receipts'/(label+'.json')
    if receipt.exists():raise FileExistsError('No automatic repeat of an existing GPU job')
    if shutil.disk_usage(TASK).free<10*1024**3+600*1024**2:raise RuntimeError('Storage reserve would be breached')
    script='cache_priors.py' if a.kind=='cache' else 'run_window.py'
    cmd=['/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python','-u','-B',str(TASK/'gpu'/script),'--window',a.window]
    if a.arm:cmd+=['--arm',a.arm]
    env=dict(os.environ,PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(TASK/'tmp'),
        HF_HOME=str(FRESH/'data/huggingface'),HF_HUB_OFFLINE='1',
        HUGGINGFACE_HUB_CACHE=str(FRESH/'data/huggingface/hub'),TORCH_HOME=str(FRESH/'data/torch_hub'),
        MPLCONFIGDIR=str(TASK/'tmp/matplotlib'),MPLBACKEND='Agg')
    log=TASK/'logs'/(label+'.log');start=time.perf_counter()
    write(receipt,dict(status='STARTED',service_pid=os.getpid(),kind=a.kind,window=a.window,arm=a.arm))
    with log.open('xb') as f:
        child=subprocess.Popen(cmd,cwd=FRESH/'source/DROID-W',env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        write(receipt,dict(status='RUNNING',service_pid=os.getpid(),child_pid=child.pid,kind=a.kind,window=a.window,arm=a.arm))
        code=child.wait()
    algorithm_failure=(TASK/'runs'/a.window/str(a.arm)/'ALGORITHM_FAILURE.json').exists() if a.kind=='window' else False
    value=dict(status='COMPLETE' if code==0 else ('ALGORITHM_FAILURE' if algorithm_failure else 'FAILED'),returncode=code,service_pid=os.getpid(),child_pid=child.pid,
        kind=a.kind,window=a.window,arm=a.arm,seconds=time.perf_counter()-start,source_sha256=source_record)
    write(receipt,value);print(json.dumps(value),flush=True)
    raise SystemExit(0 if algorithm_failure else code)


if __name__=='__main__':main()

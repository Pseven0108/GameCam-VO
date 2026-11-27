"""Serial, inspectable local GPU jobs. Stops on failure; never silently retries."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import shutil
import psutil

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
PYTHON='D:/aaa/envs/gamecam-vo/python.exe'


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);a=p.parse_args()
    jobs=json.loads(a.plan.read_text());state={'plan':str(a.plan),'status':'STARTED','jobs':[]}
    statepath=TASK/'private'/(a.plan.stem+'_STATE.json')
    env=dict(os.environ,TEMP='D:/aaa/tmp/gamecam-vo',TMP='D:/aaa/tmp/gamecam-vo',
             TORCH_HOME='D:/aaa/caches/torch',HF_HOME='D:/aaa/caches/huggingface',
             OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MPLCONFIGDIR='D:/aaa/caches/task010a/matplotlib',PYTHONUTF8='1')
    for job in jobs:
        if shutil.disk_usage(ROOT).free<15*1024**3:raise RuntimeError('D: safety reserve below 15 GiB')
        record={'id':job['id'],'command':job['command'],'status':'RUNNING','started':time.time()}
        gpu=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free,utilization.gpu',
                            '--format=csv,noheader'],capture_output=True,text=True)
        record['gpu_preflight']=gpu.stdout.strip() if gpu.returncode==0 else 'QUERY_FAILED'
        state['jobs'].append(record);statepath.write_text(json.dumps(state,indent=2))
        log=TASK/'private'/('job_'+job['id']+'.log')
        if log.exists():raise RuntimeError('Existing job log; explicit new attempt required')
        print('START_JOB',job['id'],flush=True)
        with log.open('w',encoding='utf-8') as f:
            proc=subprocess.Popen(job['command'],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
            record['launcher_pid']=proc.pid;statepath.write_text(json.dumps(state,indent=2))
            with (TASK/'private'/('resources_'+job['id']+'.jsonl')).open('w') as monitor:
                while proc.poll() is None:
                    q=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True)
                    monitor.write(json.dumps({'elapsed':time.time()-record['started'],'gpu_memory_used_MiB_and_utilization_percent':q.stdout.strip(),
                        'host_cpu_percent':psutil.cpu_percent(),'scope':'whole local host/card, includes desktop and other processes'})+'\n');monitor.flush()
                    time.sleep(1)
        record.update(exit_code=proc.returncode,seconds=time.time()-record['started'],status='COMPLETE' if proc.returncode==0 else 'FAILED')
        if proc.returncode:
            state['status']='STOPPED_ON_FAILURE';statepath.write_text(json.dumps(state,indent=2));print('FAILED_JOB',job['id'],flush=True);sys.exit(proc.returncode)
        statepath.write_text(json.dumps(state,indent=2));print('END_JOB',job['id'],record['seconds'],flush=True)
    state['status']='COMPLETE';statepath.write_text(json.dumps(state,indent=2))


if __name__=='__main__':main()

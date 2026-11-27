"""Independent serial E2E execution. Default command only validates the plan."""
import argparse,csv,json,os,subprocess,sys
from pathlib import Path
from common import ROOT,TASK,dump,sha
from authorization import require_approved_runtime

def load_jobs():
    return list(csv.DictReader((TASK/'configs/EXECUTION_ORDER.csv').open()))

def validate_plan():
    jobs=load_jobs();seen=set()
    for j in jobs:
        key=(j['sequence'],int(j['seed']),j['arm'])
        if key in seen or j['arm'] not in ('A0','A1','A4','A5','A7') or int(j['seed']) not in (43,44,45):raise ValueError('Invalid factorial job')
        seen.add(key)
    if len(seen)!=285:raise ValueError('Expected 285 independent jobs')
    return jobs

def execute_job(job,approval,driver=None):
    require_approved_runtime(approval,'END_TO_END',job['job_key'])
    out=TASK/'execution_ledger'/job['job_key'];out.mkdir(parents=True,exist_ok=False)
    dump(out/'ATTEMPT.json',dict(status='STARTED',**job,automatic_retry=False))
    if driver is None:
        if sys.platform!='linux':raise RuntimeError('Formal native model runs require approved Linux RTX3090 environment')
        import torch
        if '3090' not in torch.cuda.get_device_name(0):raise RuntimeError('Formal GPU tier must be RTX3090')
        free,total=torch.cuda.mem_get_info()
        if free<23000*1024**2:raise RuntimeError('Insufficient unoccupied formal GPU capacity')
        from native_binding import verify_candidate_identity
        verify_candidate_identity()
        command=[sys.executable,'-B',str(TASK/'native_driver.py'),'--window',job['window'],
                 '--arm',job['arm'],'--seed',str(job['seed']),'--approval',str(Path(approval).resolve()),'--job-key',job['job_key']]
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TASK011D_RUNTIME_APPROVAL=str(Path(approval).resolve()),TASK011D_RUNTIME_JOB=job['job_key'])
        with (out/'stdout.txt').open('wb') as stdout,(out/'stderr.txt').open('wb') as stderr:
            code=subprocess.run(command,stdout=stdout,stderr=stderr,env=env).returncode
        run=TASK/'runs'/str(job['seed'])/job['window']/job['arm']
        if code==0 and (run/'COMPLETE.json').is_file():result=dict(status='COMPLETE',initialized=True)
        elif (run/'ALGORITHM_FAILURE.json').is_file():result=dict(status='INITIALIZATION_FAILED',initialized=False)
        else:result=dict(status='ENGINEERING_FAILURE',initialized=None,exit_code=code)
    else:result=driver(job,out)  # CPU unit-test injection only; no default synthetic results
    result.update(sequence=job['sequence'],environment=job['environment'],seed=int(job['seed']),arm=job['arm'],job_key=job['job_key'])
    dump(out/'TERMINAL.json',result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--approval');p.add_argument('--job-key');a=p.parse_args()
    jobs=validate_plan()
    if not a.execute:print(json.dumps(dict(status='VALIDATE_ONLY',planned=len(jobs),GPU_not_started=True)));return
    chosen=[j for j in jobs if j['job_key']==a.job_key] if a.job_key else jobs
    if not chosen:raise ValueError('Unknown job')
    for job in chosen:
        r=execute_job(job,a.approval)
        if r['status']=='ENGINEERING_FAILURE':raise RuntimeError('Batch stopped; no skip or retry')

if __name__=='__main__':main()

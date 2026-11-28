"""Independent serial E2E execution. Default command only validates the plan."""
import argparse,csv,json,os,subprocess,sys,shutil,time,traceback
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

def verify_terminal(job):
    out=TASK/'execution_ledger'/job['job_key']
    attempt=out/'ATTEMPT.json';terminal=out/'TERMINAL.json'
    if not out.exists():return None
    if not attempt.exists() or not terminal.exists():raise RuntimeError('UNFINISHED_ATTEMPT: '+job['job_key'])
    receipt=json.loads(terminal.read_text())
    if receipt['status']=='ENGINEERING_FAILURE':raise RuntimeError('Prior engineering failure; no automatic retry/skip')
    if receipt['job_key']!=job['job_key']:raise RuntimeError('Terminal identity mismatch')
    for r in receipt['artifacts']:
        p=TASK/r['path']
        if not p.is_file() or p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:
            raise RuntimeError('Terminal evidence hash changed: '+r['path'])
    return receipt

def artifact_manifest(job,out):
    roots=[out,TASK/'runs'/str(job['seed'])/job['window']/job['arm']]
    records=[]
    for root in roots:
        if root.exists():
            for p in sorted(root.rglob('*')):
                if p.is_file() and p.name!='TERMINAL.json':
                    records.append(dict(path=p.relative_to(TASK).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
    if job['arm']=='A0':
        root=TASK/'fixed_state/snapshots'/str(job['seed'])/job['window'];index=root/'SNAPSHOT_INDEX.jsonl'
        if index.exists():
            records.append(dict(path=index.relative_to(TASK).as_posix(),bytes=index.stat().st_size,sha256=sha(index)))
            for line in index.read_text().splitlines():
                r=json.loads(line);p=root/r['path']
                records.append(dict(path=p.relative_to(TASK).as_posix(),bytes=r['bytes'],sha256=r['sha256']))
    return records

def execute_job(job,approval,driver=None):
    require_approved_runtime(approval,'END_TO_END',job['job_key'])
    existing=verify_terminal(job)
    if existing:return existing
    if shutil.disk_usage(TASK).free<10*1024**3:raise RuntimeError('STORAGE_BLOCKED before next attempt')
    out=TASK/'execution_ledger'/job['job_key'];out.mkdir(parents=True,exist_ok=False)
    dump(out/'ATTEMPT.json',dict(status='STARTED',**job,automatic_retry=False,started_unix=time.time(),
         protocol_sha256=sha(TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json'),
         approval_sha256=sha(approval)))
    try:
      if driver is None:
        if sys.platform!='linux':raise RuntimeError('Formal native model runs require approved Linux RTX3090 environment')
        gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.free','--format=csv,noheader,nounits'],text=True).strip()
        if '3090' not in gpu or int(gpu.rsplit(',',1)[1].strip())<23000:raise RuntimeError('GPU identity/capacity changed')
        if subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip():
            raise RuntimeError('Another CUDA process present; do not compete or terminate it')
        from native_binding import verify_candidate_identity
        verify_candidate_identity()
        command=[sys.executable,'-B',str(TASK/'native_driver.py'),'--window',job['window'],
                 '--arm',job['arm'],'--seed',str(job['seed']),'--approval',str(Path(approval).resolve()),'--job-key',job['job_key']]
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TASK011D_RUNTIME_APPROVAL=str(Path(approval).resolve()),TASK011D_RUNTIME_JOB=job['job_key'])
        with (out/'stdout.txt').open('wb') as stdout,(out/'stderr.txt').open('wb') as stderr:
            from process_launcher import run_native
            code=run_native(command,stdout,stderr,env,
                cwd='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/source/DROID-W',
                audit=out/'PROCESS_GROUP_RECEIPT.json')
        run=TASK/'runs'/str(job['seed'])/job['window']/job['arm']
        if code==0 and (run/'COMPLETE.json').is_file():result=dict(status='COMPLETE',initialized=True)
        elif (run/'ALGORITHM_FAILURE.json').is_file():result=dict(status='INITIALIZATION_FAILED',initialized=False)
        else:result=dict(status='ENGINEERING_FAILURE',initialized=None,exit_code=code)
      else:result=driver(job,out)  # CPU test injection only; never formal synthetic outcomes
    except Exception as error:
        dump(out/'LAUNCH_EXCEPTION.json',dict(type=type(error).__name__,error=str(error),traceback=traceback.format_exc()))
        result=dict(status='ENGINEERING_FAILURE',initialized=None,error=str(error))
    result.update(sequence=job['sequence'],environment=job['environment'],seed=int(job['seed']),arm=job['arm'],job_key=job['job_key'])
    result.update(finished_unix=time.time(),artifacts=artifact_manifest(job,out))
    dump(out/'TERMINAL.json',result)
    return result

def checkpoint(plan,completed,status):
    rows=[]
    for j in plan:
        p=TASK/'execution_ledger'/j['job_key']/'TERMINAL.json'
        if p.exists():
            x=json.loads(p.read_text());rows.append({k:v for k,v in x.items() if k!='artifacts'})
    from common import csvwrite
    csvwrite(TASK/'E2E_EXECUTION_LEDGER.csv',rows,fields=['sequence','environment','seed','arm','job_key','status','initialized','finished_unix','exit_code','error'])
    dump(TASK/'BATCH_CHECKPOINT.json',dict(status=status,planned=len(plan),terminal=len(rows),
        checkpoint_after_order=completed,canary_terminal=sum(r['job_key'] in {j['job_key'] for j in plan[:15]} for r in rows),
        canary_engineering_only=True,secondary_thresholds_approved=False,updated_unix=time.time(),
        automatic_retries=0,FSR_runs=0))

def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--approval');p.add_argument('--job-key');a=p.parse_args()
    jobs=validate_plan()
    if not a.execute:print(json.dumps(dict(status='VALIDATE_ONLY',planned=len(jobs),GPU_not_started=True)));return
    chosen=[j for j in jobs if j['job_key']==a.job_key] if a.job_key else jobs
    if not chosen:raise ValueError('Unknown job')
    for job in chosen:
        r=execute_job(job,a.approval)
        order=int(job['order'])
        print('E2E_TERMINAL',order,job['job_key'],r['status'],flush=True)
        if order%5==0 or r['status']=='ENGINEERING_FAILURE':checkpoint(jobs,order,'STOPPED' if r['status']=='ENGINEERING_FAILURE' else 'RUNNING')
        if r['status']=='ENGINEERING_FAILURE':raise RuntimeError('Batch stopped; no skip or retry')
        if order==15:
            if not all(verify_terminal(j) for j in jobs[:15]):raise RuntimeError('Canary terminal receipt missing')
            dump(TASK/'CANARY_ENGINEERING_HEALTH.json',dict(status='PASS',jobs=15,performance_used_for_decision=False,continue_remaining=270))
    if not a.job_key:checkpoint(jobs,285,'ALL_285_TERMINAL')

if __name__=='__main__':main()

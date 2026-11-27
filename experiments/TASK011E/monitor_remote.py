"""Compact pinned-SSH progress read; never starts or retries a job."""
import json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,'D:/aaa/GameCam-VO-TASK011D/experiments/TASK011D')
from publish_review import command

CODE=r'''
from pathlib import Path
import json,subprocess,shutil,time
root=Path('/root/rivermind-data/GAMECAM_TASK011E_FAST_20261128_R1');t=root/'repo/experiments/TASK011E'
r=dict(when_unix=time.time(),disk_free_bytes=shutil.disk_usage(t).free)
for n in ['BATCH_CHECKPOINT.json','BATCH_STOPPED.json','BATCH_TERMINAL.json','CANARY_ENGINEERING_HEALTH.json']:
 p=t/n
 if p.exists():r[n]=json.loads(p.read_text())
r['service_log']=(root/'SERVICE.log').read_text()[-3000:]
caches=[]
for p in sorted((t/'cache').glob('*')):
 if p.is_dir():
  files=list(p.glob('*.npz'));caches.append(dict(window=p.name,frames=len(files),bytes=sum(f.stat().st_size for f in files),complete=(p/'CACHE_RECEIPT.json').exists()))
r['caches']=caches
attempts=sorted((t/'cache_execution').glob('*_ATTEMPT.json'),key=lambda p:p.stat().st_mtime)
if attempts:
 name=attempts[-1].name.replace('_ATTEMPT.json','_stderr.txt');p=t/'cache_execution'/name
 r['latest_cache_stderr']=p.read_text()[-3000:] if p.exists() else None
job_attempts=sorted((t/'execution_ledger').glob('*/ATTEMPT.json'),key=lambda p:p.stat().st_mtime) if (t/'execution_ledger').exists() else []
r['E2E_attempts']=len(job_attempts);r['E2E_terminal']=len(list((t/'execution_ledger').glob('*/TERMINAL.json')))
if job_attempts:
 a=job_attempts[-1];r['latest_job']=json.loads(a.read_text());err=a.parent/'stderr.txt'
 r['latest_job_stderr']=err.read_text()[-5000:] if err.exists() else None
g=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used','--format=csv,noheader'],capture_output=True,text=True)
r['gpu']=g.stdout.strip();r['GPU_query_rc']=g.returncode
print(json.dumps(r))
'''

if __name__=='__main__':
    p=subprocess.run(command(CODE),capture_output=True,timeout=35,creationflags=subprocess.CREATE_NO_WINDOW)
    if p.returncode:raise RuntimeError('Read-only progress query failed: '+p.stderr.decode('utf-8','replace')[-1000:])
    x=json.loads(p.stdout);task=Path(__file__).resolve().parent
    with (task/'private/PROGRESS_READS.jsonl').open('ab') as f:f.write(p.stdout.rstrip()+b'\n')
    print(json.dumps(x,indent=2))

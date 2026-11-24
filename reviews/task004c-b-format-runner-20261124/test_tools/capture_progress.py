import json,pathlib,subprocess,shutil,time
from remote_cpu import ROOT,call
code=r'''
import json,pathlib,subprocess,shutil,time,os
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1')
d={'time':time.time(),'disk_free':shutil.disk_usage(r).free}
for q in (r/'attempts/capture',r/'C0'):
 d[str(q.relative_to(r))]={'exists':q.exists(),'files':len(list(q.rglob('*'))) if q.exists() else 0,'bytes':sum(p.stat().st_size for p in q.rglob('*') if p.is_file()) if q.exists() else 0}
for name in ('C0_EXACT_BUDGET_BEFORE_SAVE.json','C0_LIVE_CLOSURE_INVENTORY.json'):
 q=r/name if name.startswith('C0_EXACT') else r/'evidence'/name
 if q.exists():
  z=json.loads(q.read_text());d[name]={k:v for k,v in z.items() if k not in ('families','storages','objects','files','tensors','family_inventory','storage_inventory')}
for name in ('C0_RECEIPT.json','SUCCESS.json','PROCESS_RECEIPT.json'):
 q=r/'attempts/capture'/name
 if q.exists():d[name]=json.loads(q.read_text())
d['processes']=subprocess.run(['ps','-eo','pid,ppid,etimes,pcpu,pmem,stat,comm'],capture_output=True,text=True).stdout[-5000:]
p=r/'attempts/capture/native_trace.jsonl'
if p.exists():d['trace_tail']=p.read_text()[-3500:]
print(json.dumps(d))
'''
print(call('CAPTURE_SAVE_PROGRESS_R2',code,timeout=120))

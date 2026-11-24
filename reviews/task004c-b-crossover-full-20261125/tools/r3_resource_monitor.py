import json
from remote import ROOT,call
code=r'''
import pathlib,subprocess,json,os,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE')
script=r/'resource_monitor.py'
text="""import pathlib,time,json,subprocess,shutil,os
r=pathlib.Path(__file__).resolve().parent
with (r/'evidence/RESOURCE_TIMELINE.jsonl').open('x',buffering=1) as f:
 while not (r/'evidence/RESOURCE_MONITOR_STOP').exists():
  gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20)
  stages=[]
  for p in (r/'attempts').iterdir():
   if p.name=='capture' or not p.is_dir() or (p/'PROCESS_RECEIPT.json').exists():continue
   stages.append(p.name)
  row={'unix':time.time(),'stages_in_progress':stages,'gpu_csv':gpu.stdout.strip(),'gpu_exit':gpu.returncode,'disk_free_bytes':shutil.disk_usage(r).free,'shm_used_bytes':shutil.disk_usage('/dev/shm').used,'shm_free_bytes':shutil.disk_usage('/dev/shm').free}
  for name,where in [('cgroup_current','/sys/fs/cgroup/memory.current'),('cgroup_peak','/sys/fs/cgroup/memory.peak')]:
   try:row[name]=int(pathlib.Path(where).read_text())
   except OSError:pass
  f.write(json.dumps(row)+'\\n');time.sleep(5)
"""
assert not script.exists();script.write_text(text)
with (r/'evidence/RESOURCE_MONITOR.stdout.txt').open('xb') as of,(r/'evidence/RESOURCE_MONITOR.stderr.txt').open('xb') as ef:
 p=subprocess.Popen(['/usr/bin/python3','-B','-u',str(script)],env=dict(os.environ,CUDA_VISIBLE_DEVICES=''),stdout=of,stderr=ef,start_new_session=True)
report={'pid':p.pid,'start_unix':time.time(),'models_imported':False,'period_s':5,'shutdown_authorized':False}
(r/'evidence/RESOURCE_MONITOR_STARTED.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
'''
print(json.dumps(call('R3_RESOURCE_MONITOR_START',code,timeout=90),indent=2))

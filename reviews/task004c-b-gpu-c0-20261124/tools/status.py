import json,sys
from remote_cpu import call
label=sys.argv[1]
code=r'''
import pathlib,json,collections,shutil
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_20261124_R1');o=r/'attempts/capture'
d={'attempt_exists':o.is_dir(),'disk_free':shutil.disk_usage(r).free,'C0_exists':(r/'C0').is_dir()}
for name in ['PROCESS_STARTED.json','PROCESS_RECEIPT.json','C0_RECEIPT.json','SUCCESS.json']:
 p=o/name
 if p.is_file():d[name]=json.loads(p.read_text())
for name in ['process.stdout.txt','process.stderr.txt','native_trace.jsonl','resource_samples.jsonl']:
 p=o/name
 if p.is_file():
  with p.open('rb') as f:f.seek(max(0,p.stat().st_size-6000));d[name]=f.read().decode(errors='replace')[-4500:]
print(json.dumps(d))
'''
print(call(label,code,timeout=30))

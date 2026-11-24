import sys,json
from remote_cpu import ROOT,call
label,mode=sys.argv[1:]
code=r'''
import json,pathlib,subprocess,sys,shutil,time
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1');mode=json.load(sys.stdin)['mode']
out=r/'attempts'/mode;log=r/'artifacts'/('STAGE_'+mode)
files=['LAUNCH_INTENT.json','PROCESS_RECEIPT.json','SUCCESS.json','C0_RECEIPT.json','RESTORE_RECEIPT.json','process.stdout.txt','process.stderr.txt']
data={'mode':mode,'data_free_bytes':shutil.disk_usage(r).free,'gpu':subprocess.run(['nvidia-smi','--query-gpu=name,memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True).stdout,'attempts':{x.name:sorted(y.name for y in x.iterdir()) for x in (r/'attempts').iterdir() if x.is_dir()}}
for f in files:
 p=out/f
 if p.is_file():data[f]=p.read_text()[-7000:]
for f in ('stderr.txt','stdout.txt','RECEIPT.json'):
 p=log/f
 if p.is_file():data['wrapper_'+f]=p.read_text()[-4000:]
print(json.dumps(data))
'''
out=call(label,code,input_bytes=json.dumps({'mode':mode}).encode(),timeout=120)
(ROOT/'evidence'/(label+'.json')).write_text(out);print(out)

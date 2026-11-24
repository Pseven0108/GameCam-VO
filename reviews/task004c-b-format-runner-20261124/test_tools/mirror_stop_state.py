import base64,json,hashlib
from remote_cpu import ROOT,call
files={}
for name in ('state/STAGE_LEDGER.json','TASK004C_B_AUTONOMOUS_RUN_STATE.json'):
 raw=(ROOT/'review_original_v2'/name).read_bytes();files[name]={'b64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()}
code=r'''
import base64,hashlib,json,pathlib,sys
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1');items=json.load(sys.stdin);done=[]
for name,row in items.items():
 p=r/name;assert p.resolve().is_relative_to(r.resolve()) and not p.exists()
 p.parent.mkdir(parents=True,exist_ok=True);raw=base64.b64decode(row['b64'],validate=True);assert hashlib.sha256(raw).hexdigest()==row['sha256']
 with p.open('xb') as f:f.write(raw)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'];done.append(name)
print(json.dumps({'frozen_stop_ledger_saved':done,'no_gpu_stage_launched':True}))
'''
print(call('STOP_STATE_LEDGER_MIRROR_R1',code,input_bytes=json.dumps(files).encode(),timeout=60))

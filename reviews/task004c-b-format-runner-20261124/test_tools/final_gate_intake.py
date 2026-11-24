"""Read-only final gate inputs and inherited policy discovery."""
import base64,json
from remote_cpu import ROOT,call
code=r'''
import base64,json,pathlib,shutil,subprocess
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1');s=r/'source_candidate'
lock=json.loads((r/'configs/identity_lock.json').read_text())
base=pathlib.Path('/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/release')
policies=[]
for p in base.rglob('*.json'):
 if p.stat().st_size<10000:
  try:
   d=json.loads(p.read_text())
   if d.get('schema')=='GAMECAM_TASK004_PHASE_POLICY_V1' and d.get('arm')=='E0':policies.append({'path':str(p),'doc':d})
  except (ValueError,UnicodeError):pass
result={'gpu':subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True).stdout,'data_disk':dict(zip(('total','used','free'),shutil.disk_usage(r))),
 'policy_candidates':policies,'lock':lock,'source_commit':subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD'],text=True).strip(),
 'source_files':{n:base64.b64encode((s/n).read_bytes()).decode() for n in ('run.py','src/slam.py','src/depth_video.py')}}
print(json.dumps(result))
'''
a=json.loads(call('FINAL_RUNNER_GATE_INTAKE_R1',code,timeout=120))
(ROOT/'evidence/FINAL_RUNNER_GATE_INTAKE.json').write_text(json.dumps({k:v for k,v in a.items() if k!='source_files'},indent=2))
for n,b in a['source_files'].items():
 p=ROOT/'source_intake'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(b,validate=True))
print(json.dumps({k:v for k,v in a.items() if k not in ('lock','source_files')},indent=2))

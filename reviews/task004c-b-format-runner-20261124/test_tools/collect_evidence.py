import base64,hashlib,json,pathlib,sys
from remote_cpu import ROOT,call
label=sys.argv[1]
code=r'''
import base64,hashlib,json,pathlib,subprocess
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1')
selected={}
for folder in ('evidence','configs','operational','cpu_tests','artifacts','attempts'):
 for p in (r/folder).rglob('*'):
  if not p.is_file() or p.is_symlink():continue
  rel=p.relative_to(r)
  if any(x in rel.parts for x in ('shared_cpu','corrected_cpu_snapshot','snapshot_evidence','__pycache__')):continue
  if p.suffix.lower() not in ('.json','.jsonl','.txt','.md','.csv','.py','.yaml','.yml','.patch','.diff'):continue
  if p.stat().st_size>12*1024**2:continue
  selected[str(rel)]=p
for name in ('C0/manifest.json','C0/COMPLETE.json','C0_EXACT_BUDGET_BEFORE_SAVE.json'):
 if (r/name).is_file():selected[name]=r/name
payload={'files':[],'diffs':{}}
for name,p in sorted(selected.items()):
 raw=p.read_bytes();payload['files'].append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'b64':base64.b64encode(raw).decode()})
s=r/'source_candidate'
for name,args in {'FORMAT_ONLY.patch':['diff','aa0cca3ed0d6e5d381422d8219234b8c0c6ad065','0184690a51877223de32c78ada65002afa91103d','--'],
 'STAGE_RUNNER.patch':['diff','0184690a51877223de32c78ada65002afa91103d','5d357c1d3079de134dd8b41a20a00632da37f0b0','--'],
 'SOURCE_HISTORY.txt':['log','--format=%H %s','-10'],
 'FROZEN_BASELINE.diff':['diff','c3414af6047d06bafc1a6645d09f23247f3b2cdc','HEAD','--','src','native_control','task004_controls.py','runner']}.items():
 p=subprocess.run(['git','-C',str(s),*args],capture_output=True)
 if p.returncode:
  assert name=='FROZEN_BASELINE.diff',name
  payload['diffs']['FROZEN_BASELINE_UNAVAILABLE.txt']=base64.b64encode(p.stderr).decode();continue
 payload['diffs'][name]=base64.b64encode(p.stdout).decode()
print(json.dumps(payload))
'''
raw=call(label,code,timeout=180);doc=json.loads(raw);target=ROOT/'remote_evidence';target.mkdir(exist_ok=True)
rows=[]
for row in doc['files']:
 p=target/row['path'];p.parent.mkdir(parents=True,exist_ok=True);raw=base64.b64decode(row['b64'])
 assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
 if p.exists() and p.read_bytes()!=raw:
  history=ROOT/'evidence_collection_history'/label/row['path'];history.parent.mkdir(parents=True,exist_ok=True);history.write_bytes(p.read_bytes())
 p.write_bytes(raw);rows.append({k:v for k,v in row.items() if k!='b64'})
for name,value in doc['diffs'].items():
 p=ROOT/'source_diff'/name;p.parent.mkdir(exist_ok=True);p.write_bytes(base64.b64decode(value))
(ROOT/'evidence'/(label+'_COLLECTION.json')).write_text(json.dumps({'files':rows},indent=2))
print(json.dumps({'files':len(rows),'bytes':sum(x['bytes'] for x in rows),'integrity':'ALL_SHA_VERIFIED','mutable_logs_previous_bytes_preserved':True}))


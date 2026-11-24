import json,base64
from remote_cpu import ROOT,call
p=ROOT/'candidate_patch/native_control/snapshot.py'
s=p.read_text(encoding='utf-8')
s=s.replace('import base64\n','import base64\nimport gzip\n')
s=s.replace("FORMAT = 'GAMECAM_NATIVE_EXPLICIT_OBJECT_STORAGE_V2'","FORMAT = 'GAMECAM_NATIVE_EXPLICIT_OBJECT_STORAGE_V3_GZIP_LOSSLESS'")
s=s.replace("        count=CountingHashWriter();torch.save(raw,count)","        count=CountingHashWriter()\n        with gzip.GzipFile(filename='',mode='wb',compresslevel=1,fileobj=count,mtime=0) as compressed:\n            torch.save(raw,compressed)")
s=s.replace("'device':record['device'],'cpu_shared':record['shared']}","'device':record['device'],'cpu_shared':record['shared'],'encoding':'TORCH_ZIP_GZIP_V1'}")
s=s.replace('                torch.save(raw,f);f.flush();os.fsync(f.fileno())',"                with gzip.GzipFile(filename='',mode='wb',compresslevel=1,fileobj=f,mtime=0) as compressed:\n                    torch.save(raw,compressed)\n                f.flush();os.fsync(f.fileno())")
s=s.replace("        raw=torch.load(str(root/s['file']),map_location='cpu',weights_only=True,mmap=True)","        if s.get('encoding')!='TORCH_ZIP_GZIP_V1':raise ControlError('Unknown storage encoding')\n        with gzip.GzipFile(filename=str(root/s['file']),mode='rb') as compressed:\n            raw=torch.load(compressed,map_location='cpu',weights_only=True)")
assert s.count('TORCH_ZIP_GZIP_V1')==2 and s.count('torch.save(raw,compressed)')==2
p.write_text(s,encoding='utf-8')
files={x.relative_to(ROOT/'candidate_patch').as_posix():base64.b64encode(x.read_bytes()).decode() for x in (ROOT/'candidate_patch').rglob('*.py')}
code=r'''
import pathlib,base64,json,hashlib,sys
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1');s=r/'source_candidate'
files=json.load(sys.stdin);state=json.loads((r/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').read_text())
assert state['budgets']['CPU_correction_rounds_used']==1
diag=json.loads((r/'cpu_tests/complete_object_diagnostic_r1_fixture16/CPU_CHECKPOINT_ROUNDTRIP_REPORT.json').read_text())
assert {x['type']+'|'+x['reason'] for x in diag['unsupported']}=={"<class 'function'>|Unregistered closure/function"}
before={n:hashlib.sha256((s/n).read_bytes()).hexdigest() for n in files}
for n,b in files.items():(s/n).write_bytes(base64.b64decode(b))
receipt={'round':2,'before':before,'after':{n:hashlib.sha256((s/n).read_bytes()).hexdigest() for n in files},'changes':['Register all three actually audited LoRA owner classes, 71 callables','Lossless streaming gzip on complete tensor-storage archives; no precision reduction or tail omission'],'diagnostic_only_errors_known_identity_functions':len(diag['unsupported']),'CPU_correction_budget_remaining':0}
(r/'evidence/CPU_CORRECTION_ROUND2.json').write_text(json.dumps(receipt,indent=2))
state['budgets']['CPU_correction_rounds_used']=2
state['next_action']='Final CPU full-model roundtrip and complete 152-case regression; if unresolved serializer blocker, stop'
(r/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').write_text(json.dumps(state,indent=2));print(json.dumps({'receipt':receipt,'state':state}))
'''
d=json.loads(call('DEPLOY_CLOSURE_CORRECTION_R2',code,input_bytes=json.dumps(files).encode()))
(ROOT/'evidence/CPU_CORRECTION_ROUND2.json').write_text(json.dumps(d['receipt'],indent=2))
(ROOT/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').write_text(json.dumps(d['state'],indent=2))
print(json.dumps(d['receipt'],indent=2))

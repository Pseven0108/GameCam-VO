import json,pathlib,base64,hashlib
from remote_cpu import ROOT,call
p=ROOT/'candidate_patch/native_control/snapshot.py'
s=(ROOT/'source_intake/snapshot.py').read_text(encoding='utf-8')
s=s.replace('self.nodes={}; self.memo={}; self.storages={}; self.storage_memo={}; self.classes={}',
'''self.nodes={}; self.memo={}; self.storages={}; self.storage_memo={}; self.classes={}
        self.registered_callables=None''')
s=s.replace('    def encode(self, x):\n', '''    def encode(self, x):
        from native_control.metric3d_identity import collect, TAG
        if self.registered_callables is None:
            self.registered_callables=collect(x,self.services)
        if id(x) in self.registered_callables:
            if id(x) in self.memo:return {'$ref':self.memo[id(x)]}
            nid='o%07d'%len(self.nodes);self.memo[id(x)]=nid
            self.nodes[nid]={'kind':TAG,'pin':self.registered_callables[id(x)]}
            return {'$ref':nid}
''')
s=s.replace("        elif kind=='object':\n", "        elif kind=='metric3d_lora_identity_callable_v1':\n            from native_control.metric3d_identity import restore\n            value=restore(n['pin'])\n        elif kind=='object':\n")
assert s.count('registered_callables')==5 and 'value=restore' in s
p.write_text(s,encoding='utf-8')
files={x.relative_to(ROOT/'candidate_patch').as_posix():base64.b64encode(x.read_bytes()).decode() for x in (ROOT/'candidate_patch').rglob('*.py')}
code=r'''
import pathlib,base64,json,hashlib,datetime,sys
FILES=json.load(sys.stdin)
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1');s=r/'source_candidate'
state=json.loads((r/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').read_text())
assert state['budgets']['CPU_correction_rounds_used']==1
old=json.loads((r/'evidence/CPU_CORRECTION_ROUND1.json').read_text())
assert all('\\' in n and v is None for n,v in old['before'].items())
quarantine=r/'operational/transport_preimages';quarantine.mkdir(exist_ok=False)
for n,sha in old['after'].items():
 p=s/n
 assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
 p.rename(quarantine/n.replace('\\','__'))
before={}
for n,b in FILES.items():
 p=s/n;before[n]=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
 p.write_bytes(base64.b64decode(b))
state['budgets']['CPU_correction_rounds_used']=1
state['next_action']='Validate the source-pinned callable adapter against actual CPU weighted models and full runtime graph'
(r/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').write_text(json.dumps(state,indent=2))
receipt={'round':1,'before':before,'after':{n:hashlib.sha256((s/n).read_bytes()).hexdigest() for n in FILES},'CUDA_initialized':False,'BA_math_changed':False}
(r/'evidence/CPU_CORRECTION_ROUND1_APPLIED.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({'receipt':receipt,'state':state}))
'''
d=json.loads(call('DEPLOY_CLOSURE_CORRECTION_R1_POSIX_PATHS',code,input_bytes=json.dumps(files).encode()))
(ROOT/'TASK004C_B_AUTONOMOUS_RUN_STATE.json').write_text(json.dumps(d['state'],indent=2))
(ROOT/'evidence/CPU_CORRECTION_ROUND1_APPLIED.json').write_text(json.dumps(d['receipt'],indent=2))
print(json.dumps(d['receipt'],indent=2))

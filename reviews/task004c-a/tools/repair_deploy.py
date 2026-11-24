from transport import *
files={}
for f in ['checkpoint_io.py','task004c_capture.py','task004_controls.py','task004c_prefix.py','replay_one.py','remote_operation.py','cpu_contract_tests.py']:files[f]=(ROOT/'tools'/f).read_text(encoding='utf-8')
policies={a:json.loads((A/'release/policies'/f'{a}.json').read_text(encoding='utf-8')) for a in ['E0','E1']}
code=r'''
import sys,json,pathlib,hashlib,py_compile,shutil
p=json.loads(sys.stdin.readline());r=pathlib.Path(p['auth']['remote_root']);assert r.is_dir() and not (r/'DEPLOYMENT.json').exists();assert not list((r/'captures').iterdir()) and not list((r/'replays').iterdir());old_auth_sha=hashlib.sha256((r/'AUTHORIZATION.json').read_bytes()).hexdigest()
for d in ['control','policies','captures','replays','analysis','archives','test_logs']: assert (r/d).is_dir()
(r/'AUTHORIZATION.json').write_text(p['auth_raw'])
assert hashlib.sha256((r/'AUTHORIZATION.json').read_bytes()).hexdigest()==p['auth_sha256']
receipt={'files':{},'no_model_initialized':True,'no_cuda_initialized':True,'initial_deploy_authorization_encoding_fixed_before_any_model':True,'previous_incomplete_auth_sha256':old_auth_sha}
for f,s in p['files'].items():
 q=r/'control'/f;q.write_text(s);compile(s,str(q),'exec');receipt['files'][f]=hashlib.sha256(q.read_bytes()).hexdigest()
for a,d in p['policies'].items():(r/'policies'/(a+'.json')).write_text(json.dumps(d,indent=2)+'\n')
(r/'DEPLOYMENT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
r=remote(code,{'auth':AUTH,'auth_raw':(ROOT/'AUTHORIZATION.json').read_text(encoding='utf-8'),'auth_sha256':hashlib.sha256((ROOT/'AUTHORIZATION.json').read_bytes()).hexdigest(),'files':files,'policies':policies},'DEPLOY_UTF8_RECOVER',60)
(ROOT/'evidence/DEPLOYMENT.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))

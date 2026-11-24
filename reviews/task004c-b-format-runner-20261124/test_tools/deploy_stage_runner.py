"""Deploy stage-qualified runner source; no model or GPU execution."""
import base64,json
from remote_cpu import ROOT,call
FILES=('native_control/stages.py','native_control/runtime.py','native_control/dataset.py','native_control/native_driver.py',
       'native_control/binding.py','native_control/install.py','native_control/admission.py','native_control/stage_authorization.py',
       'task004_controls.py','src/tracker.py','runner/run_native_stage.py')
code=r'''
import base64,hashlib,json,pathlib,subprocess,sys
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1');s=r/'source_candidate'
def git(*a):return subprocess.check_output(['git','-C',str(s),*a],text=True).strip()
assert git('rev-parse','HEAD')=='0184690a51877223de32c78ada65002afa91103d'
assert not git('status','--porcelain','--untracked-files=all')
p=json.load(sys.stdin)
protected={n:hashlib.sha256((s/n).read_bytes()).hexdigest() for n in ('native_control/configdict_adapter.py','native_control/metric3d_identity.py','native_control/timm_format_adapter.py','native_control/snapshot.py')}
for n,v in p['files'].items():
 raw=base64.b64decode(v,validate=True);compile(raw,n,'exec');(s/n).write_bytes(raw)
for n,v in p['tools'].items():
 raw=base64.b64decode(v,validate=True);compile(raw,n,'exec');(r/'operational'/n).write_bytes(raw)
(r/'authorization').mkdir();(r/'authorization/TASK_REQUEST.txt').write_bytes(base64.b64decode(p['authorization'],validate=True))
git('add','--',*p['files']);git('diff','--cached','--check');git('commit','-m','Qualify C0 restore, short schedule and formal trajectory runner stages')
assert not git('status','--porcelain','--untracked-files=all')
assert protected=={n:hashlib.sha256((s/n).read_bytes()).hexdigest() for n in protected}
receipt={'source_commit':git('rev-parse','HEAD'),'source_tree':git('rev-parse','HEAD^{tree}'),'worktree_clean':True,'changed_files':list(p['files']),'protected_adapter_sha256':protected,'GPU_executions':0}
(r/'evidence/STAGE_SOURCE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''
payload={'files':{n:base64.b64encode((ROOT/'candidate_patch'/n).read_bytes()).decode() for n in FILES},'tools':{n:base64.b64encode((ROOT/'tools'/n).read_bytes()).decode() for n in ('test_stage_runner.py','stage_entry.py')},'authorization':base64.b64encode((ROOT/'authorization/TASK_REQUEST.txt').read_bytes()).decode()}
out=call('STAGE_RUNNER_DEPLOY_R1',code,input_bytes=json.dumps(payload).encode(),timeout=180)
(ROOT/'evidence/STAGE_SOURCE_RECEIPT.json').write_text(out);print(out)

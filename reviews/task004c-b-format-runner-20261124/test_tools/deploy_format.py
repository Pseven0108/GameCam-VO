"""One isolated Format adapter correction, from the accepted ConfigDict candidate."""
import base64,json
from remote_cpu import ROOT,call
REMOTE = r'''
import base64,hashlib,json,pathlib,shutil,subprocess,sys,time
base=pathlib.Path('/root/rivermind-data')
prior=base/'DROID_W_TASK004C_B_CONFIGDICT_CLOSURE_20261124_R1'
origin=base/'DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1'
root=base/'DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1'
src=root/'source_candidate'
parent='aa0cca3ed0d6e5d381422d8219234b8c0c6ad065'
def git(p,*a):return subprocess.check_output(['git','-C',str(p),*a],text=True).strip()
assert git(prior/'source_candidate','rev-parse','HEAD')==parent
assert not git(prior/'source_candidate','status','--porcelain','--untracked-files=all')
assert not root.exists(),'Independent task root must not preexist'
assert shutil.disk_usage(base).free>10*1024**3+1024**3
payload=json.load(sys.stdin)
root.mkdir()
for n in ('evidence','artifacts','operational','attempts','cpu_tests','reports'): (root/n).mkdir()
subprocess.run(['git','clone','--local',str(prior/'source_candidate'),str(src)],check=True,capture_output=True)
git(src,'switch','-c','codex/task004c-b-format-runner-ready-20261124')
git(src,'config','user.name','GameCam-VO Research')
git(src,'config','user.email','gamecam-vo@users.noreply.github.com')
for n in ('native_control','checkpoint','schedule','runner','control_common.py'):(root/n).symlink_to(src/n,target_is_directory=(src/n).is_dir())
for n in ('tests','configs','source_before'):shutil.copytree(prior/n,root/n)
for n in ('APPROVED_47_FAMILY_PROTOCOL.json','FILE_BACKED_CPU_VALIDATION.json'):shutil.copyfile(prior/'evidence'/n,root/'evidence'/n)
protected={n:hashlib.sha256((src/n).read_bytes()).hexdigest() for n in ('native_control/configdict_adapter.py','native_control/metric3d_identity.py')}
assert protected['native_control/configdict_adapter.py']=='7a4535739d385300a8eef522a6c3ccae98a26b85f0b126ba0d032505886f388f'
assert protected['native_control/metric3d_identity.py']=='b723b0eecb68449d9f9126c3453ec940c473d17a377d1ff4629dc32be036a3b4'
for n,v in payload['files'].items():
    assert n in ('native_control/snapshot.py','native_control/timm_format_adapter.py')
    (src/n).write_bytes(base64.b64decode(v,validate=True))
for n,v in payload['tools'].items(): (root/'operational'/n).write_bytes(base64.b64decode(v,validate=True))
fixture=(prior/'operational/cpu_model_fixture.py').read_text()
assert fixture.count(str(prior))==1
(root/'operational/cpu_model_fixture.py').write_text(fixture.replace(str(prior),str(root),1))
git(src,'add','--',*payload['files'])
git(src,'diff','--cached','--check')
git(src,'commit','-m','Restore pinned timm Format enum singleton without generic class allocation')
assert not git(src,'status','--porcelain','--untracked-files=all')
assert protected=={n:hashlib.sha256((src/n).read_bytes()).hexdigest() for n in protected}
r={'attempt':1,'format_repair_budget':1,'parent_commit':parent,'source_commit':git(src,'rev-parse','HEAD'),'tree':git(src,'rev-parse','HEAD^{tree}'),'protected_adapter_sha256':protected,'changed_files':{n:hashlib.sha256((src/n).read_bytes()).hexdigest() for n in payload['files']},'gpu_attempts':0,'data_free_bytes':shutil.disk_usage(root).free}
(root/'evidence/FORMAT_ROUND1_SOURCE_RECEIPT.json').write_text(json.dumps(r,indent=2))
(root/'evidence/FORMAT_FULL_SOURCE_DIFF.patch').write_text(git(src,'diff','--binary',parent,'HEAD')+'\n')
print(json.dumps(r))
'''
if __name__=='__main__':
    data={'files':{n:base64.b64encode((ROOT/'candidate_patch'/n).read_bytes()).decode() for n in ('native_control/snapshot.py','native_control/timm_format_adapter.py')},'tools':{n:base64.b64encode((ROOT/'tools'/n).read_bytes()).decode() for n in ('test_format.py',)}}
    out=call('FORMAT_DEPLOY_ROUND1',REMOTE,input_bytes=json.dumps(data).encode(),timeout=240)
    (ROOT/'evidence/FORMAT_ROUND1_SOURCE_RECEIPT.json').write_text(out)
    print(out)

import json
from remote_cpu import ROOT,call
code=r'''
import hashlib,json,pathlib,subprocess
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1');src=root/'source_candidate'
base='668a88c74c7f7a88a572679d2bd8e86c0a05514b'
def git(*args):return subprocess.check_output(['git','-C',str(src),*args],text=True).strip()
assert git('rev-parse','HEAD')==base
assert git('diff','--cached','--name-only').splitlines()==['native_control/dataset.py']
assert not git('diff','--name-only')
author=subprocess.run(['git','-C',str(src),'var','GIT_AUTHOR_IDENT'],capture_output=True,text=True)
(root/'evidence/COMMIT_AUTHOR_DIAGNOSIS.json').write_text(json.dumps({'exit_code':author.returncode,'stdout':author.stdout,'stderr':author.stderr},indent=2))
assert author.returncode!=0
name=git('log','-1','--format=%an');email=git('log','-1','--format=%ae')
subprocess.run(['git','-C',str(src),'config','user.name',name],check=True)
subprocess.run(['git','-C',str(src),'config','user.email',email],check=True)
q=subprocess.run(['git','-C',str(src),'commit','-m','Accept only the verified zero-depth CPU placeholder in NativeViperRGB'],capture_output=True,text=True)
(root/'evidence/SOURCE_COMMIT_RECEIPT.json').write_text(json.dumps({'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr},indent=2));assert q.returncode==0
head=git('rev-parse','HEAD');assert git('rev-parse','HEAD^')==base
assert git('diff',base,'--name-only').splitlines()==['native_control/dataset.py']
before=(root/'evidence/NativeViperRGB.before.py').read_bytes();after=(src/'native_control/dataset.py').read_bytes()
assert after==(root/'evidence/NativeViperRGB.after.py').read_bytes()
result={'root':str(root),'source_commit':head,'parent_commit':base,'parent_of_parent':'0931141cf88247dc8fb0c7628c1d91b6531fea90',
 'changed_runtime_files':['native_control/dataset.py'],'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest(),
 'old_candidate_modified':False,'GPU_runs':0,'None_depth_policy':'REJECT under the explicitly required Tensor-only zero-placeholder contract',
 'author_metadata_recovered_without_code_or_environment_change':True}
(root/'evidence/SOURCE_PROVENANCE.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
'''
d=json.loads(call('FINISH_SOURCE_COMMIT',code,timeout=60))
(ROOT/'evidence/SOURCE_PROVENANCE.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))

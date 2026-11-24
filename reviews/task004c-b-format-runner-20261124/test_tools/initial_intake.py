import base64,json,hashlib
from remote_cpu import ROOT,call
code=r'''
import base64,hashlib,importlib,inspect,json,os,pathlib,shutil,subprocess
from importlib.metadata import version
prior=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_CONFIGDICT_CLOSURE_20261124_R1')
src=prior/'source_candidate'
def git(*args):return subprocess.check_output(['git','-C',str(src),*args],text=True).strip()
assert git('rev-parse','HEAD')=='aa0cca3ed0d6e5d381422d8219234b8c0c6ad065'
assert not git('status','--porcelain')
fmt=importlib.import_module('timm.layers.format');cls=fmt.Format
p=pathlib.Path(inspect.getsourcefile(cls));raw=p.read_bytes()
assert version('timm')=='0.9.10' and hashlib.sha256(raw).hexdigest()=='8b4d8d2d76d65cfbf8589092505e0c9d28d0a7af7df941abe59deb9cc664dfae'
files={}
paths=['native_control/snapshot.py','native_control/configdict_adapter.py','native_control/metric3d_identity.py','native_control/runtime.py','native_control/native_driver.py','native_control/dataset.py','native_control/install.py','native_control/admission.py','native_control/binding.py','native_control/storage_budget.py','runner/run_native_smoke.py','src/tracker.py','src/slam.py','src/trajectory_filler.py','control_common.py','task004_controls.py','checkpoint/rng_state.py']
for rel in paths:
 b=(src/rel).read_bytes();files[rel]={'b64':base64.b64encode(b).decode(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
model_fixture=prior/'operational/cpu_model_fixture.py';b=model_fixture.read_bytes();files['REFERENCE_CPU_MODEL_FIXTURE.py']={'b64':base64.b64encode(b).decode(),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
q=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True)
result={'actual_source_commit':git('rev-parse','HEAD'),'actual_tree':git('rev-parse','HEAD^{tree}'),'worktree_clean':True,'requested_stale_start_commit':'a324b57760fdaf4929385f2271991d773533799d','preserve_already_accepted_ConfigDict_fix':True,'gpu_query_exit':q.returncode,'gpu':q.stdout.strip(),'data_disk':shutil.disk_usage(prior)._asdict(),'shm':shutil.disk_usage('/dev/shm')._asdict(),'timm_version':version('timm'),'format_class':cls.__module__+':'+cls.__qualname__,'format_MRO':[x.__module__+':'+x.__qualname__ for x in cls.__mro__],'format_members':{k:{'name':v.name,'value':v.value,'exact_type':type(v) is cls} for k,v in cls.__members__.items()},'new_owner':str(cls.__new__),'init_owner':str(cls.__init__),'Format_source_sha256':hashlib.sha256(raw).hexdigest(),'format_source':raw.decode(),'files':files}
print(json.dumps(result))
'''
result=json.loads(call('FORMAT_RUNNER_INITIAL_INTAKE_R1',code,timeout=150,python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'))
for rel,entry in result.pop('files').items():
 raw=base64.b64decode(entry['b64'],validate=True);assert hashlib.sha256(raw).hexdigest()==entry['sha256']
 p=ROOT/'source_intake'/rel;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(raw)
with (ROOT/'evidence/INITIAL_SOURCE_ENV_AUDIT.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps({k:result[k] for k in ['actual_source_commit','worktree_clean','gpu_query_exit','gpu','data_disk','shm','timm_version','format_MRO','format_members','Format_source_sha256']}))

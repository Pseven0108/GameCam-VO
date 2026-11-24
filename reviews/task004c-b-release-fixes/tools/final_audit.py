"""Freeze the remote full candidate, preserve proofs, no GPU commands."""
import base64,hashlib,io,json,pathlib,zipfile
from remote_access import ROOT,run
REMOTE='/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1'
baseline=json.loads((ROOT/'evidence/REMOTE_BASELINE_IDENTITY.json').read_text())
code=r'''
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import ast,base64,hashlib,importlib.metadata,io,json,pathlib,shutil,subprocess,sys,zipfile
p=json.load(sys.stdin);root=pathlib.Path(REMOTE_ROOT);source=root/'source_candidate'
sys.path.insert(0,str(root));sys.path.insert(1,str(source))
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
def git(*args):return subprocess.run(['git','-C',str(source),'-c','user.name=GameCam Release Fixes','-c','user.email=gamecam@localhost',*args],capture_output=True,text=True,check=True).stdout.strip()
origin=pathlib.Path(p['source_origin'])
assert subprocess.run(['git','-C',str(origin),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()==p['baseline_commit']
assert subprocess.run(['git','-C',str(origin),'status','--porcelain=v1','-uno'],capture_output=True,text=True,check=True).stdout.strip()==''
unchanged=[]
for row in p['full_candidate_file_manifest']:
 f=origin/row['path'];match=(f.is_symlink() and os.readlink(f)==row['target']) if row['kind']=='symlink' else (f.is_file() and sha(f)==row['sha256'])
 assert match,row['path'];unchanged.append(row['path'])
prior=root.parent/'DROID_W_TASK004C_B_NATIVE_INTEGRATION_20261124_R1/artifacts/CPU_SUITE_handoff/CPU_TEST_REPORT.json'
assert sha(prior)==p['original_118_report_sha256']
lock=json.loads((root/'configs/identity_lock.json').read_text());pins={**lock['remote_pins'],**lock['execution_source_pins']}
assert all(sha(path)==pin for path,pin in pins.items())
cpu=root/'artifacts/RELEASE_CPU_final/CPU_TEST_REPORT.json';tests=json.loads(cpu.read_text());assert tests['total']==tests['passed']==152 and not tests['cuda_initialized']
proof=json.loads((root/'artifacts/FULL_BUFFER_CPU_PROOF/FULL_BUFFER_PROOF.json').read_text());assert proof['PASS'] and not proof['cuda_initialized']
cert={'schema':'GAMECAM_FILE_BACKED_CPU_VALIDATION_V1','PASS':True,'total_tensor_bytes':proof['total_tensor_bytes'],
      'shm_delta_bytes':proof['shm_delta_bytes'],'torch_distribution_version':importlib.metadata.version('torch'),
      'file_backed_module_sha256':sha(source/'native_control/file_backed.py'),'baseline_commit':p['baseline_commit'],
      'test_report_sha256':sha(cpu),'full_proof_sha256':sha(root/'artifacts/FULL_BUFFER_CPU_PROOF/FULL_BUFFER_PROOF.json'),
      'native_Tracker_Rerun_GPU_validated':False,'GPU_execution_authorized_this_task':False}
with (root/'evidence/FILE_BACKED_CPU_VALIDATION.json').open('x') as f:json.dump(cert,f,indent=2)
from native_control.admission import cpu_storage_admission
storage_gate=cpu_storage_admission(root,backend='owned_file_mmap',validation=root/'evidence/FILE_BACKED_CPU_VALIDATION.json')
assert storage_gate['validation_passed'] and not storage_gate['issues']
# A visible, small CPU-only exact-budget artifact; never labelled NATIVE_C0.
import torch
assert not torch.cuda.is_initialized()
torch.cuda._lazy_init=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('CUDA forbidden in final CPU audit'))
from native_control.snapshot import prepare_state,save_prepared_state
demo=root/'artifacts/EXACT_BUDGET_CPU_FIXTURE';demo.mkdir()
x=torch.arange(8192,dtype=torch.float32);v=x[13::2]
plan=prepare_state({'base':x,'view':v,'same':v,'half':torch.ones(31,dtype=torch.float16),'empty':torch.empty(0)},
  provenance={'artifact_kind':'CPU_NATIVE_INTERFACE_FIXTURE','not_native_C0':True,'seed':43},destination_parent=demo)
save_prepared_state(plan,demo/'SNAPSHOT')
actual=sum(f.stat().st_size for f in (demo/'SNAPSHOT').iterdir())
assert actual==plan['budget']['exact_checkpoint_logical_bytes']
budget={'scope':'CPU_SYNTHETIC_FIXTURE_NOT_REAL_C0','plan':plan['budget'],'actual_logical_bytes':actual,
        'actual_allocated_file_bytes':sum(f.stat().st_blocks*512 for f in (demo/'SNAPSHOT').iterdir()),
        'exact_logical_match':True,'complete_real_C0_bytes':None,'cuda_initialized':torch.cuda.is_initialized()}
with (demo/'BUDGET_VERIFICATION.json').open('x') as f:json.dump(budget,f,indent=2)
# Check all C/CUDA and optimization math files against the exact remote commit.
cuda=[]
for row in p['full_candidate_file_manifest']:
 rel=row['path'];f=source/rel
 if row['kind']=='file' and (f.suffix in ('.c','.cpp','.cu','.h','.hpp','.cuh') or rel.startswith(('src/geom/','src/modules/'))):
  assert sha(f)==row['sha256'],rel;cuda.append(rel)
before=subprocess.run(['git','-C',str(source),'show',p['baseline_commit']+':src/depth_video.py'],capture_output=True,check=True).stdout.decode()
after=(source/'src/depth_video.py').read_text()
def native_calls(text):
 return [ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='droid_backends']
assert native_calls(before)==native_calls(after)
# Keep test/config provenance in the full candidate Git history.
shutil.copytree(root/'tests',source/'tests',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
for f in (root/'configs').iterdir():
 if f.is_file():shutil.copy2(f,source/'configs'/f.name)
git('add','--all');git('commit','-m','Fix scoped D guards; validate file-backed IPC and exact C0 serialization budget')
commit=git('rev-parse','HEAD');assert git('rev-parse','HEAD^')==p['baseline_commit']
assert git('status','--porcelain=v1','-uno')==''
patch=subprocess.run(['git','-C',str(source),'diff',p['baseline_commit'],'HEAD','--','.'],capture_output=True,check=True).stdout
(root/'artifacts/RELEASE_FIXES_FROM_093.patch').write_bytes(patch)
changed=git('diff','--name-status',p['baseline_commit'],'HEAD')
# Only remove the two new, disposable synthetic backing payloads after every
# full-test process exited. Reports, CPU snapshots and all historical data stay.
removed=[];backing=root/'artifacts/FULL_BUFFER_CPU_PROOF/backing'
for record in proof['backings']:
 desc=record['descriptor'];path=pathlib.Path(desc['path']);s=path.stat()
 assert path.resolve().parent==backing.resolve() and not path.is_symlink() and s.st_ino==desc['st_ino'] and s.st_size==desc['byte_size']
 expected=proof['final']['images' if s.st_size==1382400000 else 'dino']['sha256'];assert sha(path)==expected
 for proc in pathlib.Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:maps=(proc/'maps').read_text()
  except (FileNotFoundError,PermissionError,ProcessLookupError):continue
  assert str(path) not in maps,'Synthetic buffer still mapped by process '+proc.name
 removed.append({'file':str(path),'inode':s.st_ino,'bytes':s.st_size,'sha256':expected})
for record in removed:pathlib.Path(record['file']).unlink()
result={'baseline_commit':p['baseline_commit'],'new_full_candidate_commit':commit,'parent_is_exact_baseline':True,
 'forbidden_local_text_commit_used':False,'original_candidate_paths_unchanged':len(unchanged),'protected_asset_pins_unchanged':len(pins),
 'original_118_record_sha256':sha(prior),'CPU_report_sha256':sha(cpu),'tests_total':tests['total'],'tests_passed':tests['passed'],
 'protected_math_and_C_CUDA_paths_unchanged':len(cuda),'native_extension_call_AST_unchanged':True,
 'changed_paths':changed,'storage_gate_CPU_only':storage_gate,'certificate':cert,'budget_fixture':budget,
 'synthetic_temp_payloads_removed':removed,'historical_files_deleted':0,
 'data_disk_after':dict(zip(('total','used','free'),shutil.disk_usage(root))),
 'shm_after':dict(zip(('total','used','free'),shutil.disk_usage('/dev/shm'))),
 'cuda_initialized':torch.cuda.is_initialized(),'GPU_queries':0,'model_runs':0,'real_C0_created':False,'RGB_prefixes_executed':0}
with (root/'evidence/FINAL_RELEASE_AUDIT.json').open('x') as f:json.dump(result,f,indent=2)
stream=io.BytesIO()
with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
 for name in ['evidence/FILE_BACKED_CPU_VALIDATION.json','artifacts/RELEASE_FIXES_FROM_093.patch']:
  z.write(root/name,name)
 for f in demo.rglob('*'):
  if f.is_file():z.write(f,f.relative_to(root).as_posix())
result['artifacts_b64']=base64.b64encode(stream.getvalue()).decode();print(json.dumps(result))
'''.replace('REMOTE_ROOT',repr(REMOTE))
r=json.loads(run('FINAL_CPU_RELEASE_AUDIT',code,timeout=240,python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python',input_bytes=json.dumps(baseline).encode()))
raw=base64.b64decode(r.pop('artifacts_b64'));target=ROOT/'evidence/FINAL_ARTIFACTS';target.mkdir(exist_ok=False)
with zipfile.ZipFile(io.BytesIO(raw)) as z:
    assert z.testzip() is None
    for n in z.namelist():
        f=target/n;assert f.resolve().is_relative_to(target.resolve());f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(n))
(ROOT/'evidence/FINAL_RELEASE_AUDIT.json').write_text(json.dumps(r,indent=2))
print(json.dumps({k:r[k] for k in ['baseline_commit','new_full_candidate_commit','original_candidate_paths_unchanged','protected_asset_pins_unchanged','tests_total','tests_passed','protected_math_and_C_CUDA_paths_unchanged','native_extension_call_AST_unchanged','data_disk_after','shm_after','model_runs','real_C0_created']},indent=2))
print(json.dumps(r['budget_fixture'],indent=2))

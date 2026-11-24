"""Publish capture-only metadata after both real-loader and legacy CPU gates pass."""
import base64,json,pathlib,shutil
from remote_cpu import ROOT,call
old=ROOT.parent/'DROID_W_TASK004C_B_GPU_C0_20261124_R1'
payload={'entry_b64':base64.b64encode((old/'tools/capture_entry.py').read_bytes()).decode()}
code=r'''
import base64,hashlib,json,pathlib,shutil,subprocess,sys,time
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1');source=root/'source_candidate'
decision=json.loads((root/'evidence/CPU_PHASE_FINAL_DECISION.json').read_text());assert decision['CPU_passed'] and not decision['CUDA_initialized']
assert decision['new_loader_tests_passed']==21 and decision['historical_152_passed']==152 and decision['real_RGB001_018_checked']==18
provenance=json.loads((root/'evidence/SOURCE_PROVENANCE.json').read_text())
head=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip();assert head==provenance['source_commit']
assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'])
assert subprocess.check_output(['git','-C',str(source),'diff','668a88c74c7f7a88a572679d2bd8e86c0a05514b','--name-only'],text=True).splitlines()==['native_control/dataset.py']
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
lock=json.loads((root/'configs/identity_lock.json').read_text())
manifest=pathlib.Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487/INPUT.json')
assert sha(manifest)==lock['input_manifest_sha256'];doc=json.loads(manifest.read_text())
assert [r['rgb_id'] for r in doc['frames']]==list(range(1,488))
RGB=[]
for row in doc['frames']:
 path=manifest.parent/row['file'];expected=row.get('sha256',row.get('rgb_sha256'));actual=sha(path)
 assert expected and actual==expected
 RGB.append({'rgb_id':row['rgb_id'],'file':str(path),'bytes':path.stat().st_size,'sha256':actual})
(root/'evidence/ALL_487_RGB_INPUT_VERIFIED.json').write_text(json.dumps({'input_manifest_sha256':sha(manifest),'frames':RGB,'all_487_matched':True},indent=2))
oldarena=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_20261124_R1/attempts/capture/shared_cpu')
assert oldarena.is_dir() and not list(oldarena.iterdir())
maps=[];errors=[]
for proc in pathlib.Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  if str(oldarena)+'/' in (proc/'maps').read_text():maps.append(int(proc.name))
 except (FileNotFoundError,ProcessLookupError):pass
 except PermissionError:errors.append(int(proc.name))
assert not maps and not errors
(root/'evidence/OLD_ARENA_INACTIVE.json').write_text(json.dumps({'old_arena_empty':True,'active_maps':maps,'permission_errors':errors},indent=2))
p=json.load(sys.stdin);entry=base64.b64decode(p['entry_b64']);(root/'operational/capture_entry.py').write_bytes(entry)
report=root/'artifacts/RELEASE_CPU_c0_r2_ready/CPU_TEST_REPORT.json';shutil.copyfile(report,root/'evidence/CPU_RELEASE_REPORT.json')
pins={}
for name in ['native_control','checkpoint','schedule','runner','src']:
 for file in (source/name).rglob('*.py'):
  rel=str(file.relative_to(source));pins[rel if name in ('native_control','checkpoint','schedule','runner') else 'source_candidate/'+rel]=sha(file)
for name in ['task004_controls.py','task003_observer.py','control_common.py','run.py']:pins['source_candidate/'+name]=sha(source/name)
auth={'cpu_report_sha256':sha(report),'candidate_pins':pins,'reviewed_candidate_commit':head,
 'upstream_reviewed_parent_commit':'668a88c74c7f7a88a572679d2bd8e86c0a05514b',
 'approved_modes':['capture'],'max_native_process_lifecycles':1,'automatic_retry':False,
 'real_C0_authorized':True,'restore_authorized':False,'cross_D_authorized':False,'formal_B_runs_authorized':False,
 'operational_entry_sha256':hashlib.sha256(entry).hexdigest(),'authorization':'USER_APPROVED_GPU_C0_R2_20261124',
 'required_boundary':'16 first-stage + 8 second-stage graph.update; frame-end before next input; 47-family closure',
 'loader_test_count':21,'legacy_test_count':152,'RGB_frames_CPU_validated':18}
(root/'evidence/CPU_NATIVE_RELEASE.json').write_text(json.dumps(auth,indent=2))
(root/'RUN_AUTHORIZATION.json').write_text(json.dumps({k:v for k,v in auth.items() if k!='candidate_pins'},indent=2))
sys.path.insert(0,str(root));from native_control.admission import preflight
admission=preflight(root,lock,cpu_report=root/'evidence/CPU_RELEASE_REPORT.json',cpu_storage_backend='owned_file_mmap',storage_validation=root/'evidence/FILE_BACKED_CPU_VALIDATION.json')
memory={}
for name in ['memory.max','memory.current']:
 path=pathlib.Path('/sys/fs/cgroup')/name
 if path.exists():memory[name]=path.read_text().strip()
admission['cgroup']=memory;admission['all_487_RGB_verified']=True;admission['prior_arena_inactive']=True;admission['source_commit']=head
(root/'artifacts/GPU_ADMISSION_capture.json').write_text(json.dumps(admission,indent=2))
print(json.dumps({'root':str(root),'admitted':admission['admitted'],'issues':admission['issues'],'disk':admission['data_disk'],
 'shm':admission['shared_memory'],'GPU':admission['gpu'],'compute_apps':admission['compute_apps'],'cgroup':memory,
 'all_487_RGB_verified':True,'source_commit':head,'cpu_report_sha256':auth['cpu_report_sha256'],'native_lifecycles_started':0}))
'''
d=json.loads(call('C0_R2_REALTIME_ADMISSION',code,input_bytes=json.dumps(payload).encode(),timeout=180,
 python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'))
(ROOT/'evidence/GPU_ADMISSION_LOCAL.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
if not d['admitted']:raise SystemExit(2)
# Reuse the previously archived one-lifecycle coordinator, changing only task paths.
original=(old/'tools/execute_capture.py').read_text('utf-8')
updated=original.replace('DROID_W_TASK004C_B_GPU_C0_20261124_R1','DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1')
updated=updated.replace("'ADMITTED_CAPTURE_EXECUTION'","'C0_R2_SINGLE_GPU_EXECUTION'")
(ROOT/'tools/execute_capture.py').write_text(updated,encoding='utf-8')

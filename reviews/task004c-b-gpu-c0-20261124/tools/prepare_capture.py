"""Isolate the reviewed commit and publish capture-only authorization metadata."""
import base64,hashlib,json,pathlib
from remote_cpu import ROOT,call
previous=pathlib.Path(r'D:\aaa\GameCam-VO\experiments\DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1')
expected=json.loads((previous/'evidence/FINAL_RELEASE_AUDIT.json').read_text())
entry=(ROOT/'tools/capture_entry.py').read_bytes()
payload={'entry_b64':base64.b64encode(entry).decode(),'entry_sha256':hashlib.sha256(entry).hexdigest(),
 'expected_CPU_report_sha256':expected['CPU_report_sha256'],'candidate_commit':expected['new_full_candidate_commit']}
code=r'''
import base64,hashlib,json,pathlib,shutil,subprocess,sys,time
p=json.load(sys.stdin)
origin=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_NATIVE_RELEASE_FIXES_20261124_R1')
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_20261124_R1')
root.mkdir(exist_ok=False)
for name in ['artifacts','evidence','attempts','operational']:(root/name).mkdir()
q=subprocess.run(['git','clone','--no-hardlinks','--local',str(origin/'source_candidate'),str(root/'source_candidate')],capture_output=True,text=True,timeout=60)
(root/'evidence/CLONE_RECEIPT.json').write_text(json.dumps({'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr},indent=2))
assert q.returncode==0
source=root/'source_candidate'
head=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
assert head==p['candidate_commit']=='668a88c74c7f7a88a572679d2bd8e86c0a05514b'
assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'])
for name in ['native_control','checkpoint','schedule','runner','control_common.py']:(root/name).symlink_to(source/name,target_is_directory=(source/name).is_dir())
shutil.copytree(origin/'configs',root/'configs')
def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
report=origin/'artifacts/RELEASE_CPU_final/CPU_TEST_REPORT.json'
assert sha(report)==p['expected_CPU_report_sha256']
shutil.copyfile(report,root/'evidence/CPU_RELEASE_REPORT.json')
cert=origin/'evidence/FILE_BACKED_CPU_VALIDATION.json'
shutil.copyfile(cert,root/'evidence/FILE_BACKED_CPU_VALIDATION.json')
proof=origin/'artifacts/FULL_BUFFER_CPU_PROOF/FULL_BUFFER_PROOF.json'
shutil.copyfile(proof,root/'evidence/FULL_BUFFER_CPU_PROOF.json')
pins={}
for name in ['native_control','checkpoint','schedule','runner','src']:
 for path in sorted((source/name).rglob('*.py')):pins[str(path.relative_to(source))]=sha(path)
for name in ['task004_controls.py','task003_observer.py','control_common.py','run.py']:pins['source_candidate/'+name]=sha(source/name)
entry=base64.b64decode(p['entry_b64']);assert hashlib.sha256(entry).hexdigest()==p['entry_sha256']
(root/'operational/capture_entry.py').write_bytes(entry)
token={'cpu_report_sha256':sha(root/'evidence/CPU_RELEASE_REPORT.json'),'candidate_pins':{},
 'reviewed_candidate_commit':head,'authorization':'USER_APPROVED_GPU_C0_CAPTURE_ONLY_20261124',
 'approved_modes':['capture'],'max_native_process_lifecycles':1,'automatic_retry':False,
 'real_C0_authorized':True,'restore_authorized':False,'cross_D_authorized':False,'formal_B_runs_authorized':False,
 'operational_entry_sha256':p['entry_sha256'],'operational_spawn_setup':'Same as official run.py before SLAM construction; no candidate source changes'}
# Candidate pins use paths as seen by the existing runner; source files remain exact.
for rel,value in pins.items():token['candidate_pins'][rel if rel.startswith('source_candidate/') or rel.startswith(('native_control/','checkpoint/','schedule/','runner/')) else 'source_candidate/'+rel]=value
(root/'evidence/CPU_NATIVE_RELEASE.json').write_text(json.dumps(token,indent=2))
(root/'RUN_AUTHORIZATION.json').write_text(json.dumps({k:v for k,v in token.items() if k!='candidate_pins'},indent=2))
sys.path.insert(0,str(root))
from native_control.admission import preflight
lock=json.loads((root/'configs/identity_lock.json').read_text())
admission=preflight(root,lock,cpu_report=root/'evidence/CPU_RELEASE_REPORT.json',cpu_storage_backend='owned_file_mmap',storage_validation=root/'evidence/FILE_BACKED_CPU_VALIDATION.json')
(root/'artifacts/GPU_ADMISSION_capture.json').write_text(json.dumps(admission,indent=2))
result={'root':str(root),'source_commit':head,'admitted':admission['admitted'],'issues':admission['issues'],
 'disk':admission['data_disk'],'shm':admission['shared_memory'],'models_started':0,'entry_sha256':p['entry_sha256'],
 'source_files_pinned':len(token['candidate_pins']),'CPU_report_sha256':token['cpu_report_sha256'],
 'GPU':admission['gpu'],'compute_apps':admission['compute_apps']}
print(json.dumps(result))
'''
d=json.loads(call('PREPARE_CAPTURE',code,input_bytes=json.dumps(payload).encode(),timeout=180,
 python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'))
(ROOT/'evidence/CAPTURE_PREPARED.json').write_text(json.dumps(d,indent=2))
print(json.dumps(d))
if not d['admitted']:raise SystemExit(2)

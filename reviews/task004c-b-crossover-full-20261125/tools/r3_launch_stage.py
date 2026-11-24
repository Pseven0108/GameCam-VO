"""One explicit stage launch, never a retry loop or altered optimizer."""
import json,sys
from remote import ROOT,call
mode=sys.argv[1]
assert mode in ('B1','B2','B4','B3')
if mode=='B4':
 import subprocess,os
 q=subprocess.run([sys.executable,str(ROOT/'tools/r3_archive_consumed.py')],env=dict(os.environ,CUDA_VISIBLE_DEVICES=''),capture_output=True,text=True)
 print(q.stdout,flush=True)
 if q.returncode:raise RuntimeError('Lossless archive failed: '+q.stderr[-2000:])
if mode=='B3':
 import subprocess,os
 for helper,args in [('r3_archive_b4_non_schedule.py',[]),('r3_offload_completed_logs.py',['B4'])]:
  q=subprocess.run([sys.executable,str(ROOT/'tools'/helper),*args],env=dict(os.environ,CUDA_VISIBLE_DEVICES=''),capture_output=True,text=True)
  print(q.stdout,flush=True)
  if q.returncode:raise RuntimeError('Completed B4 archive failed: '+q.stderr[-2500:])
code=r'''
import os,pathlib,subprocess,json,time,hashlib,shutil
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261125_R3_OFFLINE');mode=MODE
report=json.loads((r/'evidence/IO_CPU_TEST_REPORT.json').read_text())
assert report['total']==report['passed']==18 and not report['cuda_initialized']
recovery=json.loads((r/'evidence/R3_RECOVERY_CPU_REPORT.json').read_text());assert recovery['PASS'] and recovery['passed']==recovery['total']>=10
full=json.loads((r/'artifacts/FULL_BUFFER_CPU_PROOF/FULL_BUFFER_PROOF.json').read_text());assert full['PASS'] and full['total_tensor_bytes']==2246400000 and not full['cuda_initialized']
video=json.loads((r/'artifacts/R3_VIDEO_IO_PROOF/VIDEO_LOSSLESS_PROOF.json').read_text());assert video['PASS'] and video['all_array_hashes_shape_dtype_match']
for test in ('test_io_lifecycle','test_r3_recovery','full_buffer_tmpfs_stress'):
 assert json.loads((r/'evidence'/(test+'.receipt.json')).read_text())['exit_code']==0
s=r/'source_candidate'
assert subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD'],text=True).strip()=='5d357c1d3079de134dd8b41a20a00632da37f0b0'
assert subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD^{tree}'],text=True).strip()=='c018a65009aaf4f7457e2da5225a5f322a168b77'
assert not subprocess.check_output(['git','-C',str(s),'status','--porcelain','--untracked-files=all'],text=True).strip()
m=json.loads((r/'C0/manifest.json').read_text());assert m['state_sha256']=='18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92'
log=r/'artifacts'/('STAGE_'+mode);log.mkdir(exist_ok=False)
assert not (r/'attempts'/mode).exists(),'Never reuse a failed attempt'
free=shutil.disk_usage(r).free
shm=shutil.disk_usage('/dev/shm').free
assert free>=11*1024**3,'Output reservation plus 10GiB floor not available'
assert shm>=10*1024**3+2246400000+64*1024**2,'tmpfs mapped arena reservation plus floor not available'
(r/'evidence'/('STORAGE_BEFORE_'+mode+'.json')).write_text(json.dumps({'free_bytes':free,'shm_free_bytes':shm,'CPU_restore_storage_bytes':2246400000,'arena_backing':'EXISTING_TMPFS_SAME_FILE_MMAP_REDUCER','logs_output_reservation_bytes':1024**3,'safety_floor':10*1024**3,'all_stages_sequential':True,'no_history_cleanup':True}))
py='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',GAMECAM_NATIVE_WORKSPACE=str(r),GAMECAM_IO_OVERLAY='1',
 PYTHONPATH=str(r)+':'+str(r/'overlay')+':'+str(s)+':'+str(r/'operational'))
cmd=[py,'-B','-u',str(s/'runner/run_native_stage.py'),'--mode',mode,'--cpu-report',str(r/'evidence/CPU_FINAL_ACCEPTANCE.json'),'--execute']
with (log/'stdout.txt').open('xb') as out,(log/'stderr.txt').open('xb') as err:
 p=subprocess.Popen(cmd,env=env,cwd=s,stdout=out,stderr=err,start_new_session=True)
receipt={'mode':mode,'wrapper_pid':p.pid,'start_unix':time.time(),'automatic_retry':False,'base_commit':m['provenance']['candidate_source_commit'],'overlay_only':True}
(log/'STARTED.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''.replace('MODE',repr(mode))
print(json.dumps(call('R3_LAUNCH_'+mode,code,timeout=180),indent=2))

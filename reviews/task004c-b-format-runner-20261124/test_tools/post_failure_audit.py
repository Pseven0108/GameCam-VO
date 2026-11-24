import json
from remote_cpu import ROOT,call
code=r'''
import hashlib,json,pathlib,subprocess,time,shutil,sys,os
r=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_FORMAT_RUNNER_20261124_R1');s=r/'source_candidate'
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
release=json.loads((r/'evidence/CPU_STAGE_RELEASE.json').read_text())
pins={**release['candidate_pins'],**release['protected_pins'],**release['runtime_pins']};checks=[]
for name,expected in pins.items():
 p=pathlib.Path(name) if pathlib.Path(name).is_absolute() else r/name
 actual=sha(p) if p.is_file() else None;checks.append({'path':name,'expected':expected,'actual':actual,'match':expected==actual})
assert all(x['match'] for x in checks)
assert subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD'],text=True).strip()==release['candidate_commit']
assert not subprocess.check_output(['git','-C',str(s),'status','--porcelain','--untracked-files=all'],text=True).strip()
restore=r/'attempts/restore_check';receipt=json.loads((restore/'PROCESS_RECEIPT.json').read_text());rr=json.loads((restore/'RESTORE_RECEIPT.json').read_text())
assert receipt['exit_code']==1 and not (restore/'SUCCESS.json').exists()
assert rr['all_tensor_and_object_nodes_match'] and rr['next_input_match'] and rr['rng_restored_last'] and rr['new_process_pid']!=rr['source_pid']
err=(restore/'process.stderr.txt').read_text();assert 'FileExistsError' in err and "mkdir(parents=True,exist_ok=False)" in err
trace=restore/'native_trace.jsonl';events=[json.loads(x) for x in trace.read_text().splitlines() if x.strip()]
assert not events,'A later frame event occurred despite directory-boundary failure'
assert not any((r/'attempts'/name).exists() for name in ('record_S1','replay_D0_S1','record_S0','replay_D1_S0','B1','B2','B4','B3'))
case=r/'cpu_tests/DIRECTORY_LIFECYCLE_DIAGNOSTIC_R1';case.mkdir(exist_ok=False)
script=case/'reproduce.py'
script.write_text("""import json,os,pathlib,sys,torch\nfrom torch.utils.tensorboard import SummaryWriter\np=pathlib.Path(sys.argv[1])/"native"\nassert os.environ.get("CUDA_VISIBLE_DEVICES")=="" and not torch.cuda.is_initialized()\nassert not p.exists()\nw=SummaryWriter(str(p))\ntry:\n assert p.is_dir()\n try:p.mkdir(parents=True,exist_ok=False)\n except FileExistsError:observed="FileExistsError"\n else:raise AssertionError("Expected native lifecycle defect was not reproduced")\nfinally:w.close()\nassert not torch.cuda.is_initialized()\nprint(json.dumps({"status":"EXPECTED_FAILURE_REPRODUCED","native_stage_succeeded":False,"observed":observed,"SummaryWriter_created_directory":True,"model_loaded":False,"CUDA_initialized":False}))\n""")
python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
start=time.time()
with (case/'stdout.txt').open('xb') as out,(case/'stderr.txt').open('xb') as er:
 q=subprocess.run([python,'-B',str(script),str(case)],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),stdout=out,stderr=er,timeout=60)
repro={'exit_code':q.returncode,'runtime_seconds':time.time()-start,'stdout_sha256':sha(case/'stdout.txt'),'stderr_sha256':sha(case/'stderr.txt'),'script_sha256':sha(script)}
(case/'PROCESS_RECEIPT.json').write_text(json.dumps(repro,indent=2));assert q.returncode==0
result={'status':'STOPPED_AT_RGB019_OUTPUT_DIRECTORY_COLLISION','time_unix':time.time(),
 'actual_native_C0_capture':'PASS','C0_restore_object_tensor_graph':'PASS','actual_RGB019_processed':False,
 'RGB019_event_count':len(events),'Short80_attempts':0,'Formal487_attempts':0,'new_C0_captures':1,'fresh_GPU_restore_attempts':1,
 'automatic_retries':0,'stage_not_modified_after_release':True,'protected_checks':checks,
 'source_commit':release['candidate_commit'],'source_tree':release['candidate_tree'],'worktree_clean':True,
 'data_disk':shutil.disk_usage(r)._asdict(),'shared_memory':shutil.disk_usage('/dev/shm')._asdict(),
 'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.free','--format=csv,noheader,nounits'],text=True),
 'GPU_compute_apps':subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'],text=True),
 'restore_receipt':rr,'native_stage_process':receipt,'CPU_failure_reproduction':repro,
 'directory':{'exists':(restore/'native').is_dir(),'files':sorted(x.name for x in (restore/'native').iterdir())},
 'failure_Arena_retained':True,'historical_evidence_deleted':False,'new_algorithmic_evidence':False,
 'instance_shutdown':False,'instance_rebooted':False}
with (r/'evidence/POST_FAILURE_PRESERVATION_AUDIT.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='protected_checks'}|{'protected_files_verified':len(checks),'CPU_failure_reproduction_result':json.loads((case/'stdout.txt').read_text())}))
'''
out=call('POST_FAILURE_PRESERVATION_AUDIT_R1',code,timeout=180)
(ROOT/'evidence/POST_FAILURE_PRESERVATION_SUMMARY.json').write_text(out)
print(out)


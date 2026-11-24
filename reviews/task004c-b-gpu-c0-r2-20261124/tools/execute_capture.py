"""Execute exactly one admitted capture lifecycle; no restore or BA replay."""
import json
from remote_cpu import ROOT,call
code=r'''
import hashlib,json,os,pathlib,subprocess,time,signal,shutil,sys
root=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_R2_20261124_R1')
source=root/'source_candidate';sys.path.insert(0,str(root))
auth=json.loads((root/'RUN_AUTHORIZATION.json').read_text())
assert auth['approved_modes']==['capture'] and auth['automatic_retry'] is False
assert not (root/'attempts/capture').exists() and not (root/'C0').exists(),'A native attempt already exists; retry forbidden'
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==auth['reviewed_candidate_commit']
from native_control.admission import preflight
lock=json.loads((root/'configs/identity_lock.json').read_text())
admission=preflight(root,lock,cpu_report=root/'evidence/CPU_RELEASE_REPORT.json',cpu_storage_backend='owned_file_mmap',storage_validation=root/'evidence/FILE_BACKED_CPU_VALIDATION.json')
(root/'artifacts/FINAL_GPU_ADMISSION_capture.json').write_text(json.dumps(admission,indent=2))
if not admission['admitted']:
 print(json.dumps({'status':'BLOCKED_BEFORE_MODEL','issues':admission['issues'],'native_lifecycles':0}));sys.exit(0)
out=root/'attempts/capture';out.mkdir(exist_ok=False)
token=hashlib.sha256(os.urandom(32)).hexdigest()
intent={'mode':'capture','max_rgb':80,'expected_C0_boundary_rgb':18,'formal_experiment':False,
 'child_token':token,'created':time.time(),'automatic_retry':False,'authorization':'GPU_C0_ONLY_STOP_AFTER_CAPTURE'}
with (out/'LAUNCH_INTENT.json').open('x') as f:json.dump(intent,f,indent=2)
data='/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data'
env=dict(os.environ,PYTHONPATH=str(root)+':'+str(source),PYTHONHASHSEED='43',PYTHONDONTWRITEBYTECODE='1',
 OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',CUDA_VISIBLE_DEVICES='0',
 GAMECAM_NATIVE_WORKSPACE=str(root),GAMECAM_FILE_BACKED_CPU_ROOT=str(out/'shared_cpu'),
 TORCH_HOME=data+'/torch_hub',HF_HOME=data+'/huggingface',HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
 MPLBACKEND='Agg',RERUN_NO_ANALYTICS='1',GAMECAM_NATIVE_CONTROL_BOUNDED='1',GAMECAM_NATIVE_INTERNAL_CHILD=token,
 GAMECAM_NATIVE_ATTEMPT=str(out),GAMECAM_NATIVE_LOCK=str(root/'configs/identity_lock.json'),
 GAMECAM_TASK003_OBSERVER_JSONL=str(out/'observer.jsonl'),GAMECAM_NATIVE_APPROVED_MODE='capture')
python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python'
args=[python,'-B','-u',str(root/'operational/capture_entry.py'),'--mode','capture','--max-rgb','80',
 '--cpu-report',str(root/'evidence/CPU_RELEASE_REPORT.json'),'--execute','--model-child']
start=time.time();samples=[];stopped=None
with (out/'process.stdout.txt').open('xb') as stdout,(out/'process.stderr.txt').open('xb') as stderr,(out/'resource_samples.jsonl').open('x') as log:
 proc=subprocess.Popen(args,env=env,cwd=source,stdout=stdout,stderr=stderr,start_new_session=True)
 (out/'PROCESS_STARTED.json').write_text(json.dumps({'pid':proc.pid,'pgid':proc.pid,'started_unix':start,'args':args,
  'native_lifecycles_started':1,'automatic_retry':False,'entry_sha256':auth['operational_entry_sha256']},indent=2))
 print(json.dumps({'status':'MODEL_PROCESS_STARTED','pid':proc.pid,'native_lifecycles_started':1}),flush=True)
 while proc.poll() is None:
  sample={'unix':time.time(),'elapsed_seconds':time.time()-start,'disk_free':shutil.disk_usage(root).free,
          'shm_used':shutil.disk_usage('/dev/shm').used}
  for name in ['memory.current','memory.peak']:
   path=pathlib.Path('/sys/fs/cgroup')/name
   if path.exists():sample[name]=path.read_text().strip()
  gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8)
  sample['GPU']=gpu.stdout.strip();sample['GPU_query_exit']=gpu.returncode
  log.write(json.dumps(sample)+'\n');log.flush();samples.append(sample)
  if sample['disk_free']<10*1024**3:stopped='DISK_BELOW_10_GIB_FLOOR'
  if sample['elapsed_seconds']>1200:stopped='CAPTURE_TIMEOUT_1200_SECONDS'
  if stopped:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=12)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
   break
  time.sleep(2)
 exit_code=proc.wait()
result={'mode':'capture','exit_code':exit_code,'native_lifecycles_started':1,'automatic_retry':False,
 'runtime_seconds':time.time()-start,'supervisor_stop_reason':stopped,
 'success_receipt_exists':(out/'SUCCESS.json').is_file(),'C0_RECEIPT_exists':(out/'C0_RECEIPT.json').is_file(),
 'C0_COMPLETE_exists':(root/'C0/COMPLETE.json').is_file(),'disk_free_after':shutil.disk_usage(root).free,
 'shm_peak_sampled_bytes':max((x['shm_used'] for x in samples),default=None),
 'restore_executed':False,'cross_D_executed':False,'B1_B2_B3_B4_executed':False}
with (out/'PROCESS_RECEIPT.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result),flush=True)
'''
text=call('C0_R2_SINGLE_GPU_EXECUTION',code,timeout=1500,python='/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python')
rows=[json.loads(x) for x in text.splitlines() if x.strip().startswith('{')]
(ROOT/'evidence/CAPTURE_EXECUTION.json').write_text(json.dumps(rows,indent=2))
for row in rows:print(json.dumps(row),flush=True)

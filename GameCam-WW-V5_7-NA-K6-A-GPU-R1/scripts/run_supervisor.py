"""Strict launch contract and single-attempt supervisor; importing this module is CPU-only."""
import csv, hashlib, json, os, shutil, subprocess, sys, time, uuid
from pathlib import Path
from runtime_dependency_pins import RuntimePins,PinError,static_entry,record_prelaunch_failure
from monitor_transport import MonitorReader,MonitorError,await_startup
from windows_contract import monitor_command,windows_to_wsl,pin
O=Path(__file__).resolve().parents[1]
WSL_PY='/home/lsuser/.local/share/gamecam-vo/envs/droid-w/bin/python'
CONTRACT_VERSION='K6-A-GPU-R1-01'
CPU_STATUS='CPU_TRANSPORT_VALIDATED_WAITING_FOR_MODEL_AUTHORIZATION'
ARTIFACT_NAMES=('R1_2_1_03_inherited_evidence_verification.json','R1_2_1_04_path_contract_final.json','R1_2_1_05_gt_input_isolation_audit.md','R1_2_1_06_model_authorization_guard.json','R1_2_1_07_script_sha256_manifest.csv','R1_2_1_08_protection_verification.json','R1_2_1_09_final_decision.md')
SAFETY_FLAGS=('cuda_free_monitor_enabled','nvml_free_monitor_enabled','windows_monitor_enabled','windows_shell_health_enabled','mandatory_monitor_fail_closed')
REQUIRED_RUNTIME={'scripts/run_supervisor.py','scripts/run_condition.py','scripts/k6a_safety.py','scripts/monitor_transport.py','scripts/windows_monitor.ps1','scripts/windows_contract.py','scripts/validate_monitor_cpu.py','scripts/query_dxgi_budget.ps1','config/host_pin.json','config/protocol.json','config/cases.json','config/GT_reference_pin.json','config/launch_contract.json','scripts/runtime_dependency_pins.py','config/dependency_pins.json','config/frozen_weight_manifest.csv','config/inherited_external_dependency_manifest.csv','config/k4_input_frames.csv','config/k4_input_contract.json','config/camera_intrinsics_contract.csv','config/external_dependency_manifest.csv'}
class LaunchContractError(RuntimeError):
 def __init__(self,reasons,code='BLOCKED_BY_LAUNCH_CONTRACT'):
  self.reasons=reasons if isinstance(reasons,list) else [reasons];self.code=code;super().__init__('; '.join(self.reasons))
def require(condition,reason,code='BLOCKED_BY_LAUNCH_CONTRACT'):
 if not condition:raise LaunchContractError(reason,code)
def read_json(p):
 try:return json.loads(Path(p).read_text(encoding='utf-8-sig'))
 except (OSError,ValueError) as e:raise LaunchContractError('MISSING_OR_INVALID_FILE:'+str(p)) from e
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def write_new(p,x):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)
def local(root,relative):
 root=Path(root).resolve();relative=Path(relative)
 require(not relative.is_absolute() and '..' not in relative.parts,'NONLOCAL_CONTRACT_PATH:'+str(relative));p=(root/relative).resolve()
 require(p.is_relative_to(root),'CONTRACT_PATH_ESCAPE:'+str(p));return p

def validate_authorization(host,protocol,contract,method='droidw',case='V56_01_middle'):
 """Pure predicate; a successful return cannot start a process or mutate files."""
 checks={
 'HOST_AUTHORIZATION_REQUIRED':host.get('model_execution_authorized') is True,
 'PROTOCOL_AUTHORIZATION_REQUIRED':protocol.get('model_execution_authorized') is True,
 'AUTHORIZATION_FLAGS_DISAGREE':host.get('model_execution_authorized') is protocol.get('model_execution_authorized'),
 'ATTEMPT_LIMIT_MUST_BE_ONE':type(protocol.get('model_attempt_limit')) is int and protocol['model_attempt_limit']==1,
 'PROTOCOL_CPU_ONLY_MUST_BE_FALSE':protocol.get('cpu_only') is False,
 'HOST_CPU_ONLY_MUST_BE_FALSE':host.get('cpu_only') is False,
 'MAPPING_MUST_BE_FALSE':protocol.get('mapping_enabled') is False,
 'METHODS_MUST_BE_DROIDW_ONLY':protocol.get('methods')==['droidw'] and method=='droidw',
 'CASES_MUST_BE_FIRST_WINDOW_ONLY':protocol.get('cases')==['V56_01_middle'] and case=='V56_01_middle',
 'MAX_FRAMES_MUST_BE_120':type(protocol.get('max_frames')) is int and protocol['max_frames']==120,
 'STRIDE_MUST_BE_ONE':type(protocol.get('stride')) is int and protocol['stride']==1,
 'MEMORY_FLOOR_MUST_BE_512':type(protocol.get('free_hard_stop_MiB')) is int and protocol['free_hard_stop_MiB']==512,
 'NO_AUTOMATIC_RETRY_REQUIRED':protocol.get('no_automatic_retry') is True,
 'ALL_MANDATORY_MONITORS_REQUIRED':all(contract.get('safety',{}).get(k) is True for k in SAFETY_FLAGS),
 'WINDOWS_FRESHNESS_MUST_BE_3':protocol.get('windows_max_age_seconds')==3,
 'GPU_FRESHNESS_MUST_BE_3':protocol.get('nvml_smi_max_age_seconds')==3,
 'WINDOWS_SHELL_TIMEOUT_MUST_BE_500':protocol.get('windows_shell_timeout_ms')==500,
 'DXGI_DROP_FRACTION_MUST_BE_025':protocol.get('host_context_dxgi_budget_drop_fraction')==.25,
 'SHARED_GROWTH_MUST_BE_1024':protocol.get('shared_usage_growth_stop_MiB')==1024,
 'SHARED_GROWTH_SAMPLES_MUST_BE_3':protocol.get('shared_growth_consecutive_samples')==3,
 }
 failures=[k for k,v in checks.items() if not v]
 if failures:raise LaunchContractError(failures,'BLOCKED_BY_AUTHORIZATION_GUARD')
 return dict(authorized=True,checks=checks,method=method,case=case)

def read_authorization(root,method='droidw',case='V56_01_middle'):
 # Both entrypoints call this independently; there is no cached host/protocol state.
 host=read_json(local(root,'config/host_pin.json'));protocol=read_json(local(root,'config/protocol.json'));contract=read_json(local(root,'config/launch_contract.json'))
 return validate_authorization(host,protocol,contract,method,case)

def validate_artifacts(root):
 root=Path(root).resolve();contract=read_json(local(root,'config/launch_contract.json'))
 require(contract.get('version')==CONTRACT_VERSION,'LAUNCH_CONTRACT_VERSION')
 require(contract.get('stage_directory_name')==root.name,'CURRENT_STAGE_ROOT_MISMATCH')
 require(contract.get('outputs')==dict(logs='logs',runs='runs',evidence='evidence'),'OUTPUT_ROOTS_MUST_BE_CURRENT')
 require(set(contract.get('artifacts',{}))==set(ARTIFACT_NAMES),'FORMAL_ARTIFACT_SET_MISMATCH')
 checks=[]
 for name in ARTIFACT_NAMES:
  p=local(root,name);require(p.is_file(),'FORMAL_ARTIFACT_MISSING:'+name);digest=sha(p);require(digest==contract['artifacts'][name],'FORMAL_ARTIFACT_SHA_MISMATCH:'+name)
  if p.suffix=='.json':require(read_json(p).get('passed') is True,'FORMAL_ARTIFACT_NOT_PASSED:'+name)
  checks.append(dict(path=name,sha256=digest,passed=True))
 require('**'+CPU_STATUS+'**' in local(root,ARTIFACT_NAMES[-1]).read_text(encoding='utf-8'),'CPU_FINAL_STATE_NOT_VALIDATED')
 require('结果：PASS' in local(root,'R1_2_1_05_gt_input_isolation_audit.md').read_text(encoding='utf-8'),'GT_ISOLATION_REPORT_NOT_PASSED')
 # The historical manifest validates frozen historical files, not the intentionally patched entrypoints.
 old_manifest=local(root,'R1_2_1_07_script_sha256_manifest.csv');frozen=local(root,'evidence/frozen_R1_2_1_runtime');count=0
 with old_manifest.open(encoding='utf-8-sig',newline='') as f:
  for row in csv.DictReader(f):
   p=local(frozen,row['path']);require(p.is_file() and sha(p)==row['sha256'],'INHERITED_MANIFEST_MISMATCH:'+row['path']);count+=1
 require(count>0,'EMPTY_INHERITED_MANIFEST')
 return dict(passed=True,artifacts=checks,frozen_historical_files_verified=count,no_historical_directory_fallback=True)

def validate_runtime_manifest(root):
 root=Path(root).resolve();contract=read_json(local(root,'config/launch_contract.json'));name=contract.get('runtime_manifest')
 require(name=='K6A_GPU_R1_runtime_manifest.csv','CURRENT_MANIFEST_NAME_REQUIRED')
 manifest=local(root,name);freeze=read_json(local(root,'evidence/runtime_manifest_freeze.json'))
 require(manifest.is_file() and sha(manifest)==freeze.get('sha256'),'RUNTIME_MANIFEST_FREEZE_MISMATCH')
 require(freeze.get('version')=='K6-A-GPU-R1-01','RUNTIME_MANIFEST_VERSION')
 rows=[];seen=set()
 with manifest.open(encoding='utf-8-sig',newline='') as f:
  for row in csv.DictReader(f):
   rel=row['path'];require(rel not in seen,'DUPLICATE_MANIFEST_PATH:'+rel);seen.add(rel);p=local(root,rel)
   require(row['manifest_version']==freeze['version'] and p.is_file() and p.stat().st_size==int(row['bytes']) and sha(p)==row['sha256'],'RUNTIME_SHA_MISMATCH:'+rel,'BLOCKED_BY_RUNTIME_MANIFEST');rows.append(row)
 require(REQUIRED_RUNTIME<=seen,'REQUIRED_RUNTIME_FILE_NOT_PINNED')
 actual={p.relative_to(root).as_posix() for d in ['scripts','config'] for p in (root/d).rglob('*') if p.is_file() and p.suffix in {'.py','.ps1','.json','.csv'}}
 require(actual==seen,'RUNTIME_MANIFEST_FILE_SET_MISMATCH')
 return dict(passed=True,version=freeze['version'],sha256=freeze['sha256'],files=len(rows),rows=rows)

def reject_existing_attempt(root):
 require(not local(root,'logs/model_attempt.json').exists(),'MODEL_ATTEMPT_ALREADY_CONSUMED','BLOCKED_BY_AUTHORIZATION_GUARD')

def preflight(root=O):
 artifact=validate_artifacts(root);runtime=validate_runtime_manifest(root);reject_existing_attempt(root);authorization=read_authorization(root);dependencies=static_entry(root)
 for relative in ['runs/droidw/V56_01_middle','logs/droidw_V56_01_middle.log','logs/windows_monitor.pid.json','logs/windows_monitor.jsonl','logs/monitor_session.json','logs/windows_monitor.stop','logs/supervisor_result.json','logs/condition_claim.json']:
  require(not local(root,relative).exists(),'EXISTING_FORMAL_OUTPUT:'+relative)
 return dict(passed=True,artifacts=artifact,runtime=runtime,authorization=authorization,dependencies=dependencies)

def reserve_attempt(root,session,command):
 reject_existing_attempt(root);attempt_id=str(uuid.uuid4());record=dict(attempt=1,attempt_id=attempt_id,monitor_session_id=session,launch_intent=True,model_process_started=False,model_process_completed=False,command=[*command,'--attempt-id',attempt_id],created_unix=time.time(),host_pin_sha256=sha(local(root,'config/host_pin.json')),protocol_sha256=sha(local(root,'config/protocol.json')),runtime_manifest_sha256=sha(local(root,'K6A_GPU_R1_runtime_manifest.csv')))
 write_new(local(root,'logs/model_attempt.json'),record);return record

def claim_condition_attempt(root,args):
 record=read_json(local(root,'logs/model_attempt.json'));require(record.get('attempt')==1 and record.get('launch_intent') is True and record.get('attempt_id')==args.attempt_id and record.get('monitor_session_id')==args.monitor_session_id,'CONDITION_ATTEMPT_IDENTITY_MISMATCH','BLOCKED_BY_AUTHORIZATION_GUARD')
 for field,relative in [('host_pin_sha256','config/host_pin.json'),('protocol_sha256','config/protocol.json'),('runtime_manifest_sha256','K6A_GPU_R1_runtime_manifest.csv')]:require(record.get(field)==sha(local(root,relative)),'CONDITION_ATTEMPT_PIN_CHANGED:'+field)
 claim=local(root,'logs/condition_claim.json');require(not claim.exists(),'CONDITION_ATTEMPT_ALREADY_CLAIMED','BLOCKED_BY_AUTHORIZATION_GUARD');write_new(claim,dict(attempt_id=args.attempt_id,monitor_session_id=args.monitor_session_id,pid=os.getpid(),claimed_unix=time.time()))
 return record

def cmd(args):return subprocess.check_output(args,shell=False,encoding='utf-8',errors='replace',timeout=15).strip()
def capture(reader,monitor):
 if monitor.poll() is not None:raise MonitorError('MONITOR_PRODUCER_EXITED')
 x=dict(unix_time=time.time(),gpu=cmd(['nvidia-smi','--query-gpu=index,uuid,memory.total,memory.used,memory.free,utilization.gpu','--format=csv,noheader']),processes=cmd(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader']),wsl_processes=cmd(['wsl','-d','Ubuntu','--','ps','-eo','pid=,comm=']))
 x['windows']=reader.read_last();return x

def main(root=O):
 try:checks=preflight(root)
 except (LaunchContractError,PinError,OSError,ValueError) as e:
  failure=record_prelaunch_failure(root,'supervisor',e)
  print(json.dumps(failure),flush=True);return 2
 require(Path(root).resolve()==O.resolve(),'LIVE_SUPERVISOR_ROOT_MISMATCH')
 pin();LIN=windows_to_wsl(O)
 assert shutil.disk_usage(O).free>10*1024**3
 session=str(uuid.uuid4());write_new(O/'logs/monitor_session.json',dict(monitor_session_id=session,created_unix=time.time()))
 reader=MonitorReader(O/'logs/windows_monitor.jsonl',session)
 monlog=(O/'logs/windows_monitor.stdout.log').open('x',encoding='utf-8')
 monitor=None;model=None;summary=dict(monitor_session_id=session,model_launched=False,launch_intent=False,model_process_started=False,model_process_completed=False,attempts=0,started_unix=time.time())
 try:
  mc=monitor_command(O,session)
  monitor=subprocess.Popen(mc,shell=False,stdout=monlog,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  pair=await_startup(reader,lambda:monitor.poll() is None)
  before=capture(reader,monitor)
  assert not any('python' in l.lower() for l in before['wsl_processes'].splitlines()),'Another WSL Python process exists; do not terminate it'
  write_new(O/'evidence/model_preflight.json',before)
  pair=await_startup(reader,lambda:monitor.poll() is None)
  write_new(O/'evidence/monitor_startup_barrier.json',dict(passed=True,producer_pid=monitor.pid,monitor_session_id=session,records=pair,checked_unix=time.time()))
  command=['wsl','-d','Ubuntu','--',WSL_PY,'-B','-u',LIN+'/scripts/run_condition.py','--method','droidw','--case','V56_01_middle','--monitor-session-id',session]
  attempt=reserve_attempt(O,session,command);command=attempt['command'];summary.update(launch_intent=True,attempts=1,attempt_id=attempt['attempt_id'])
  # Exclusive log creation means even a refused repeated command cannot erase evidence.
  with (O/'logs/droidw_V56_01_middle.log').open('x',encoding='utf-8') as log:
   if monitor.poll() is not None:raise MonitorError('MONITOR_PRODUCER_EXITED_AT_LAUNCH')
   reader.read_last()
   model=subprocess.Popen(command,shell=False,stdout=log,stderr=subprocess.STDOUT)
   summary.update(model_launched=True,model_process_started=True,attempts=1,model_launcher_pid=model.pid,command=command)
   print('ONE_MODEL_ATTEMPT_STARTED',flush=True);started=time.monotonic();stop_reason=None
   while model.poll() is None:
    try:
     if monitor.poll() is not None:raise MonitorError('MONITOR_PRODUCER_EXITED_DURING_MODEL')
     reader.read_last()
     if time.monotonic()-started>3600:raise RuntimeError('TRACKING_OPERATION_WATCHDOG_3600_SECONDS')
    except Exception as e:
     if stop_reason is None:
      stop_reason=str(e);write_new(O/'logs/supervisor_stop.json',dict(reason=stop_reason,unix_time=time.time()))
      rp=O/'runs/droidw/V56_01_middle/result.json'
      if rp.exists():
       r=json.loads(rp.read_text());pid=int(r['pid'])
       # Signal only the recorded task child after checking its exact command line.
       line=cmd(['wsl','-d','Ubuntu','--','ps','-p',str(pid),'-o','args='])
       if LIN+'/scripts/run_condition.py' in line and '--case V56_01_middle' in line:
        subprocess.run(['wsl','-d','Ubuntu','--','kill','-TERM',str(pid)],check=True,timeout=10)
      else:
       # WSL loader has not published identity; never guess another process PID.
       summary['stop_before_child_identity']=True
     if time.monotonic()-started>3660:raise RuntimeError('Child failed to exit after own-process stop; no replay')
    time.sleep(.2)
  summary['model_exit_code']=model.returncode;summary['model_process_completed']=True
  rp=O/'runs/droidw/V56_01_middle/result.json'
  if rp.exists():summary['model_result']=json.loads(rp.read_text())
  # Record termination before any separate CPU evaluation is permitted.
  summary['wsl_processes_after']=cmd(['wsl','-d','Ubuntu','--','ps','-eo','pid=,comm='])
  assert not any('python' in l.lower() for l in summary['wsl_processes_after'].splitlines()),'Model Python has not exited'
  summary['model_process_fully_exited']=True
  try:write_new(O/'evidence/model_postflight.json',capture(reader,monitor))
  except Exception as e:summary['postflight_monitor_error']=str(e)
 except BaseException as e:
  summary['supervisor_error']=str(e);print(type(e).__name__,str(e),flush=True)
 finally:
  if monitor is not None:
   with (O/'logs/windows_monitor.stop').open('x') as f:f.write(session)
   try:monitor.wait(timeout=15)
   except subprocess.TimeoutExpired:summary['monitor_exit_timeout']=True
   summary['monitor_exit_code']=monitor.poll();summary['monitor_producer_exited']=monitor.poll() is not None
  monlog.close();summary['finished_unix']=time.time();write_new(O/'logs/supervisor_result.json',summary)
 print(json.dumps({k:v for k,v in summary.items() if k!='model_result'}),flush=True)
 return 0 if summary.get('model_process_fully_exited') else 2
if __name__=='__main__':sys.exit(main())

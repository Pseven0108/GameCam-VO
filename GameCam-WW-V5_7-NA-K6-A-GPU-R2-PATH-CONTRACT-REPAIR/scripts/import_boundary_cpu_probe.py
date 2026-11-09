"""CPU-only exact import-boundary probe. Never calls native runtime or constructors."""
import argparse,hashlib,json,os,pathlib,sys,time,traceback
from runtime_dependency_pins import RuntimePins
from model_io_boundary_v2 import ModelIOBoundary
from diagnostic_import_policy import IMPORT_POLICY,VerifiedSourceFinder,validate_worker_import_policy,prepare_import_scratch
from diagnostic_early_failure import publish_pre_model_failure
from diagnostic_phases import PhaseRecorder
from worker_terminal import read_terminal

def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);p.add_argument('--mode',choices=['legacy','recovered','injected'],required=True);a=p.parse_args()
 os.umask(0o077);started=time.monotonic();assert os.environ['CUDA_VISIBLE_DEVICES']=='' and sys.dont_write_bytecode
 c=json.loads(pathlib.Path(a.candidate).read_text());root=pathlib.Path(c['source_root']);phase=root/c['runtime_phase_relative'];session=pathlib.Path(a.out).absolute();assert session.is_dir();out=session/'model';out.mkdir(mode=0o700)
 pins=RuntimePins(phase);static=pins.static_check();os.environ.update(pins.spec['environment']);os.environ['TMPDIR']=str(session/'tmp')
 if a.mode!='legacy':
  os.environ['MPLCONFIGDIR']=str(out/'matplotlib');os.environ['MPLBACKEND']='Agg'
  validate_worker_import_policy(dict(c,planned_model_output=str(out),python_import_policy=IMPORT_POLICY,pinned_environment=dict(c['pinned_environment'],**{'PYTHONDONTWRITEBYTECODE':'1'})))
 reads=[str(phase/'config/dependency_pins.json'),c['effective_config_record']['path']]
 reads += [str(phase/r['path']) for r in pins.spec['files'].values()]
 for r in [pins.spec['config'],pins.spec['k4_live_contract']]+list(pins.weights.values()):reads += [r['path_linux'],r['real_linux']]
 reads += [pins.spec['hf']['ref_path_linux'],pins.spec['hf']['ref_real_linux']]
 # Exact session worker lists from the real child, with CPU test output isolated.
 worker_files=[session/n for n in ['cuda_samples.jsonl','cuda.latest.json','frame_samples.jsonl','ipc_worker_events.jsonl','worker_terminal.json']]
 worker_reads=[session/n for n in ['work.permit.json','nvml.latest.json','supervisor_heartbeat.jsonl','supervisor_stop.json']]
 from ipc_runtime import IPCPolicy,expected_root
 policy=IPCPolicy(expected_root('CPU_IMPORT_'+a.mode),session/'tmp','CPU_IMPORT_'+a.mode,session);policy.install_arena()
 if a.mode!='legacy':prepare_import_scratch(dict(c,planned_model_output=str(out)))
 sources=[str(root/r['path']) for r in c['source_records']]+[r['path'] for r in c['external_source_records']]
 boundary=ModelIOBoundary(reads,sources,[root,c['external_production_root']],[out],[c['runtime_environment_prefix']],ipc_policy=policy,worker_files=worker_files,worker_read_files=worker_reads,worker_atomic_files=[session/'cuda.latest.json',session/'worker_terminal.json'],worker_root=session,import_scratch_root=out/'import_tmp' if a.mode!='legacy' else None)
 observed=[]
 def observe(event,args):
  if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
   raw=os.fsdecode(args[0]);observed.append({'path':raw,'mode':str(args[1]),'flags':args[2]})
 sys.addaudithook(observe);boundary.install()
 finder=VerifiedSourceFinder(root,c['source_records'],c['external_source_records']).install() if a.mode!='legacy' else None
 result=dict(status='RUNNING',frames_submitted=0,frames_completed=0,error=None,dependency_pin_events=[]);diag=PhaseRecorder(out,session,'CPU_IMPORT_'+a.mode)
 def event(e):result['dependency_pin_events'].append(e);diag.dependency_event(e)
 pins.event_sink=event;diag.emit('PROCESS_STARTED');pins.install_before_import();stage='TORCH_IMPORT';imports=[];CUDA_blocked=[]
 try:
  if a.mode=='injected':raise ImportError('CPU_INJECTED_TORCH_IMPORT_FAILURE')
  with diag.span('TORCH_IMPORT'):
   import torch,cv2,numpy as np
  imports += ['torch','cv2','numpy'];assert not torch.cuda.is_initialized();pins.assert_hooks(require_torch=True)
  def forbid(*args,**kwargs):CUDA_blocked.append(True);raise AssertionError('CUDA_FORBIDDEN_IN_CPU_IMPORT_PROBE')
  torch.cuda.init=forbid;torch.cuda._lazy_init=forbid;torch.cuda.is_available=lambda:False
  torch._C._cuda_init=forbid
  if a.mode=='recovered':
   stage='DROIDW_MODULE_IMPORT';repo=root/'baselines/droid_w/upstream';os.chdir(repo);sys.path.insert(0,str(repo))
   from native_adapter_v2 import _native_runtime
   from native_linux_guard_v2 import Guard
   from src.depth_video import DepthVideo
   from src.modules.droid_net import DroidNet
   from src.tracker import Tracker
   from src.utils.datasets import get_dataset,RGB_NoPose
   imports += ['native_adapter_v2','native_linux_guard_v2','src.depth_video','src.modules.droid_net','src.tracker','src.utils.datasets']
  assert not torch.cuda.is_initialized() and not CUDA_blocked
  assert not any(e['event'] in ['weight_load_started','weight_load_completed'] for e in pins.events)
  report={'status':'PASS','mode':a.mode,'python':sys.version,'imports':imports,'CUDA_initialized':False,'CUDA_initialization_calls':len(CUDA_blocked),'checkpoint_loaded':False,'model_constructed':False,'Tracker_constructed':False,'RGB_submitted':0,'pycache_prefix':sys.pycache_prefix,'dont_write_bytecode':sys.dont_write_bytecode,'source_imports':finder.events if finder else [],'dependency_events':pins.events,'observed_open_events':observed,'denied_io_events':boundary.events,'runtime_seconds':time.monotonic()-started,'scope':'CPU_REAL_DEPENDENCY_IMPORT_ONLY'}
  from linux_safety import atomic_json
  atomic_json(out/'CPU_IMPORT_RESULT.json',report)
  print(json.dumps({'status':'PASS','imports':imports,'CUDA_initialized':False,'source_import_count':len(report['source_imports']),'observed_open_count':len(observed),'seconds':report['runtime_seconds']}),flush=True);return 0
 except BaseException as exc:
  traceback.print_exc();publish_pre_model_failure(result,out,session,'CPU_IMPORT_'+a.mode,exc,stage,boundary,None,diag)
  term=read_terminal(session,'CPU_IMPORT_'+a.mode,os.getpid(),'droidw_diagnostic');assert term['primary_failure']==str(exc)
  from linux_safety import atomic_json
  atomic_json(out/'CPU_IMPORT_FAILURE_AUDIT.json',dict(mode=a.mode,primary_failure=str(exc),terminal=term,CUDA_initialized=('torch' in sys.modules and sys.modules['torch'].cuda.is_initialized()),model_constructed=False,checkpoint_loaded=False,observed_open_events=observed,denied_io_events=boundary.events))
  return 2
if __name__=='__main__':raise SystemExit(main())

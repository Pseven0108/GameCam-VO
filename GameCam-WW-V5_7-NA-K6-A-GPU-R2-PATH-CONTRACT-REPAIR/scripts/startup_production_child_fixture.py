"""CPU fixture executes the production diagnostic main with an in-memory test context.
No reusable authorization, nonce, or diagnostic claim is created. Native runtime is
replaced only in this CPU process by a hard stop before any constructor.
"""
import argparse,builtins,json,os,pathlib,sys,time,threading,resource
trace=[];opens=[]
def timed(label,fn):
 def call(*a,**kw):
  t0=time.monotonic_ns();w0=time.time_ns();io=len(opens)
  try:return fn(*a,**kw)
  finally:
   end=time.monotonic_ns();trace.append(dict(phase=label,start_monotonic_ns=t0,end_monotonic_ns=end,duration_ms=(end-t0)/1e6,start_unix_ns=w0,end_unix_ns=time.time_ns(),pid=os.getpid(),thread_id=threading.get_ident(),RSS_bytes=int(pathlib.Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE'),CUDA_involved=False,file_IO_count=len(opens)-io))
 return call
def audit_open(event,args):
 if event=='open':opens.append(str(args[0]))
sys.addaudithook(audit_open)

p=argparse.ArgumentParser();p.add_argument('--candidate');p.add_argument('--out');p.add_argument('--fault',default='none');p.add_argument('--cuda-synthetic',action='store_true');a=p.parse_args();assert os.environ['CUDA_VISIBLE_DEVICES']==('0' if a.cuda_synthetic else '')
import bounded_diagnostic_child as child
from runtime_dependency_pins import RuntimePins
from model_io_boundary_v2 import ModelIOBoundary
from ipc_runtime import IPCPolicy
recorded_boundaries=[]
original_boundary_install=ModelIOBoundary.install
def boundary_install(self,*a,**kw):
 recorded_boundaries.append(self);return original_boundary_install(self,*a,**kw)
ModelIOBoundary.install=boundary_install
for cls,attr in [(RuntimePins,'static_check'),(RuntimePins,'install_before_import'),(ModelIOBoundary,'install'),(IPCPolicy,'install_arena')]:setattr(cls,attr,timed(cls.__name__+':'+attr,getattr(cls,attr)))
c=json.loads(pathlib.Path(a.candidate).read_text());session=pathlib.Path(a.out).absolute();out=session/'model';c.update(planned_model_output=str(out),planned_session_directory=str(session),planned_session_id='CPU_EXACT_CHILD',planned_ipc_root='/dev/shm/gamecam-ipc/CPU_EXACT_CHILD');c['pinned_environment'].update(CUDA_VISIBLE_DEVICES='0' if a.cuda_synthetic else '',TMPDIR=str(session/'tmp'),MPLCONFIGDIR=str(out/'matplotlib'),MPLBACKEND='Agg');c['pinned_environment'].pop('PYTHONPYCACHEPREFIX',None)
from diagnostic_import_policy import IMPORT_POLICY
c['python_import_policy']=IMPORT_POLICY
from runtime_dependency_pins import RuntimePins
pins=RuntimePins(pathlib.Path(c['source_root'])/c['runtime_phase_relative']);cfg=pins.read_original_config();cfg['max_frames']=120;cfg['data']['output']=str(out)
config_path=session.parent/'exact_child_effective_config.json';config_path.write_text(json.dumps(cfg,indent=2)+'\n');c['effective_config_record']={'path':str(config_path),'sha256':__import__('hashlib').sha256(config_path.read_bytes()).hexdigest()}
class MockContext:
 def __init__(self,*args):pass
 def validate_child(self,session_dir,sid):
  assert session_dir==str(session) and sid=='CPU_EXACT_CHILD'
  if '/candidate_final/' in a.candidate:
   from diagnostic_authorization import DiagnosticContext as RealContext
   raw=pathlib.Path(a.candidate).read_bytes();RealContext(a.candidate,__import__('hashlib').sha256(raw).hexdigest(),None).validate_candidate()
  return c
child.DiagnosticContext=MockContext
original=builtins.__import__;blocked=[];started=time.monotonic()
def cpu_stop(*args,**kw):
 import torch
 guard=None;cuda_timeline=[]
 assert not torch.cuda.is_initialized()
 if a.cuda_synthetic:
  from native_linux_guard_v2 import Guard
  guard=Guard(session,out,torch,'CPU_EXACT_CHILD',execution_kind='cpu_dummy',diagnostic=kw['diagnostic'])
  cuda_timeline.append(dict(phase='GUARD_READY',monotonic_ns=time.monotonic_ns(),snapshot=guard.snapshot()))
 def deny(*args,**kw):blocked.append(True);raise AssertionError('CUDA_FORBIDDEN_IN_EXACT_CHILD_CPU_FIXTURE')
 if not a.cuda_synthetic:torch.cuda.init=deny;torch.cuda._lazy_init=deny;torch._C._cuda_init=deny;torch.cuda.is_available=lambda:False
 repo=pathlib.Path(c['source_root'])/'baselines/droid_w/upstream';os.chdir(repo);sys.path.insert(0,str(repo))
 from src.depth_video import DepthVideo
 from src.modules.droid_net import DroidNet
 from src.tracker import Tracker
 from src.utils.datasets import get_dataset,RGB_NoPose
 if a.cuda_synthetic:
  assert torch.cuda.is_initialized()
  begin=time.monotonic();x=torch.ones((256,256),device='cuda');y=torch.ones_like(x)
  while time.monotonic()-begin<2:
   z=x@y;torch.cuda.synchronize();guard.check('synthetic_small_tensor');time.sleep(.05)
  del x,y,z;torch.cuda.synchronize();torch.cuda.empty_cache();guard.check('synthetic_release')
  cuda_timeline.append(dict(phase='TENSOR_RELEASED',monotonic_ns=time.monotonic_ns(),snapshot=guard.snapshot()))
  guard.finish()
 else:assert not torch.cuda.is_initialized() and not blocked
 result={'status':'PRODUCTION_CHILD_SYNTHETIC_VALIDATED' if a.cuda_synthetic else 'CPU_IMPORT_CLOSURE_VALIDATED','real_child_main_executed':True,'authorization_context':'IN_MEMORY_CPU_MOCK_ONLY','native_runtime_replaced_before_call':True,'native_runtime_executed':False,'constructors_called':0,'checkpoint_load_events':[e for e in args[9].events if e['event'].startswith('weight_load_')],'CUDA_initialized':bool(torch.cuda.is_initialized()),'CUDA_synthetic_only':bool(a.cuda_synthetic),'cuda_timeline':cuda_timeline,'CUDA_initialization_calls':len(blocked),'RGB_submitted':0,'BA_executed':False,'pycache_prefix':sys.pycache_prefix,'dont_write_bytecode':sys.dont_write_bytecode,'seconds':time.monotonic()-started}
 assert result['checkpoint_load_events']==[]
 from linux_safety import atomic_json
 result['security_events']=[e for b in recorded_boundaries for e in b.events];result['phase_trace']=trace;result['open_count']=len(opens);result['instrumentation']='selected function and import wrappers; overlapping spans are not additive';atomic_json(out/'CPU_EXACT_CHILD_RESULT.json',result);print(json.dumps(result),flush=True);return 0
def imports(name,globals=None,locals=None,fromlist=(),level=0):
 if name=='torch' and a.fault=='early-import':raise ImportError('CPU_EXACT_CHILD_EARLY_IMPORT_FAILURE')
 target=(name in {'torch','cv2','numpy'} and name not in sys.modules) or (name.startswith('src.') and sys._getframe(1).f_code.co_filename==__file__)
 module=timed('import:'+name,original)(name,globals,locals,fromlist,level) if target else original(name,globals,locals,fromlist,level)
 if name=='native_adapter_v2' and '_native_runtime' in fromlist:module._native_runtime=cpu_stop
 return module
builtins.__import__=imports
raise SystemExit(child.main(['--candidate',a.candidate,'--candidate-sha','0'*64,'--session-dir',str(session),'--session','CPU_EXACT_CHILD']))

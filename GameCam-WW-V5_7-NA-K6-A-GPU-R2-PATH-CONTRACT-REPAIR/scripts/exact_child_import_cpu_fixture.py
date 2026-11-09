"""CPU fixture executes the production diagnostic main with an in-memory test context.
No reusable authorization, nonce, or diagnostic claim is created. Native runtime is
replaced only in this CPU process by a hard stop before any constructor.
"""
import argparse,builtins,json,os,pathlib,sys,time
p=argparse.ArgumentParser();p.add_argument('--candidate');p.add_argument('--out');p.add_argument('--fault',default='none');a=p.parse_args();assert os.environ['CUDA_VISIBLE_DEVICES']==''
import bounded_diagnostic_child as child
c=json.loads(pathlib.Path(a.candidate).read_text());session=pathlib.Path(a.out).absolute();out=session/'model';c.update(planned_model_output=str(out),planned_session_directory=str(session),planned_session_id='CPU_EXACT_CHILD',planned_ipc_root='/dev/shm/gamecam-ipc/CPU_EXACT_CHILD');c['pinned_environment'].update(CUDA_VISIBLE_DEVICES='',TMPDIR=str(session/'tmp'),MPLCONFIGDIR=str(out/'matplotlib'),MPLBACKEND='Agg');c['pinned_environment'].pop('PYTHONPYCACHEPREFIX',None)
from diagnostic_import_policy import IMPORT_POLICY
c['python_import_policy']=IMPORT_POLICY
from runtime_dependency_pins import RuntimePins
pins=RuntimePins(pathlib.Path(c['source_root'])/c['runtime_phase_relative']);cfg=pins.read_original_config();cfg['max_frames']=120;cfg['data']['output']=str(out)
config_path=session.parent/'exact_child_effective_config.json';config_path.write_text(json.dumps(cfg,indent=2)+'\n');c['effective_config_record']={'path':str(config_path),'sha256':__import__('hashlib').sha256(config_path.read_bytes()).hexdigest()}
class MockContext:
 def __init__(self,*args):pass
 def validate_child(self,session_dir,sid):assert session_dir==str(session) and sid=='CPU_EXACT_CHILD';return c
child.DiagnosticContext=MockContext
original=builtins.__import__;blocked=[];started=time.monotonic()
def cpu_stop(*args,**kw):
 import torch
 assert not torch.cuda.is_initialized()
 def deny(*args,**kw):blocked.append(True);raise AssertionError('CUDA_FORBIDDEN_IN_EXACT_CHILD_CPU_FIXTURE')
 torch.cuda.init=deny;torch.cuda._lazy_init=deny;torch._C._cuda_init=deny;torch.cuda.is_available=lambda:False
 repo=pathlib.Path(c['source_root'])/'baselines/droid_w/upstream';os.chdir(repo);sys.path.insert(0,str(repo))
 from src.depth_video import DepthVideo
 from src.modules.droid_net import DroidNet
 from src.tracker import Tracker
 from src.utils.datasets import get_dataset,RGB_NoPose
 assert not torch.cuda.is_initialized() and not blocked
 result={'status':'CPU_IMPORT_CLOSURE_VALIDATED','real_child_main_executed':True,'authorization_context':'IN_MEMORY_CPU_MOCK_ONLY','native_runtime_replaced_before_call':True,'native_runtime_executed':False,'constructors_called':0,'checkpoint_load_events':[e for e in args[9].events if e['event'].startswith('weight_load_')],'CUDA_initialized':False,'CUDA_initialization_calls':len(blocked),'RGB_submitted':0,'BA_executed':False,'pycache_prefix':sys.pycache_prefix,'dont_write_bytecode':sys.dont_write_bytecode,'seconds':time.monotonic()-started}
 assert result['checkpoint_load_events']==[]
 from linux_safety import atomic_json
 atomic_json(out/'CPU_EXACT_CHILD_RESULT.json',result);print(json.dumps(result),flush=True);return 0
def imports(name,globals=None,locals=None,fromlist=(),level=0):
 if name=='torch' and a.fault=='early-import':raise ImportError('CPU_EXACT_CHILD_EARLY_IMPORT_FAILURE')
 module=original(name,globals,locals,fromlist,level)
 if name=='native_adapter_v2' and '_native_runtime' in fromlist:module._native_runtime=cpu_stop
 return module
builtins.__import__=imports
raise SystemExit(child.main(['--candidate',a.candidate,'--candidate-sha','0'*64,'--session-dir',str(session),'--session','CPU_EXACT_CHILD']))

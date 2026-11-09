"""Actual production child main under a CPU-only in-memory context and supervisor.
Model runtime is replaced BEFORE invocation; no GPU authorization file exists.
"""
import argparse,builtins,hashlib,json,os,pathlib,sys,time,threading,traceback
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);p.add_argument('--fault',default='none');p.add_argument('--supervised',action='store_true');a=p.parse_args()
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and sys.dont_write_bytecode and sys.pycache_prefix is None
c=json.loads(pathlib.Path(a.candidate).read_text());session=pathlib.Path(a.out).absolute();out=session/'model';sid=session.name
c.update(planned_model_output=str(out),planned_session_directory=str(session),planned_session_id=sid,planned_ipc_root='/dev/shm/gamecam-ipc/'+sid)
c['pinned_environment'].update(CUDA_VISIBLE_DEVICES='',TMPDIR=str(session/'tmp'),MPLCONFIGDIR=str(out/'matplotlib'),MPLBACKEND='Agg');c['pinned_environment'].pop('PYTHONPYCACHEPREFIX',None)
# Reject checkpoint/GT/image reads even when RuntimePins otherwise approves them.
# Static SHA identity checks occur in the parent, before this CPU fixture starts.
forbidden=[];io=[];cpu_guard_active=False
image_suffixes={'.png','.jpg','.jpeg','.exr'};weight_suffixes={'.pth','.pt','.ckpt','.safetensors','.bin'}
def audit(event,args):
 if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
  path=pathlib.Path(os.fsdecode(args[0]));io.append(str(path))
  if cpu_guard_active and (path.suffix.lower() in image_suffixes|weight_suffixes or path.name in ('Camera_Pose.txt','Skeleton.txt','State.txt')):
   forbidden.append(str(path));raise RuntimeError('CPU_IMPORT_FORBIDDEN_ASSET_READ:'+str(path))
sys.addaudithook(audit)
import bounded_diagnostic_child as child
from runtime_dependency_pins import RuntimePins
from model_io_boundary_v2 import ModelIOBoundary
from diagnostic_import_policy import VerifiedSourceFinder
boundaries=[];finders=[];base_install=ModelIOBoundary.install
ModelIOBoundary.install=lambda self:(boundaries.append(self),base_install(self))[-1]
base_finder_install=VerifiedSourceFinder.install
VerifiedSourceFinder.install=lambda self:(finders.append(self),base_finder_install(self))[-1]
# The production child repeats file-only SHA checks; allow these, then arm the
# CPU asset guard immediately before dependency imports, where model I/O could occur.
base_pins_install=RuntimePins.install_before_import
RuntimePins.install_before_import=lambda self:arm_after_install(self)
def arm_after_install(pins):
 global cpu_guard_active
 gate=base_pins_install(pins);cpu_guard_active=True;return gate
pins=RuntimePins(pathlib.Path(c['source_root'])/c['runtime_phase_relative']);cfg=pins.read_original_config();cfg['max_frames']=120;cfg['data']['output']=str(out)
config_path=session.parent/(sid+'-effective-config.json');config_path.write_text(json.dumps(cfg,indent=2)+'\n');c['effective_config_record']=dict(path=str(config_path),sha256=hashlib.sha256(config_path.read_bytes()).hexdigest())
class MockContext:
 def __init__(self,*args):pass
 def validate_child(self,session_dir,identity):
  assert session_dir==str(session) and identity==sid
  return c
child.DiagnosticContext=MockContext
if a.fault=='original-hub':VerifiedSourceFinder.bind_torch_hub=lambda *args:None
if a.fault=='hub-identity':c['dynamic_source_policy']['hub_entrypoints'][0]['requested_path']='/tmp/unregistered/hubconf.py'
original_import=builtins.__import__;torch_guarded=False;blocked_calls=[]
def guard_torch(torch):
 global torch_guarded
 if torch_guarded:return
 assert not torch.cuda.is_initialized()
 def deny(*args,**kwargs):blocked_calls.append('CUDA');raise RuntimeError('CPU_IMPORT_CUDA_FORBIDDEN')
 torch.cuda.init=deny;torch.cuda._lazy_init=deny;torch._C._cuda_init=deny;torch.cuda.is_available=lambda:False
 def deny_module(*args,**kwargs):blocked_calls.append('torch.nn.Module.__init__');raise RuntimeError('CPU_IMPORT_MODEL_CONSTRUCTION_FORBIDDEN')
 torch.nn.Module.__init__=deny_module
 torch_guarded=True
# A call profiler refuses constructors and deserializers BEFORE their bodies.
def profile(frame,event,arg):
 if event!='call' or not cpu_guard_active:return
 name=frame.f_code.co_name;filename=frame.f_code.co_filename
 if (name in ('load','load_file','load_state_dict_from_url') and any(x in filename for x in ('torch/serialization','safetensors/torch','torch/hub'))) or (name=='create_model' and '/timm/' in filename) or (name=='__init__' and '/baselines/droid_w/' in filename and frame.f_locals.get('self') is not None and type(frame.f_locals['self']).__name__ in {'DepthVideo','Tracker','DroidNet','DepthModel','BaseDepthModel','DensePredModel','DinoVisionTransformer','RAFTDepthNormalDPT5','Fit3DModels'}):
  blocked_calls.append(filename+':'+name);raise RuntimeError('CPU_IMPORT_MODEL_CALL_FORBIDDEN:'+name)

def cpu_native(*args,**kwargs):
 torch=args[6];assert not torch.cuda.is_initialized();sys.setprofile(profile);startup=kwargs['diagnostic'].startup
 stop=threading.Event();thread=None
 if a.supervised:
  # These samples are explicitly synthetic CPU fixture data. No CUDA query is made.
  startup.set_phase('CUDA_INITIALIZING');startup.set_phase('CUDA_CONTEXT_READY')
  from linux_safety import atomic_json,append_json,EXPECTED_UUID
  def samples():
   seq=0
   while not stop.is_set():
    seq+=1;x=dict(kind='cuda',session=sid,sample_seq=seq,monotonic_time=time.monotonic(),unix_time=time.time(),ok=True,gpu_uuid=EXPECTED_UUID,fixture_only=True,real_CUDA=False,cuda_free_MiB=4096.,allocated_MiB=0.,reserved_MiB=0.,worker_pid=os.getpid())
    append_json(session/'cuda_samples.jsonl',x);atomic_json(session/'cuda.latest.json',x);stop.wait(.2)
  thread=threading.Thread(target=samples,daemon=True);thread.start();startup.set_phase('CUDA_MONITOR_READY')
  deadline=time.monotonic()+10
  while not (session/'work.permit.json').exists():
   if time.monotonic()>deadline:raise RuntimeError('CPU_SYNTHETIC_PERMIT_TIMEOUT')
   time.sleep(.03)
  from startup_protocol import validate_permit
  validate_permit(json.loads((session/'work.permit.json').read_text()),sid,'cpu_dummy');startup.set_phase('WORKER_READY')
 try:
  if a.fault=='timeout':
   while True:time.sleep(.1)
  if a.fault=='illegal-read':(session/'supervisor.private').read_text()
  from dynamic_prior_cpu_probe import import_prior_sources
  probe=import_prior_sources(c,torch)
  assert not torch.cuda.is_initialized() and not blocked_calls and not forbidden
  from linux_safety import atomic_json
  record=dict(status='PRODUCTION_CHILD_DYNAMIC_IMPORT_CPU_PASSED',real_child_main_executed=True,native_runtime_replaced_before_call=True,authorization_context='CPU_IN_MEMORY_MOCK',GPU_authorization_created=False,real_CUDA=False,CUDA_initialized=bool(torch.cuda.is_initialized()),blocked_calls=blocked_calls,forbidden_asset_reads=forbidden,probe=probe,source_import_events=[e for f in finders for e in f.events],boundary_events=[e for b in boundaries for e in b.events],checkpoint_load_events=[e for e in args[9].events if e['event'].startswith('weight_load_')],dont_write_bytecode=sys.dont_write_bytecode,pycache_prefix=sys.pycache_prefix,open_count=len(io))
  atomic_json(out/'CPU_DYNAMIC_PRIOR_RESULT.json',record);assert not record['checkpoint_load_events'];print(json.dumps(dict(status=record['status'],rows=len(probe['rows']),seconds=probe['total_dynamic_seconds'])),flush=True);return 0
 except BaseException as exc:
  from diagnostic_early_failure import publish_pre_model_failure
  publish_pre_model_failure(args[4],out,session,sid,exc,'DYNAMIC_PRIOR_CPU_IMPORT',boundaries[-1],None,kwargs['diagnostic']);traceback.print_exc();return 2
 finally:
  stop.set()
  if thread:thread.join(timeout=2)

def imports(name,globals=None,locals=None,fromlist=(),level=0):
 if name=='torch' and a.fault=='early-import':raise ImportError('CPU_DYNAMIC_PRIOR_EARLY_IMPORT_FAILURE')
 m=original_import(name,globals,locals,fromlist,level)
 if name=='torch' and sys._getframe(1).f_code.co_filename.endswith('/bounded_diagnostic_child.py'):guard_torch(m)
 if name=='native_adapter_v2' and '_native_runtime' in fromlist:
  if a.fault=='preparation-timeout':
   while True:time.sleep(.1)
  m._native_runtime=cpu_native
 return m
builtins.__import__=imports
raise SystemExit(child.main(['--candidate',a.candidate,'--candidate-sha',hashlib.sha256(pathlib.Path(a.candidate).read_bytes()).hexdigest(),'--session-dir',str(session),'--session',sid]))

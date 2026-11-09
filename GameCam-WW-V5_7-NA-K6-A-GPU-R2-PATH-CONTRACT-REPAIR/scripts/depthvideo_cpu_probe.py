import ast,hashlib,json,os,pathlib,sys,time,traceback,gc
from ipc_runtime import IPCPolicy
from model_io_boundary_v2 import ModelIOBoundary
from linux_safety import atomic_json
D=pathlib.Path(sys.argv[1]);SID=sys.argv[2];R=pathlib.Path(sys.argv[3]);fallback=sys.argv[4]=='fallback';out=D/'model';started=time.monotonic()
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
# Importing modules and class definitions is allowed, executing weights/Tracker/BA is not.
import torch,safetensors.torch
for mod,name in [(torch,'load'),(torch.serialization,'load'),(safetensors.torch,'load_file'),(safetensors,'safe_open')]:
 setattr(mod,name,lambda *a,**k:(_ for _ in ()).throw(AssertionError('REAL_CHECKPOINT_FORBIDDEN')))
for name in ('init','_lazy_init'):setattr(torch.cuda,name,lambda *a,**k:(_ for _ in ()).throw(AssertionError('CUDA_FORBIDDEN')))
os.environ['MPLCONFIGDIR']=str(out/'mpl');sys.path.insert(0,str(R/'baselines/droid_w/upstream'));os.chdir(R/'baselines/droid_w/upstream')
from src.depth_video import DepthVideo
source=pathlib.Path(sys.modules['src.depth_video'].__file__);source_sha=hashlib.sha256(source.read_bytes()).hexdigest();tree=ast.parse(source.read_text());cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='DepthVideo');ctor=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='__init__');calls=[ast.unparse(x.func) for x in ast.walk(ctor) if isinstance(x,ast.Call)];assert not any(x in calls for x in ('torch.load','safetensors.load_file','Tracker.run','droid_backends.ba'))
policy=IPCPolicy('/dev/shm/gamecam-ipc/'+SID,str(D/'tmp'),SID,D);policy.install_arena(force_fallback=fallback)
# Everything under the constructor's approved source/config is read-only.
reads=[source];sources=[x for x in R.rglob('*.py')];b=ModelIOBoundary(reads,sources,[R],[out],[sys.prefix],ipc_policy=policy,worker_files=[D/'ipc_worker_events.jsonl'],worker_root=D);b.install()
cfg={'data':{'output':str(out)},'scene':'SYNTHETIC_NO_RGB','cam':{'H_out':16,'W_out':16},'tracking':{'buffer':2,'backend':{'metric_depth_reg':True},'mono_thres':.01,'uncertainty_params':{'activate':True,'enable_bidirectional_uncer':False,'feature_dim':384,'enable_affine_transform':True}},'mono_prior':{'feature_extractor':'dinov2_reg_small_fine'},'device':'cpu','debug':False}
class Printer:
 def print(self,*a,**k):pass
report={'status':'FAIL','scope':'actual imported DepthVideo, buffer2/H16/W16 CPU-only constructor, uncertainty active384; synthetic configuration only','source_path':str(source),'source_sha256':source_sha,'constructor_calls':calls,'real_checkpoint_loaded':False,'tracker_constructed':False,'tracker_run_called':False,'real_ba_executed':False,'CUDA_initialized':False,'GT_values_read':False,'pid':os.getpid(),'fallback':fallback}
try:
 dv=DepthVideo(cfg,Printer());assert dv.counter.value==0;dv.counter.value=1;assert dv.counter.value==1
 tensors={k:{'shape':list(v.shape),'dtype':str(v.dtype),'device':str(v.device),'shared':v.is_shared(),'bytes':v.numel()*v.element_size()} for k,v in vars(dv).items() if isinstance(v,torch.Tensor)};assert all(v['device']=='cpu' for v in tensors.values());assert not torch.cuda.is_initialized()
 fds=[]
 for f in pathlib.Path('/proc/self/fd').iterdir():
  try:
   target=os.readlink(f)
   if '/dev/shm/' in target:fds.append({'fd':f.name,'target':target})
  except OSError:pass
 report.update(status='PASS',constructed=True,counter_roundtrip=True,tensors=tensors,native_shared_memory_fds=fds,maps=[x for x in pathlib.Path('/proc/self/maps').read_text().splitlines() if '/dev/shm/' in x],ipc_events=list(policy.events),boundary_denied_events=b.events,torch_version=str(torch.__version__),native_shared_memory_limit='torch_* shared tensors are native C++ shm_open/unlink and bypass Python open audit. They are fd-owned, immediately unlinked; owner process exit checked by external controller. Not claimed session-path isolation or OS sandbox.')
 del dv;gc.collect()
except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc(),constructed=False,ipc_events=list(policy.events),boundary_denied_events=b.events)
report['seconds']=time.monotonic()-started;atomic_json(out/'depthvideo_report.json',report);print(json.dumps({'status':report['status'],'error':report.get('error'),'seconds':report['seconds']}));raise SystemExit(0 if report['status']=='PASS' else 2)

"""Real weighted models, independent restore, and real CPU runtime construction."""
import os,sys,pathlib,json,time,hashlib,types,random,math,subprocess,traceback,shutil
ROOT=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1')
SRC=ROOT/'source_candidate';sys.path[:0]=[str(ROOT),str(SRC)]
import torch,numpy as np,yaml
import importlib.abc
class CPUOptionalCudaBackendUnavailable(importlib.abc.MetaPathFinder):
 """CPU fixture: choose the installed model's own no-xformers branch at import.

 This does not replace a forward method or attention operator. GPU launch scripts
 never install this finder and retain their original CUDA xformers implementation.
 """
 def find_spec(self,fullname,path=None,target=None):
  if fullname=='xformers' or fullname.startswith('xformers.'):
   raise ModuleNotFoundError('CPU fixture: optional CUDA-only xformers unavailable')
sys.meta_path.insert(0,CPUOptionalCudaBackendUnavailable())
from native_control.snapshot import ObjectEncoder,save_state,load_state
from native_control.metric3d_identity import TAG,Metric3DLoRAIdentityV1
from checkpoint.rng_state import capture_rng_state,restore_rng_state
from control_common import ControlError,digest
torch.set_num_threads(2)
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not torch.cuda.is_initialized()
OUT=ROOT/'cpu_tests/closure_roundtrip_r2_rng_validation'
DATA=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data')
os.environ.update(TORCH_HOME=str(DATA/'torch_hub'),HF_HOME=str(DATA/'huggingface'),HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',MPLBACKEND='Agg')
torch.hub.set_dir(str(DATA/'torch_hub'));hub_original=torch.hub.load
def hub(repo,model,*a,**kw):
 repos={'yvanyin/metric3d':'yvanyin_metric3d_main','ywyue/FiT3D':'ywyue_FiT3D_main'}
 if repo not in repos:raise ControlError('Unknown repository; no network fetch')
 return hub_original(str(DATA/'torch_hub'/repos[repo]),model,*a,**{**kw,'source':'local'})
torch.hub.load=hub
for repo in ('yvanyin_metric3d_main','ywyue_FiT3D_main'):sys.path.append(str(DATA/'torch_hub'/repo))

def models_build(cfg):
 from src.utils.mono_priors.metric_depth_estimators import get_metric_depth_estimator
 from src.utils.mono_priors.img_feature_extractors import get_feature_extractor
 from src.modules.droid_net import DroidNet
 from collections import OrderedDict
 metric=get_metric_depth_estimator(cfg);fit=get_feature_extractor(cfg);droid=DroidNet()
 sd=OrderedDict((k.replace('module.',''),v) for k,v in torch.load(cfg['tracking']['pretrained'],map_location='cpu',weights_only=True).items())
 for k in ('update.weight.2.weight','update.weight.2.bias','update.delta.2.weight','update.delta.2.bias'):sd[k]=sd[k][:2]
 droid.load_state_dict(sd);droid.eval()
 # CPU fixture only: initialize this nonpersistent constant buffer with the exact
 # installed formula. Otherwise upstream get_bins() hard-codes device='cuda'.
 # No method, weight, dtype, dropout rate or GPU execution path is patched.
 decoder=metric.depth_model.decoder
 anchor=torch.exp(torch.linspace(math.log(decoder.min_val),math.log(decoder.max_val),decoder.num_depth_regressor_anchor,device='cpu')).unsqueeze(0)
 decoder.register_buffer('depth_expectation_anchor',anchor,persistent=False)
 return {'Metric3D':metric,'FiT3D':fit,'DroidNet':droid}

def evaluate(models):
 results={};values={}
 x=torch.linspace(-1.,1.,3*112*112).reshape(1,3,112,112)
 r0=capture_rng_state()
 with torch.no_grad():
  pred,conf,extra=models['Metric3D'].inference({'input':x})
  values['metric_depth']=pred;values['metric_confidence']=conf
  values['metric_normal']=extra['prediction_normal']
  values['fit_features']=models['FiT3D'].get_intermediate_layers(x,n=[8,9,10,11],reshape=True)[-1]
  values['droid_feature']=models['DroidNet'].fnet(x.unsqueeze(1))
  values['droid_context']=models['DroidNet'].cnet(x.unsqueeze(1))
 # Exercise gradient semantics using the real weighted LoRALinear, and separately
 # every identity callable. No training or parameter-gradient accumulation.
 first=next(m for m in models['Metric3D'].modules() if type(m).__module__+':'+type(m).__qualname__=='mono.model.decode_heads.RAFTDepthNormalDPTDecoder5:LoRALinear')
 z=torch.linspace(-.4,.4,2*first.in_features).reshape(2,first.in_features).requires_grad_()
 y=first(z);values['weighted_lora_output']=y.detach();values['weighted_lora_input_gradient']=torch.autograd.grad(y.square().mean(),z)[0]
 functions=[m.lora_dropout for m in models['Metric3D'].modules() if hasattr(m,'lora_dropout') and callable(m.lora_dropout) and not isinstance(m.lora_dropout,torch.nn.Module)]
 for fn in functions:
  z=torch.linspace(-1,1,11,requires_grad=True);a=z.detach().clone();rng=torch.get_rng_state().clone();v=fn(z)
  assert v is z and torch.equal(a,z.detach()) and torch.equal(torch.get_rng_state(),rng)
  assert torch.equal(torch.autograd.grad(v.square().sum(),z)[0],2*a)
 def rng_signature(state):
  def value(x):
   if isinstance(x,torch.Tensor):return {'dtype':str(x.dtype),'shape':list(x.shape),'bytes':x.detach().cpu().contiguous().numpy().tobytes().hex()}
   if isinstance(x,dict):return {k:value(v) for k,v in x.items()}
   if isinstance(x,(tuple,list)):return [value(v) for v in x]
   return x
  return digest(value(state))
 r1=capture_rng_state();results['rng_unchanged']=rng_signature(r0)==rng_signature(r1)
 assert results['rng_unchanged']
 for name,v in values.items():
  assert torch.isfinite(v).all(),name
  results[name]={'shape':list(v.shape),'dtype':str(v.dtype),'sha256':hashlib.sha256(v.detach().contiguous().numpy().tobytes()).hexdigest()}
 results['identity_callables_tested']=len(functions)
 return results,values

def worker(path):
 OUT.mkdir(exist_ok=True)
 bundle,m=load_state(path)
 e=ObjectEncoder();tree=e.encode(bundle)
 assert tree==m['root'] and e.nodes==m['nodes']
 assert bundle['first_callable'] is bundle['same_callable']
 assert bundle['first_callable'] is bundle['callable_owner'].lora_dropout
 assert bundle['view'].untyped_storage()._cdata==bundle['base'].untyped_storage()._cdata
 assert tuple(bundle['view'].shape)==(3,4) and bundle['view'].stride()==(8,2) and bundle['view'].storage_offset()==1
 restore_rng_state(bundle['rng'])
 result,values=evaluate(bundle['models'])
 expected=json.loads((OUT/'EXPECTED_FORWARD.json').read_text())
 assert result==expected,[(k,result.get(k),expected.get(k)) for k in result if result.get(k)!=expected.get(k)]
 receipt={'status':'PASS','fresh_pid':os.getpid(),'source_pid':bundle['source_pid'],'all_object_nodes_and_tensor_views_match':True,'function_ref_aliases_preserved':True,'tensor_storage_aliases_preserved':True,'forward_all_exact_SHA_equal':True,'weighted_layer_input_gradient_exact':True,'RNG_equal':True,'CUDA_initialized':torch.cuda.is_initialized(),'outputs':result}
 assert receipt['fresh_pid']!=receipt['source_pid'] and not receipt['CUDA_initialized']
 (OUT/'FRESH_PROCESS_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print('RESTORE_CPU_PASS',flush=True)

def parent():
 OUT.mkdir(exist_ok=False)
 cfg=yaml.safe_load(pathlib.Path('/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/release/candidates/r2_sealed_config.yaml').read_text())
 cfg['device']='cpu';cfg['data']['output']=str(OUT)
 os.environ['GAMECAM_TASK003_OBSERVER_JSONL']=str(OUT/'observer.jsonl')
 random.seed(43);np.random.seed(43);torch.manual_seed(43)
 print('BUILD_REAL_WEIGHTED_MODELS',flush=True);models=models_build(cfg)
 graph=ObjectEncoder();graph.encode(models)
 print('MODEL_CLOSURE_PASS',len(graph.nodes),flush=True)
 report={'model_nodes':len(graph.nodes),'model_storage_bytes':sum(s['raw'].numel() for s in graph.storages.values()),'registered_identity_nodes':sum(v['kind']==TAG for v in graph.nodes.values()),'negative_tests':{},'model_forward_cpu_fixture':{'constant_buffer':'depth_expectation_anchor','source_formula':'exp(linspace(log(min_val),log(max_val),256))','device':'cpu','attention_backend':'unmodified upstream Attention.forward via original ImportError no-xformers branch','reason':'CPU xformers has no 64-d head implementation; installed get_bins hard-codes CUDA; no network method/weight or GPU path modified'}}
 def reject(name,x):
  try:ObjectEncoder().encode(x)
  except ControlError as ex:report['negative_tests'][name]={'PASS':True,'reason':str(ex)}
  else:raise AssertionError('Unknown object accepted: '+name)
 reject('unknown_lambda',lambda x:x)
 external=7
 reject('captured_closure',lambda x:x+external)
 reject('opaque_runtime_handle',object())
 print('FORWARD_REAL_WEIGHTED_MODELS',flush=True);expected,values=evaluate(models)
 (OUT/'EXPECTED_FORWARD.json').write_text(json.dumps(expected,indent=2))
 first=next(m for m in models['Metric3D'].modules() if type(m).__module__+':'+type(m).__qualname__=='mono.model.decode_heads.RAFTDepthNormalDPTDecoder5:LoRALinear')
 base=torch.arange(24,dtype=torch.float32).reshape(3,8)
 bundle={'first_callable':first.lora_dropout,'models':models,'same_callable':first.lora_dropout,'callable_owner':first,'base':base,'view':base[:,1::2],'source_pid':os.getpid(),'rng':capture_rng_state()}
 snap=pathlib.Path('/dev/shm/gamecam_task004cb_cpu_real_model_roundtrip_'+str(os.getpid()))
 assert shutil.disk_usage('/dev/shm').free>8*1024**3
 print('SAVE_CPU_SNAPSHOT_TMPFS',flush=True)
 m=save_state(bundle,snap,provenance={'artifact_kind':'CPU_NATIVE_INTERFACE_FIXTURE','fixture':'CPU_REAL_WEIGHTED_MODELS_NOT_NATIVE_C0'},floor_bytes=0)
 report['CPU_snapshot_path']=str(snap);report['CPU_snapshot_bytes']=sum(v['bytes'] for v in m['files'].values());report['CPU_snapshot_sha256']=m['state_sha256']
 with (OUT/'restore_child.stdout.txt').open('xb') as o,(OUT/'restore_child.stderr.txt').open('xb') as er:
  q=subprocess.run([sys.executable,'-B','-u',__file__,'--worker',str(snap)],stdout=o,stderr=er,env=os.environ,timeout=900)
 report['restore_exit_code']=q.returncode
 if q.returncode:
  (OUT/'PARTIAL_REPORT.json').write_text(json.dumps(report,indent=2));raise ControlError('Fresh CPU restore failed: '+(OUT/'restore_child.stderr.txt').read_text()[-5000:])
 print('BUILD_CPU_RUNTIME_BUFFER500',flush=True)
 from src.depth_video import DepthVideo
 from src.tracker import Tracker
 from src.trajectory_filler import PoseTrajectoryFiller
 from native_control.dataset import NativeViperRGB
 from native_control.barrier import WriterBarrier
 from src.utils.sys_timer import timer
 from task003_observer import recorder
 import torch.multiprocessing as mp
 from types import SimpleNamespace
 ctx=mp.get_context('spawn');sink=SimpleNamespace()
 # I/O services are explicit exclusions. Constructors receive functional CPU sinks.
 class Sink:
  def __init__(self):self.progress_counter=ctx.Value('i',0)
  def print(self,*a,**kw):pass
  def add_text(self,*a,**kw):pass
 sink=Sink();os.environ['GAMECAM_FILE_BACKED_CPU_ROOT']=str(OUT/'shared_cpu')
 video=DepthVideo(cfg,sink)
 slam=SimpleNamespace(cfg=cfg,device='cpu',droid_net=models['DroidNet'],video=video,verbose=False,save_dir=str(OUT),printer=sink)
 # Keep exactly the already weighted factory objects: constructor-side cache reuse
 # avoids a redundant third model initialization; no model method is replaced.
 import src.motion_filter as mf
 mf.get_metric_depth_estimator=lambda cfg:models['Metric3D']
 mf.get_feature_extractor=lambda cfg:models['FiT3D']
 tracker=Tracker(slam,sink,sink)
 filler=PoseTrajectoryFiller(cfg,models['DroidNet'],video,sink,device='cpu')
 stream=NativeViperRGB(cfg,'/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487/INPUT.json',OUT)
 # Synthetic recurrent/cache values only: no claim of native initialized data.
 tracker.motion_filter.net=torch.zeros(1,128,45,80);tracker.motion_filter.inp=tracker.motion_filter.net.clone();tracker.motion_filter.fmap=torch.zeros(1,128,45,80)
 tracker.frontend.last_pose=video.poses[0];tracker.frontend.last_disp=video.disps[0];tracker.frontend.last_time=video.timestamp[0]
 g=tracker.frontend.graph
 from src.modules.droid_net import CorrBlock
 g.corr=CorrBlock(torch.zeros(1,1,128,16,16),torch.zeros(1,1,128,16,16))
 g.net=torch.zeros(1,1,128,45,80);g.inp=g.net.clone()
 roots={'tracker':tracker,'stream':stream,'filler':filler,'observer':recorder(),'timer':timer,'rng':capture_rng_state(),'cursor':{'next_input_index':18,'prev_kf_idx':11,'curr_kf_idx':11,'prev_ba_idx':0,'intrinsic':stream.get_intrinsic()}}
 services={'sink':sink,'video_counter':video.counter,'observer_file':getattr(roots['observer'],'_file',None)}
 runtime=ObjectEncoder(services=services);runtime.encode(roots)
 families=json.loads((ROOT/'evidence/APPROVED_47_FAMILY_PROTOCOL.json').read_text())['tensors']
 covered=[]
 for f in families:
  name=f['name'];parts=name.replace('frontend.graph.corr.corr_pyramid[*]','frontend.graph.corr.corr_pyramid').split('.')
  if parts[0]=='video':obj=video;parts=parts[1:]
  elif parts[0]=='motion_filter':obj=tracker.motion_filter;parts=parts[1:]
  elif parts[0]=='frontend':obj=tracker.frontend;parts=parts[1:]
  else:raise AssertionError(name)
  for part in parts:obj=getattr(obj,part)
  covered.append({'name':name,'present':True,'source':'CPU_REAL_CONSTRUCTOR_PLUS_SYNTHETIC_CACHE','type':str(type(obj))})
 assert len(covered)==47
 (OUT/'RUNTIME_OBJECT_GRAPH.json').write_text(json.dumps({'nodes':runtime.nodes,'classes':runtime.classes},indent=2))
 report['runtime_closure']={'nodes':len(runtime.nodes),'unique_storage_bytes':sum(s['raw'].numel() for s in runtime.storages.values()),'families_covered':covered,'CUDA_state_values_verified':False}
 report['CUDA_initialized']=torch.cuda.is_initialized();assert not report['CUDA_initialized']
 report['status']='PASS';(OUT/'CPU_CHECKPOINT_ROUNDTRIP_REPORT.json').write_text(json.dumps(report,indent=2));print('CPU_ROUNDTRIP_COMPLETE',flush=True)

if __name__=='__main__':
 try:
  if len(sys.argv)>1:worker(sys.argv[2])
  else:parent()
 except BaseException as ex:
  OUT.mkdir(exist_ok=True)
  (OUT/'FAILURE.json').write_text(json.dumps({'error':str(ex),'traceback':traceback.format_exc(),'CUDA_initialized':torch.cuda.is_initialized()},indent=2))
  raise

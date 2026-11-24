"""Run only on the pinned wild interpreter, with CUDA hidden. No RGB/GT read."""
import os,sys,pathlib,json,hashlib,types,inspect,dis,traceback,subprocess,time
ROOT=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_AUTONOMOUS_20261124_R1')
SRC=ROOT/'source_candidate'
sys.path[:0]=[str(ROOT),str(SRC)]
import torch,numpy as np,yaml
torch.set_num_threads(2)
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not torch.cuda.is_initialized()
out=ROOT/'cpu_tests/closure_audit_round0_models';out.mkdir(exist_ok=False)
data=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/data')
os.environ.update(TORCH_HOME=str(data/'torch_hub'),HF_HOME=str(data/'huggingface'),HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
torch.hub.set_dir(str(data/'torch_hub'))
original_hub_load=torch.hub.load
def local_hub(repo,model,*args,**kwargs):
 official={'yvanyin/metric3d':'yvanyin_metric3d_main','ywyue/FiT3D':'ywyue_FiT3D_main'}
 if repo not in official:raise RuntimeError('Unknown prior repository')
 return original_hub_load(str(data/'torch_hub'/official[repo]),model,*args,**{**kwargs,'source':'local'})
torch.hub.load=local_hub
cfg=yaml.safe_load(pathlib.Path('/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/release/candidates/r2_sealed_config.yaml').read_text())
cfg['device']='cpu';cfg['data']['output']=str(out)
from src.utils.mono_priors.metric_depth_estimators import get_metric_depth_estimator
from src.utils.mono_priors.img_feature_extractors import get_feature_extractor
from src.modules.droid_net import DroidNet
from collections import OrderedDict
report={'artifact_kind':'CPU_REAL_MODEL_CLOSURE_AUDIT','models':{},'functions':[],'unsupported':[],'cuda_initialized':False}
models={}
for name,make in [('Metric3D',lambda:get_metric_depth_estimator(cfg)),('FiT3D',lambda:get_feature_extractor(cfg)),('DroidNet',DroidNet)]:
 t=time.time();print('INITIALIZING',name,flush=True)
 model=make()
 if name=='DroidNet':
  sd=OrderedDict((k.replace('module.',''),v) for k,v in torch.load(cfg['tracking']['pretrained'],map_location='cpu',weights_only=True).items())
  for k in ['update.weight.2.weight','update.weight.2.bias','update.delta.2.weight','update.delta.2.bias']:sd[k]=sd[k][:2]
  model.load_state_dict(sd);model.eval();del sd
 models[name]=model
 report['models'][name]={'class':type(model).__module__+':'+type(model).__qualname__,'parameters':sum(x.numel() for x in model.parameters()),'buffers':sum(x.numel() for x in model.buffers()),'initialization_seconds':time.time()-t}
 print('MODEL_READY',name,flush=True)

# Exhaustively visit the real weighted graph rather than stopping at the first lambda.
seen=set()
def walk(x,path,owner=None,attr=None):
 if x is None or isinstance(x,(str,int,float,bool,bytes,torch.Tensor,torch.dtype,torch.device,np.generic,np.dtype,pathlib.Path,slice,type)) :return
 if id(x) in seen:return
 seen.add(id(x))
 if isinstance(x,types.FunctionType):
  c=x.__code__
  d={'path':path,'owner':type(owner).__module__+':'+type(owner).__qualname__ if owner is not None else None,'attribute':attr,'module':x.__module__,'qualname':x.__qualname__,'closure':None if x.__closure__ is None else repr(x.__closure__),'freevars':list(c.co_freevars),'argcount':c.co_argcount,'posonlyargcount':c.co_posonlyargcount,'kwonlyargcount':c.co_kwonlyargcount,'defaults':repr(x.__defaults__),'kwdefaults':repr(x.__kwdefaults__),'code_sha256':hashlib.sha256(c.co_code).hexdigest(),'bytecode_hex':c.co_code.hex(),'instructions':[(i.opname,str(i.argval)) for i in dis.get_instructions(x)],'source':inspect.getsourcefile(x)}
  p=pathlib.Path(d['source']) if d['source'] else None
  d['source_sha256']=hashlib.sha256(p.read_bytes()).hexdigest() if p and p.is_file() else None
  if attr=='lora_dropout':
   v=torch.linspace(-2,2,19,requires_grad=True);before=v.detach().clone();rng=torch.get_rng_state().clone();y=x(v);g=torch.autograd.grad(y.square().sum(),v)[0]
   d['identity_behavior']={'same_object':y is v,'input_unmodified':torch.equal(v.detach(),before),'rng_unchanged':torch.equal(torch.get_rng_state(),rng),'gradient_equal':torch.equal(g,2*before),'owner_r':getattr(owner,'r',None),'owner_lora_alpha':getattr(owner,'lora_alpha',None),'model_training':owner.training}
  report['functions'].append(d);return
 if isinstance(x,(types.ModuleType,types.GeneratorType)):
  report['unsupported'].append({'path':path,'type':str(type(x))});return
 if isinstance(x,types.MethodType):walk(x.__self__,path+'.__self__');return
 if isinstance(x,dict):
  for k,v in x.items():walk(k,path+'.key');walk(v,path+'['+repr(k)+']',x,k)
 elif isinstance(x,(list,tuple,set,frozenset)):
  for i,v in enumerate(x):walk(v,path+'['+str(i)+']',x,str(i))
 elif hasattr(x,'__dict__'):
  for k,v in vars(x).items():walk(v,path+'.'+k,x,k)
 else:report['unsupported'].append({'path':path,'type':str(type(x)),'repr':repr(x)[:300]})
walk(models,'weighted_models')
report['visited_objects']=len(seen);report['cuda_initialized']=torch.cuda.is_initialized()
from native_control.snapshot import ObjectEncoder
for name,model in models.items():
 try:
  e=ObjectEncoder();e.encode(model)
  report['models'][name]['closure']={'status':'PASS','nodes':len(e.nodes),'unique_storage_bytes':sum(r['raw'].numel() for r in e.storages.values())}
 except BaseException as ex:report['models'][name]['closure']={'status':'BLOCKED','reason':str(ex)}
assert not torch.cuda.is_initialized()
(out/'CPU_REAL_MODEL_OBJECT_AUDIT.json').write_text(json.dumps(report,indent=2))
print('AUDIT_COMPLETE',json.dumps({'model_summary':report['models'],'functions':len(report['functions']),'unsupported':len(report['unsupported']),'CUDA':False}),flush=True)

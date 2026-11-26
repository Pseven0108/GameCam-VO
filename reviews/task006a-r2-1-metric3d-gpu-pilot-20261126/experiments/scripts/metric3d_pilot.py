"""Independent Metric3D GPU diagnostic; fixed weights, no optimizer, no SLAM."""
import argparse,hashlib,json,os,pathlib,subprocess,time,traceback
BASE=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
HUB=BASE/'data/torch_hub/yvanyin_metric3d_main'
CKPT=BASE/'data/torch_hub/checkpoints/metric_depth_vit_large_800k.pth'
COMMIT='eb5b6fac0dc155e4e52f576e304fbf11655ff339'
CKPT_SHA='15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def dump(p,obj):
 with p.open('x',encoding='utf-8') as f:f.write(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--out',required=True)
 parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
 out=pathlib.Path(args.out).resolve()
 if not str(out).startswith('/root/rivermind-data/GAMECAM_TASK006A_R2_1_'):raise ValueError('Independent output required')
 out.mkdir(parents=True,exist_ok=False)
 receipt={'status':'STARTED','stage':'SMOKE' if args.smoke else 'PILOT','model_forwards':0,'training':False,'SLAM':False}
 rows=[]
 try:
  import shutil
  free=shutil.disk_usage(out).free
  if free<10*1024**3+250*1024**2:raise RuntimeError('Need 10GiB reserve plus current output budget')
  gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,uuid,driver_version,memory.free','--format=csv,noheader,nounits'],text=True).strip()
  jobs=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()
  if jobs:raise RuntimeError('Other GPU compute process; no takeover')
  if int(gpu.split(',')[-1])<12000:raise RuntimeError('Conservative pilot memory guard, not measured model minimum')
  if sha(CKPT)!=CKPT_SHA:raise RuntimeError('Checkpoint identity differs')
  if subprocess.check_output(['git','-C',str(HUB),'rev-parse','HEAD'],text=True).strip()!=COMMIT:raise RuntimeError('Hub revision differs')
  if subprocess.check_output(['git','-C',str(HUB),'status','--short','--untracked-files=no'],text=True).strip():raise RuntimeError('Tracked model source changed')
  manifest=pathlib.Path(args.manifest);samples=json.loads(manifest.read_text())['samples']
  if not 1<=len(samples)<=16 or (args.smoke and len(samples)!=1):raise ValueError('Pilot/sample limit')
  for item in samples:
   if sha(pathlib.Path(item['rgb_path']))!=item['rgb_sha256']:raise RuntimeError('RGB identity mismatch')
   if item['fx']<=0 or not item['sequence_id'] or not item['frame_id']:raise RuntimeError('Missing sample identity/K')
  os.environ.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
  import sys;sys.path.insert(0,str(HUB))
  import numpy as np
  import torch
  import torch.nn.functional as F
  from torchvision import transforms
  import torchvision.transforms.functional as TF
  import cv2
  def no_download(*a,**k):raise RuntimeError('Runtime network download forbidden')
  torch.hub.load_state_dict_from_url=no_download
  torch.hub.set_dir(str(BASE/'data/torch_hub'))
  torch.manual_seed(43);np.random.seed(43)
  init=time.perf_counter()
  model=torch.hub.load(str(HUB),'metric3d_vit_large',source='local',pretrain=False)
  state=torch.load(str(CKPT),map_location='cpu')
  keys=model.load_state_dict(state['model_state_dict'],strict=False)
  del state
  dump(out/'CHECKPOINT_COMPATIBILITY.json',{'missing_keys':keys.missing_keys,'unexpected_keys':keys.unexpected_keys})
  # Upstream inference uses no masks. The official checkpoint omits only the
  # zero-initialized encoder mask token, read exclusively in the masked branch.
  # Keep that parameter unchanged; do not hide any other missing weight.
  allowed={'depth_model.encoder.mask_token'}
  if set(keys.missing_keys)-allowed or keys.unexpected_keys:raise RuntimeError('Unexpected checkpoint incompatibility')
  encoder=model.depth_model.encoder
  if keys.missing_keys:
   source=HUB/'mono/model/backbones/ViT_DINO_reg.py'
   if sha(source)!='70963202c3fca5f75e313bfd21223514251b273b132282cf100767f3942ea712':raise RuntimeError('Reviewed mask-token source differs')
   if not torch.equal(encoder.mask_token,torch.zeros_like(encoder.mask_token)):raise RuntimeError('Unloaded mask token is not native zero initialization')
  mask_observations=[]
  def observe_encoder(module,arguments,kwargs):
   if kwargs.get('masks') is not None or (len(arguments)>1 and arguments[1] is not None):raise RuntimeError('Untrained mask-token branch requested')
   mask_observations.append({'positional_inputs':len(arguments),'masks':None})
   return None
  encoder_guard=encoder.register_forward_pre_hook(observe_encoder,with_kwargs=True)
  model=model.eval().cuda()
  receipt.update(GPU=gpu,torch=torch.__version__,CUDA_build=torch.version.cuda,Metric3D_commit=COMMIT,
                 checkpoint_sha256=CKPT_SHA,manifest_sha256=sha(manifest),script_sha256=sha(pathlib.Path(__file__)),
                 model_load_seconds=time.perf_counter()-init,seed=43,cudnn_deterministic=torch.backends.cudnn.deterministic,
                 cudnn_benchmark=torch.backends.cudnn.benchmark,model_training=model.training)
  selected=[(name,layer) for name,layer in model.named_modules() if name.endswith('.depth_regressor')]
  if len(selected)!=1:raise RuntimeError('Ambiguous depth-bin hook')
  name,layer=selected[0];parent=dict(model.named_modules())[name.rsplit('.',1)[0]]
  capture={}
  def hook(module,inputs,output):
   capture['logits']=output.detach().cpu().numpy().copy()
   return None
  for item in samples:
   if shutil.disk_usage(out).free<10*1024**3+150*1024**2:raise RuntimeError('Output storage reserve reached')
   print('SAMPLE_START',item['sequence_id'],item['frame_id'],flush=True)
   original=cv2.cvtColor(cv2.imread(item['rgb_path'],cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
   if list(original.shape[:2])!=item['source_hw']:raise RuntimeError('Source RGB dimensions differ')
   h,w=item['input_hw'];rgb=cv2.resize(original,(w,h),interpolation=cv2.INTER_LINEAR) if [h,w]!=item['source_hw'] else original
   scale=min(616/h,1064/w);hh,ww=int(h*scale),int(w*scale);dh,dw=616-hh,1064-ww
   pad=(dw//2,dh//2,dw-dw//2,dh-dh//2);arrays={};timing=[]
   def preprocess(image):
    x=torch.from_numpy(image.copy()).permute(2,0,1)[None].float()/255.
    x=transforms.Resize((hh,ww))(x)
    x=transforms.Normalize([.485,.456,.406],[.229,.224,.225])(x)
    return TF.pad(x,pad,fill=0.).cuda()
   def infer(x):
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();started=time.perf_counter()
    with torch.no_grad():d,c,details=model.inference({'input':x})
    torch.cuda.synchronize();seconds=time.perf_counter()-started;receipt['model_forwards']+=1
    mem={'seconds_forward':seconds,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved()}
    if not torch.isfinite(d).all() or not torch.isfinite(c).all():raise RuntimeError('Nonfinite native output; preserve failure')
    return d,c,details,mem
   if args.smoke:
    x=preprocess(rgb);d,c,details,mem=infer(x)
    base_d=d.detach().cpu().numpy().copy();base_c=c.detach().cpu().numpy().copy()
    timing.append(dict(mode='native_without_hook_cold',**mem));del x,d,c,details
   for mode in ['native','flip']:
    x=preprocess(rgb if mode=='native' else rgb[:,::-1]);handle=layer.register_forward_hook(hook)
    try:d,c,details,mem=infer(x)
    finally:handle.remove()
    if d.shape!=(1,1,616,1064) or c.shape!=d.shape:raise RuntimeError('Unexpected canonical output shape')
    if args.smoke and mode=='native':
     hookcheck={'depth_max_abs_diff':float(np.max(np.abs(base_d-d.detach().cpu().numpy()))),
                'confidence_max_abs_diff':float(np.max(np.abs(base_c-c.detach().cpu().numpy()))),
                'depth_allclose':bool(np.allclose(base_d,d.detach().cpu().numpy(),rtol=1e-5,atol=1e-6)),
                'confidence_allclose':bool(np.allclose(base_c,c.detach().cpu().numpy(),rtol=1e-5,atol=1e-6)),
                'rtol':1e-5,'atol':1e-6}
     dump(out/'HOOK_EQUIVALENCE.json',hookcheck)
     if not(hookcheck['depth_allclose'] and hookcheck['confidence_allclose']):raise RuntimeError('Read-only hook equivalence failed')
    def restore(t,interp):
     unpad=t[:,:,dh//2:616-(dh-dh//2),dw//2:1064-(dw-dw//2)]
     return F.interpolate(unpad,(h,w),mode=interp,align_corners=False)[0,0].detach().cpu().numpy()
    arrays[mode+'_canonical_depth']=d[0,0].detach().cpu().numpy()
    arrays[mode+'_canonical_confidence']=c[0,0].detach().cpu().numpy()
    unclipped=restore(d,'bicubic')*item['fx']/1000.
    arrays[mode+'_depth_unclipped']=unclipped
    arrays[mode+'_depth']=np.clip(unclipped,0,300)
    arrays[mode+'_confidence']=restore(c,'bilinear')
    logits=capture.pop('logits')[0].astype(np.float64)
    anchors=parent.depth_expectation_anchor[0].detach().cpu().numpy().astype(np.float64)
    if logits.shape[0]!=len(anchors) or len(anchors)!=256:raise RuntimeError('Actual anchors/logits mismatch')
    z=logits-logits.max(axis=0,keepdims=True);prob=np.exp(z);prob/=prob.sum(axis=0,keepdims=True)
    entropy=-(prob*np.log(np.maximum(prob,np.finfo(float).tiny))).sum(axis=0)
    mean=(prob*anchors[:,None,None]).sum(axis=0)
    stats={'initial_depth':mean,'bin_entropy':entropy,'bin_entropy_normalized':entropy/np.log(len(anchors)),
           'bin_variance':(prob*(anchors[:,None,None]-mean)**2).sum(axis=0),'bin_max_probability':prob.max(axis=0),
           'effective_bins':np.exp(entropy)}
    for field,value in stats.items():arrays[mode+'_'+field]=value.astype(np.float32)
    arrays[mode+'_anchors']=anchors.astype(np.float32)
    if args.smoke and mode=='native':arrays['native_raw_bin_logits']=logits.astype(np.float32)
    timing.append(dict(mode=mode+'_with_hook',canonical_shape=list(d.shape),bin_shape=list(logits.shape),**mem))
    del x,d,c,details,logits,z,prob
   a=arrays['native_depth'];b=arrays['flip_depth'][:,::-1]
   valid=np.isfinite(a)&np.isfinite(b)&(a>0)&(b>0)
   arrays['tta_valid']=valid
   arrays['flip_relative_disagreement']=np.where(valid,np.abs(a-b)/(np.abs(a)+1e-6),np.nan).astype(np.float32)
   arrays['flip_log_disagreement']=np.where(valid,np.abs(np.log(a+1e-6)-np.log(b+1e-6)),np.nan).astype(np.float32)
   arrays['confidence_flip_abs_difference']=np.abs(arrays['native_confidence']-arrays['flip_confidence'][:,::-1])
   destination=out/(item['sample_id']+'.npz')
   np.savez_compressed(destination,**arrays)
   row={'sample':item,'output':str(destination),'bytes':destination.stat().st_size,'sha256':sha(destination),
        'canonical_hw':[616,1064],'resize_scale':scale,'resized_hw':[hh,ww],'padding_ltrb':list(pad),
        'depth_restore':'baseline fx/1000; bicubic; clamp0..300','confidence_restore':'same unpad; bilinear; no depth scale',
        'times':timing,'TTA_invalid_pixels':int((~valid).sum()),'bin_anchor_count':len(anchors),
        'GT_used_for_inference':False,'model_weights_updated':False}
   rows.append(row);dump(out/(item['sample_id']+'.receipt.json'),row)
   print('SAMPLE_COMPLETE',item['sample_id'],'bytes',row['bytes'],flush=True)
  receipt.update(status='PASS',samples=len(rows),results=rows,mask_token_missing_allowance=keys.missing_keys,
                 encoder_input_observations=mask_observations,mask_token_used=False)
 except BaseException as e:
  receipt.update(status='FAILED',error=str(e),traceback=traceback.format_exc(),results=rows)
  dump(out/'INFERENCE_RECEIPT.json',receipt)
  raise
 dump(out/'INFERENCE_RECEIPT.json',receipt)
 print('STAGE_COMPLETE',receipt['status'],'samples',len(rows),'forwards',receipt['model_forwards'],flush=True)

if __name__=='__main__':main()

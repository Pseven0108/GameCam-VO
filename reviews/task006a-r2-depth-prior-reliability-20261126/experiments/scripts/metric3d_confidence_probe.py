"""UNEXECUTED GPU research runner. Standalone depth inference, never BA/SLAM.

Run only after a fresh trusted-SSH hardware check and approved sample manifest.
The current R2 CPU report does not claim this runner has passed a GPU smoke test.
"""
import argparse,hashlib,json,os,pathlib,subprocess,time

BASE=pathlib.Path('/root/rivermind-data/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408')
HUB=BASE/'data/torch_hub/yvanyin_metric3d_main'
CHECKPOINT=BASE/'data/torch_hub/checkpoints/metric_depth_vit_large_800k.pth'
EXPECTED='15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972'

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 # Hardware guard comes BEFORE importing torch or deserializing a checkpoint.
 info=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.free','--format=csv,noheader,nounits'],text=True)
 processes=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).strip()
 if processes:raise RuntimeError('GPU has another compute process; no takeover')
 if int(info.strip().split(',')[-1])<12000:raise RuntimeError('Conservative probe budget requires 12000 MiB free, not a measured minimum')
 assert sha(CHECKPOINT)==EXPECTED
 head=subprocess.check_output(['git','-C',str(HUB),'rev-parse','HEAD'],text=True).strip()
 assert head=='eb5b6fac0dc155e4e52f576e304fbf11655ff339'
 manifest_path=pathlib.Path(a.manifest);items=json.loads(manifest_path.read_text())['samples']
 if not 1<=len(items)<=16:raise ValueError('Small pilot is 1..16 images, not a full dataset pass')
 for row in items:
  if not row.get('sequence_id') or not row.get('frame_id') or row['fx']<=0:raise ValueError('Sample identity/focal missing')
  assert sha(pathlib.Path(row['rgb_path']))==row['rgb_sha256']
 out=pathlib.Path(a.out).resolve()
 if not str(out).startswith('/root/rivermind-data/GAMECAM_TASK006A_R2_'):raise ValueError('Independent R2 output required')
 out.mkdir(exist_ok=False,parents=True)
 os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
 import sys;sys.path.insert(0,str(HUB))
 import numpy as np
 import torch
 import torch.nn.functional as F
 from torchvision import transforms
 import torchvision.transforms.functional as TF
 from PIL import Image
 torch.hub.set_dir(str(BASE/'data/torch_hub'))
 def no_download(*args,**kwargs):raise RuntimeError('Network checkpoint download prohibited by probe')
 torch.hub.load_state_dict_from_url=no_download
 model=torch.hub.load(str(HUB),'metric3d_vit_large',source='local',pretrain=False)
 state=torch.load(str(CHECKPOINT),map_location='cpu')
 keys=model.load_state_dict(state['model_state_dict'],strict=False)
 del state
 # Fail closed: this pilot has no reviewed allow-list of incompatible keys.
 # The upstream loader uses strict=False, but a diagnostic must not silently
 # turn unmatched randomly initialized layers into purported checkpoint output.
 if keys.missing_keys or keys.unexpected_keys:
  (out/'CHECKPOINT_COMPATIBILITY_FAILURE.json').write_text(json.dumps({
   'missing_keys':keys.missing_keys,'unexpected_keys':keys.unexpected_keys,
   'model_forward_executed':False,'reason':'No reviewed checkpoint incompatibility allow-list'},indent=2)+'\n')
  raise RuntimeError('Checkpoint/model keys differ; stop before CUDA model execution')
 model=model.eval().cuda()
 chosen=[(name,mod) for name,mod in model.named_modules() if name.endswith('.depth_regressor')]
 if len(chosen)!=1:raise RuntimeError('Cannot uniquely identify native depth-bin regressor')
 name,layer=chosen[0];parent=dict(model.named_modules())[name.rsplit('.',1)[0]]
 capture={}
 def hook(module,inputs,output):capture['logits']=output.detach().cpu().numpy() # return None; no output mutation
 handle=layer.register_forward_hook(hook)
 rows=[]
 try:
  for i,item in enumerate(items):
   rgb=np.asarray(Image.open(item['rgb_path']).convert('RGB')).copy();h,w=rgb.shape[:2]
   scale=min(616/h,1064/w);hh,ww=int(h*scale),int(w*scale);dh,dw=616-hh,1064-ww
   pad=(dw//2,dh//2,dw-dw//2,dh-dh//2)
   arrays={};times=[]
   for mode in ('native','flip'):
    image=rgb if mode=='native' else rgb[:,::-1].copy()
    x=torch.from_numpy(image).permute(2,0,1)[None].float()/255.
    x=transforms.Resize((hh,ww))(x)
    x=transforms.Normalize([.485,.456,.406],[.229,.224,.225])(x)
    x=TF.pad(x,pad,fill=0.).cuda()
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();started=time.perf_counter()
    with torch.no_grad():d,c,details=model.inference({'input':x})
    torch.cuda.synchronize();seconds=time.perf_counter()-started
    if not torch.isfinite(d).all() or not torch.isfinite(c).all():raise RuntimeError('Nonfinite output; stop, no retry')
    def restore(t,interp):
     t=t[:,:,dh//2:616-(dh-dh//2),dw//2:1064-(dw-dw//2)]
     return F.interpolate(t,(h,w),mode=interp,align_corners=False)[0,0].detach().cpu().numpy()
    arrays[mode+'_depth']=np.clip(restore(d,'bicubic')*item['fx']/1000.,0,300)
    arrays[mode+'_confidence']=restore(c,'bilinear')
    arrays[mode+'_canonical_confidence']=c[0,0].detach().cpu().numpy()
    logits=capture.pop('logits')[0].astype(np.float64)
    anchors=parent.depth_expectation_anchor[0].detach().cpu().numpy().astype(np.float64)
    if logits.shape[0]!=len(anchors):raise RuntimeError('Depth anchor/logit mismatch')
    z=logits-logits.max(axis=0,keepdims=True);prob=np.exp(z);prob/=prob.sum(axis=0,keepdims=True)
    entropy=-(prob*np.log(np.maximum(prob,np.finfo(float).tiny))).sum(axis=0)
    mean=(prob*anchors[:,None,None]).sum(axis=0)
    arrays[mode+'_initial_depth']=mean.astype(np.float32)
    arrays[mode+'_bin_entropy']=entropy.astype(np.float32)
    arrays[mode+'_bin_variance']=(prob*(anchors[:,None,None]-mean)**2).sum(axis=0).astype(np.float32)
    arrays[mode+'_bin_max_probability']=prob.max(axis=0).astype(np.float32)
    arrays[mode+'_effective_bins']=np.exp(entropy).astype(np.float32)
    arrays[mode+'_anchors']=anchors.astype(np.float32)
    times.append({'mode':mode,'seconds_forward_with_hook':seconds,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                  'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'confidence_shape':list(c.shape),'logits_shape':list(logits.shape)})
    del details,d,c,x,logits,z,prob
   destination=out/(f'{i:03d}_'+item['sequence_id']+'_'+item['frame_id']+'.npz')
   np.savez_compressed(destination,**arrays)
   rows.append({'sample':item,'output':str(destination),'sha256':sha(destination),'times':times,
                'TTA_flip_before_preprocessing':True,'depth_GT_used_as_inference_input':False})
 finally:handle.remove()
 (out/'INFERENCE_RECEIPT.json').write_text(json.dumps({'Metric3D_commit':head,'checkpoint_sha256':EXPECTED,
  'torch':torch.__version__,'CUDA_build':torch.version.cuda,'model':'metric3d_vit_large','data_type':'float32',
  'load_state_dict_missing':keys.missing_keys,'load_state_dict_unexpected':keys.unexpected_keys,
  'GPU':info,'sample_count':len(rows),'results':rows,'SLAM_executed':False,'training_executed':False,
  'GT_error_evaluation_performed':False},indent=2)+'\n')

if __name__=='__main__':main()

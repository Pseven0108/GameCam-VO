"""Official-model forwards, independent of DROID-W, with explicit temporal context."""
import argparse
import gc
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback
from contextlib import contextmanager
import cv2
import numpy as np
from PIL import Image
import torch
import torch.nn.functional as F
from safetensors.torch import load_file

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
EXT=Path('D:/aaa/external_models/TASK010A');WEIGHT=EXT/'weights'


@contextmanager
def empty_parameters():
    """Defer parameter storage only; scalar control tensors remain on CPU.

    Every registered parameter must subsequently be strictly checkpoint-loaded.
    Avoids the upstream DINO linspace.item incompatibility with a meta device context.
    """
    original=torch.nn.Module.register_parameter
    def register(module,name,param):
        if param is not None:param=torch.nn.Parameter(param.to(device='meta'),requires_grad=param.requires_grad)
        return original(module,name,param)
    torch.nn.Module.register_parameter=register
    try:yield
    finally:torch.nn.Module.register_parameter=original


def resize_size(w,h,limit):
    scale=math.sqrt(limit/(w*h));ww=max(1,round(w*scale/14));hh=max(1,round(h*scale/14))
    while ww*hh*196>limit:
        if ww/hh>w/h:ww-=1
        else:hh-=1
    return ww*14,hh*14


def read_inputs(ds,limit):
    frames=[];pil=[]
    for fid in ds['rgb_ids']:
        path=Path(ds['rgb_dir'])/(f'{fid:05d}'+ds.get('image_suffix','.jpg'))
        with Image.open(path) as im:
            im.load();image=im.convert('RGB');pil.append(image.copy());wh=resize_size(*image.size,limit)
            frames.append(torch.from_numpy(np.array(image.resize(wh,Image.Resampling.LANCZOS)).copy()).permute(2,0,1).float()/255)
    return frames,pil


def save_prediction(out,fid,context,prob,conf=None,depth=None):
    p=prob.detach().float().cpu().numpy().squeeze()
    if p.ndim!=2 or not np.isfinite(p).all() or p.min()<0 or p.max()>1:raise RuntimeError('Invalid dynamic output')
    values={'target_rgb_id':np.array(fid),'context_rgb_ids':np.array(context),'probability':p}
    if conf is not None:values['confidence']=conf.detach().float().cpu().numpy().squeeze()
    if depth is not None:values['depth']=depth.detach().float().cpu().numpy().squeeze()
    np.savez_compressed(out/f'{fid:05d}.npz',**values)
    return {'rgb_id':fid,'context_rgb_ids':context,'hw':list(p.shape),'mean':float(p.mean()),
        'p90':float(np.quantile(p,.9)),'p99':float(np.quantile(p,.99)),
        'fraction_gt_point4':float((p>.4).mean()),'fraction_gt_point5':float((p>.5).mean())}


def gmos(ds,out,args,receipt):
    source=EXT/'gmos';sys.path[:0]=[str(source/'core/sam2'),str(source)]
    from core.pi3_encoder import Pi3Encoder
    from core.sam2_encoder import SAM2Encoder
    from core.gmos_s import GMOS_S
    from sam2.utils.transforms import SAM2Transforms
    frames,pil=read_inputs(ds,args.pixel_limit)
    ids=ds['rgb_ids'];indices=list(range(len(ids)))[:args.limit or len(ids)]
    print('GMOS: instantiate meta encoder',flush=True)
    with empty_parameters():encoder=Pi3Encoder()
    full=load_file(str(WEIGHT/'pi3.safetensors'))
    current=encoder.state_dict();subset={k:v for k,v in full.items() if k in current}
    match=encoder.load_state_dict(subset,strict=True,assign=True)
    receipt['pi3_load']={'strict_encoder':True,'excluded_unused_original_heads':sorted(set(full)-set(current))}
    del full,subset;gc.collect();print('GMOS: load encoder on GPU',flush=True);encoder.cuda().eval()
    tokens={}
    for index in indices:
        context=[max(0,min(len(ids)-1,index+o)) for o in [-8,-4,0,4,8]]
        x=torch.stack([frames[t] for t in context])[None].cuda()
        torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();tic=time.perf_counter()
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):token=encoder(x)[:,2].float()
        torch.cuda.synchronize();tokens[index]=token.cpu()
        receipt['encoder_timings'].append({'rgb_id':ids[index],'seconds':time.perf_counter()-tic,
            'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'context':[ids[t] for t in context]})
        print('GMOS_ENCODER',ds['name'],ids[index],receipt['encoder_timings'][-1],flush=True)
        del x,token
    encoder.cpu();del encoder;gc.collect();torch.cuda.empty_cache()
    with empty_parameters():sam=SAM2Encoder()
    state=torch.load(WEIGHT/'sam2.1_hiera_large.pt',map_location='cpu',weights_only=True,mmap=True)['model']
    subset={k:v for k,v in state.items() if k in sam.state_dict()}
    sam.load_state_dict(subset,strict=True,assign=True)
    receipt['sam2_load']={'strict_required_encoder_keys':True,'parameters':sum(p.numel() for p in sam.parameters())}
    del state,subset;sam.cuda().eval()
    with empty_parameters():model=GMOS_S()
    state=torch.load(WEIGHT/'gmos_s.pth',map_location='cpu',weights_only=True)['model_state_dict']
    state={k.removeprefix('module.'):v for k,v in state.items()}
    unused='pe_layer.positional_encoding_gaussian_matrix'
    # Released checkpoint retains this old positional BUFFER, absent from all
    # current GMOS_S forward reads. No learned or required tensor is omitted.
    if unused in state:
        receipt['unused_checkpoint_buffer']={'key':unused,'shape':list(state[unused].shape),'used_in_current_forward':False}
        del state[unused]
    model.load_state_dict(state,strict=True,assign=True);model.cuda().eval();del state
    receipt['gmos_load']={'strict_all_current_parameters_and_buffers':True}
    prep=SAM2Transforms(resolution=1024,mask_threshold=0.,max_hole_area=0.,max_sprinkle_area=0.)
    for index in indices:
        x=prep(pil[index])[None].cuda();torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();tic=time.perf_counter()
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
            backbone=sam.forward_image(x);_,vision,_,_=sam._prepare_backbone_features(backbone)
            btn,high=sam._get_vision_features(vision)
        with torch.inference_mode():
            result=model(tokens[index].cuda(),btn.float(),[t.float() for t in high])
            logits=F.interpolate(result['fg_mask'],size=frames[0].shape[-2:],mode='bilinear',align_corners=False)
            probability=logits.sigmoid()[0,0]
        torch.cuda.synchronize()
        context=receipt['encoder_timings'][index]['context']
        row=save_prediction(out,ids[index],context,probability)
        row.update(seconds=time.perf_counter()-tic,peak_allocated_bytes=torch.cuda.max_memory_allocated())
        receipt['frames'].append(row);print('GMOS_DONE',ds['name'],ids[index],row,flush=True)


def pi3mos(ds,out,args,receipt):
    source=Path('D:/aaa/external_models/Pi3MOS-SLAM_TASK008_FRESH');sys.path.insert(0,str(source))
    from pi3.models.pi3 import Pi3
    checkpoint=Path('D:/aaa/external_models/pi3mos_task008_weights/pi3mos_official.pth')
    with empty_parameters():model=Pi3()
    model.load_state_dict(load_file(str(checkpoint)),strict=True,assign=True);model.cuda().eval()
    receipt['weight_load']={'strict':True,'checkpoint':'TASK008 official safetensors; historical identity reused'}
    frames,_=read_inputs(ds,args.pixel_limit);ids=ds['rgb_ids']
    for index in list(range(len(ids)))[:args.limit or len(ids)]:
        context=[max(0,index+o) for o in [-10,-5,0]]
        x=torch.stack([frames[t] for t in context])[None].cuda()
        torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();tic=time.perf_counter()
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):pred=model(x)
        torch.cuda.synchronize()
        row=save_prediction(out,ids[index],[ids[t] for t in context],pred['dynamic_masks'][0,-1,0,:,:,0],
            pred['conf'][0,-1,:,:,0],pred['local_points'][0,-1,:,:,2])
        row.update(seconds=time.perf_counter()-tic,peak_allocated_bytes=torch.cuda.max_memory_allocated())
        receipt['frames'].append(row);print('PI3MOS_DONE',ds['name'],ids[index],row,flush=True)
        del x,pred


def geomotion(ds,out,args,receipt):
    source=EXT/'GeoMotion';sys.path.insert(0,str(source))
    from pi3.models.pi3_conf_flow_cam_lowfeature_wo_mean import create_pi3_motion_segmentation_model
    with empty_parameters():model=create_pi3_motion_segmentation_model(pi3_model_path=None)
    state=torch.load(WEIGHT/'geomotion_cvpr.pth',map_location='cpu',weights_only=True,mmap=True)
    model.load_state_dict(state['model_state_dict'],strict=True,assign=True);del state
    model.cuda().eval();frames,_=read_inputs(ds,args.pixel_limit);ids=ds['rgb_ids']
    receipt['weight_load']={'strict':True,'double_ImageNet_normalization_avoided':True,'RAFT_input':'original dense-flow magnitudes from admitted pair cache'}
    flowdir=TASK/'outputs/flows'/ds['name']
    # Eight consecutive frames; overlap allowed, per-frame predictions taken once.
    for start in range(0,args.limit or len(ids),4):
        end=min(len(ids),start+4)
        context=list(range(start,end)) if args.geo_context==4 else list(range(max(0,start-4),min(len(ids),start+4)))
        if len(context)<2:raise RuntimeError('Insufficient GeoMotion temporal input')
        x=torch.stack([frames[t] for t in context])[None].cuda();hh,ww=x.shape[-2:]
        flows=[]
        for t in context:
            j=min(len(ids)-1,t+2)
            path=flowdir/f'{ids[t]:05d}_{ids[j]:05d}.npz'
            if not path.exists():path=flowdir/f'{ids[t]:05d}_{ids[max(0,t-2)]:05d}.npz'
            with np.load(path,allow_pickle=False) as z:f=torch.from_numpy(z['flow'].copy()).permute(2,0,1)[None]
            f=F.interpolate(f,(hh,ww),mode='bilinear',align_corners=False)[0]
            f[0]*=ww/ds['hw'][1];f[1]*=hh/ds['hw'][0];flows.append(torch.linalg.norm(f,dim=0))
        flow=torch.stack(flows)[None].cuda();torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();tic=time.perf_counter()
        with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):pred=model(x,flows=flow)
        torch.cuda.synchronize();elapsed=time.perf_counter()-tic
        for t in range(start,end):
            if args.limit and t>=args.limit:break
            local=context.index(t)
            row=save_prediction(out,ids[t],[ids[c] for c in context],pred['motion_mask'][0,local],
                pred['conf'][0,local,:,:,0],pred['local_points'][0,local,:,:,2])
            row.update(chunk_seconds=elapsed,peak_allocated_bytes=torch.cuda.max_memory_allocated())
            receipt['frames'].append(row);print('GEOMOTION_DONE',ds['name'],ids[t],row,flush=True)
        del x,flow,pred


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',choices=['gmos','pi3mos','geomotion'],required=True)
    p.add_argument('--dataset',required=True);p.add_argument('--limit',type=int,default=0)
    p.add_argument('--pixel-limit',type=int,default=255000);p.add_argument('--output-suffix',default='')
    p.add_argument('--geo-context',type=int,choices=[4,8],default=4);a=p.parse_args()
    ds=next(d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text()) if d['name']==a.dataset)
    out=TASK/'outputs'/a.model/(a.dataset+a.output_suffix);out.mkdir(parents=True,exist_ok=False)
    print('START',a.model,a.dataset,flush=True)
    receipt={'status':'STARTED','model':a.model,'dataset':a.dataset,'frames':[],'encoder_timings':[],
             'pixel_limit':a.pixel_limit,'GPU':torch.cuda.get_device_name(0),'torch':torch.__version__,
             'autocast':'BF16; parameters FP32','GT_loaded':False,'original_source_edited':False,
             'geomotion_context_frames':a.geo_context if a.model=='geomotion' else None}
    torch.set_num_threads(2);torch.manual_seed(43);np.random.seed(43);cv2.setNumThreads(1)
    tic=time.perf_counter()
    try:
        globals()[a.model](ds,out,a,receipt)
        receipt.update(status='COMPLETE',total_seconds=time.perf_counter()-tic)
    except Exception:
        receipt.update(status='FAILED',traceback=traceback.format_exc(),total_seconds=time.perf_counter()-tic)
        raise
    finally:(out/'receipt.json').write_text(json.dumps(receipt,indent=2))


if __name__=='__main__':main()

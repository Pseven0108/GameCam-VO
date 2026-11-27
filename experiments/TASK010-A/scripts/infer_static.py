"""Bounded pretrained MDTracker inference, without importing BA-Track SLAM."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import torch
import torch.nn.functional as F


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dataset',required=True);ap.add_argument('--source',required=True);ap.add_argument('--weights',required=True)
    ap.add_argument('--cache-root',required=True);ap.add_argument('--output',required=True)
    ap.add_argument('--frames',type=int,default=8);ap.add_argument('--height',type=int,default=192)
    ap.add_argument('--width',type=int,default=336);ap.add_argument('--grid',type=int,default=6)
    ap.add_argument('--precision',choices=['fp32','bf16','fp16'],default='fp32')
    ap.add_argument('--metric-priors',type=Path,help='Optional independently cached Metric3D depth; never GT')
    args=ap.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(Path(args.source).resolve()))
    from omegaconf import OmegaConf
    from main.frontend.md_tracker import MDTracker
    cfg=OmegaConf.load(Path(args.source)/'configs/davis_demo.yaml')
    model=MDTracker(cfg).eval()
    state=torch.load(args.weights,map_location='cpu',weights_only=True)
    model.load_state_dict(state,strict=True);model.cuda()
    root=Path(args.cache_root); ds=next(d for d in json.loads((Path(__file__).resolve().parents[3]/'experiments/TASK010-A/private/DATA_MANIFEST.json').read_text()) if d['name']==args.dataset); ids=ds['rgb_ids']; rgbds=[];hashes=[]
    for fid in ids:
        p=Path(ds['rgb_dir'])/(f'{fid:05d}'+ds.get('image_suffix','.jpg'));im=Image.open(p).convert('RGB').resize((args.width,args.height),Image.Resampling.BILINEAR)
        rgb=np.asarray(im,dtype=np.float32).transpose(2,0,1)
        if args.metric_priors:
            prior=args.metric_priors/f'depth_{fid:05d}.npy'
            d=torch.from_numpy(np.load(prior,allow_pickle=False).copy()).float()[None,None]
        else:
            prior=root/'A/predictions'/f'{fid:05d}.npz'
            with np.load(prior,allow_pickle=False) as z:
                if int(z['target_rgb_id'])!=fid:raise ValueError('Frame mismatch')
                d=torch.from_numpy(z['depth_model'].copy()).float()[None,None]
        d=F.interpolate(d,size=(args.height,args.width),mode='bilinear',align_corners=False)[0,0]
        # This is a nonmetric Pi3 auxiliary depth, not UniDepth or ground truth.
        if not torch.isfinite(d).all() or (d>0.01).sum()<100:raise ValueError('Invalid auxiliary depth')
        d=d.clamp_min(0.011)
        rgbds.append(torch.cat([torch.from_numpy(rgb),d[None]],0))
        hashes.append({'rgb_id':fid,'rgb_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                       'prior_sha256':hashlib.sha256(prior.read_bytes()).hexdigest()})
    rgbds=torch.stack(rgbds)[None].cuda()
    ys=torch.linspace(12,args.height-13,args.grid,device='cuda');xs=torch.linspace(12,args.width-13,args.grid,device='cuda')
    yy,xx=torch.meshgrid(ys,xs,indexing='ij');xy=torch.stack([xx.flatten(),yy.flatten()],-1)
    depth=rgbds[0,0,3,yy.flatten().long(),xx.flatten().long()]
    queries=torch.cat([torch.zeros(len(xy),1,device='cuda'),xy,depth[:,None]],-1)[None]
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();start=time.perf_counter()
    amp={'bf16':torch.bfloat16,'fp16':torch.float16}.get(args.precision,torch.float32)
    with torch.inference_mode(),torch.autocast('cuda',dtype=amp,enabled=args.precision!='fp32'):
        tracks,_,depths,static,vis,dynamic,_=model(rgbds.clone(),queries,iters=4)
    torch.cuda.synchronize();elapsed=time.perf_counter()-start
    arrays={k:v.detach().float().cpu().numpy() for k,v in
            [('total_xy',tracks),('track_depth',depths),('static_xyz',static),('visibility',vis),('dynamic_probability',dynamic)]}
    if not all(np.isfinite(x).all() for x in arrays.values()):raise ValueError('Nonfinite MDTracker output')
    np.savez_compressed(out/'predictions.npz',**arrays,rgb_ids=ids)
    (out/'input_manifest.json').write_text(json.dumps(hashes,indent=2))
    stats={'status':'INDEPENDENT_INFERENCE_COMPLETE','input_shape':list(rgbds.shape),'queries':int(queries.shape[1]),
           'precision':args.precision,'seconds':elapsed,'seconds_per_frame':elapsed/len(ids),
           'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),
           'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,
           'checkpoint_sha256':hashlib.sha256(Path(args.weights).read_bytes()).hexdigest(),
           'depth_source':('Cached official Metric3D prediction; not GT or official UniDepth pipeline' if args.metric_priors else
                           'TASK008 Pi3 local_points z; auxiliary nonmetric, not official UniDepth pipeline'),
           'outputs':{k:{'shape':list(v.shape),'min':float(v.min()),'median':float(np.median(v)),
                           'max':float(v.max())} for k,v in arrays.items()},
           'dynamic_gt_available':False,'accuracy_claim':False,'droid_integration_complete':False}
    (out/'statistics.json').write_text(json.dumps(stats,indent=2))
    panels=[]
    for t in sorted(set([0,len(ids)//2,len(ids)-1])):
        im=Image.open(Path(ds['rgb_dir'])/(f'{ids[t]:05d}'+ds.get('image_suffix','.jpg'))).convert('RGB').resize((args.width,args.height))
        draw=ImageDraw.Draw(im)
        for j,p in enumerate(arrays['total_xy'][0,t]):
            if arrays['visibility'][0,t,j]<.5:continue
            color=(255,50,40) if arrays['dynamic_probability'][0,t,j]>.4 else (30,255,70)
            x,y=p;draw.ellipse((x-2,y-2,x+2,y+2),fill=color)
            sx,sy=arrays['static_xyz'][0,t,j,:2];draw.line((x,y,sx,sy),fill=(30,160,255),width=1)
        draw.text((5,5),f'RGB{ids[t]} total: dot / static: blue',fill='white');panels.append(im)
    sheet=Image.new('RGB',(args.width*len(panels),args.height))
    for i,im in enumerate(panels):sheet.paste(im,(i*args.width,0))
    sheet.save(out/'track_contact_sheet.jpg',quality=90)
    print(json.dumps(stats,indent=2))


if __name__=='__main__':main()

"""Bounded, sequential native Metric3D and DINO forwards on the local 5060."""
import argparse,json,time
import numpy as np
from runtime_local import *

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['depth','features'],required=True)
    p.add_argument('--limit',type=int,default=64);a=p.parse_args()
    import torch
    import torch.nn.functional as F
    from src.utils.common import setup_seed
    offline_hub();setup_seed(43);torch.set_num_threads(4)
    out=CACHE;out.mkdir(parents=True,exist_ok=True)
    cfg=config(out);stream=stream_class()(cfg)
    if a.mode=='depth':
        from src.utils.mono_priors.metric_depth_estimators import get_metric_depth_estimator,predict_metric_depth
        model=get_metric_depth_estimator(cfg)
        replaced=compatible_metric_attention()
        print('LOCAL_ATTENTION_BACKEND',replaced,'PyTorch_SDPA',flush=True)
        captured={};original=model.inference
        def tapped(value):
            d,c,more=original(value);captured['confidence']=c.detach().clone();return d,c,more
        model.inference=tapped
    else:
        from src.utils.mono_priors.img_feature_extractors import get_feature_extractor,predict_img_features
        model=get_feature_extractor(cfg)
    torch.cuda.reset_peak_memory_stats();records=[];started=time.perf_counter()
    with torch.no_grad(),torch.amp.autocast('cuda',enabled=True):
        for i in range(min(a.limit,len(stream))):
            path=out/a.mode/f'{i:05d}.npz'
            if path.exists():
                records.append(dict(index=i,rgb_id=stream.ids[i],sha256=sha(path),reused=True));continue
            _,image,_,_=stream[i]
            t=time.perf_counter();fields={};rng=[]
            if a.mode=='depth':
                for name,x in [('native',image),('flip',torch.flip(image,[-1]))]:
                    cpu=torch.get_rng_state().clone();gpu=torch.cuda.get_rng_state().clone()
                    depth=predict_metric_depth(model,i,x,cfg,'cuda',save_depth=False)
                    conf=captured.pop('confidence')
                    h,w=image.shape[-2:];scale=min(616/h,1064/w)
                    dh,dw=616-int(h*scale),1064-int(w*scale)
                    conf=conf[:,:,dh//2:616-(dh-dh//2),dw//2:1064-(dw-dw//2)]
                    conf=F.interpolate(conf,size=(h,w),mode='bilinear',align_corners=False)[0,0]
                    torch.cuda.synchronize()
                    rng.append(torch.equal(cpu,torch.get_rng_state()) and torch.equal(gpu,torch.cuda.get_rng_state()))
                    fields[name+'_depth']=depth.cpu().numpy();fields[name+'_confidence']=conf.cpu().numpy()
                d,f=fields['native_depth'],fields['flip_depth'][:,::-1]
                fields['tta_valid']=np.isfinite(d)&np.isfinite(f)&(d>0)&(f>0)
            else:
                cpu=torch.get_rng_state().clone();gpu=torch.cuda.get_rng_state().clone()
                feature=predict_img_features(model,i,image,cfg,'cuda',save_feat=False)
                torch.cuda.synchronize()
                rng.append(torch.equal(cpu,torch.get_rng_state()) and torch.equal(gpu,torch.cuda.get_rng_state()))
                fields['feature']=feature.cpu().numpy()
            if not all(rng):raise RuntimeError('A cached forward consumed RNG')
            if any(not np.isfinite(v).all() for v in fields.values()):raise RuntimeError('Nonfinite cached output')
            path.parent.mkdir(exist_ok=True);np.savez_compressed(path,**fields)
            record=dict(index=i,rgb_id=stream.ids[i],sha256=sha(path),seconds=time.perf_counter()-t,
                dtype={k:str(v.dtype) for k,v in fields.items()},shape={k:list(v.shape) for k,v in fields.items()},
                RNG_unchanged=True)
            records.append(record);write(out/f'{a.mode}_PROGRESS.json',dict(done=len(records),total=a.limit,last=record))
            print('CACHE',a.mode,i,record['seconds'],flush=True)
    write(out/f'{a.mode}_RECEIPT_{a.limit:03d}.json',dict(status='COMPLETE',frames=len(records),records=records,
        seconds=time.perf_counter()-started,autocast='native float16',input_resize_device='cpu',
        peak_allocated=torch.cuda.max_memory_allocated(),peak_reserved=torch.cuda.max_memory_reserved()))
    print('CACHE_COMPLETE',a.mode,len(records),flush=True)

if __name__=='__main__':main()

"""Cache exactly the native depth restoration plus raw confidence and flip."""
import argparse,json,time,traceback
import numpy as np
from runtime import *


def main():
    p=argparse.ArgumentParser();p.add_argument('--window',required=True);a=p.parse_args()
    import torch
    import torch.nn.functional as F
    from src.utils.common import setup_seed
    from src.utils.mono_priors.metric_depth_estimators import get_metric_depth_estimator,predict_metric_depth
    out=TASK/'cache'/a.window;out.mkdir(parents=True,exist_ok=False)
    cfg=config(a.window,out);setup_seed(43);offline_hub()
    model=get_metric_depth_estimator(cfg).to('cuda').eval()
    stream=stream_class()(cfg,a.window);captured={};original=model.inference
    def tapped(value):
        d,c,more=original(value);captured['confidence']=c.detach().clone();return d,c,more
    model.inference=tapped
    h,w=360,640;scale=min(616/h,1064/w);hh,ww=int(h*scale),int(w*scale);dh,dw=616-hh,1064-ww
    records=[];started=time.perf_counter()
    with torch.no_grad():
        for i in range(len(stream)):
            _,image,_,_=stream[i];image=image.cuda()
            fields={}
            for name,x in [('native',image),('flip',torch.flip(image,[-1]))]:
                cpu_rng=torch.get_rng_state().clone();gpu_rng=torch.cuda.get_rng_state().clone()
                t=time.perf_counter()
                depth=predict_metric_depth(model,i,x,cfg,'cuda',save_depth=False)
                conf=captured.pop('confidence')[:,:,dh//2:616-(dh-dh//2),dw//2:1064-(dw-dw//2)]
                conf=F.interpolate(conf,size=(h,w),mode='bilinear',align_corners=False)[0,0]
                torch.cuda.synchronize()
                if not torch.equal(cpu_rng,torch.get_rng_state()) or not torch.equal(gpu_rng,torch.cuda.get_rng_state()):
                    raise RuntimeError('Native forward changes RNG state; unverified cache replacement forbidden')
                fields[name+'_depth']=depth.detach().cpu().numpy()
                fields[name+'_confidence']=conf.detach().cpu().numpy()
                if not np.isfinite(fields[name+'_depth']).all() or not np.isfinite(fields[name+'_confidence']).all():
                    raise RuntimeError('Nonfinite real prior output')
            aa,bb=fields['native_depth'],fields['flip_depth'][:,::-1]
            fields['tta_valid']=np.isfinite(aa)&np.isfinite(bb)&(aa>0)&(bb>0)
            dest=out/f'{i:05d}.npz';np.savez_compressed(dest,**fields)
            records.append(dict(timestamp=i,rgb_id=stream.ids[i],sha256=sha(dest),bytes=dest.stat().st_size))
            print('PRIOR',a.window,i,flush=True)
    write(out/'CACHE_RECEIPT.json',dict(status='COMPLETE',records=records,frames=len(records),
        model_forwards=2*len(records),seconds=time.perf_counter()-started,native_forward_RNG_unchanged=True,
        actual_metric_focal=cfg['cam']['fx'],actual_tracker_K=stream.get_intrinsic().tolist(),
        native_restoration_unchanged=True,source_predictor_sha256=sha(SOURCE/'src/utils/mono_priors/metric_depth_estimators.py')))


if __name__=='__main__':
    try:main()
    except BaseException:
        traceback.print_exc();raise

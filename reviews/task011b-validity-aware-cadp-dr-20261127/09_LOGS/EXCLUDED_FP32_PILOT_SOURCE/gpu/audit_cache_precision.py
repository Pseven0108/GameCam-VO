"""Compare cached forwards to the actual native MotionFilter autocast context."""
import argparse, time
import numpy as np
from runtime import *


def main():
    import torch
    from src.utils.common import setup_seed
    from src.utils.mono_priors.metric_depth_estimators import get_metric_depth_estimator, predict_metric_depth
    p=argparse.ArgumentParser();p.add_argument('--window',required=True);a=p.parse_args()
    out=TASK/'precision_audit_001';out.mkdir(exist_ok=False)
    cfg=config(a.window,out);setup_seed(43);torch.set_num_threads(4);offline_hub()
    model=get_metric_depth_estimator(cfg).to('cuda').eval()
    stream=stream_class()(cfg,a.window);_,image,_,_=stream[0];image=image.cuda()
    captured={};original=model.inference
    def tap(value):
        d,c,more=original(value);captured['confidence']=c.detach().clone();return d,c,more
    model.inference=tap
    values={};rows=[]
    for name,amp in [('fp32_repeat',False),('native_amp_0',True),('native_amp_1',True)]:
        before_cpu=torch.get_rng_state().clone();before_cuda=torch.cuda.get_rng_state().clone();t=time.perf_counter()
        with torch.no_grad(),torch.amp.autocast('cuda',enabled=amp):
            depth=predict_metric_depth(model,0,image,cfg,'cuda',save_depth=False)
        torch.cuda.synchronize()
        values[name]=depth.cpu().numpy().copy()
        values[name+'_confidence']=captured.pop('confidence').cpu().numpy().copy()
        rows.append(dict(name=name,autocast_enabled=amp,output_dtype=str(depth.dtype),seconds=time.perf_counter()-t,
            rng_unchanged=bool(torch.equal(before_cpu,torch.get_rng_state()) and torch.equal(before_cuda,torch.cuda.get_rng_state()))))
    with np.load(TASK/'cache'/a.window/'00000.npz',allow_pickle=False) as z:values['cached_fp32']=z['native_depth'].copy()
    comparisons=[]
    for left,right in [('cached_fp32','fp32_repeat'),('cached_fp32','native_amp_0'),('native_amp_0','native_amp_1')]:
        x,y=values[left].astype(np.float64),values[right].astype(np.float64);delta=abs(x-y)
        comparisons.append(dict(left=left,right=right,bitwise_equal=bool(np.array_equal(values[left],values[right])),
            max_absolute_error=float(delta.max()),median_absolute_error=float(np.median(delta)),
            mean_absolute_error=float(delta.mean()),different_pixels=int(np.count_nonzero(delta)),pixels=int(x.size),
            relative_mean=float((delta/(abs(y)+1e-6)).mean()),all_finite=bool(np.isfinite(x).all() and np.isfinite(y).all())))
    np.savez_compressed(out/'same_frame_outputs.npz',**values)
    receipt=dict(status='COMPLETE',window=a.window,rgb_id=stream.ids[0],calls=rows,comparisons=comparisons,
        native_context="MotionFilter.track @torch.amp.autocast('cuda',enabled=True)",
        native_autocast_dtype=str(torch.get_autocast_gpu_dtype()),motion_filter_sha256=sha(SOURCE/'src/motion_filter.py'),
        predictor_sha256=sha(SOURCE/'src/utils/mono_priors/metric_depth_estimators.py'),
        archive_sha256=sha(out/'same_frame_outputs.npz'))
    write(out/'PRECISION_AUDIT.json',receipt);print(json.dumps(receipt,indent=2),flush=True)


if __name__=='__main__':main()

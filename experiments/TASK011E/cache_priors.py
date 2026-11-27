import argparse as _approval_argparse,os as _approval_os
from authorization import require_approved_runtime as _require_runtime
_gate_parser=_approval_argparse.ArgumentParser(add_help=False)
_gate_parser.add_argument('--approval',default=_approval_os.environ.get('TASK011D_RUNTIME_APPROVAL'))
_gate_parser.add_argument('--job-key',default=_approval_os.environ.get('TASK011D_RUNTIME_JOB'))
_gate_parser.add_argument('--window')
_gate_parser.add_argument('--arm')
_gate_parser.add_argument('--seed',type=int)
_gate_args,_=_gate_parser.parse_known_args()
_require_runtime(_gate_args.approval,'PRIOR_CACHE',_gate_args.job_key)
from authorization import verify_requested_job as _verify_requested_job
_verify_requested_job('PRIOR_CACHE',_gate_args.job_key,_gate_args.window,_gate_args.arm,_gate_args.seed)
from native_binding import verify_upstream_source as _verify_upstream
_verify_upstream()
"""Cache exactly the native depth restoration plus raw confidence and flip."""
import argparse,json,time,traceback,io,shutil
import numpy as np
from runtime import *


def main():
    p=argparse.ArgumentParser();p.add_argument('--window',required=True);p.add_argument('--approval',required=True);p.add_argument('--job-key',required=True);a=p.parse_args()
    from authorization import require_approved_runtime
    require_approved_runtime(a.approval,'PRIOR_CACHE',a.job_key)
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
    # MotionFilter.track supplies this context in the frozen native pipeline.
    # no_grad alone changes Metric3D's arithmetic and is not an equivalent cache.
    with torch.no_grad(),torch.amp.autocast('cuda',enabled=True):
        for i in range(len(stream)):
            _,image,_,_=stream[i]
            # Native Tracker passes the CPU RGB tensor to predict_metric_depth;
            # resizing/normalization happen on CPU before its internal .to(cuda).
            if image.device.type!='cpu':raise RuntimeError('Native RGB preprocessing device changed')
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
            dest=out/f'{i:05d}.npz'
            payload=io.BytesIO();np.savez_compressed(payload,**fields);raw=payload.getvalue()
            free=shutil.disk_usage(out).free
            if free<10*1024**3+len(raw)+1024**2:
                write(out/'STORAGE_BLOCKED.json',dict(status='STORAGE_BLOCKED',timestamp=i,
                    completed_frames=len(records),free_bytes=free,next_write_bytes=len(raw),safety_bytes=10*1024**3))
                raise RuntimeError('CACHE_STORAGE_BLOCKED: preserve partial cache; no automatic retry')
            with dest.open('xb') as file:file.write(raw)
            records.append(dict(timestamp=i,rgb_id=stream.ids[i],sha256=sha(dest),bytes=dest.stat().st_size))
            print('PRIOR',a.window,i,flush=True)
    write(out/'CACHE_RECEIPT.json',dict(status='COMPLETE',records=records,frames=len(records),
        model_forwards=2*len(records),seconds=time.perf_counter()-started,native_forward_RNG_unchanged=True,
        actual_metric_focal=cfg['cam']['fx'],actual_tracker_K=stream.get_intrinsic().tolist(),
        native_restoration_unchanged=True,autocast_enabled=True,autocast_dtype=str(torch.get_autocast_gpu_dtype()),
        precision_protocol='NATIVE_MOTION_FILTER_AUTOCAST_V2',input_preprocess_device='cpu',
        source_predictor_sha256=sha(SOURCE/'src/utils/mono_priors/metric_depth_estimators.py')))


if __name__=='__main__':
    try:main()
    except BaseException:
        traceback.print_exc();raise

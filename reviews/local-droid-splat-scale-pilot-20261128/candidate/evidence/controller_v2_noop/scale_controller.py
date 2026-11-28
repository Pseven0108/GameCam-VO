"""Instance-local BA interception. Production files are never edited."""
from functools import wraps
import json,pathlib
import torch
from scale_alignment import fit_prior,apply_prior

MAIN='FRONTEND_MAIN_LOOP_LOCAL_BA'
PASSTHROUGH={'INITIALIZATION','INITIALIZATION_SECOND_STAGE','FINAL_GLOBAL_BA','TRAJECTORY_FILLER','ONLINE_GLOBAL_BA'}

def install(video, extension, *, scale_enabled, a5_enabled, coefficients, log_path, endpoint_callback=None):
    if a5_enabled and extension is None:raise ValueError('A5 requires its isolated extension')
    if hasattr(video,'_local_scale_installed'):raise RuntimeError('Controller already installed')
    original=video.ba;namespace=original.__func__.__globals__
    backend=namespace['droid_backends'];n_calls=0;latest_fit=None;fits={};endpoint_done=False
    log_path=pathlib.Path(log_path)
    if log_path.exists():raise FileExistsError(log_path)
    def emit(row):
        with log_path.open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
    class Proxy:
        def __getattr__(self,key):return getattr(backend,key)
        @torch.no_grad()
        def ba(self,*args):
            nonlocal n_calls,latest_fit,endpoint_done
            if len(args)!=30:raise RuntimeError('Native BA positional contract drift')
            stage=getattr(video,'_local_scale_stage',None)
            if stage!=MAIN and stage not in PASSTHROUGH:raise RuntimeError('Unknown BA stage')
            eligible=stage==MAIN and not bool(args[23]) and video.metric_depth_reg
            if eligible and endpoint_callback is not None and not endpoint_done:
                endpoint_callback(args,backend,extension)
                endpoint_done=True
            args=list(args);n=int(video.counter.value);n_calls+=1
            raw_ts=video.timestamp[:n].detach().cpu()
            if not torch.isfinite(raw_ts).all() or not torch.equal(raw_ts,raw_ts.round()):
                raise RuntimeError('Keyframe timestamp is not an exact input identity')
            ts=raw_ts.to(torch.int64).tolist()
            current=getattr(video,'_local_input_timestamp',None)
            row=dict(call=n_calls,stage=stage,local_input_timestamp=current,keyframes=n,
                scale_active=bool(scale_enabled and eligible),a5_active=bool(a5_enabled and eligible),
                native_iterations=int(args[15]),gamma_depth=float(args[20]),fit_records=[])
            if scale_enabled and eligible:
                if current!=latest_fit:
                    # DROID-Splat's linear alignment excludes the newest candidate,
                    # uses >=2 view support, and never changes any camera pose.
                    indices=torch.arange(max(n-1,0),device=video.device,dtype=torch.int64)
                    if len(indices):
                        thresh=torch.full((len(indices),),.05,device=video.device)
                        before_pose=args[0].clone()
                        # The native kernel uses disps.size(0) as its valid frame
                        # bound. Exclude unused buffer slots from view support.
                        counts=backend.depth_filter(args[0][:n],args[1][:n],args[2],indices,thresh)
                        d=args[1].index_select(0,indices)
                        mask=(counts>=2)&torch.isfinite(d)&(d>1e-3)&(d>.01*d.mean((1,2),keepdim=True))
                        # The learned correspondence weight replaces DROID-Splat's
                        # tracker confidence; it is only an eligibility threshold,
                        # identical with and without A5, never a GT score.
                        w=args[5];ii=args[11]
                        for slot in indices.tolist():
                            edge=ii==slot
                            keep=mask[slot]
                            if edge.any():keep=keep&(w[edge].mean((0,1))>.1)
                            else:keep=torch.zeros_like(keep)
                            r=fit_prior(args[3][slot],d[slot],keep.float(),affine=False)
                            fits[ts[slot]]=r;row['fit_records'].append(dict(timestamp=ts[slot],**r.record()))
                        if not torch.equal(before_pose,args[0]):raise RuntimeError('Alignment mutated camera poses')
                    latest_fit=current
                corrected=args[3].clone()
                for slot,stamp in enumerate(ts):
                    if stamp in fits:corrected[slot]=apply_prior(args[3][slot],fits[stamp])
                args[3]=corrected.contiguous()
            if a5_enabled and eligible:
                strength=torch.zeros_like(args[1])
                for slot,stamp in enumerate(ts):
                    value=coefficients[stamp]
                    if value.shape!=args[1][slot].shape or not torch.isfinite(value).all() or (value<0).any() or (value>1).any():
                        raise RuntimeError('Invalid A5 coefficient cache')
                    strength[slot]=value
                result=extension.ba(*args,strength.contiguous(),True,False)
                row['reliability_mean']=float(strength[:n].mean())
            else:result=backend.ba(*args)
            row.update(disparity_min=float(args[1][:n].min()),negative_before_clamp=int((args[1][:n]<0).sum()),
                uncertainty_median=float(args[6][:n].median()),keyframe_input_indices=ts)
            if not bool(args[23]):
                row.update(dx_l2=float(result[0].norm()),dz_l2=float(result[1].norm()))
            emit(row);return result
    proxy=Proxy()
    @wraps(original)
    def wrapped(*args,**kwargs):
        if namespace['droid_backends'] is not backend:raise RuntimeError('Concurrent BA interceptor')
        namespace['droid_backends']=proxy
        try:return original(*args,**kwargs)
        finally:namespace['droid_backends']=backend
    video.ba=wrapped
    video._local_scale_installed=True

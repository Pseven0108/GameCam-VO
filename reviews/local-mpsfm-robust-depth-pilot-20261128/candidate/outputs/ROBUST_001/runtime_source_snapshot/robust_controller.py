"""Fail-closed, instance-local interception of Frontend Main-loop Local BA."""
from functools import wraps
import json,pathlib
import numpy as np
import torch
MAIN='FRONTEND_MAIN_LOOP_LOCAL_BA'
PASSTHROUGH={'INITIALIZATION','INITIALIZATION_SECOND_STAGE','FINAL_GLOBAL_BA','TRAJECTORY_FILLER','ONLINE_GLOBAL_BA'}

def eligible(stage,motion_only,metric_depth):
    if stage!=MAIN and stage not in PASSTHROUGH:raise RuntimeError('Unknown BA stage')
    return stage==MAIN and not motion_only and metric_depth

def install(video,extension,*,robust_enabled,a5_enabled,coefficients,log_path,endpoint_callback=None):
    if (a5_enabled or robust_enabled) and extension is None:raise ValueError('Missing isolated candidate extension')
    if hasattr(video,'_local_robust_installed'):raise RuntimeError('Already intercepted')
    original=video.ba;namespace=original.__func__.__globals__;backend=namespace['droid_backends']
    log_path=pathlib.Path(log_path)
    if log_path.exists():raise FileExistsError(log_path)
    n_calls=0;endpoint_done=False;detail_done=False
    class Proxy:
        def __getattr__(self,key):return getattr(backend,key)
        @torch.no_grad()
        def ba(self,*args):
            nonlocal n_calls,endpoint_done,detail_done
            if len(args)!=30:raise RuntimeError('Native BA signature drift')
            stage=getattr(video,'_local_scale_stage',None)
            active=eligible(stage,bool(args[23]),video.metric_depth_reg)
            if active and endpoint_callback is not None and not endpoint_done:
                endpoint_callback(args,backend,extension);endpoint_done=True
            n_calls+=1;n=int(video.counter.value)
            ts=video.timestamp[:n].detach().cpu()
            if not torch.isfinite(ts).all() or not torch.equal(ts,ts.round()):raise RuntimeError('Invalid keyframe identity')
            stamps=ts.long().tolist()
            row=dict(call=n_calls,stage=stage,local_input_timestamp=getattr(video,'_local_input_timestamp',None),
                keyframes=n,keyframe_input_indices=stamps,robust_active=bool(robust_enabled and active),
                a5_active=bool(a5_enabled and active),native_iterations=int(args[15]),gamma_depth=float(args[20]))
            if active and (a5_enabled or robust_enabled):
                strength=torch.ones_like(args[1])
                if a5_enabled:
                    strength.zero_()
                    for slot,stamp in enumerate(stamps):
                        value=coefficients[stamp]
                        if value.shape!=args[1][slot].shape or not torch.isfinite(value).all() or (value<0).any() or (value>1).any():
                            raise RuntimeError('Invalid A5 coefficient')
                        strength[slot]=value
                capture=bool(robust_enabled and not detail_done)
                result=extension.ba(*args,strength.contiguous(),True,False,robust_enabled,.1,capture)
                row['reliability_mean']=float(strength[:n].mean())
                if robust_enabled:
                    trace=result[3].detach().cpu().numpy()
                    if not np.isfinite(trace).all() or (trace[:,:,0]<0).any():raise RuntimeError('Missing robust per-iteration trace')
                    row['robust_iteration_trace']=trace.tolist()
                    if capture:
                        from robust_math import terms
                        detail=result[4].detach().cpu().numpy()
                        d,dm,eta,a,q,C,b,Cg,bg=np.moveaxis(detail,-1,0)
                        oracle=terms(Cg,bg,eta,dm,d,a,alpha=float(args[20]))
                        comparisons=[]
                        for field,actual in [('q',q),('C',C),('b',b)]:
                            diff=abs(actual.astype(np.float64)-oracle[field])
                            comparisons.append(dict(field=field,max_abs=float(diff.max()),
                                within_tolerance=bool(np.allclose(actual,oracle[field],atol=2e-7,rtol=3e-5))))
                        np.savez_compressed(log_path.parent/'FIRST_ROBUST_NATIVE_STATE.npz',detail=detail,trace=trace)
                        receipt=dict(status='PASS' if all(x['within_tolerance'] for x in comparisons) else 'FAIL',
                            comparisons=comparisons,iterations=detail.shape[0],full_element_count=int(q.size),
                            detail_fields=['d','dm','eta','a','q','C','b','Cg','bg'],
                            input_rgb_id=1658+int(getattr(video,'_local_input_timestamp')),
                            damping_independent_of_q=True,oracle='independent CPU float64 evaluation of every saved element')
                        (log_path.parent/'REAL_STATE_IRLS_ORACLE.json').write_text(json.dumps(receipt,indent=2)+'\n')
                        if receipt['status']!='PASS':raise RuntimeError('Real native IRLS terms exceed CPU oracle tolerance')
                        detail_done=True
                result=result[:2]
            else:result=backend.ba(*args)
            row.update(disparity_min=float(args[1][:n].min()),negative_before_clamp=int((args[1][:n]<0).sum()),
                clamp_below_1e5=int((args[1][:n]<1e-5).sum()),uncertainty_median=float(args[6][:n].median()))
            if not bool(args[23]):row.update(dx_l2=float(result[0].norm()),dz_l2=float(result[1].norm()))
            if not all(torch.isfinite(args[i]).all() for i in [0,1,6,7,9]):raise RuntimeError('Nonfinite live BA state')
            with log_path.open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
            return result
    proxy=Proxy()
    @wraps(original)
    def wrapped(*args,**kwargs):
        if namespace['droid_backends'] is not backend:raise RuntimeError('Concurrent interceptor')
        namespace['droid_backends']=proxy
        try:return original(*args,**kwargs)
        finally:namespace['droid_backends']=backend
    video.ba=wrapped;video._local_robust_installed=True

"""Experimental depth-prior-only controller; imports torch only at runtime.

Native U/UBA/target weights and the original two BA iterations are forwarded
unchanged. Initialization, final BA and filler use the installed native path.
"""
from dataclasses import dataclass,asdict
from functools import wraps
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from reliability import validity,disagreements,build_scores

MAIN='FRONTEND_MAIN_LOOP_LOCAL_BA'
PASSTHROUGH={'INITIALIZATION','INITIALIZATION_SECOND_STAGE','FINAL_GLOBAL_BA','TRAJECTORY_FILLER','ONLINE_GLOBAL_BA'}
ARMS={
 'A0':('OriginalInstalled',False,False),
 'A1':('OriginalD1Endpoint',True,False),
 'A2':('NativeOnly',True,False),
 'A3':('ValidityAwareFlip',True,False),
 'A4':('ValidityAwareRank',True,False),
 'A5':('ValidityAwareMax',True,False),
 'A6':('ValidityAwareRank',True,True),
}


@dataclass(frozen=True)
class ControlConfig:
    arm: str
    CADP_DR_ENABLE: bool
    DEPTH_RELIABILITY_METHOD: str
    TTA_VALIDITY_ENABLE: bool=True
    GEOMETRY_NEED_ENABLE: bool=False
    DEPTH_PRIOR_ALPHA: float=.01
    RELIABILITY_FUSION_WEIGHT: float=.5
    DEPTH_MIN_NATIVE_UNITS: float=1e-6
    DISAGREEMENT_EPSILON: float=1e-6

    def validate(self):
        if self.arm not in ARMS:raise ValueError('Unknown preregistered arm')
        method,enabled,geometry=ARMS[self.arm]
        if (self.DEPTH_RELIABILITY_METHOD,self.CADP_DR_ENABLE,self.GEOMETRY_NEED_ENABLE)!=(method,enabled,geometry):
            raise ValueError('Arm/config mismatch')
        if not self.TTA_VALIDITY_ENABLE:raise ValueError('Disabling validity is not a main experiment arm')
        if self.DEPTH_PRIOR_ALPHA!=.01 or self.RELIABILITY_FUSION_WEIGHT!=.5:
            raise ValueError('No unregistered alpha/fusion-weight change')
        return self


def arm_config(arm):
    method,enabled,geometry=ARMS[arm]
    return ControlConfig(arm,enabled,method,GEOMETRY_NEED_ENABLE=geometry).validate()


def should_intervene(config,phase,motion_only,metric_depth_reg):
    config.validate()
    if not config.CADP_DR_ENABLE:return False
    if motion_only:return False
    if phase!=MAIN and phase not in PASSTHROUGH:
        raise RuntimeError('Unknown/missing BA stage marker; no prior intervention allowed')
    return phase==MAIN and bool(metric_depth_reg)


def coefficient_map(native,flip_aligned,confidence,tta_valid,config):
    config.validate()
    if config.arm in ('A0','A1'):
        return np.ones(np.asarray(native).shape,dtype=np.float64),dict(original_prior_endpoint=True)
    masks=validity(native,flip_aligned,tta_valid,config.DEPTH_MIN_NATIVE_UNITS)
    values=disagreements(native,flip_aligned,masks['pair_valid'],config.DISAGREEMENT_EPSILON)
    scores=build_scores(confidence,values['SymmetricRelative'],masks,config.RELIABILITY_FUSION_WEIGHT)
    method=config.DEPTH_RELIABILITY_METHOD
    if method=='NativeOnly':result=scores['NativeOnly']['reliability'].copy()
    elif method=='ValidityAwareRank':result=scores['ValidityAwareFusion']['reliability'].copy()
    elif method in ('ValidityAwareFlip','ValidityAwareMax'):
        result=scores['NativeOnly']['reliability'].copy()
        chosen=scores['FlipOnly' if method=='ValidityAwareFlip' else 'MaxFusion']
        own=chosen['prior_allowed'];result[own]=chosen['reliability'][own]
    else:raise ValueError('Unknown risk control method')
    if np.any(result[~masks['native_valid']]!=0):raise RuntimeError('Invalid native prior unexpectedly enabled')
    return result,dict(native_invalid=int((~masks['native_valid']).sum()),pair_invalid=int((~masks['pair_valid']).sum()),
        native_fallback=int((scores['NativeOnly']['prior_allowed']&~masks['pair_valid']).sum()),
        prior_positive=int((result>0).sum()),mean_coefficient=float(result.mean()),
        coefficient_P50=float(np.median(result)),coefficient_P95=float(np.quantile(result,.95)),
        is_correctness_probability=False)


def install(video,candidate,config,reliability_by_timestamp,output,regression_callback=None):
    """Install only on a fresh instance from the frozen upstream source.

    reliability_by_timestamp is a complete map of 64 input indices to full
    360x640 reliability fields. It is derived independently of trajectory GT.
    """
    config.validate()
    if hasattr(video,'_task011b_installed'):raise RuntimeError('Controller already installed')
    import torch
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise FileExistsError('Preserve every native call receipt')
    original=video.ba
    namespace=original.__func__.__globals__
    native_backend=namespace['droid_backends']
    native_ba=native_backend.ba
    n_calls=0
    regression_done=False
    fields={}
    for timestamp,value in reliability_by_timestamp.items():
        value=np.asarray(value)
        if value.shape!=(video.ht,video.wd) or not np.isfinite(value).all() or (value<0).any() or (value>1).any():
            raise ValueError('Risk cache differs from tracker grid or bounded coefficient contract')
        sampled=value[video.slice_h,video.slice_w]
        if sampled.shape!=tuple(video.disps.shape[-2:]):raise ValueError('Native disparity sampling grid differs')
        fields[int(timestamp)]=torch.as_tensor(sampled.copy(),dtype=torch.float32,device=video.device)

    class Proxy:
        def __getattr__(self,name):return getattr(native_backend,name)
        def ba(self,*args):
            nonlocal n_calls,regression_done
            if len(args)!=30:raise RuntimeError('Frozen native BA positional signature changed')
            phase=getattr(video,'_task011b_phase',None)
            active=should_intervene(config,phase,bool(args[23]),video.metric_depth_reg)
            if regression_callback is not None and phase==MAIN and not bool(args[23]) and not regression_done:
                regression_callback(args,native_ba,candidate)
                regression_done=True
            n_calls+=1
            receipt=dict(call=n_calls,arm=config.arm,phase=phase,intervention=active,
                iterations=int(args[15]),native_gamma_depth=float(args[20]),motion_only=bool(args[23]),
                enable_update_uncer=bool(args[25]),enable_udba=bool(args[26]),
                original_U_and_geometric_weights_forwarded=True)
            if abs(float(args[20])-config.DEPTH_PRIOR_ALPHA)>1e-12:
                raise RuntimeError('Native alpha differs from preregistration')
            if not active:
                result=native_ba(*args)
            else:
                strength=torch.zeros_like(video.disps)
                n=int(video.counter.value)
                timestamps=video.timestamp[:n].detach().cpu().numpy()
                for slot,ts in enumerate(timestamps):
                    if not float(ts).is_integer() or int(ts) not in fields:
                        raise RuntimeError('Native keyframe timestamp has no exact prior cache identity')
                    strength[slot]=fields[int(ts)]
                result=candidate.ba(*args,strength.contiguous(),True,config.GEOMETRY_NEED_ENABLE)
                if len(result)!=3:raise RuntimeError('Candidate trace missing')
                geo=result[2].detach().cpu().numpy()
                if config.GEOMETRY_NEED_ENABLE:
                    if not np.isfinite(geo).all() or (geo[:,:,0]<0).any() or (geo[:,:,0]>1).any():
                        raise RuntimeError('Invalid geometry-need trace')
                    receipt['geometry_g_mean']=float(geo[:,:,0].mean())
                    receipt['geometry_g_min']=float(geo[:,:,0].min())
                    receipt['geometry_g_max']=float(geo[:,:,0].max())
                    receipt['geometry_u_median']=float(np.median(geo[:,:,1]))
                    receipt['geometry_trace']=geo.tolist()
                receipt['positive_strength_pixels']=int((strength[:n]>0).sum().item())
                receipt['relative_reliability_mean']=float(strength[:n].mean().item())
                receipt['candidate_native_solve_unchanged']=True
            n=int(video.counter.value)
            if not bool(args[23]):
                receipt['dx_l2']=float(result[0].norm().item())
                receipt['dz_l2']=float(result[1].norm().item())
                receipt['native_post_disparity_min']=float(args[1][:n].min().item())
                receipt['negative_before_native_outer_clamp']=int((args[1][:n]<0).sum().item())
            receipt['U_median']=float(args[6][:n].median().item())
            receipt['U_mean']=float(args[6][:n].mean().item())
            receipt['observer_version']=2
            receipt['keyframe_input_indices']=video.timestamp[:n].detach().cpu().int().tolist()
            if not bool(args[23]):
                source_indices=torch.unique(torch.cat([torch.arange(int(args[13]),int(args[14]),device=args[11].device),args[11]]))
                prior_mask=(args[3].index_select(0,source_indices)>0).float()
                effective=prior_mask*(strength.index_select(0,source_indices) if active else 1.)
                receipt['active_source_indices']=source_indices.cpu().tolist()
                receipt['depth_variables']=int(effective.numel())
                receipt['prior_eligible_native_pixels']=int(prior_mask.sum().item())
                receipt['prior_effective_positive_pixels']=int((effective>0).sum().item())
                if active and config.GEOMETRY_NEED_ENABLE:
                    receipt['effective_prior_mean_by_iteration']=[float((effective*result[2][i,:,0,None,None]).mean().item()) for i in range(int(args[15]))]
                else:receipt['effective_prior_mean_by_iteration']=[float(effective.mean().item())]*int(args[15])
            with output.open('a',encoding='utf-8') as f:f.write(json.dumps(receipt,allow_nan=False)+'\n')
            return result
    proxy=Proxy()

    @wraps(original)
    def wrapped(*args,**kwargs):
        if namespace['droid_backends'] is not native_backend:
            raise RuntimeError('Another BA interceptor is active; do not mix experiments')
        namespace['droid_backends']=proxy
        try:return original(*args,**kwargs)
        finally:namespace['droid_backends']=native_backend
    video.ba=wrapped
    video._task011b_installed=True
    return dict(config=asdict(config),scope=MAIN,installed_original_module_unchanged=True)

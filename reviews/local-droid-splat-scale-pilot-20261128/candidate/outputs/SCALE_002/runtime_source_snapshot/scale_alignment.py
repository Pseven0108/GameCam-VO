"""DROID-Splat-style fixed-map alignment of *inverse depth*.

Weighted normal equations follow ChenHoy/DROID-Splat, src/geom/__init__.py,
commit f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2 (Apache-2.0).
Scale-only is the preregistered local candidate; affine is an optional API,
not an automatically selected experiment. Neither fit uses trajectory GT.
"""
from dataclasses import dataclass, asdict
import torch

@dataclass
class Alignment:
    scale: float=1.
    shift: float=0.
    valid_pixels: int=0
    accepted: bool=False
    reason: str='NOT_FITTED'
    before_mae: float=0.
    after_mae: float=0.
    def record(self):return asdict(self)

@torch.no_grad()
def fit_prior(prediction, target, weights, *, affine=False, minimum_pixels=300,
              minimum_scale=.05):
    if prediction.shape!=target.shape or weights.shape!=target.shape:
        raise ValueError('Disparity and mask shapes differ')
    valid=torch.isfinite(prediction)&torch.isfinite(target)&torch.isfinite(weights)
    valid &= (prediction>0)&(target>1e-3)&(weights>0)
    n=int(valid.sum())
    result=Alignment(valid_pixels=n)
    if n<minimum_pixels:
        result.reason='INSUFFICIENT_MULTIVIEW_PIXELS';return result
    p=prediction[valid].double();t=target[valid].double();w=weights[valid].double()
    a00=(w*p*p).sum();a01=(w*p).sum();a11=w.sum()
    b0=(w*p*t).sum();b1=(w*t).sum()
    result.before_mae=float((w*(p-t).abs()).sum()/a11)
    if affine:
        det=a00*a11-a01*a01
        if det <= torch.finfo(torch.float64).eps*a00*a11*100:
            result.reason='DEGENERATE_AFFINE_SYSTEM';return result
        scale=(a11*b0-a01*b1)/det
        shift=(-a01*b0+a00*b1)/det
    else:
        if a00<=0:
            result.reason='DEGENERATE_SCALE_SYSTEM';return result
        scale=b0/a00;shift=scale.new_zeros(())
    if not torch.isfinite(scale) or not torch.isfinite(shift) or scale<minimum_scale:
        result.reason='INVALID_SCALE_OR_SHIFT';return result
    # Never create a negative corrected disparity from a valid input prior.
    output=scale*prediction[prediction>0].double()+shift
    if not torch.isfinite(output).all() or (output<=0).any():
        result.reason='NONPOSITIVE_CORRECTED_PRIOR';return result
    result.scale=float(scale);result.shift=float(shift)
    result.after_mae=float((w*(scale*p+shift-t).abs()).sum()/a11)
    result.accepted=True;result.reason='ACCEPTED_FIXED_POSE_GEOMETRY_FIT'
    return result

@torch.no_grad()
def apply_prior(prediction, result):
    if not result.accepted:return prediction.clone()
    valid=torch.isfinite(prediction)&(prediction>0)
    # Ineligible pixels remain exactly zero; affine must not invent measurements.
    return torch.where(valid,prediction*result.scale+result.shift,torch.zeros_like(prediction))

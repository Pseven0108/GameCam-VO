"""Fixed [0,1] probability displays; depth stretch is visualization only."""
import numpy as np
from PIL import Image


def heatmap(prob):
    p=np.asarray(prob,np.float32)
    assert np.isfinite(p).all() and p.min()>=0 and p.max()<=1
    return np.stack([255*p,210*(1-np.abs(2*p-1)),255*(1-p)],-1).astype(np.uint8)


def scalar_depth_view(depth):
    d=np.asarray(depth,np.float32);valid=np.isfinite(d)&(d>0)
    out=np.zeros((*d.shape,3),np.uint8)
    if not valid.any():return out,{'valid_fraction':0.}
    lo,hi=np.percentile(np.log(d[valid]),[2,98]);span=max(float(hi-lo),1e-12)
    normalized=np.clip((np.log(np.maximum(d,1e-12))-lo)/span,0,1)
    out=heatmap(normalized);out[~valid]=0
    return out,{'log_depth_display_P02':float(lo),'log_depth_display_P98':float(hi),'metric_units':False,'display_only':True}


def save_views(rgb_path,prob_original,conf,depth,out,fid,threshold=.4):
    with Image.open(rgb_path) as im:rgb=np.array(im.convert('RGB'))
    assert prob_original.shape==rgb.shape[:2]
    mask=prob_original>threshold
    overlay=rgb.copy();red=np.array([255,0,0],np.float32)
    overlay[mask]=np.rint(.55*rgb[mask]+.45*red).astype(np.uint8)
    for name in ['probability_gray','probability_heat','masks','overlays','confidence','depth']: (out/name).mkdir(exist_ok=True,parents=True)
    Image.fromarray(np.rint(prob_original*255).astype(np.uint8)).save(out/'probability_gray'/f'{fid:05d}.png')
    Image.fromarray(heatmap(prob_original)).save(out/'probability_heat'/f'{fid:05d}.jpg',quality=92)
    Image.fromarray(mask.astype(np.uint8)*255).save(out/'masks'/f'{fid:05d}.png')
    Image.fromarray(overlay).save(out/'overlays'/f'{fid:05d}.jpg',quality=94)
    Image.fromarray(heatmap(conf)).save(out/'confidence'/f'{fid:05d}.jpg',quality=92)
    view,meta=scalar_depth_view(depth);Image.fromarray(view).save(out/'depth'/f'{fid:05d}.jpg',quality=92)
    return meta

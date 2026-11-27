"""Isolated experimental BA observation gates; no native U/depth/solver rewrite."""
import functools
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from gamecam.modules.dynamic_prior.dynamic_mask import sample_probability
from gamecam.modules.dynamic_prior.feature_alignment import ImageGeometry

ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'experiments/TASK010-A'


def neutral_severity(p,t0=.4,t1=.8):
    return ((p-t0)/(t1-t0)).clamp(0,1)


def native_source_weight(u):
    return (1/(45*u-35).clamp_min(.1)).clamp(0,1)


class ScoreCache:
    def __init__(self,name,model):
        self.directory=TASK/'outputs'/model/name;self.loaded={}
        self.manifest=json.loads((self.directory/'PREDICTION_SHA256.json').read_text())
    def get(self,fid,device):
        if fid not in self.loaded:
            path=self.directory/f'{fid:05d}.npz'
            if hashlib.sha256(path.read_bytes()).hexdigest()!=self.manifest.get(path.name):raise ValueError('Prediction cache SHA mismatch')
            with np.load(path,allow_pickle=False) as z:
                if int(z['target_rgb_id'])!=fid:raise ValueError('Model frame identity mismatch')
                x=z['probability'].copy()
            if not np.isfinite(x).all() or x.min()<0 or x.max()>1:raise ValueError('Invalid motion score')
            self.loaded[fid]=torch.from_numpy(x)
        return self.loaded[fid].to(device)


def install_fusion(video,dataset,method,log_path):
    original=video.ba;ids=dataset['rgb_ids'];hw=tuple(dataset['hw']);rows=[]
    name=dataset['name'];model=method if method in ('geomotion','geomotion_full') else ('gmos' if method in ('gmos','fusion','fusion_static') else 'pi3mos')
    cache=ScoreCache(name,model)
    flowdir=TASK/'outputs/flows'/name
    geometry_cache={}

    def geometry(i,j,device,h,w):
        key=(i,j)
        if key not in geometry_cache:
            path=flowdir/f'{i:05d}_{j:05d}.npz'
            if path.exists():
                with np.load(path,allow_pickle=False) as z:
                    g=z['geometry_score'].copy();v=z['valid'].astype(np.float32)
                geometry_cache[key]=(torch.from_numpy(g),torch.from_numpy(v))
            else:geometry_cache[key]=None
        result=geometry_cache[key]
        if result is None:return None
        # DROID native feature coordinates are pixel positions 8*x, not resized centers.
        return tuple(t.to(device)[::video.down_scale,::video.down_scale][:h,:w] for t in result)

    @functools.wraps(original)
    def wrapped(target,weight,eta,ii,jj,*args,**kwargs):
        nonlocal rows
        ri=[ids[int(video.timestamp[i].item())] for i in ii.tolist()]
        rj=[ids[int(video.timestamp[j].item())] for j in jj.tolist()]
        h,w=weight.shape[2:4];device=weight.device
        yy,xx=torch.meshgrid(torch.arange(h,device=device),torch.arange(w,device=device),indexing='ij')
        source=torch.stack((xx,yy),-1).float()[None].expand(len(ri),-1,-1,-1)
        if method=='geometry':
            severity=torch.zeros(len(ri),h,w,device=device)
        else:
            ms=torch.stack([cache.get(fid,device) for fid in ri]);mt=torch.stack([cache.get(fid,device) for fid in rj])
            mapping=ImageGeometry(hw,tuple(ms.shape[-2:]))
            mi,_=sample_probability(ms,mapping.feature_to_map(source))
            mj,_=sample_probability(mt,mapping.feature_to_map(target[0]))
            p=torch.maximum(mi,mj)
            severity=neutral_severity(p)
        if method in ('legacy','legacy_mean'):
            g=((1-mi)*(1-mj)).clamp_min(.1)
            if method=='legacy_mean':g=torch.ones_like(g)*g.mean()
        else:
            supported=0
            if method in ('geometry','fusion','fusion_static'):
                for e,(i,j) in enumerate(zip(ri,rj)):
                    result=geometry(i,j,device,h,w)
                    if result is None:severity[e]=0;continue
                    residual,valid=result;supported+=1
                    if method=='geometry':severity[e]=residual*valid
                    else:severity[e]*=residual*valid
            # Fusion avoids applying the full external penalty to already suppressed UBA observations.
            if method in ('fusion','fusion_static'):
                severity*=native_source_weight(video.uncertainties[ii])
            g=1-.75*severity
        if not torch.isfinite(g).all() or g.min()<.249999 or g.max()>1.000001:
            if method not in ('legacy','legacy_mean'):raise ValueError('Gate contract failed')
        row={'call':len(rows),'method':method,'edges':len(ri),'mean_gate':float(g.mean()),
             'phase':getattr(video,'_task010_phase','UNVERIFIED'),
             'attenuated_fraction':float((g<.999999).float().mean()),'neutral_fraction':float((g==1).float().mean()),
             'gate_min':float(g.min()),'source_u_median':float(video.uncertainties[ii].median()),
             'source_uba_mean':float(native_source_weight(video.uncertainties[ii]).mean()),
             'input_weight_mean':float(weight.mean()),'output_weight_mean':float((weight*g[None,...,None]).mean()),
             'u_mutated_by_hook':False,'motion_only':bool(kwargs.get('motion_only',False))}
        rows.append(row)
        with Path(log_path).open('a') as f:f.write(json.dumps(row)+'\n')
        return original(target,weight*g[None,...,None],eta,ii,jj,*args,**kwargs)
    video.ba=wrapped
    return rows


def install_observer(video,mapping,out):
    original=video.ba;rows=[];out=Path(out);out.mkdir(exist_ok=False)
    @functools.wraps(original)
    def wrapped(target,weight,eta,ii,jj,*args,**kwargs):
        row={'call':len(rows),'edges':int(len(ii)),'weight_mean':float(weight.mean()),
             'phase':getattr(video,'_task010_phase','UNVERIFIED'),
             'enable_udba':bool(kwargs.get('enable_udba',False)),
             'enable_update_uncer':bool(kwargs.get('enable_update_uncer',False)),
             'motion_only':bool(kwargs.get('motion_only',False)),
             'u_median':float(video.uncertainties[ii].median()),
             'u_p95':float(torch.quantile(video.uncertainties[ii].flatten(),.95)),
             'positive_weight_fraction':float((weight>0).float().mean())}
        with torch.no_grad():
            coords,valid=video.reproject(ii,jj)
            proxy=(valid[...,0]>0)&torch.isfinite(coords).all(-1)&(coords[...,0]>=0)&(coords[...,0]<weight.shape[3]-1)&(coords[...,1]>=0)&(coords[...,1]<weight.shape[2]-1)
            row.update(geometric_valid_proxy_count=int(proxy.sum()),positive_weight_components=int((weight>0).sum()),
                       support_count_is_proxy_not_native_kernel_counter=True)
        rows.append(row)
        with (out/'calls.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        return original(target,weight,eta,ii,jj,*args,**kwargs)
    video.ba=wrapped
    return rows

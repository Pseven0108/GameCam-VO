"""Bounded native BA input receipts; no tensor mutation or extra solve."""
import functools
import json
from pathlib import Path
import numpy as np
import torch


def install_ba_observer(video,timestamp_to_rgb,output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    original=video.ba
    rows=[]
    saved=set()

    @functools.wraps(original)
    def wrapped(target,weight,eta,ii,jj,*args,**kwargs):
        ri=[timestamp_to_rgb[int(video.timestamp[i].item())] for i in ii.tolist()]
        rj=[timestamp_to_rgb[int(video.timestamp[j].item())] for j in jj.tolist()]
        candidates=[e for e,(i,j) in enumerate(zip(ri,rj)) if i!=j]
        if candidates:
            e=max(candidates,key=lambda e:rj[e])
            fid=rj[e]
            bucket=(fid-301)//8
            if bucket not in saved and len(saved)<4:
                np.savez_compressed(output/f'ba_input_bucket{bucket}.npz',
                    source_rgb=ri[e],target_rgb=fid,target=target[0,e].detach().float().cpu().numpy(),
                    weight=weight[0,e].detach().float().cpu().numpy(),
                    source_disp=video.disps[ii[e]].detach().float().cpu().numpy(),
                    source_u=video.uncertainties[ii[e]].detach().float().cpu().numpy(),
                    source_pose_w2c=video.poses[ii[e]].detach().float().cpu().numpy(),
                    target_pose_w2c=video.poses[jj[e]].detach().float().cpu().numpy())
                saved.add(bucket)
        row={'call':len(rows),'edges':len(ri),'min_rgb':min(ri+rj),'max_rgb':max(ri+rj),
             'motion_only':bool(kwargs.get('motion_only',False)),
             'enable_update_uncer':bool(kwargs.get('enable_update_uncer',False)),
             'enable_udba':bool(kwargs.get('enable_udba',False)),'native_weight_mean':float(weight.mean()),
             'native_weight_finite':bool(torch.isfinite(weight).all())}
        rows.append(row)
        with (output/'calls.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
        return original(target,weight,eta,ii,jj,*args,**kwargs)
    video.ba=wrapped
    return rows

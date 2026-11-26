"""Runtime hook at DepthVideo.ba, before native U weighting. No upstream rewrite."""
import functools
import json
from pathlib import Path
import torch
from .feature_alignment import ImageGeometry
from .dynamic_mask import DynamicObservationGate, GateConfig


def install_video_gate(video, cache, timestamp_to_rgb: dict[int, int], config=GateConfig(), log_path=None):
    if hasattr(video, "_task009_original_ba"):
        raise RuntimeError("Gate already installed: double multiplication prohibited")
    original = video.ba
    gate = DynamicObservationGate(config)
    log_path = Path(log_path) if log_path else None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    calls = []

    @functools.wraps(original)
    def wrapped(target, weight, eta, ii, jj, *args, **kwargs):
        if not config.enabled:
            return original(target, weight, eta, ii, jj, *args, **kwargs)
        if target.shape != weight.shape:
            raise ValueError("Unexpected native BA target/weight layout")
        si, sj = ii.detach().cpu().tolist(), jj.detach().cpu().tolist()
        def rgb_ids(indices):
            out=[]
            for i in indices:
                ts=float(video.timestamp[int(i)].item())
                if ts != int(ts) or int(ts) not in timestamp_to_rgb:
                    raise ValueError(f"Unmapped native timestamp {ts}")
                out.append(timestamp_to_rgb[int(ts)])
            return out
        ri,rj=rgb_ids(si),rgb_ids(sj)
        ms,mt=cache.batch(ri, weight.device),cache.batch(rj, weight.device)
        if ms.shape != mt.shape:
            raise ValueError("Probability-map geometry differs across edge endpoints")
        h,w=weight.shape[2:4]
        yy,xx=torch.meshgrid(torch.arange(h,device=weight.device),torch.arange(w,device=weight.device),indexing="ij")
        source=torch.stack((xx,yy),-1).float()[None].expand(len(si),-1,-1,-1)
        geometry=ImageGeometry(cache.tracker_hw,tuple(ms.shape[-2:]),float(video.down_scale))
        gated,stats=gate(weight,ms,mt,geometry.feature_to_map(source),geometry.feature_to_map(target[0]))
        receipt={"call":len(calls), "source_rgb":ri,"target_rgb":rj,"shape":list(weight.shape),
                 "native_u_untouched":True, "target_sampling":"predicted_target_correspondence",
                 **stats}
        calls.append(receipt)
        if log_path:
            with log_path.open("a",encoding="utf-8") as f:f.write(json.dumps(receipt)+"\n")
        return original(target,gated,eta,ii,jj,*args,**kwargs)

    video._task009_original_ba=original
    video.ba=wrapped
    return calls

"""Independent official RAFT + forward/backward and robust epipolar diagnostics.

Motion scores are heuristic evidence, never calibrated probabilities or mask GT.
"""
import argparse
import json
from pathlib import Path
import time
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision.models.optical_flow import raft_large
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
WEIGHT=Path('D:/aaa/external_models/TASK010A/weights/raft_large.pth')


def camera_flow(disparity,pose_i_w2c,pose_j_w2c,k):
    """Native xyzw, world-to-camera, feature-grid K; returns flow in feature pixels."""
    h,w=disparity.shape;y,x=np.mgrid[:h,:w].astype(np.float64)
    fx,fy,cx,cy=np.asarray(k,dtype=np.float64)
    Ri=Rotation.from_quat(pose_i_w2c[3:]).as_matrix();Rj=Rotation.from_quat(pose_j_w2c[3:]).as_matrix()
    r=Rj@Ri.T;t=pose_j_w2c[:3]-r@pose_i_w2c[:3]
    d=np.asarray(disparity,dtype=np.float64)
    rays=np.stack([(x-cx)/fx,(y-cy)/fy,np.ones_like(x)],-1)
    transformed=rays@r.T+t*d[...,None]
    z=transformed[...,2]
    valid=np.isfinite(d)&(d>1.00001e-5)&np.isfinite(transformed).all(-1)&(z>.2)
    q=np.stack([fx*transformed[...,0]/np.maximum(z,1e-12)+cx,fy*transformed[...,1]/np.maximum(z,1e-12)+cy],-1)
    flow=q-np.stack([x,y],-1)
    return flow,valid


def sampson_error(Fm,xy,q):
    p=np.concatenate([xy,np.ones((*xy.shape[:-1],1))],-1)
    t=np.concatenate([q,np.ones((*q.shape[:-1],1))],-1)
    a=p@Fm.T;b=t@Fm
    return np.abs(np.sum(t*a,axis=-1))/np.sqrt(np.maximum(np.sum(a[...,:2]**2,axis=-1)+np.sum(b[...,:2]**2,axis=-1),1e-12))


def geometry_score(flow,backward):
    h,w=flow.shape[:2];y,x=np.mgrid[:h,:w].astype(np.float32);xy=np.stack([x,y],-1);q=xy+flow
    reverse=cv2.remap(backward,q[...,0],q[...,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT,borderValue=1e6)
    fb=np.linalg.norm(flow+reverse,axis=-1)
    valid=((q[...,0]>=1)&(q[...,0]<w-2)&(q[...,1]>=1)&(q[...,1]<h-2)&
           (fb < 1.+.05*np.linalg.norm(flow,axis=-1)))
    select=valid[::4,::4]
    a=xy[::4,::4][select];b=q[::4,::4][select]
    Fm,mask=cv2.findFundamentalMat(a,b,cv2.USAC_MAGSAC,1.,.999,10000) if len(a)>=24 else (None,None)
    if Fm is None or Fm.shape!=(3,3) or not np.isfinite(Fm).all():
        return np.zeros((h,w),np.float32),valid,fb,np.zeros((h,w),np.float32),None,0.
    error=sampson_error(Fm,xy,q).astype(np.float32)
    # Predeclared dead zone in tracker image pixels, not fitted against trajectory GT.
    score=np.clip((error-1.)/3.,0,1)*valid
    return score.astype(np.float32),valid,fb,error,Fm,float(np.mean(mask))


def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);a=p.parse_args()
    ds=next(d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text()) if d['name']==a.dataset)
    out=TASK/'outputs/flows'/a.dataset;out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2);cv2.setNumThreads(1);cv2.setRNGSeed(43)
    model=raft_large(weights=None,progress=False)
    model.load_state_dict(torch.load(WEIGHT,map_location='cpu',weights_only=True),strict=True);model.cuda().eval()
    ids=ds['rgb_ids'];h,w=ds['hw'];hh=(h+7)//8*8;ww=(w+7)//8*8
    images={}
    for fid in ids:
        path=Path(ds['rgb_dir'])/(f'{fid:05d}'+ds.get('image_suffix','.jpg'))
        rgb=cv2.cvtColor(cv2.imread(str(path)),cv2.COLOR_BGR2RGB)
        rgb=cv2.resize(rgb,(w,h),interpolation=cv2.INTER_LINEAR)
        image=torch.from_numpy(rgb.copy()).permute(2,0,1)[None].float()/127.5-1
        images[fid]=F.pad(image,(0,ww-w,0,hh-h),mode='replicate')
    rows=[]
    for delta in [2,4]:
        for index in range(len(ids)-delta):
            i,j=ids[index],ids[index+delta]
            torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();tic=time.perf_counter()
            # FP32 matches torchvision's standard inference; no silent mixed-precision change.
            with torch.inference_mode():
                forward=model(images[i].cuda(),images[j].cuda(),num_flow_updates=12)[-1][0,:,:h,:w].permute(1,2,0).cpu().numpy()
                backward=model(images[j].cuda(),images[i].cuda(),num_flow_updates=12)[-1][0,:,:h,:w].permute(1,2,0).cpu().numpy()
            torch.cuda.synchronize();elapsed=time.perf_counter()-tic
            for s,t,f,b in [(i,j,forward,backward),(j,i,backward,forward)]:
                score,valid,fb,error,Fm,inlier=geometry_score(f,b)
                np.savez_compressed(out/f'{s:05d}_{t:05d}.npz',flow=f,geometry_score=score,valid=valid,
                    fb_error=fb,sampson_error=error,fundamental=Fm if Fm is not None else np.empty((0,0)))
                rows.append({'source_rgb':s,'target_rgb':t,'fb_valid_fraction':float(valid.mean()),
                    'dynamic_score_mean':float(score.mean()),'positive_score_fraction':float((score>0).mean()),
                    'RANSAC_inlier_fraction':inlier,'pair_forward_backward_seconds':elapsed,
                    'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'GT_used':False})
            print('FLOW',a.dataset,i,j,elapsed,flush=True)
    (out/'receipt.json').write_text(json.dumps({'status':'COMPLETE','dataset':a.dataset,'pairs':rows,
        'precision':'FP32','updates':12,'model':'torchvision RAFT Large C_T_SKHT_V2',
        'score_semantics':'uncalibrated robust epipolar residual; not moving-object GT'},indent=2))


if __name__=='__main__':main()

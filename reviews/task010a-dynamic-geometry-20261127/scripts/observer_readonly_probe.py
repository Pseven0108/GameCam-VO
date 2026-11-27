"""Actual native projection observer contract; GPU math, no model/BA/SLAM run."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
from gamecam.compat.torch_scatter_python import install
install()
from src.depth_video import DepthVideo

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'
with np.load(TASK/'outputs/droid/night007_dev_baseline_s43_r2/keyframes.npz',allow_pickle=False) as z:
    poses=torch.from_numpy(z['poses_w2c'].copy()).cuda();disps=torch.from_numpy(z['disps'].copy()).cuda()
k=torch.from_numpy(np.load(TASK/'private/datasets/night007_dev/intrinsics.npy')[0]).float().cuda()/8
video=SimpleNamespace(poses=poses,disps=disps,intrinsics=k[None].repeat(len(poses),1))
before=[v.clone() for v in [poses,disps,video.intrinsics]]
rng_cpu=torch.get_rng_state().clone();rng_cuda=torch.cuda.get_rng_state().clone()
ii=torch.tensor([0,0,1,3],device='cuda');jj=torch.tensor([0,1,3,1],device='cuda')
coords,valid=DepthVideo.reproject(video,ii,jj)
same=[torch.equal(a,b) for a,b in zip(before,[poses,disps,video.intrinsics])]
result={'status':'PASS' if all(same) else 'FAIL','poses_unchanged':same[0],
    'disps_unchanged':same[1],'K_unchanged':same[2],'CPU_RNG_unchanged':torch.equal(rng_cpu,torch.get_rng_state()),
    'CUDA_RNG_unchanged':torch.equal(rng_cuda,torch.cuda.get_rng_state()),
    'coordinates_finite':bool(torch.isfinite(coords).all()),'self_edge_and_cross_edges_tested':True,
    'model_loaded':False,'native_BA_called':False,'full_SLAM_called':False,
    'limit':'State/RNG preservation does not eliminate scheduling effects on later atomic numerical reductions'}
if not all(result[k] for k in ['poses_unchanged','disps_unchanged','K_unchanged','CPU_RNG_unchanged','CUDA_RNG_unchanged','coordinates_finite']):
    raise RuntimeError(json.dumps(result))
(TASK/'09_reproducibility/OBSERVER_READONLY_GPU_PROBE.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))

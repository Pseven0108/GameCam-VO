"""Actual sm_120 CUDA extension checks; never substitutes an import-only PASS."""
import argparse
import json
from pathlib import Path
import torch
from gamecam.compat.torch_scatter_python import install
scatter_receipt=install()
from lietorch import SE3
from torch_scatter import scatter_sum,scatter_mean

p=argparse.ArgumentParser()
p.add_argument('--core-only',action='store_true')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
torch.set_num_threads(2)
x=torch.tensor([[.1,.2,.3,.01,.02,.03]],device='cuda',dtype=torch.float32)
g=SE3.exp(x)
torch.testing.assert_close(g.log(),x,atol=2e-6,rtol=2e-5)
torch.testing.assert_close((g*g.inv()).matrix(),torch.eye(4,device='cuda')[None],atol=1e-5,rtol=1e-5)
y=scatter_sum(torch.tensor([1.,2.,3.],device='cuda'),torch.tensor([0,1,0],device='cuda'),dim=0)
torch.testing.assert_close(y,torch.tensor([4.,2.],device='cuda'))
torch.testing.assert_close(scatter_mean(torch.tensor([1.,2.,3.],device='cuda'),torch.tensor([0,1,0],device='cuda'),dim=0),torch.tensor([2.,2.],device='cuda'))
r={'lietorch_cuda_se3':'PASS','upstream_python_scatter_sum_mean_on_cuda':'PASS','scatter_compatibility':scatter_receipt,'gpu':torch.cuda.get_device_name(),
   'torch':torch.__version__,'capability':torch.cuda.get_device_capability()}
if not a.core_only:
    import droid_backends
    from src.modules.droid_net import DroidNet
    from src.depth_video import DepthVideo
    from src.frontend import Frontend
    from src.backend import Backend
    from src.trajectory_filler import PoseTrajectoryFiller
    poses=torch.tensor([[0,0,0,0,0,0,1],[.01,0,0,0,0,0,1]],device='cuda',dtype=torch.float32)
    disps=torch.ones((2,8,8),device='cuda')
    k=torch.tensor([20.,20.,3.5,3.5],device='cuda')
    ii=torch.tensor([0],device='cuda');jj=torch.tensor([1],device='cuda')
    dist=droid_backends.frame_distance(poses,disps,k,ii,jj,.75)
    if not torch.isfinite(dist).all():raise RuntimeError('Nonfinite native frame distance')
    r.update(droid_imports='PASS',droid_native_frame_distance='PASS',distance=dist.tolist())
torch.cuda.synchronize()
a.output.write_text(json.dumps(r,indent=2))
print(json.dumps(r,indent=2))

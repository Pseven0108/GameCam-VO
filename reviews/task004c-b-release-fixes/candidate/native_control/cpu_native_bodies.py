"""CPU-only interface fixture loading actual Python class bodies via AST.

CUDA decorators and extension/CNN computations are mocked. This tests native
control placement, never native numerical BA correctness or trajectory quality.
"""
import ast
from contextlib import nullcontext
import pathlib
import types
import numpy as np
import torch
from native_control.runtime import active
from native_control.install import install_factor_graph,install_depth_video,selected_flags


class MockCorr:
    def __init__(self,a,b):self.size=a.shape[1]
    def cat(self,other):self.size+=other.size;return self
    def __getitem__(self,mask):self.size=int(mask.sum());return self
    def __call__(self,coords):return torch.zeros(1,coords.shape[1],4,*coords.shape[2:4])


def coords_grid(h,w,device='cpu'):
    y,x=torch.meshgrid(torch.arange(h,device=device),torch.arange(w,device=device),indexing='ij')
    return torch.stack((x,y),dim=-1).float()


def load_class(root,file,name,extra=None):
    source=pathlib.Path(root)/file;tree=ast.parse(source.read_text())
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name==name)
    for n in ast.walk(cls):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):n.decorator_list=[]
    module=ast.Module(body=[cls],type_ignores=[]);ast.fix_missing_locations(module)
    ns={'torch':torch,'np':np,'task004c':active,'CorrBlock':MockCorr,'AltCorrBlock':MockCorr,
        'pops':types.SimpleNamespace(coords_grid=coords_grid),'SummaryWriter':object,
        'task003':lambda:types.SimpleNamespace(stage='frontend_local_predecision',ba_before=lambda *a,**k:None,ba_after=lambda *a,**k:None),
        'task004_local_flags':lambda *a:None,'selected_flags':selected_flags,'__name__':'native_cpu_body_fixture'}
    ns.update(extra or {});exec(compile(module,str(source),'exec'),ns)
    return ns[name]


class FakeVideo:
    def __init__(self,D=1):
        self.ht=32;self.wd=32;self.down_scale=8;self.device='cpu';self.D=D;self.counter=types.SimpleNamespace(value=3)
        self.nets=torch.zeros(6,128,4,4);self.inps=torch.zeros_like(self.nets);self.fmaps=torch.zeros(6,1,128,4,4)
        self.disps=torch.ones(6,4,4);self.poses=torch.zeros(6,7);self.uncertainties=torch.ones(6,4,4)
        self.timestamp=torch.tensor([0.,7.,17.,0.,0.,0.]);self.images=torch.zeros(6,3,32,32)
        self.dirty=torch.zeros(6,dtype=torch.bool);self.npc_dirty=self.dirty.clone()
        self.disps_up=torch.ones(6,32,32);self.intrinsics=torch.ones(6,4)
        self.depth_scale=torch.ones(6);self.depth_shift=torch.zeros(6)
        self.mono_disps=torch.ones(6,4,4);self.mono_disps_up=torch.ones(6,32,32)
        self.valid_depth_mask=torch.ones(6,32,32,dtype=torch.bool);self.valid_depth_mask_small=torch.ones(6,4,4,dtype=torch.bool)
        self.uncertainty_aware=True;self.dino_feats=torch.ones(6,2,2,3)
        self.cfg={'tracking':{'uncertainty_params':{'lr':.01,'weight_decay':.0002}}}
    def reproject(self,ii,jj):
        xy=coords_grid(4,4)[None,None].expand(1,len(ii),4,4,2).clone()+self.disps[0,0,0]*.01
        return xy,torch.ones(1,len(ii),4,4,1)
    def ba(self,*args,**kwargs):
        self.disps += .01 if self.D else .03
        self.poses[:self.counter.value,0] += .1 if self.D else .2
    def upsample(self,*args):pass
    def get_lock(self):return nullcontext()


def fake_update(net,inp,corr,motn,ii,jj):
    e=len(ii);h,w=motn.shape[-2:]
    return net,torch.zeros(1,e,h,w,2),torch.ones(1,e,h,w,2),torch.ones(len(torch.unique(ii)),h,w)*.1,None

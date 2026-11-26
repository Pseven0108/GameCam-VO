"""Same-input CUDA comparison of scalar and vectorized sparse-target adapters."""
import argparse
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile

import numpy as np
import torch

from gamecam.modules.motion_decomposition import droid_adapter as current

ROOT=Path(__file__).resolve().parents[3]


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    loader=importlib.machinery.SourceFileLoader('task009_old_static',str(ROOT/'experiments/TASK009/intake/static_adapter_r1.py.txt'))
    spec=importlib.util.spec_from_loader(loader.name,loader);old=importlib.util.module_from_spec(spec);loader.exec_module(old)
    directory=ROOT/'experiments/TASK009/outputs/mdtracker_metric_32f_160x280_fp32_r1'
    class Video:
        down_scale=8
        timestamp=torch.tensor([0.,2.,8.,24.,30.],device='cuda')
        def ba(self,*args,**kwargs):return args
    ids=dict(enumerate(range(301,333)))
    pairs=[(0,1),(1,0),(2,3),(3,2),(4,2)]
    ii=torch.tensor([r[0] for r in pairs],device='cuda');jj=torch.tensor([r[1] for r in pairs],device='cuda')
    eta=torch.ones(5,27,48,device='cuda')
    rows=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'runtime/tmp') as td:
        v0,v1=Video(),Video()
        old.install_static_targets(v0,old.StaticTrackCache(directory,(216,384)),ids,Path(td)/'old.jsonl')
        current.install_static_targets(v1,current.StaticTrackCache(directory,(216,384)),ids,Path(td)/'new.jsonl')
        for seed in (43,44,45):
            torch.manual_seed(seed)
            target=torch.rand(1,len(pairs),27,48,2,device='cuda')*40
            weight=torch.rand_like(target);before=target.clone()
            x=v0.ba(target,weight,eta,ii,jj)[0];y=v1.ba(target,weight,eta,ii,jj)[0]
            rows.append(dict(seed=seed,bit_equal=bool(torch.equal(x,y)),max_abs=float((x-y).abs().max()),input_unchanged=bool(torch.equal(target,before))))
    if not all(r['bit_equal'] and r['input_unchanged'] for r in rows):raise ValueError('Sparse adapter CUDA mismatch')
    a.output.write_text(json.dumps(dict(status='PASS',device=torch.cuda.get_device_name(),torch=torch.__version__,rows=rows,
        scope='Adapter same-input equality only; no claim that native BA is deterministic'),indent=2))
    print(a.output.read_text())


if __name__=='__main__':main()

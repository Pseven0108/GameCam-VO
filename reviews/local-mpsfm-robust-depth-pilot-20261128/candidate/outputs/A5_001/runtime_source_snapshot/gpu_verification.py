"""Bounded same-state endpoint and CPU/GPU formula checks, before candidate use."""
import importlib.util,json,pathlib,types
import numpy as np
import torch
from endpoint_check import check as native_check,FIELDS
from robust_math import terms

def check(args,native,candidate,path):
    path=pathlib.Path(path)
    adapter=types.SimpleNamespace(ba=lambda *a:candidate.ba(*a,False,.1,False))
    native_check(args,native,adapter,path)
    old=pathlib.Path('/mnt/d/aaa/GameCam-VO-DROID-SPLAT-CANDIDATE/toolchain/build/a5_sm120_001/local_a5_splat_c3414af6.so')
    spec=importlib.util.spec_from_file_location('local_a5_splat_c3414af6',old)
    a5=importlib.util.module_from_spec(spec);spec.loader.exec_module(a5)
    cpu_rng=torch.get_rng_state();gpu_rng=torch.cuda.get_rng_state()
    saved={i:x.detach().cpu().clone() for i,x in enumerate(args) if isinstance(x,torch.Tensor)}
    outputs={}
    for name,mod in [('old_a5',a5),('new_a5',candidate)]:
        call=[saved[i].to(x.device) if i in saved else x for i,x in enumerate(args)]
        strength=torch.full_like(call[1],.37)
        extra=[strength,True,False]+([False,.1,False] if name=='new_a5' else [])
        result=mod.ba(*call,*extra);torch.cuda.synchronize()
        outputs[name]={label:call[i].detach().cpu().clone() for i,label in FIELDS.items()}
        outputs[name].update(dx=result[0].cpu().clone(),dz=result[1].cpu().clone())
        del call,strength,result
    rows=[]
    for field,left in outputs['old_a5'].items():
        right=outputs['new_a5'][field];dif=(left.double()-right.double()).abs()
        rows.append(dict(field=field,max_abs=float(dif.max()) if dif.numel() else 0.,
            bitwise_equal=torch.equal(left,right),within_tolerance=bool(torch.allclose(left,right,atol=1e-5,rtol=1e-4))))
    np.savez_compressed(path.parent/'A5_ENDPOINT_ARRAYS.npz',**{name+'__'+field:v.numpy() for name,vals in outputs.items() for field,v in vals.items()})
    # CPU/GPU oracle, deterministic synthetic fixtures (no live RNG consumed).
    v=np.linspace(.002,3,504,dtype=np.float32).reshape(7,72)
    inp=[np.ones_like(v)*.3,np.cos(v),np.ones_like(v)*.02,v,v*1.3+.001,(np.arange(v.size).reshape(v.shape)%7/6).astype(np.float32)]
    gpu=[torch.as_tensor(x,device='cuda') for x in inp]
    actual=candidate.prior_terms(*gpu,.01,.1);reference=terms(*inp)
    oracle=[]
    for i,key in enumerate(['C','b','q','objective']):
        arr=actual[i].cpu().numpy();error=abs(arr.astype(np.float64)-reference[key])
        oracle.append(dict(field=key,max_abs=float(error.max()),within_tolerance=bool(np.allclose(arr,reference[key],atol=2e-7,rtol=3e-5))))
    preserved=all(torch.equal(x.detach().cpu(),saved[i]) for i,x in enumerate(args) if i in saved)
    rng_ok=torch.equal(cpu_rng,torch.get_rng_state()) and torch.equal(gpu_rng,torch.cuda.get_rng_state())
    receipt=dict(a5_endpoint_comparisons=rows,synthetic_CPU_float64_GPU_float32=oracle,
        live_inputs_preserved=preserved,rng_preserved=rng_ok,
        passed=all(r['within_tolerance'] for r in rows+oracle) and preserved and rng_ok,
        scope='one real BA state; endpoint checks are not universal deterministic-equivalence certificates')
    (path.parent/'ADDITIONAL_GPU_VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if not receipt['passed']:raise RuntimeError('GPU verification failed')

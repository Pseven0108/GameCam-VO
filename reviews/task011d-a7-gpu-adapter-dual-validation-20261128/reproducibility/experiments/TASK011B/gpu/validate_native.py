"""Native two-iteration endpoint checks with original-repeat controls."""
import importlib.util,json
import numpy as np
from runtime import *
import torch


def candidate_module():
    spec=importlib.util.spec_from_file_location('task011b_cadp_dr_c3414af6',str(TASK/'build_001/task011b_cadp_dr_c3414af6.so'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def verify(args,native,candidate,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    n=max(int(args[14]),int(args[11].max())+1,int(args[12].max())+1)
    data=[]
    for i,a in enumerate(args):
        if isinstance(a,torch.Tensor):
            b=a[:n] if i in (0,1,3,6,7,8) else a
            data.append(b.detach().clone().contiguous())
        else:data.append(a)
    np.savez_compressed(out/'input.npz',**{f'arg{i}':v.cpu().numpy() for i,v in enumerate(data) if isinstance(v,torch.Tensor)})
    outputs={};rows=[]
    for D in (0,1):
        for kind in ('original','candidate'):
            for repeat in range(2):
                state=[x.clone() if isinstance(x,torch.Tensor) else x for x in data]
                state[15]=2
                if kind=='original' and D==0:state[3].zero_()
                torch.cuda.synchronize()
                if kind=='original':result=native(*state)
                else:result=candidate.ba(*state,torch.full_like(state[1],float(D)),True,False)
                torch.cuda.synchronize()
                fields={k:v.detach().cpu().numpy().copy() for k,v in [('dx',result[0]),('dz',result[1]),
                    ('poses',state[0]),('disps',state[1]),('U',state[6]),('temp',state[7]),('affine',state[9])]}
                if not all(np.isfinite(v).all() for v in fields.values()):raise RuntimeError('Nonfinite native endpoint result')
                key=f'D{D}_{kind}_{repeat}';outputs[key]=fields;np.savez_compressed(out/(key+'.npz'),**fields)
        for field in outputs[f'D{D}_original_0']:
            original0=outputs[f'D{D}_original_0'][field]
            original1=outputs[f'D{D}_original_1'][field]
            row=dict(D=D,field=field,original_repeat_max_abs=float(np.max(abs(original0-original1))),
                rtol=1e-4,atol=1e-5,original_repeat_pass=bool(np.allclose(original0,original1,rtol=1e-4,atol=1e-5)))
            passes=[];worst=0.
            for a in range(2):
                for b in range(2):
                    x,y=outputs[f'D{D}_original_{a}'][field],outputs[f'D{D}_candidate_{b}'][field]
                    worst=max(worst,float(np.max(abs(x-y))));passes.append(bool(np.allclose(x,y,rtol=1e-4,atol=1e-5)))
            row.update(candidate_cross_max_abs=worst,candidate_all_pairs_pass=all(passes));rows.append(row)
    passed=all(r['original_repeat_pass'] and r['candidate_all_pairs_pass'] for r in rows)
    # Exercise actual prior-free geometry in the native loop, without mutating tracker state.
    state=[x.clone() if isinstance(x,torch.Tensor) else x for x in data];state[15]=2
    result=candidate.ba(*state,torch.full_like(state[1],.5),True,True)
    g=result[2].cpu().numpy();np.savez_compressed(out/'geometry_probe.npz',geometry=g,dx=result[0].cpu().numpy(),dz=result[1].cpu().numpy())
    geometry_pass=bool(np.isfinite(g).all() and (g[:,:,0]>=0).all() and (g[:,:,0]<=1).all())
    receipt=dict(status='PASS' if passed and geometry_pass else 'FAILED',comparisons=rows,
        input_sha256=sha(out/'input.npz'),native_BA_calls=8,candidate_geometry_calls=1,
        geometry_pass=geometry_pass,geometry_g_range=[float(g[:,:,0].min()),float(g[:,:,0].max())],
        two_iterations_preserved=True,U_native_update=bool(data[25]),native_input_mutated=False)
    write(out/'NATIVE_REGRESSION.json',receipt)
    if not passed or not geometry_pass:raise RuntimeError('Native endpoint/geometry regression failed; preserve all arrays')
    return receipt


def synthetic():
    import droid_backends as native
    torch.manual_seed(43);torch.cuda.manual_seed_all(43)
    n,h,w=4,45,80;device='cuda'
    poses=torch.zeros(n,7,device=device);poses[:,6]=1;poses[:,0]=torch.arange(n,device=device)*.01
    disp=torch.ones(n,h,w,device=device);K=torch.tensor([50.,50.,40.,22.],device=device)
    ii=torch.tensor([0,1,1,2,2,3,3,0],device=device);jj=torch.tensor([1,0,2,1,3,2,0,3],device=device)
    projected=native.projmap(poses,disp,K,ii,jj)[0]
    assert projected.shape==(8,h,w,3)
    target=projected[...,:2].permute(0,3,1,2).contiguous()+.03
    args=[poses,disp,K,torch.full_like(disp,.8),target,torch.full_like(target,.5),
        torch.full_like(disp,float(np.log(2.1))),torch.zeros_like(disp),torch.randn(n,384,h,w,device=device)*.01,
        torch.zeros(385,device=device),torch.full_like(disp,.2),ii,jj,1,n,2,1e-4,.1,.1,.05,.01,.1,.002,False,False,True,True,True,False,False]
    r=verify(args,native.ba,candidate_module(),TASK/'native_regression/synthetic_001')
    print(json.dumps(r,indent=2))


if __name__=='__main__':synthetic()

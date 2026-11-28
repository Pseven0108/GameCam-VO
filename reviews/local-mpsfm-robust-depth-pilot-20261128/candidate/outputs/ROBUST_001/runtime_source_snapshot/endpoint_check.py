"""Same-state native endpoint check; never alters the live Tracker tensors."""
import hashlib,json,pathlib
import numpy as np
import torch

FIELDS={0:'poses',1:'disparities',6:'uncertainties',7:'temp_y_cdot',9:'affine_weights'}

def check(args,native,candidate,path):
    if candidate is None:raise ValueError('Missing independent candidate module')
    path=pathlib.Path(path)
    if path.exists():raise FileExistsError(path)
    cpu_rng=torch.get_rng_state();cuda_rng=torch.cuda.get_rng_state()
    inputs={i:x.detach().cpu().clone() for i,x in enumerate(args) if isinstance(x,torch.Tensor)}
    def digest(t):return hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()
    receipt=dict(atol=1e-5,rtol=1e-4,scope='one_real_frontend_state',
        input_sha256={str(i):digest(x) for i,x in inputs.items()},comparisons=[])
    outputs={}
    for name in ['native_1','native_2','candidate_disabled','candidate_ones']:
        call=[inputs[i].to(x.device) if i in inputs else x for i,x in enumerate(args)]
        # No views share storage in this frozen positional BA signature; fail
        # closed if a future interface starts passing aliased tensors.
        ptrs=[x.untyped_storage().data_ptr() for x in args if isinstance(x,torch.Tensor)]
        if len(ptrs)!=len(set(ptrs)):raise RuntimeError('Endpoint inputs contain unhandled storage aliases')
        if name.startswith('native'):result=native.ba(*call)
        else:
            strength=torch.ones_like(call[1])
            result=candidate.ba(*call,strength,name=='candidate_ones',False)
        torch.cuda.synchronize()
        fields={label:call[i].detach().cpu().clone() for i,label in FIELDS.items()}
        fields.update(dx=result[0].detach().cpu().clone(),dz=result[1].detach().cpu().clone())
        if not all(torch.isfinite(x).all() for x in fields.values()):raise RuntimeError('Nonfinite endpoint replay')
        outputs[name]=fields
        del call,result
        if name.startswith('candidate'):del strength
    for left,right in [('native_1','native_2'),('native_1','candidate_disabled'),('native_1','candidate_ones')]:
        for field,a in outputs[left].items():
            b=outputs[right][field];diff=(a.double()-b.double()).abs()
            receipt['comparisons'].append(dict(left=left,right=right,field=field,
                bitwise_equal=torch.equal(a,b),max_abs=float(diff.max()) if diff.numel() else 0.,
                rmse=float(diff.square().mean().sqrt()) if diff.numel() else 0.,
                within_tolerance=bool(torch.allclose(a,b,atol=receipt['atol'],rtol=receipt['rtol']))))
    receipt['all_comparisons_pass']=all(x['within_tolerance'] for x in receipt['comparisons'])
    receipt['live_inputs_unchanged']=all(torch.equal(x.detach().cpu(),inputs[i]) for i,x in enumerate(args) if i in inputs)
    receipt['interpretation']='Local same-state check only; Native U atomic reductions are not guaranteed bitwise deterministic.'
    np.savez_compressed(path.with_suffix('.npz'),**{name+'__'+field:value.numpy() for name,fields in outputs.items() for field,value in fields.items()})
    path.write_text(json.dumps(receipt,indent=2)+'\n')
    if not receipt['live_inputs_unchanged']:raise RuntimeError('Endpoint diagnostic altered live inputs')
    if not torch.equal(cpu_rng,torch.get_rng_state()) or not torch.equal(cuda_rng,torch.cuda.get_rng_state()):
        raise RuntimeError('Endpoint diagnostic consumed live RNG')
    if not receipt['all_comparisons_pass']:raise RuntimeError('Endpoint equivalence exceeded preregistered local tolerance')

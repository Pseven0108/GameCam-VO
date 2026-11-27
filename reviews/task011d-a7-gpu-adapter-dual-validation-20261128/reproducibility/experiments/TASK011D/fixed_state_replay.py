"""A5/A7/A5 same-state replay; never a full trajectory or GT scorer."""
import argparse,hashlib,json
from pathlib import Path
import time
import numpy as np
from common import TASK,dump
from authorization import require_approved_runtime
from collect_snapshots import argument_manifest,rng_restore,serialized_clone,eligible

def replay(snapshot,candidate,device='cpu'):
    import torch
    source_manifest=argument_manifest(snapshot['args']);results={};states={}
    if not eligible(snapshot.get('phase'),snapshot['args'],True):raise ValueError('Noneligible or unmarked BA snapshot')
    if source_manifest!=snapshot['argument_manifest']:raise ValueError('Snapshot original inputs changed')
    # Directly re-check strength means/support against the exact saved state.
    from uniform_control import torch_uniform_for_call
    slots=torch.as_tensor([x['source_slot'] for x in snapshot['source_metadata']['frames']],dtype=torch.long)
    reference=snapshot['a5'].cpu();nv=snapshot['native_valid'].cpu();mono=snapshot['args'][3].cpu()
    expected,proof=torch_uniform_for_call(reference,nv,mono,slots)
    if not torch.equal(expected,snapshot['a7'].cpu()):
        # CUDA and CPU reductions can differ while respecting the fixed 1e-6
        # contract. Compare actual coefficients, never silently replace them.
        if not torch.allclose(expected,snapshot['a7'].cpu(),rtol=0,atol=1e-6):raise ValueError('Saved A7 does not match actual-state definition')
    for name,field in (('A5_first','a5'),('A7','a7'),('A5_repeat','a5')):
        state=serialized_clone(snapshot,device)
        if argument_manifest(state['args'])!=source_manifest:raise ValueError('Replay input/alias/layout mismatch')
        # CPU RNG remains CPU regardless of tensor target mapping.
        rng_restore(state['rng'])
        if device.startswith('cuda'):torch.cuda.synchronize()
        start=time.perf_counter()
        output=candidate.ba(*state['args'],state[field].contiguous(),True,False)
        if device.startswith('cuda'):torch.cuda.synchronize()
        elapsed=time.perf_counter()-start
        states[name]=dict(poses=state['args'][0].detach().cpu().clone(),disps=state['args'][1].detach().cpu().clone(),
            U=state['args'][6].detach().cpu().clone(),dx=output[0].detach().cpu().clone(),dz=output[1].detach().cpu().clone())
        results[name]=dict(seconds=elapsed,initial_30_arguments_identical=True,
            U_UBA_initial_state_identical=True,original_U_update_flags_preserved=True,
            existing_solver_diagnostics='NONE_ADDED; native extension unchanged')
        if argument_manifest(snapshot['args'])!=source_manifest:raise RuntimeError('Source snapshot mutated')
    def distance(a,b,k):return float(torch.linalg.vector_norm(states[a][k].double()-states[b][k].double()).item())
    summary={}
    for key in ('poses','disps','U','dx','dz'):
        contrast=distance('A5_first','A7',key);noise=distance('A5_first','A5_repeat',key)
        summary[key]=dict(A5_A7_l2=contrast,A5_A5_l2=noise,numeric_uncertainty=(noise>=.5*contrast),
                         near_noise_ratio_warning=.5,warning_not_a_significance_test=True,
                         smaller_update_not_an_accuracy_certificate=True)
    return dict(experiment='FIXED_STATE_REPLAY',sequence=snapshot['sequence'],seed=snapshot['seed'],
        call=snapshot['call'],branches=results,contrasts=summary,mean_check=proof,
        synthetic=bool(snapshot['synthetic']),complete_trajectory=False,ATE_RPE_computed=False),states

def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot');p.add_argument('--approval');p.add_argument('--job-key');p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:
        print(json.dumps(dict(status='VALIDATE_ONLY',formal_Native_BA_started=False,protocol='configs/FIXED_STATE_PROTOCOL.json')));return
    require_approved_runtime(a.approval,'FIXED_STATE_REPLAY',a.job_key)
    path=Path(a.snapshot).resolve();registered=(TASK/'fixed_state/snapshots').resolve()
    if not path.is_relative_to(registered):raise ValueError('Only registered TASK011D A0 snapshots may be loaded')
    index=[json.loads(line) for line in (path.parent/'SNAPSHOT_INDEX.jsonl').read_text().splitlines()]
    matching=[r for r in index if r['path']==path.name]
    from common import sha
    if len(matching)!=1 or sha(path)!=matching[0]['sha256']:raise ValueError('Snapshot registration/hash mismatch')
    out=TASK/'fixed_state/results'/a.job_key;out.mkdir(parents=True,exist_ok=False)
    dump(out/'ATTEMPT.json',dict(status='STARTED',snapshot_sha256=sha(path),job_key=a.job_key,automatic_retry=False))
    import torch
    import native_binding
    snapshot=torch.load(path,map_location='cpu',weights_only=True)
    window=path.parent.name;expected=f"s{snapshot['seed']}_{window}_ba{snapshot['call']:06d}"
    if a.job_key!=expected or snapshot.get('synthetic',False):raise ValueError('Formal snapshot job identity mismatch')
    candidate=native_binding.load_candidate()
    result,states=replay(snapshot,candidate,'cuda:0')
    torch.save(states,out/'paired_outputs.pt');dump(out/'RESULT.json',result)

if __name__=='__main__':main()

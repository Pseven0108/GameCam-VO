"""All eligible A0 local-BA inputs, no result-based selection or native calls.

The serializer retains Tensor storage aliasing, dtype, stride and offsets. Real
capture is dormant until the separately approved native runner installs it.
"""
import hashlib,io,json,os,random,time
from pathlib import Path
import shutil
import numpy as np

NAMES=('poses','disps','intrinsics','mono_disps','targets','weights','uncertainties','temp_y_cdot',
 'dino_feats','affine_weights','eta','ii','jj','t0','t1','iterations','lm','ep','gamma_data','gamma_prior',
 'gamma_depth','lr','weight_decay','motion_only','depth_only','enable_update_uncer','enable_udba',
 'enable_affine_transform','enable_bidirectional_uncer','debug')
MAIN='FRONTEND_MAIN_LOOP_LOCAL_BA'

def eligible(phase,args,metric_depth_reg):
    if len(args)!=30:raise ValueError('Exactly 30 original native arguments required')
    return phase==MAIN and not bool(args[23]) and bool(metric_depth_reg)

def rng_capture():
    import torch
    n=np.random.get_state()
    return dict(python=random.getstate(),numpy=[n[0],n[1].tolist(),n[2],n[3],n[4]],
        torch_cpu=torch.get_rng_state(),torch_cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else [])

def rng_restore(state):
    import torch
    random.setstate(state['python']);n=state['numpy'];np.random.set_state((n[0],np.array(n[1],dtype=np.uint32),n[2],n[3],n[4]))
    torch.set_rng_state(state['torch_cpu'].cpu())
    if state['torch_cuda']:torch.cuda.set_rng_state_all([x.cpu() for x in state['torch_cuda']])

def serialized_clone(payload,device='cpu'):
    import torch
    b=io.BytesIO();torch.save(payload,b);b.seek(0)
    return torch.load(b,map_location=device,weights_only=True)

def argument_manifest(args):
    import torch
    rows=[];storages={}
    for name,x in zip(NAMES,args):
        if torch.is_tensor(x):
            storage=x.untyped_storage();key=(str(x.device),storage.data_ptr(),storage.nbytes())
            alias=storages.setdefault(key,len(storages))
            raw=x.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
            rows.append(dict(name=name,tensor=True,dtype=str(x.dtype),shape=list(x.shape),stride=list(x.stride()),
                storage_offset=x.storage_offset(),storage_bytes=storage.nbytes(),alias_group=alias,
                sha256=hashlib.sha256(raw).hexdigest()))
        else:
            if not isinstance(x,(bool,int,float)):raise ValueError('Unregistered native scalar type')
            rows.append(dict(name=name,tensor=False,value=x,type=type(x).__name__))
    return rows

def storage_budget(payload):
    import torch
    seen=set();total=0
    def visit(x):
        nonlocal total
        if torch.is_tensor(x):
            s=x.untyped_storage();key=(str(x.device),s.data_ptr(),s.nbytes())
            if key not in seen:seen.add(key);total+=s.nbytes()
        elif isinstance(x,dict):
            for v in x.values():visit(v)
        elif isinstance(x,(list,tuple)):
            for v in x:visit(v)
    visit(payload)
    return dict(unique_tensor_storage_bytes=total,conservative_serialization_bytes=total+max(1024**2,total//20),
                safety_free_bytes=10*1024**3)

class SnapshotCollector:
    def __init__(self,root,sequence,seed,minimum_free=10*1024**3,synthetic=False):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False)
        self.sequence=sequence;self.seed=seed;self.count=0;self.minimum_free=minimum_free;self.synthetic=synthetic
        self.cumulative_bytes=0
    def capture(self,phase,args,metric_depth_reg,a5,a7,native_valid,source_metadata):
        if not eligible(phase,args,metric_depth_reg):return None
        import torch
        if abs(float(args[20])-.01)>1e-12:raise ValueError('Alpha changed')
        started=time.perf_counter()
        record=dict(sequence=self.sequence,seed=self.seed,call=self.count,phase=phase,
            args=tuple(args),a5=a5,a7=a7,native_valid=native_valid,source_metadata=source_metadata,
            rng=rng_capture(),synthetic=self.synthetic,
            original_U_update_flags=[bool(args[25]),bool(args[26])],complete_native_signature=30)
        budget=storage_budget(record);free=shutil.disk_usage(self.root).free
        if free<self.minimum_free+budget['conservative_serialization_bytes']:raise RuntimeError('SNAPSHOT_STORAGE_BLOCKED')
        record['argument_manifest']=argument_manifest(args)
        path=self.root/f'local_ba_{self.count:06d}.pt';partial=path.with_suffix('.pt.partial')
        if path.exists() or partial.exists():raise FileExistsError('Preserve every snapshot attempt')
        torch.save(record,partial)
        if shutil.disk_usage(self.root).free<self.minimum_free:raise RuntimeError('Snapshot write exhausted safety floor; partial retained')
        partial.rename(path)
        from common import sha
        self.cumulative_bytes+=path.stat().st_size
        receipt=dict(sequence=self.sequence,seed=self.seed,call=self.count,path=path.name,bytes=path.stat().st_size,
            cumulative_bytes=self.cumulative_bytes,snapshot_count=self.count+1,
            sha256=sha(path),budget=budget,synthetic=self.synthetic,observer_wall_seconds=time.perf_counter()-started,
            original_30_input_hashes=record['argument_manifest'],source_metadata=source_metadata)
        with (self.root/'SNAPSHOT_INDEX.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(receipt,allow_nan=False)+'\n')
        self.count+=1;return path

def install_native_collector(video,collector,a5_fields,valid_fields):
    """Read-only input observer around the installed native module for A0 only."""
    import torch
    from uniform_control import gather_source_strength,source_slots_gpu
    cache=torch.as_tensor(np.stack([a5_fields[i][video.slice_h,video.slice_w] for i in range(64)]),dtype=torch.float32,device=video.device)
    valid=torch.as_tensor(np.stack([valid_fields[i][video.slice_h,video.slice_w] for i in range(64)]),dtype=torch.bool,device=video.device)
    namespace=video.ba.__func__.__globals__;original=namespace['droid_backends']
    class Observer:
        def __getattr__(self,name):return getattr(original,name)
        def ba(self,*args):
            phase=getattr(video,'_task011b_phase',None)
            if eligible(phase,args,video.metric_depth_reg):
                a7,proof=gather_source_strength(video,args,cache,valid)
                slots=source_slots_gpu(args[11],args[13],args[14],int(video.counter.value))
                keys=video.timestamp.index_select(0,slots).long()
                nv=valid.index_select(0,keys);mono=args[3].index_select(0,slots)
                r5=torch.where(nv&(mono>0),cache.index_select(0,keys),0.)
                a5=torch.zeros_like(video.disps);a5.index_copy_(0,slots,r5)
                vf=torch.zeros_like(video.disps,dtype=torch.bool);vf.index_copy_(0,slots,nv)
                collector.capture(phase,args,True,a5,a7,vf,proof)
            return original.ba(*args)
    namespace['droid_backends']=Observer()
    return dict(A0_native_math_unchanged=True,all_eligible_calls_observed=True,reference='A0 installed original')

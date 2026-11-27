"""Source-only A7 adapter. No CUDA/native extension or model changes.

Only a compact [sources+1,14] FP64 statistics/index packet crosses to the CPU.
All image masks, positivity checks, FP32 means and strength fields stay on-device.
"""
from functools import lru_cache,wraps
import importlib.util,json,sys
from pathlib import Path
import numpy as np

TASK=Path(__file__).resolve().parent
MEAN_ATOL=1e-6
FORMAL_ARMS=('A0','A1','A4','A5','A7')
MAIN='FRONTEND_MAIN_LOOP_LOCAL_BA'

@lru_cache(maxsize=1)
def previous():
    import hashlib
    p=TASK.parent/'TASK011C/uniform_control.py'
    lock=json.loads((TASK/'configs/FROZEN_SOURCE_LOCK.json').read_text())
    record=next(x for x in lock['dependencies'] if x['path']=='experiments/TASK011C/uniform_control.py')
    if hashlib.sha256(p.read_bytes()).hexdigest()!=record['sha256']:raise RuntimeError('Sealed C source changed')
    spec=importlib.util.spec_from_file_location('task011d_sealed_C',p)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module

def frozen():return previous().frozen()
def arm_config(arm):return previous().arm_config(arm)
def coefficient_map(*args,**kwargs):return previous().coefficient_map(*args,**kwargs)
def uniform_for_call(*args,**kwargs):return previous().uniform_for_call(*args,**kwargs)
def source_indices(*args,**kwargs):return previous().source_indices(*args,**kwargs)
def timestamp_slots(*args,**kwargs):return previous().timestamp_slots(*args,**kwargs)

def _source_core(a5,nv,mono,slots,timestamps,meta_valid):
    import torch
    if a5.ndim!=3 or a5.shape!=nv.shape or a5.shape!=mono.shape or not a5.shape[0]:raise ValueError('Source grids disagree')
    if a5.dtype!=torch.float32 or mono.dtype!=torch.float32 or nv.dtype!=torch.bool:raise ValueError('FP32/bool required')
    if not(a5.device==nv.device==mono.device==slots.device==timestamps.device==meta_valid.device):raise ValueError('Mixed devices')
    if slots.dtype!=torch.long or slots.shape!=(len(a5),) or timestamps.shape!=slots.shape or meta_valid.shape!=slots.shape:raise ValueError('Invalid source metadata')
    mask=nv & (mono>0)
    dims=(1,2);count=mask.sum(dims);den=count.clamp_min(1)
    ref=torch.where(mask,a5,torch.zeros_like(a5))
    # Actual coefficient math is FP32. There is no correction, compensation,
    # epsilon in the eligible mean, or relaxation of the 1e-6 contract.
    mu=ref.sum(dims,dtype=torch.float32)/den.to(torch.float32)
    strength=torch.where(mask,mu[:,None,None],torch.zeros_like(a5))
    # Independent FP64 audit of actual FP32 fields, still entirely on-device.
    x=ref.to(torch.float64);y=strength.to(torch.float64);den64=den.to(torch.float64)
    mx=x.sum(dims)/den64;my=y.sum(dims)/den64;difference=(mx-my).abs()
    sx=torch.where(mask,(x-mx[:,None,None]).square(),0.).sum(dims)/den64
    sy=torch.where(mask,(y-my[:,None,None]).square(),0.).sum(dims)/den64
    # PyTorch 2.1 (the frozen native environment) accepts one all() dimension;
    # flattening only the two spatial axes preserves the exact boolean rule.
    constant=((strength==mu[:,None,None])|~mask).flatten(1).all(1)
    support=((strength>0)==(ref>0)).flatten(1).all(1)
    inputs=(torch.isfinite(a5)&(a5>=0)&(a5<=1)&torch.isfinite(mono)&(nv|(a5==0))&(~mask|(a5>0))).flatten(1).all(1)
    passed=inputs&constant&support&(difference<=MEAN_ATOL)&meta_valid
    dense=(x.mean()-y.mean()).abs()
    valid_delta=(x.sum()-y.sum()).abs()/count.sum().clamp_min(1).to(torch.float64)
    columns=[slots.to(torch.float64),timestamps.to(torch.float64),count.to(torch.float64),mx,my,difference,
             sx.sqrt(),sy.sqrt(),constant.to(torch.float64),support.to(torch.float64),inputs.to(torch.float64),
             meta_valid.to(torch.float64),x.sum(dims),y.sum(dims)]
    per_source=torch.stack(columns,dim=1)
    header=torch.zeros(14,dtype=torch.float64,device=a5.device)
    header[0]=(passed.all()&(dense<=MEAN_ATOL)&(valid_delta<=MEAN_ATOL)).to(torch.float64)
    header[1]=dense;header[2]=valid_delta;header[3]=count.sum().to(torch.float64)
    header[4]=x.numel();header[5]=difference.max()
    return strength,torch.cat((header[None],per_source),dim=0)

def _read_packet(packet):
    # The only deliberate D2H in the adapter; never a pixel/buffer tensor.
    if packet.ndim!=2 or packet.shape[1]!=14:raise RuntimeError('Invalid bounded statistics packet')
    host=packet.detach().cpu().numpy()
    if not bool(host[0,0]):raise ValueError('Invalid A5 positive support, nonfinite input, mean or source metadata; STOP')
    rows=[]
    for r in host[1:]:
        n=int(r[2])
        rows.append(dict(source_slot=int(r[0]),input_timestamp=int(r[1]),eligible_pixels=n,
            A5_mean=float(r[3]) if n else None,A7_mean=float(r[4]) if n else None,
            absolute_mean_difference=float(r[5]),A5_spatial_sd=float(r[6]) if n else None,
            A7_spatial_sd=float(r[7]) if n else None,eligible_and_positive_support_equal=bool(r[9]),
            empty_support=n==0,A7_constant=bool(r[8])))
    return dict(status='PASS_SAME_STATE_COEFFICIENT_CONTRACT',frames=rows,eligible_pixels=int(host[0,3]),
        total_source_pixels=int(host[0,4]),dense_mean_difference=float(host[0,1]),
        eligible_mean_difference=float(host[0,2]),effective_alpha_mean_difference=.01*float(host[0,1]),
        absolute_tolerance=MEAN_ATOL,summary_D2H_bytes=packet.numel()*packet.element_size() if packet.device.type=='cuda' else 0,
        compute_device=str(packet.device),reduction_dtype='torch.float32',
        cross_run_equal_means_not_asserted=True,matched_against='Counterfactual A5 on THIS exact BA input',
        CUDA_equivalence='SYNTHETIC_ADAPTER_ONLY' if packet.device.type=='cuda' else 'UNVERIFIED')

def torch_uniform_for_call(a5,native_valid,mono,indices):
    """Compatibility entry: select source grids ON DEVICE; scatter result only."""
    import torch
    if a5.ndim!=3 or a5.shape!=native_valid.shape or a5.shape!=mono.shape:raise ValueError('Native grids differ')
    if indices.ndim!=1 or indices.dtype!=torch.long or not indices.numel():raise ValueError('Integer sources required')
    if not(a5.device==native_valid.device==mono.device==indices.device):raise ValueError('Mixed devices')
    valid=(indices>=0)&(indices<a5.shape[0])
    valid=valid & (torch.unique(indices).numel()==indices.numel())
    safe=indices.clamp(0,a5.shape[0]-1)
    src,packet=_source_core(a5.index_select(0,safe),native_valid.index_select(0,safe),mono.index_select(0,safe),indices,indices,valid)
    proof=_read_packet(packet)
    full=torch.zeros_like(a5);full.index_copy_(0,indices,src)
    return full,proof

def source_slots_gpu(ii,t0,t1,live):
    import torch
    if ii.ndim!=1 or ii.dtype!=torch.long:raise ValueError('Native graph source dtype/shape changed')
    if any(isinstance(x,bool) or not isinstance(x,int) for x in (t0,t1,live)) or not 0<=t0<t1<=live:raise ValueError('Native BA bounds changed')
    return torch.unique(torch.cat((torch.arange(t0,t1,dtype=torch.long,device=ii.device),ii)),sorted=True)

def gather_source_strength(video,args,a5_cache,valid_cache):
    """GPU cache indexed by exact input timestamp, not all live-frame copies."""
    import torch
    live=int(video.counter.value)
    if len(video.timestamp)<live:raise ValueError('Live timestamp array is incomplete')
    slots=source_slots_gpu(args[11],args[13],args[14],live)
    slot_ok=(slots>=0)&(slots<live)
    timestamps=video.timestamp.index_select(0,slots.clamp(0,live-1))
    ts_ok=torch.isfinite(timestamps)&(timestamps==timestamps.floor())&(timestamps>=0)&(timestamps<64)
    keys=timestamps.to(torch.long).clamp(0,63)
    a5=a5_cache.index_select(0,keys);nv=valid_cache.index_select(0,keys)
    mono=args[3].index_select(0,slots.clamp(0,live-1))
    src,packet=_source_core(a5,nv,mono,slots,timestamps,slot_ok&ts_ok)
    proof=_read_packet(packet)
    strength=torch.zeros_like(video.disps)
    strength.index_copy_(0,slots,src)
    return strength,proof

def install(video,candidate,config,reliability_by_timestamp,output,regression_callback=None,native_valid_by_timestamp=None):
    config.validate()
    if config.arm!='A7':return previous().install(video,candidate,config,reliability_by_timestamp,output,regression_callback)
    if any(hasattr(video,x) for x in ('_task011b_installed','_task011c_installed','_task011d_installed')):raise RuntimeError('Do not stack controllers')
    if native_valid_by_timestamp is None or set(native_valid_by_timestamp)!=set(reliability_by_timestamp):raise ValueError('Explicit native validity required')
    if set(reliability_by_timestamp)!=set(range(64)):raise ValueError('Exactly 64 cache input IDs required')
    import torch
    output=Path(output)
    if output.exists():raise FileExistsError('Preserve existing receipts')
    output.parent.mkdir(parents=True,exist_ok=True)
    values=[];valids=[]
    for ts in range(64):
        value=np.asarray(reliability_by_timestamp[ts]);nv=np.asarray(native_valid_by_timestamp[ts])
        if value.shape!=(video.ht,video.wd) or nv.shape!=value.shape or nv.dtype!=bool:raise ValueError('Cache schema mismatch')
        if not np.isfinite(value).all() or np.any((value<0)|(value>1)) or np.any(value[~nv]!=0):raise ValueError('Invalid A5 cache')
        sampled=value[video.slice_h,video.slice_w]
        if sampled.shape!=tuple(video.disps.shape[-2:]):raise ValueError('Native sampling changed')
        values.append(sampled.copy());valids.append(nv[video.slice_h,video.slice_w].copy())
    # Created once, not rebuilt per BA. These are 64 input-frame cache fields,
    # not 500-slot A5/validity buffer allocations.
    cache=torch.as_tensor(np.stack(values),dtype=torch.float32,device=video.device)
    valid=torch.as_tensor(np.stack(valids),dtype=torch.bool,device=video.device)
    original=video.ba;namespace=original.__func__.__globals__;backend=namespace['droid_backends'];calls=0
    class Proxy:
        def __getattr__(self,name):return getattr(backend,name)
        def ba(self,*args):
            nonlocal calls
            if len(args)!=30:raise RuntimeError('Native 30-argument signature changed')
            if abs(float(args[20])-.01)>1e-12:raise RuntimeError('Frozen alpha changed')
            phase=getattr(video,'_task011b_phase',None)
            active=frozen().should_intervene(frozen().arm_config('A5'),phase,bool(args[23]),video.metric_depth_reg)
            calls+=1
            receipt=dict(arm='A7',call=calls,phase=phase,intervention=active,iterations=int(args[15]),
                enable_update_uncer=bool(args[25]),enable_udba=bool(args[26]),native_positional_arguments_forwarded_unchanged=True)
            if active:
                strength,proof=gather_source_strength(video,args,cache,valid)
                receipt['uniform_matching']=proof
                receipt['source_slots']=[r['source_slot'] for r in proof['frames']]
                receipt['source_input_indices']=[r['input_timestamp'] for r in proof['frames']]
                result=candidate.ba(*args,strength.contiguous(),True,False)
                if len(result)!=3:raise RuntimeError('Native return signature changed')
            else:result=backend.ba(*args)
            with output.open('a',encoding='utf-8') as f:f.write(json.dumps(receipt,allow_nan=False)+'\n')
            return result
    proxy=Proxy()
    @wraps(original)
    def wrapped(*args,**kwargs):
        if namespace['droid_backends'] is not backend:raise RuntimeError('Another interceptor is active')
        namespace['droid_backends']=proxy
        try:return original(*args,**kwargs)
        finally:namespace['droid_backends']=backend
    video.ba=wrapped;video._task011d_installed=True
    return dict(scope=frozen().MAIN,source_only=True,native_extension_replaced=False)

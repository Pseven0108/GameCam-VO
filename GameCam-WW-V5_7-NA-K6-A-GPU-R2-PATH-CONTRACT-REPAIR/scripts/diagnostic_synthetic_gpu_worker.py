"""Tiny CUDA-only worker: no model imports and no checkpoint loading."""
import argparse,json,os,pathlib,time
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--session',required=True);a=p.parse_args();out=pathlib.Path(a.out)
from linux_safety import atomic_json,read_json,SafetyStop
from native_linux_guard_v2 import ModelHeartbeat
from diagnostic_phases import PhaseRecorder
synthetic=out/'synthetic';synthetic.mkdir(mode=0o700)
rec=PhaseRecorder(synthetic,out,a.session);rec.emit('SYNTHETIC_PROCESS_STARTED')
with rec.span('SYNTHETIC_TORCH_IMPORT'):import torch
rec.torch=torch
# Guard against accidental file deserialization in this synthetic process.
def forbidden(*args,**kwargs):raise RuntimeError('SYNTHETIC_CHECKPOINT_LOAD_FORBIDDEN')
torch.load=forbidden
with rec.span('SYNTHETIC_CUDA_CONTEXT'):torch.cuda.init()
hb=ModelHeartbeat(torch,out,a.session);hb.thread.start()
try:
    start=time.monotonic()
    while not (out/'work.permit.json').exists():
        hb.check()
        if time.monotonic()-start>15:raise SafetyStop('SYNTHETIC_STARTUP_TIMEOUT')
        time.sleep(.02)
    permit=read_json(out/'work.permit.json');assert permit['cpu_dummy_only'] and not permit['model_execution_authorized']
    with rec.span('SYNTHETIC_TENSOR_MATMUL'):
        x=torch.arange(64*64,device='cuda',dtype=torch.float32).reshape(64,64)/4096
        y=x@x.T;torch.cuda.synchronize()
        assert bool(torch.isfinite(y).all())
        z=y.cpu();assert z.shape==(64,64)
    hb.check();time.sleep(.4);hb.check()
    del x,y,z
    with rec.span('SYNTHETIC_RELEASE'):
        torch.cuda.empty_cache();torch.cuda.synchronize()
    result=dict(status='RUN_COMPLETED',error=None,frames_submitted=0,frames_completed=0,synthetic_only=True,real_model_loaded=False,real_tracker_constructed=False,real_ba_executed=False,CUDA_runtime=torch.version.cuda,cuda_peak_allocated_MiB=torch.cuda.max_memory_allocated()/1048576,cuda_peak_reserved_MiB=torch.cuda.max_memory_reserved()/1048576)
    atomic_json(out/'fake_result.json',result)
    from worker_terminal import publish_terminal
    publish_terminal(out,a.session,out/'fake_result.json','cpu_dummy')
finally:hb.finish()

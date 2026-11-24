"""CPU readers, not real Tracker/Rerun processes or neural models."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import hashlib,json,pathlib,shutil,traceback
import torch
from native_control.file_backed import descriptor_for

def tensor_sha(t):
    view=memoryview(t.detach().contiguous().reshape(-1).view(torch.uint8).numpy())
    h=hashlib.sha256()
    for pos in range(0,len(view),8*1024**2):h.update(view[pos:pos+8*1024**2])
    return h.hexdigest()

def info(t):
    return {'dtype':str(t.dtype),'shape':list(t.shape),'stride':list(t.stride()),'offset':t.storage_offset(),
            'is_shared':t.is_shared(),'sha256':tensor_sha(t),'descriptor':descriptor_for(t.untyped_storage())}

def reader(pipe,payload,role='CPU_READER',write=False):
    torch.cuda._lazy_init=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('CUDA forbidden in CPU shared storage test'))
    try:
        base=payload['base'];before=info(base)
        aliases=payload.get('view',base).untyped_storage()._cdata==base.untyped_storage()._cdata
        repeated=payload.get('same',base) is payload.get('view',base)
        if write:base.reshape(-1)[0]=91
        pipe.send({'role':role,'pid':os.getpid(),'before':before,'after':info(base),'alias':aliases,'repeated_object':repeated,
                   'view':info(payload['view']) if 'view' in payload else None,'shm_used':shutil.disk_usage('/dev/shm').used,
                   'cuda_initialized':torch.cuda.is_initialized(),'exit_code':0})
    except BaseException:pipe.send({'error':traceback.format_exc(),'exit_code':1});raise
    finally:pipe.close()

def full_reader(pipe,images,dino,role,start,write_allowed,finish):
    torch.set_num_threads(2)
    torch.cuda._lazy_init=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('CUDA forbidden'))
    try:
        start.wait(30)
        pipe.send({'stage':'initial','role':role,'pid':os.getpid(),'images':info(images),'dino':info(dino),
                   'shm_used':shutil.disk_usage('/dev/shm').used,'cuda_initialized':torch.cuda.is_initialized()})
        if role=='TRACKER_CPU_STANDIN':
            if not write_allowed.wait(45):raise TimeoutError('Initial read barrier not released')
            images[499,2,359,639]=73.25;dino[499,24,44,383]=-18.5;finish.set()
        else:
            if not finish.wait(45):raise TimeoutError('Writer did not publish')
        pipe.send({'stage':'after','role':role,'pid':os.getpid(),'images':info(images),'dino':info(dino),
                   'last_values':[float(images[-1,-1,-1,-1]),float(dino[-1,-1,-1,-1])],
                   'shm_used':shutil.disk_usage('/dev/shm').used,'cuda_initialized':torch.cuda.is_initialized()})
    except BaseException:pipe.send({'error':traceback.format_exc(),'exit_code':1});raise
    finally:pipe.close()

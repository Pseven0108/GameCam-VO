"""Native-sized synthetic CPU buffers; no image data, model or real C0."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import json,pathlib,shutil,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
import torch.multiprocessing as mp
from native_control.file_backed import FileArena,descriptor_for
from tests.file_support import full_reader,info
torch.cuda._lazy_init=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('CPU stress forbids CUDA'))

def main():
    out=ROOT/'artifacts/FULL_BUFFER_CPU_PROOF';out.mkdir(exist_ok=False)
    torch.set_num_threads(2);mp.set_sharing_strategy('file_descriptor')
    baseline=shutil.disk_usage('/dev/shm').used;started=time.time()
    arena=FileArena(out/'backing');images=arena.zeros((500,3,360,640),dtype=torch.float32)
    dino=arena.zeros((500,25,45,384),dtype=torch.float32);images.fill_(.25);dino.fill_(-.5)
    before={'images':info(images),'dino':info(dino)}
    total=images.untyped_storage().nbytes()+dino.untyped_storage().nbytes();assert total==2246400000
    ctx=mp.get_context('spawn');start=ctx.Event();write_allowed=ctx.Event();finish=ctx.Event()
    children=[];pipes=[];shm_samples=[baseline,shutil.disk_usage('/dev/shm').used]
    for role in ('TRACKER_CPU_STANDIN','RERUN_CPU_STANDIN'):
        recv,send=ctx.Pipe(False);child=ctx.Process(target=full_reader,args=(send,images,dino,role,start,write_allowed,finish))
        child.start();send.close();children.append(child);pipes.append(recv)
    shm_samples.append(shutil.disk_usage('/dev/shm').used);start.set();initial=[]
    for recv in pipes:
        if not recv.poll(100):raise TimeoutError('Initial full-buffer hashes not received')
        row=recv.recv();assert row['stage']=='initial',row;initial.append(row)
        assert row['images']['sha256']==before['images']['sha256'] and row['dino']['sha256']==before['dino']['sha256']
        assert not row['cuda_initialized'];shm_samples.append(row['shm_used'])
    write_allowed.set();after=[]
    for recv in pipes:
        if not recv.poll(100):raise TimeoutError('Mutated full-buffer hashes not received')
        row=recv.recv();assert row['stage']=='after',row;after.append(row)
        assert row['last_values']==[73.25,-18.5];assert not row['cuda_initialized'];shm_samples.append(row['shm_used'])
    final={'images':info(images),'dino':info(dino)}
    for row in after:
        assert row['images']['sha256']==final['images']['sha256'] and row['dino']['sha256']==final['dino']['sha256']
        assert row['images']['descriptor']['st_ino']==before['images']['descriptor']['st_ino']
        assert row['dino']['descriptor']['st_ino']==before['dino']['descriptor']['st_ino']
    for child in children:
        child.join(timeout=30);assert not child.is_alive() and child.exitcode==0
    for recv in pipes:recv.close()
    shm_samples.append(shutil.disk_usage('/dev/shm').used)
    assert max(shm_samples)-baseline<1024**2,'Large mapped buffers unexpectedly charged to /dev/shm'
    backings=[]
    for tensor in (images,dino):
        desc=descriptor_for(tensor.untyped_storage());s=pathlib.Path(desc['path']).stat()
        backings.append({'descriptor':desc,'logical_bytes':s.st_size,'allocated_bytes':s.st_blocks*512})
        assert s.st_blocks*512>=s.st_size
    result={'scope':'CPU_SYNTHETIC_NATIVE_SIZED_SHARED_BUFFERS_NOT_REAL_TRACKER_RERUN_OR_C0','total_tensor_bytes':total,
      'parent_pid':os.getpid(),'child_pids':[x.pid for x in children],'child_exit_codes':[x.exitcode for x in children],
      'before':before,'initial_readers':initial,'after_readers':after,'final':final,'backings':backings,
      'shm_baseline_used_bytes':baseline,'shm_sample_peak_used_bytes':max(shm_samples),'shm_delta_bytes':max(shm_samples)-baseline,
      'shm_total_bytes':shutil.disk_usage('/dev/shm').total,'disk_free_bytes':shutil.disk_usage(out).free,
      'duration_seconds':time.time()-started,'cuda_initialized':torch.cuda.is_initialized(),'model_constructed':False,
      'real_RGB_frames':0,'native_C0_created':False,'PASS':True}
    (out/'FULL_BUFFER_PROOF.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['scope','total_tensor_bytes','parent_pid','child_pids','child_exit_codes','shm_delta_bytes','duration_seconds','cuda_initialized','PASS']}))

if __name__=='__main__':main()

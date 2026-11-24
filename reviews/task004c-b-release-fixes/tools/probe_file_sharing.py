"""CPU empirical probe of the installed Torch2.1 spawn storage reducer."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import hashlib,inspect,json,pathlib,shutil,sys,time,traceback
import torch
import torch.multiprocessing as mp
ROOT=pathlib.Path(__file__).resolve().parents[1]
def forbidden(*a,**kw):raise RuntimeError('GPU forbidden in CPU sharing probe')
torch.cuda._lazy_init=forbidden
def meta(t):
    pointer=t.data_ptr();line=None
    for row in pathlib.Path('/proc/self/maps').read_text().splitlines():
        lo,hi=[int(x,16) for x in row.split()[0].split('-')]
        if lo<=pointer<hi:line=row;break
    return {'dtype':str(t.dtype),'shape':list(t.shape),'stride':list(t.stride()),'offset':t.storage_offset(),
            'is_shared':t.is_shared(),'mapping':line,'value2':float(t[2]),'pid':os.getpid(),
            'shm_used':shutil.disk_usage('/dev/shm').used,'cuda_initialized':torch.cuda.is_initialized()}
def worker(pipe,value,path,count,by_path):
    try:
        t=torch.from_file(path,shared=True,size=count,dtype=torch.float32) if by_path else value
        before=meta(t);t[2]=77;pipe.send({'before':before,'after':meta(t),'exit_code':0})
    except BaseException:pipe.send({'error':traceback.format_exc(),'exit_code':1});raise
def main():
    label=sys.argv[1] if len(sys.argv)>1 else 'initial'
    out=ROOT/'artifacts'/('API_SHARING_PROBE_'+label);out.mkdir(exist_ok=False)
    results=[]
    for strategy,by_path in [('file_descriptor',False),('file_system',False),('file_descriptor',True)]:
        mp.set_sharing_strategy(strategy);count=4*1024**2;path=out/(strategy+('_descriptor' if by_path else '_tensor')+'.bin')
        fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
        os.posix_fallocate(fd,0,count*4);os.close(fd)
        t=torch.from_file(str(path),shared=True,size=count,dtype=torch.float32);t.zero_();t[2]=5
        before=meta(t);ctx=mp.get_context('spawn');recv,send=ctx.Pipe(False)
        child=ctx.Process(target=worker,args=(send,None if by_path else t,str(path),count,by_path))
        started=time.time()
        try:child.start()
        except BaseException as error:
            results.append({'strategy':strategy,'transport':'path_descriptor' if by_path else 'raw_tensor',
                            'before':before,'parent_after':meta(t),'child_exit_code':None,'start_error':repr(error),
                            'file_backing_preserved':False})
            recv.close();send.close();continue
        send.close()
        if not recv.poll(45):raise TimeoutError('CPU probe child did not reply')
        got=recv.recv();child.join(timeout=20)
        disk=torch.from_file(str(path),shared=True,size=count,dtype=torch.float32)
        record={'strategy':strategy,'transport':'path_descriptor' if by_path else 'raw_tensor','before':before,'parent_after':meta(t),
                'child':got,'child_exit_code':child.exitcode,'fresh_file_value2':float(disk[2]),'seconds':time.time()-started,
                'file_backing_preserved':bool(float(disk[2])==77 and str(path) in (got.get('after',{}).get('mapping') or ''))}
        results.append(record)
    import torch.multiprocessing.reductions as reductions
    source=inspect.getsource(reductions.reduce_storage)
    (out/'INSTALLED_reduce_storage.py').write_text(source)
    result={'torch':str(torch.__version__),'results':results,'cuda_initialized':torch.cuda.is_initialized(),
            'installed_reducer_source_sha256':hashlib.sha256(source.encode()).hexdigest()}
    (out/'PROBE_RESULTS.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()

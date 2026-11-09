"""Real stdlib IPC fixtures only. No torch/model/checkpoint imports."""
import argparse,gc,json,multiprocessing as mp,os,pathlib,sys,tempfile,time
from ipc_runtime import IPCPolicy,expected_root
from model_io_boundary_v2 import ModelIOBoundary

def share_child(value,array,raw,rawarray,ready,session_dir,session,method,exit_mode,fallback):
    if method=='spawn':
        p=IPCPolicy(expected_root(session),pathlib.Path(session_dir)/'tmp',session,session_dir);p.install_arena(fallback)
        ModelIOBoundary([],[],[pathlib.Path(session_dir).parent/'project'],[session_dir],ipc_policy=p).install()
    value.value=11;array[1]=27;raw.value=19;rawarray[0]=31
    local=mp.Value('i',123);assert local.value==123
    ready.send({'pid':os.getpid(),'shared':True});ready.close()
    if exit_mode=='abnormal':os._exit(7)
    if exit_mode=='terminate':
        while True:time.sleep(.1)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--session-dir',required=True);ap.add_argument('--session',required=True);ap.add_argument('--method',choices=['fork','spawn'],default='fork');ap.add_argument('--mode',default='exercise');ap.add_argument('--force-fallback',action='store_true');a=ap.parse_args()
    session_dir=pathlib.Path(a.session_dir);project=session_dir.parent/'project';out=session_dir/'model';out.mkdir()
    if a.mode=='boundary':(out/'escape').symlink_to(project,target_is_directory=True)
    fixture=project/'source.py';weight=project/'weight.pth';dataset=project/'image.png';gt=project/'state.csv'
    policy=IPCPolicy(expected_root(a.session),session_dir/'tmp',a.session,session_dir);policy.install_arena(a.force_fallback)
    boundary=ModelIOBoundary([__file__],[],[project],[session_dir],ipc_policy=policy);boundary.install()
    ctx=mp.get_context(a.method);fd_before=len(list(pathlib.Path('/proc/self/fd').iterdir()))
    value=ctx.Value('i',0);array=ctx.Array('i',[1,2,3]);raw=ctx.RawValue('i',4);rawarray=ctx.RawArray('i',[5,6]);lock=ctx.Lock()
    with lock:value.value=2
    with value.get_lock():value.value=3
    with array.get_lock():array[0]=8
    recv,send=ctx.Pipe(duplex=False)
    exit_mode=a.mode if a.mode in ['abnormal','terminate'] else 'normal'
    child=ctx.Process(target=share_child,args=(value,array,raw,rawarray,send,str(session_dir),a.session,a.method,exit_mode,a.force_fallback));child.start();send.close()
    assert recv.poll(10),'Child IPC timeout';child_message=recv.recv();recv.close()
    if exit_mode=='terminate':child.terminate()
    child.join(10);assert not child.is_alive()
    assert child.exitcode==({'normal':0,'abnormal':7,'terminate':-15}[exit_mode])
    assert [value.value,array[1],raw.value,rawarray[0]]==[11,27,19,31]
    checks={'Value_read_write':True,'Array_parent_child_roundtrip':True,'RawValue_shared':True,'RawArray_shared':True,'Lock_native_semantics':True,'child_exited':True}
    denied=[]
    if a.mode=='boundary':
        probes=[('arbitrary_dev_shm',lambda:open('/dev/shm/gamecam-prohibited-'+str(os.getpid()),'w')),('foreign_session',lambda:tempfile.mkstemp(prefix='pym-'+str(os.getpid())+'-',dir='/dev/shm/gamecam-ipc/OTHER_CPU_SESSION')),('arbitrary_tmp',lambda:open('/tmp/gamecam-prohibited-'+str(os.getpid()),'w')),('dataset_write',lambda:dataset.write_bytes(b'bad')),('weight_write',lambda:weight.write_bytes(b'bad')),('source_write',lambda:fixture.write_text('bad')),('GT_read',lambda:gt.read_bytes()),('symlink_escape',lambda:(out/'escape'/'bad.txt').write_text('bad')),('illegal_PID_prefix',lambda:os.open(policy.root/'pym-999999-abcd1234',os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)),('IPC_plain_filename',lambda:open(policy.root/'anything.txt','w')),('source_unlink',lambda:fixture.unlink()),('external_mkdir',lambda:pathlib.Path('/tmp/gamecam-prohibited-mkdir-'+str(os.getpid())).mkdir()),('escape_symlink_creation',lambda:(out/'badlink').symlink_to(project/'source.py')),('IPC_directory_creation',lambda:(policy.root/('pym-'+str(os.getpid())+'-abcd1234')).mkdir()),('IPC_symlink_creation',lambda:(policy.root/('pym-'+str(os.getpid())+'-abcd1234')).symlink_to(out/'legal.txt')),('IPC_chmod',lambda:os.chmod(policy.root/'.gamecam-session.json',0o777)),('IPC_rename',lambda:os.rename(policy.root/'.gamecam-session.json',policy.root/('pym-'+str(os.getpid())+'-abcd1234'))),('IPC_nonexclusive_create',lambda:os.open(policy.root/('pym-'+str(os.getpid())+'-abcd1234'),os.O_CREAT|os.O_RDWR,0o600))]
        for name,fn in probes:
            try:
                z=fn()
                if hasattr(z,'close'):z.close()
            except RuntimeError as e:denied.append({'name':name,'denied':True,'reason':str(e)})
            else:raise AssertionError('Unsafe operation was allowed: '+name)
        (out/'legal.txt').write_text('legal output');checks['Session_output_actual_write']=True
    fd_counts=[]
    for _ in range(20):
        x=ctx.Value('i',0);x.value=12;del x;gc.collect();fd_counts.append(len(list(pathlib.Path('/proc/self/fd').iterdir())))
    assert max(fd_counts)-min(fd_counts)<=2
    start=time.perf_counter()
    for _ in range(20000):value.value+=1
    bench=time.perf_counter()-start
    opens=[e for e in policy.events if e['event']=='IPC_WRITE_ALLOWED' and e.get('operation')=='open'];unlinks=[e for e in policy.events if e['event']=='IPC_FILE_CLEANED']
    assert opens and unlinks
    expected=policy.fallback if a.force_fallback else policy.root
    assert all(pathlib.Path(e['path']).parent==expected for e in opens)
    assert not [p.name for p in policy.root.iterdir() if p.name!='.gamecam-session.json']
    report={'passed':True,'python':sys.version,'mode':a.mode,'method':a.method,'forced_fallback':a.force_fallback,'allocation_directory':str(expected),'checks':checks,'denied_probes':denied,'ipc_events':list(policy.events),'boundary_events':boundary.events,'fd_before':fd_before,'fd_cycle_counts':fd_counts,'fd_growth_across_cycles':max(fd_counts)-min(fd_counts),'live_Arena_maps':[l for l in pathlib.Path('/proc/self/maps').read_text().splitlines() if 'pym-' in l],'mapping_lifetime_note':'Unlinked live Arena mappings and stdlib cache may persist until interpreter exit. The owning test checks process exit before root removal.','active_multiprocessing_children':len(mp.active_children()),'child_exit_code':child.exitcode,'child_pid':child.pid,'worker_pid':os.getpid(),'microbenchmark_20000_locked_value_updates_seconds':bench,'torch_imported':'torch' in sys.modules,'real_checkpoint_loaded':False,'GT_values_read':False,'real_model_attempts':0,'native_semaphore_names':[x for x in [value.get_lock()._semlock.name,array.get_lock()._semlock.name,lock._semlock.name] if x is not None]}
    (session_dir/'ipc_fixture_result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()

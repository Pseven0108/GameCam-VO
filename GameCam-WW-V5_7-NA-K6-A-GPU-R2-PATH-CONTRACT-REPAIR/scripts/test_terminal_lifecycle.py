"""Supervisor tests use real CPU processes and unmodified safety thresholds."""
import ctypes,json,os,pathlib,signal,subprocess,sys,time,uuid
import pytest
import runner_core as core
from ipc_runtime import expected_root,cleanup_owner
from worker_terminal import TERMINAL_CLEANUP_SECONDS
HERE=pathlib.Path(__file__).parent
CASES=[('normal',None,None),('terminal_error','SYNTHETIC_PRIMARY_ERROR','TERMINAL_FAILURE_EXIT'),('terminal_delay',None,'CLEANUP_COMPLETE'),('terminal_hang','SYNTHETIC_PRIMARY_ERROR','WORKER_SHUTDOWN_TIMEOUT'),('terminal_hang_sigkill','SYNTHETIC_PRIMARY_ERROR','WORKER_SHUTDOWN_TIMEOUT'),('running_stale','CUDA_MONITOR_STALE_OVER_3_SECONDS',None),('crash','WORKER_NONZERO_EXIT:23',None),('monitor_exit','MONITOR_SUBPROCESS_EXITED:17',None),('nvml_stale','NVML_MONITOR_STALE_OVER_3_SECONDS',None),('supervisor_exception','INJECTED_SUPERVISOR_EXCEPTION',None),('sigterm','WORKER_NONZERO_EXIT:-15',None),('sigkill','WORKER_NONZERO_EXIT:-9',None),('ipc_cleanup_failure','SYNTHETIC_PRIMARY_ERROR','IPC_CLEANUP_FAILED'),('ipc_residual',None,'CLEANUP_COMPLETE'),('terminal_wrong_session','INVALID_WORKER_TERMINAL',None),('terminal_tamper','INVALID_WORKER_TERMINAL',None),('nvml_stale_terminal','SYNTHETIC_PRIMARY_ERROR','NVML_MONITOR_STALE_OVER_3_SECONDS')]
@pytest.mark.parametrize('fault,expected,cleanup_expected',CASES)
def test_supervisor_terminal_protocol_real_processes(tmp_path,monkeypatch,fault,expected,cleanup_expected):
    folder=tmp_path/'session';session='CPU_LIFECYCLE_'+uuid.uuid4().hex;env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
    args=[sys.executable,'-B',str(HERE/'lifecycle_cpu_fixture.py'),'--out',str(folder),'--session',session,'--fault',fault]
    if fault=='supervisor_exception':
        original=core.SampleReader.check
        def check(self,row,kind):
            if (folder/'work.permit.json').exists():raise RuntimeError('INJECTED_SUPERVISOR_EXCEPTION')
            return original(self,row,kind)
        monkeypatch.setattr(core.SampleReader,'check',check)
    result=core.supervise_once(folder,session,args+['--role','worker'],args+['--role','nvml'],'cpu_dummy',env=env,expected_frames=0,ipc_for_cpu_tests=True)
    if expected is None:assert result['passed'],result
    else:assert expected in result['reason'] and not result['passed'],result
    if cleanup_expected:assert cleanup_expected in result['supervisor_cleanup_reason'],result
    assert result['model_attempts']==0 and result['automatic_retries']==0
    assert result['worker_fully_exited'] and result['monitor_fully_exited']
    assert not (folder/'authorization.claim.json').exists()
    if fault=='terminal_delay':
        assert result['worker_exit_code']==0 and result['terminal_result'] and result['duration_seconds']>4
        assert 'STALE' not in (result['reason'] or '')
    if fault=='terminal_hang':
        assert result['worker_stop']['signals']==['SIGTERM'] and result['terminal_cleanup_limit_seconds']==5
    if fault=='terminal_hang_sigkill':assert result['worker_stop']['signals']==['SIGTERM','SIGKILL'] and result['worker_exit_code']==-9
    root=expected_root(session)
    if fault=='ipc_cleanup_failure':
        assert not result['ipc_cleanup']['passed'] and (root/'foreign_fixture.txt').exists()
        (root/'foreign_fixture.txt').unlink()
        owner={'binding':json.loads((root/'.gamecam-session.json').read_text()),'root':str(root),'fallback':str(folder/'tmp'),'events':[]}
        assert cleanup_owner(owner,True,True,[result['worker_pid']])['passed']
    assert not root.exists()

def test_parent_early_exit_is_detected_by_native_model_heartbeat(tmp_path):
    # Linux subreaper makes us responsible for reaping only this fixture's orphan.
    lib=ctypes.CDLL(None,use_errno=True);assert lib.prctl(36,1,0,0,0)==0
    worker_pid=None
    try:
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
        cmd=[sys.executable,'-B',str(HERE/'lifecycle_cpu_fixture.py'),'--out',str(tmp_path),'--session','CPU_PARENT_EXIT_FIXTURE','--role','parent_escape']
        p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=10);assert p.returncode==0,p.stderr
        worker_pid=json.loads((tmp_path/'orphan_child.json').read_text())['pid'];deadline=time.monotonic()+5
        while not(tmp_path/'parent_loss_result.json').exists() and time.monotonic()<deadline:time.sleep(.05)
        r=json.loads((tmp_path/'parent_loss_result.json').read_text());assert r['error']=='SUPERVISOR_PARENT_LOST' and not r['torch_imported']
        waited,status=os.waitpid(worker_pid,0);assert waited==worker_pid and status==0
        assert not pathlib.Path('/proc',str(worker_pid)).exists()
    finally:
        if worker_pid is not None:
            try:
                child,status=os.waitpid(worker_pid,os.WNOHANG)
                if child==0:os.kill(worker_pid,signal.SIGKILL);os.waitpid(worker_pid,0)
            except (ChildProcessError,ProcessLookupError):pass
        assert lib.prctl(36,0,0,0,0)==0

def test_native_adapter_publishes_terminal_before_guard_finish(tmp_path,monkeypatch):
    import builtins,types
    import native_adapter_v2 as adapter
    order=[]
    class Stop(RuntimeError):pass
    class Guard:
        phase='CPU_FIXTURE'
        def __init__(self,*args):order.append('guard_started')
        def snapshot(self):order.append('snapshot');return {'fixture_only':True}
        def finish(self):order.append('heartbeat_stopped')
    monkeypatch.setitem(sys.modules,'native_linux_guard_v2',types.SimpleNamespace(Guard=Guard,SafetyStop=Stop))
    original=builtins.__import__
    def imports(name,*args,**kw):
        if name=='src.depth_video':raise ImportError('CPU_FIXTURE_STOPS_BEFORE_NATIVE_IMPORT')
        return original(name,*args,**kw)
    monkeypatch.setattr(builtins,'__import__',imports);monkeypatch.setattr(adapter.os,'chdir',lambda *_:None);monkeypatch.setattr(sys,'path',list(sys.path));monkeypatch.setenv('GAMECAM_RUN_SESSION_DIR',str(tmp_path/'session'))
    cuda=types.SimpleNamespace(OutOfMemoryError=type('FakeOOM',(RuntimeError,),{}),max_memory_allocated=lambda:0,max_memory_reserved=lambda:0,memory_stats=lambda:{})
    fake=types.SimpleNamespace(set_num_threads=lambda *_:None,manual_seed=lambda *_:None,cuda=cuda)
    r={'started_unix':time.time(),'frames_submitted':0,'frames_completed':0}
    def save():order.append('result_saved')
    def terminal():order.append('terminal_published')
    code=adapter._native_runtime(tmp_path/'runtime',types.SimpleNamespace(method='droidw',case='CPU_FIXTURE',monitor_session_id='CPU_FIXTURE'),{},tmp_path,r,save,fake,types.SimpleNamespace(setNumThreads=lambda *_:None),types.SimpleNamespace(random=types.SimpleNamespace(seed=lambda *_:None)),types.SimpleNamespace(assert_hooks=lambda **_:None),terminal_callback=terminal)
    assert code==2 and order.index('snapshot')<order.index('terminal_published')<order.index('heartbeat_stopped')
    assert order[order.index('terminal_published')-1]=='result_saved'

@pytest.mark.parametrize('fault',['nan_time','inf_time','negative_time','bool_time','future_time','bad_hash','bad_frames','bool_frames','bad_path','bad_status','symlink'])
def test_terminal_handoff_invalid_data_is_rejected(tmp_path,fault):
    from worker_terminal import publish_terminal,read_terminal
    from linux_safety import atomic_json,SafetyStop
    result={'status':'RUN_COMPLETED','error':None,'frames_submitted':0,'frames_completed':0}
    path=tmp_path/'fake_result.json';atomic_json(path,result)
    terminal=publish_terminal(tmp_path,'CPU_TERMINAL_BINDING',path,'cpu_dummy')
    if fault=='nan_time':terminal['monotonic_time']=float('nan')
    elif fault=='inf_time':terminal['unix_time']=float('inf')
    elif fault=='negative_time':terminal['monotonic_time']=-1
    elif fault=='bool_time':terminal['unix_time']=True
    elif fault=='future_time':terminal['monotonic_time']=time.monotonic()+100
    elif fault=='bad_hash':terminal['result_sha256']='0'*64
    elif fault=='bad_frames':terminal['frames_completed']=1
    elif fault=='bool_frames':terminal['frames_completed']=False
    elif fault=='bad_path':terminal['result_relative_path']='../fake_result.json'
    elif fault=='bad_status':
        result['status']='UNKNOWN_SUCCESS';atomic_json(path,result)
        import hashlib
        terminal.update(status=result['status'],result_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    # Corrupt fixture bytes deliberately; production atomic_json correctly rejects NaN/Inf.
    terminal_path=tmp_path/'worker_terminal.json';terminal_path.write_text(json.dumps(terminal))
    if fault=='symlink':
        other=tmp_path/'terminal_copy.json';terminal_path.rename(other);terminal_path.symlink_to(other)
    with pytest.raises(SafetyStop,match='INVALID_WORKER_TERMINAL'):read_terminal(tmp_path,'CPU_TERMINAL_BINDING',os.getpid(),'cpu_dummy')

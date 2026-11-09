"""Targeted CPU tests. Fixtures never deserialize real checkpoints or import torch."""
import copy,hashlib,json,os,pathlib,signal,subprocess,sys,time,types
import pytest
from diagnostic_authorization import *
from diagnostic_phases import *
from launch_authorization import validate_authorization,SCOPE
from linux_safety import SafetyStop
@pytest.fixture
def pair():
    c=dict(schema=SCHEMA,diagnostic_admission_status='BOUNDED_DIAGNOSTIC_READY_WAITING_FOR_USER_AUTHORIZATION',entry_admission_status='DROIDW_ENTRY_PARTIAL_PASS',diagnostic_scope=DIAGNOSTIC_SCOPE,scope=SCOPE,diagnostic_model_identity={'method':'droidw','weights_sha256':'1'*64},expected_gpu_uuid='GPU-test',planned_session_id='MOCK_SESSION',maximum_authorizable_attempts=1,automatic_retry=False)
    a=dict(permission_type=DIAGNOSTIC_TYPE,candidate_sha256='a'*64,scope=copy.deepcopy(DIAGNOSTIC_SCOPE),model_identity=c['diagnostic_model_identity'],gpu_uuid='GPU-test',session='MOCK_SESSION',diagnostic_execution_authorized=True,formal_120_frame_execution_authorized=False,attempt_limit=1,automatic_retry=False,consumed=False,nonce='MOCK_ONLY_'+'x'*32,issued_unix=100.,expires_unix=200.,gpu_environment_verified=True,visible_device_count=1,user_authorization_evidence={'path':'/MOCK_ONLY/not-a-real-evidence','sha256':'b'*64})
    return c,a
@pytest.mark.parametrize('field,value',[
 ('permission_type','FORMAL_120_FRAME'),('candidate_sha256','0'*64),('gpu_uuid','WRONG'),('session','WRONG'),('scope',{}),('model_identity',{}),('attempt_limit',0),('attempt_limit',True),('attempt_limit',2),('automatic_retry',True),('consumed',True),('expires_unix',140.),('issued_unix',160.),('expires_unix',float('nan')),('nonce',''),('user_authorization_evidence',{}),('diagnostic_execution_authorized',False),('formal_120_frame_execution_authorized',True),('gpu_environment_verified',False),('visible_device_count',2)])
def test_authorization_reject(pair,field,value):
    c,a=pair;a[field]=value
    with pytest.raises(Exception):validate_diagnostic_authorization(c,'a'*64,a,{'CUDA_VISIBLE_DEVICES':'0'},150.)
def test_valid_mock(pair):
    c,a=pair;assert validate_diagnostic_authorization(c,'a'*64,a,{'CUDA_VISIBLE_DEVICES':'0'},150.)
def test_no_auth(pair):
    with pytest.raises(Exception):validate_diagnostic_authorization(pair[0],'a'*64,None,{'CUDA_VISIBLE_DEVICES':'0'},150.)
def test_permission_separation(pair):
    c,a=pair
    with pytest.raises(Exception):validate_authorization(c,'a'*64,a,{'CUDA_VISIBLE_DEVICES':'0'},150.)
    c['schema']='gamecam-droidw-entry-candidate-v1'
    with pytest.raises(Exception):validate_diagnostic_authorization(c,'a'*64,a,{'CUDA_VISIBLE_DEVICES':'0'},150.)
@pytest.mark.parametrize('field,value',[('diagnostic_admission_status','BLOCKED'),('entry_admission_status','PASS'),('maximum_authorizable_attempts',0),('automatic_retry',True)])
def test_candidate_reject(pair,field,value):
    c,a=pair;c[field]=value
    with pytest.raises(Exception):validate_diagnostic_authorization(c,'a'*64,a,{'CUDA_VISIBLE_DEVICES':'0'},150.)
def test_cli_no_auth_before_everything(tmp_path):
    command=[sys.executable,'-B',str(pathlib.Path(__file__).with_name('bounded_diagnostic_launcher.py')),'--candidate',str(tmp_path/'DOES_NOT_EXIST'),'--candidate-sha','0'*64,'--session','MOCK_NO_AUTH']
    r=subprocess.run(command,capture_output=True,text=True);x=json.loads(r.stdout)
    assert r.returncode==3 and x['worker_spawned'] is False and x['torch_imported'] is False and not list(tmp_path.iterdir())
def test_events_and_stop(tmp_path):
    r=PhaseRecorder(tmp_path,tmp_path,'MOCK_EVENT');r.emit('PRE_MODEL_LOAD')
    with r.span('MOCK_WORK'):pass
    for i in range(4):r.dependency_event(dict(event='weight_load_completed',dependency_id='MOCK_'+str(i)))
    with pytest.raises(ControlledDiagnosticStop):r.checkpoint(STOP_PHASE)
    events=[json.loads(x) for x in r.path.read_text().splitlines()]
    assert all(x['cuda'] is None and x['worker_pid']==os.getpid() and x['elapsed_ms']>=0 for x in events)
    assert all(a['monotonic_time']<=b['monotonic_time'] for a,b in zip(events,events[1:]))
    assert events[-1]['phase']=='CONTROLLED_DIAGNOSTIC_STOP' and r.stopped
    assert (r.path.stat().st_mode&0o777)==0o600
def test_stop_cannot_fake_four_weights(tmp_path):
    r=PhaseRecorder(tmp_path,tmp_path,'MOCK_EVENT')
    with pytest.raises(SafetyStop):r.checkpoint(STOP_PHASE)
    assert not r.stopped
@pytest.mark.parametrize('field,value',[('frames_submitted',1),('frames_completed',1),('tracker_run_called',True),('BA_executed',True),('diagnostic_stop_phase','INITIALIZATION_STARTED'),('diagnostic_loaded_weights',[])])
def test_terminal_scope_rejection(field,value):
    r=dict(status='DIAGNOSTIC_STOP_COMPLETED',error=None,diagnostic_stop_phase=STOP_PHASE,frames_submitted=0,frames_completed=0,tracker_run_called=False,BA_executed=False,diagnostic_loaded_weights=['a','b','c','d']);r[field]=value
    with pytest.raises(Exception):verify_terminal_result(r,{})
def test_stale_event_monitor_fails_closed(tmp_path):
    from linux_safety import atomic_json
    atomic_json(tmp_path/'nvml.latest.json',dict(kind='nvml',session='MOCK_EVENT',monotonic_time=time.monotonic()-4,sample_seq=1,ok=True))
    r=PhaseRecorder(tmp_path,tmp_path,'MOCK_EVENT')
    with pytest.raises(SafetyStop):r.emit('MOCK')
def test_native_adapter_exact_no_frame_boundary(tmp_path,monkeypatch):
    from native_adapter_v2 import _native_runtime
    rec=PhaseRecorder(tmp_path,tmp_path,'MOCK_NATIVE');rec.emit('MOCK_BEGIN')
    names=['update.weight.2.weight','update.weight.2.bias','update.delta.2.weight','update.delta.2.bias']
    class Net:
        def load_state_dict(self,*a,**kw):pass
        def cuda(self):return self
        def eval(self):return self
    class Video:
        def __init__(self,*a,**kw):self.poses=types.SimpleNamespace(shape=(350,7));self.counter=types.SimpleNamespace(value=0)
    class Tracker:
        def __init__(self,*a,**kw):
            for i in range(1,4):rec.dependency_event(dict(event='weight_load_completed',dependency_id='MOCK_WEIGHT_'+str(i)))
        def run(self,*a,**kw):raise AssertionError('TRACKER_RUN_MUST_NOT_BE_CALLED')
    class Stream:
        poses=None;depth_paths=None
        def __len__(self):return 120
        def __getitem__(self,i):raise AssertionError('FRAME_SUBMISSION_MUST_NOT_OCCUR')
    class Writer:
        def __init__(self,*a,**kw):pass
        def close(self):pass
    class Guard:
        def __init__(self,*a,**kw):self.latest={'synthetic':True};self.failure=None;self.phase='MOCK';self.hb=types.SimpleNamespace(failure=None)
        def check(self,*a,**kw):pass
        def snapshot(self):return {'synthetic_only':True}
        def finish(self):pass
    for name,attrs in [('src.depth_video',{'DepthVideo':Video}),('src.modules.droid_net',{'DroidNet':Net}),('src.tracker',{'Tracker':Tracker}),('src.utils.datasets',{'get_dataset':lambda *a,**kw:Stream()}),('torch.utils.tensorboard',{'SummaryWriter':Writer}),('native_linux_guard_v2',{'Guard':Guard,'SafetyStop':SafetyStop})]:
        m=types.ModuleType(name);m.__dict__.update(attrs);monkeypatch.setitem(sys.modules,name,m)
    root=tmp_path/'root';(root/'baselines/droid_w/upstream').mkdir(parents=True)
    original={'tracking':{'pretrained':'/MOCK_ONLY/droid.pth','buffer':350,'warmup':12},'stride':1,'verbose':True,'max_frames':60,'data':{'output':'/MOCK_ONLY/original'}}
    cfg=copy.deepcopy(original);cfg['max_frames']=120;cfg['data']['output']=str(tmp_path)
    pins=types.SimpleNamespace(assert_hooks=lambda **kw:None,effective_config=lambda out:cfg,_checked_original=original,spec={'config':{'sha256':'MOCK_ONLY'}})
    def load(*a,**kw):
        assert a[0]=='/MOCK_ONLY/droid.pth';rec.dependency_event(dict(event='weight_load_completed',dependency_id='MOCK_WEIGHT_0'));return {k:[0,0,0] for k in names}
    torch=types.SimpleNamespace(load=load,set_num_threads=lambda x:None,manual_seed=lambda x:None,cuda=types.SimpleNamespace(max_memory_allocated=lambda:0,max_memory_reserved=lambda:0,memory_stats=lambda:{}))
    cv2=types.SimpleNamespace(setNumThreads=lambda x:None);np=types.SimpleNamespace(random=types.SimpleNamespace(seed=lambda x:None))
    result=dict(started_unix=time.time(),frames_completed=0,frames_submitted=0,dependency_pin_events=[],native_snapshots=[],mapping_events=[],error=None)
    monkeypatch.setenv('GAMECAM_RUN_SESSION_DIR',str(tmp_path));old_handler=signal.getsignal(signal.SIGTERM);old_cwd=os.getcwd()
    try:
        code=_native_runtime(root/'planned-v2-runtime-root',types.SimpleNamespace(method='droidw',case='V56_01_middle',monitor_session_id='MOCK_NATIVE'),{'case_id':'MOCK_CASE'},tmp_path,result,lambda:None,torch,cv2,np,pins,diagnostic=rec)
    finally:signal.signal(signal.SIGTERM,old_handler);os.chdir(old_cwd)
    assert code==0 and result['status']=='DIAGNOSTIC_STOP_COMPLETED' and result['frames_submitted']==0
    assert result['tracker_run_called'] is False and result['BA_executed'] is False
    phases=[x['phase'] for x in rec.events]
    assert phases.index('DEPTHVIDEO_ALLOCATION_DONE')<phases.index('TRACKER_CONSTRUCTION_STARTED')<phases.index('TRACKER_CONSTRUCTION_DONE')
    verify_terminal_result(result,{})

def mock_context(tmp_path,pair,monkeypatch):
    c,a=copy.deepcopy(pair);a['issued_unix']=time.time()-1;a['expires_unix']=time.time()+100
    out=tmp_path/'MOCK_RUN';c.update(planned_session_directory=str(out),planned_authorization_ledger=str(out/'MOCK_ledger.json'),nonce_registry_root=str(tmp_path/'MOCK_nonce_registry'),planned_ipc_root=__import__('ipc_runtime').expected_root(c['planned_session_id']).as_posix(),pinned_environment={'CUDA_VISIBLE_DEVICES':'0'},worker_command_prefix=['MOCK_WORKER'],monitor_command_prefix=['MOCK_MONITOR'])
    class Context(DiagnosticContext):
        def validate_candidate(self):self._candidate=c;return c
        def _auth(self,c,env):validate_diagnostic_authorization(c,self.candidate_sha,a,env);return a
        def validate_identity(self,c):return {'MOCK_ONLY':True}
    ctx=Context(tmp_path/'MOCK_candidate.json','a'*64,tmp_path/'MOCK_not_written_authorization.json')
    worker=['MOCK_WORKER','--candidate',str(ctx.candidate_path),'--candidate-sha','a'*64,'--authorization',str(ctx.authorization_path),'--session-dir',str(out),'--session',c['planned_session_id']]
    monitor=['MOCK_MONITOR','--monitor',str(out),'--session',c['planned_session_id']]
    return ctx,c,a,out,worker,monitor

def test_actual_exclusive_claim_and_reuse(tmp_path,pair,monkeypatch):
    ctx,c,a,out,w,m=mock_context(tmp_path,pair,monkeypatch);out.mkdir()
    assert ctx.validate(out,c['planned_session_id'],w,m,{'CUDA_VISIBLE_DEVICES':'0'},consume=True)
    assert ctx.claimed and len(list((tmp_path/'MOCK_nonce_registry').iterdir()))==1
    with pytest.raises(Exception):ctx.validate(out,c['planned_session_id'],w,m,{'CUDA_VISIBLE_DEVICES':'0'},consume=True)

def test_concurrent_claim_only_once(tmp_path,pair,monkeypatch):
    import threading,concurrent.futures
    ctx,c,a,out,w,m=mock_context(tmp_path,pair,monkeypatch);out.mkdir()
    other=type(ctx)(ctx.candidate_path,ctx.candidate_sha,ctx.authorization_path)
    barrier=threading.Barrier(2)
    def identity(c):barrier.wait(timeout=3);return {}
    ctx.validate_identity=identity;other.validate_identity=identity
    def run(x):
        try:x.validate(out,c['planned_session_id'],w,m,{'CUDA_VISIBLE_DEVICES':'0'},consume=True);return True
        except Exception:return False
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(run,[ctx,other]))
    assert results.count(True)==1 and len(list((tmp_path/'MOCK_nonce_registry').iterdir()))==1

@pytest.mark.parametrize('field,value',[('candidate_sha256','0'*64),('gpu_uuid','WRONG'),('scope',{}),('expires_unix',0),('consumed',True),('attempt_limit',0),('permission_type','FORMAL_120_FRAME')])
def test_invalid_authorization_before_spawn(tmp_path,pair,monkeypatch,field,value):
    from runner_core import supervise_once
    ctx,c,a,out,w,m=mock_context(tmp_path,pair,monkeypatch);a[field]=value
    called=[]
    def forbidden(*args,**kw):called.append(True);raise AssertionError('SUBPROCESS_BEFORE_AUTHORIZATION')
    monkeypatch.setattr(subprocess,'Popen',forbidden)
    with pytest.raises(Exception):supervise_once(out,c['planned_session_id'],w,m,'droidw_diagnostic',env={'CUDA_VISIBLE_DEVICES':'0'},expected_frames=0,launch_context=ctx)
    assert not called and not out.exists() and not ctx.claimed

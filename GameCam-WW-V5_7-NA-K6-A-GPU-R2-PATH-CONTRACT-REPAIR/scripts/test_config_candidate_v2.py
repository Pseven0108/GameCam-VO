"""CPU-only regressions for effective-config and sealed candidate identities."""
import copy,hashlib,json,pathlib,subprocess
import pytest
from runtime_dependency_pins import RuntimePins,PinError
from launch_authorization import LaunchContext


def file_record(p):
    return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}


@pytest.fixture
def config_pins(tmp_path,monkeypatch):
    root=tmp_path/'stage';root.mkdir()
    original={'max_frames':60,'stride':1,'tracking':{'buffer':350,'warmup':12,'motion_filter':{'thresh':3.0}},'mapping':{'enable':False},'data':{'output':'original','input_folder':'frozen-input'},'cam':{'W':512,'H':288},'other_untouched':{'nested':[1,2,3]}}
    p=object.__new__(RuntimePins);p.root=root;p.spec={'k4_live_contract':{'path_linux':str(tmp_path/'input'/'contract.json')},'allowed_path_roots':[{'real_linux':str(tmp_path/'GameCam-VO')}]}
    monkeypatch.setattr(p,'read_original_config',lambda:copy.deepcopy(original))
    return p,original


def test_effective_config_only_two_fields_change(config_pins,tmp_path):
    p,original=config_pins;out=tmp_path/'future'/'model';cfg=p.effective_config(out)
    assert cfg['max_frames']==120 and cfg['data']['output']==str(out)
    reverted=copy.deepcopy(cfg);reverted['max_frames']=60;reverted['data']['output']='original'
    assert reverted==original and not out.exists()


@pytest.mark.parametrize('kind',['relative','existing','source','input','production','broken_symlink'])
def test_effective_config_rejects_unsafe_outputs(config_pins,tmp_path,kind):
    p,_=config_pins
    if kind=='relative':out=pathlib.Path('relative/model')
    elif kind=='existing':out=tmp_path/'existing';out.mkdir()
    elif kind=='source':out=p.root/'new'
    elif kind=='input':out=tmp_path/'input'/'new'
    elif kind=='production':out=tmp_path/'GameCam-VO'/'new'
    else:out=tmp_path/'link';out.symlink_to(tmp_path/'missing')
    with pytest.raises(PinError):p.effective_config(out)


def test_original_configuration_hash_drift_rejected(tmp_path,monkeypatch):
    original=tmp_path/'config.json';original.write_text('{"max_frames":60}')
    raw=original.read_bytes();p=object.__new__(RuntimePins)
    p.spec={'config':{'id':'fixture_config','path_linux':str(original),'real_linux':str(original),'allowed_root_linux':str(tmp_path),'allowed_root_real_linux':str(tmp_path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}}
    monkeypatch.setattr(p,'assert_manifest',lambda:None)
    original.write_text('{"max_frames":61}')
    with pytest.raises(PinError,match='SHA'):p.read_original_config()


@pytest.fixture
def candidate_tree(tmp_path):
    root=tmp_path/'source';root.mkdir();source=root/'module.py';source.write_text('VALUE = 1\n')
    def git(*args):return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True,text=True).stdout.strip()
    git('init','-q');git('add','module.py');git('-c','user.name=CPU Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Fixture source')
    external=tmp_path/'external.py';external.write_text('EXTERNAL = 1\n')
    config=tmp_path/'effective.json';config.write_text('{"max_frames":120}')
    c={'source_root':str(root),'source_git_commit':git('rev-parse','HEAD'),'source_records':[{'path':'module.py','sha256':file_record(source)['sha256']}],'external_source_records':[file_record(external)],'configuration_records':[file_record(config)]}
    return root,source,external,config,c


@pytest.mark.parametrize('fault',['none','candidate_sha','source_sha','source_commit','dirty_source','external_sha','configuration_sha','source_path_escape'])
def test_actual_candidate_identity_validation(candidate_tree,tmp_path,fault):
    root,source,external,config,c=candidate_tree
    if fault=='source_sha':c['source_records'][0]['sha256']='0'*64
    elif fault=='source_commit':c['source_git_commit']='0'*40
    elif fault=='dirty_source':source.write_text('VALUE = 2\n')
    elif fault=='external_sha':external.write_text('EXTERNAL = 2\n')
    elif fault=='configuration_sha':config.write_text('{"max_frames":121}')
    elif fault=='source_path_escape':c['source_records'][0]['path']='../escape.py'
    candidate=tmp_path/'candidate.json';candidate.write_text(json.dumps(c))
    expected='0'*64 if fault=='candidate_sha' else file_record(candidate)['sha256']
    context=LaunchContext(candidate,expected,None)
    if fault=='none':assert context.validate_candidate()==c
    else:
        with pytest.raises(PinError):context.validate_candidate()
    assert context.claimed is False


def test_framework_state_module_is_allowed_in_pinned_environment(tmp_path):
    from model_io_boundary_v2 import ModelIOBoundary
    env=tmp_path/'env';boundary=ModelIOBoundary([],[],[tmp_path/'project'],[tmp_path/'output'],[env])
    assert boundary.check_path(env/'torch/jit/_state.py')
    assert boundary.check_path(env/'torch/jit/__pycache__/_state.cpython-310.pyc')


def test_state_data_still_rejected_inside_environment(tmp_path):
    from model_io_boundary_v2 import ModelIOBoundary
    env=tmp_path/'env';boundary=ModelIOBoundary([],[],[tmp_path/'project'],[tmp_path/'output'],[env])
    with pytest.raises(RuntimeError,match='MODEL_ANALYSIS_DATA_FORBIDDEN'):boundary.check_path(env/'state.csv')


def test_native_adapter_starts_guard_before_tracker_imports(tmp_path,monkeypatch):
    import builtins,sys,time,types
    import native_adapter_v2 as adapter
    events=[]
    class Stop(RuntimeError):pass
    class FakeGuard:
        phase='fixture_guard'
        def __init__(self,*args):events.append('guard_started')
        def snapshot(self):return {'fixture':True}
        def finish(self):events.append('guard_finished');return {'fixture':True}
    monkeypatch.setitem(sys.modules,'native_linux_guard_v2',types.SimpleNamespace(Guard=FakeGuard,SafetyStop=Stop))
    original_import=builtins.__import__
    def guarded_import(name,*args,**kwargs):
        if name=='src.depth_video':
            assert events==['guard_started'],'Native imports preceded safety heartbeat'
            events.append('native_import_entered');raise ImportError('CPU_FIXTURE_STOPS_BEFORE_REAL_NATIVE_IMPORT')
        return original_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded_import)
    monkeypatch.setattr(adapter.os,'chdir',lambda *args:None);monkeypatch.setattr(sys,'path',list(sys.path))
    monkeypatch.setenv('GAMECAM_RUN_SESSION_DIR',str(tmp_path/'session'))
    cuda=types.SimpleNamespace(OutOfMemoryError=type('FakeOOM',(RuntimeError,),{}),max_memory_allocated=lambda:0,max_memory_reserved=lambda:0,memory_stats=lambda:{})
    torch=types.SimpleNamespace(set_num_threads=lambda *args:None,manual_seed=lambda *args:None,cuda=cuda)
    pins=types.SimpleNamespace(assert_hooks=lambda **kwargs:None)
    out=tmp_path/'out';out.mkdir()
    result={'started_unix':time.time(),'frames_completed':0,'frames_submitted':0}
    code=adapter._native_runtime(tmp_path/'runtime',types.SimpleNamespace(method='droidw',case='fixture',monitor_session_id='CPU_FIXTURE'),{},out,result,lambda:None,torch,types.SimpleNamespace(setNumThreads=lambda *args:None),types.SimpleNamespace(random=types.SimpleNamespace(seed=lambda *args:None)),pins)
    assert code==2 and events==['guard_started','native_import_entered','guard_finished']
    assert result['status']=='BLOCKED_BY_INPUT_CONTRACT'

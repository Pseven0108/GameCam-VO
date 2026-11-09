"""Real-process regression of scoped Arena paths and the installed Python audit hook."""
import hashlib,json,os,pathlib,subprocess,sys,uuid
import pytest
from ipc_runtime import prepare_owner,cleanup_owner,IPCError,IPCPolicy,expected_root
HERE=pathlib.Path(__file__).parent

@pytest.mark.parametrize('method,mode,fallback',[('fork','exercise',False),('spawn','exercise',False),('fork','abnormal',False),('spawn','abnormal',False),('fork','terminate',False),('spawn','terminate',False),('fork','boundary',False),('fork','exercise',True),('spawn','exercise',True)])
def test_real_ipc_roundtrip_and_audit(tmp_path,method,mode,fallback):
    session='CPU_IPC_'+uuid.uuid4().hex;d=tmp_path/'session';d.mkdir();project=tmp_path/'project';project.mkdir()
    for name in ['source.py','weight.pth','image.png','state.csv']:(project/name).write_bytes(b'SYNTHETIC_FIXTURE_ONLY')
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in project.iterdir()}
    owner=prepare_owner(d,session)
    cmd=[sys.executable,'-B',str(HERE/'ipc_cpu_fixture.py'),'--session-dir',str(d),'--session',session,'--method',method,'--mode',mode]
    if fallback:cmd+=['--force-fallback']
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
    p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=60)
    (d/'fixture.stdout.txt').write_text(p.stdout);(d/'fixture.stderr.txt').write_text(p.stderr)
    assert p.returncode==0,p.stderr+p.stdout
    result=json.loads(p.stdout);assert result['passed'] and not result['torch_imported'] and not result['real_checkpoint_loaded']
    assert not pathlib.Path('/proc',str(result['worker_pid'])).exists()
    assert result['active_multiprocessing_children']==0
    assert all(not pathlib.Path('/dev/shm', 'sem.'+name.lstrip('/')).exists() for name in result['native_semaphore_names'])
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in project.iterdir()}
    cleaned=cleanup_owner(owner,True,True,[result['worker_pid'],result['child_pid']]);assert cleaned['passed'] and cleaned['root_removed']
    (d/'cleanup_result.json').write_text(json.dumps(cleaned,indent=2)+'\n')
    if mode=='boundary':assert len(result['denied_probes'])==18 and result['boundary_events']

@pytest.mark.parametrize('fault',['reuse','permission','root_symlink','foreign_residual','cleanup_before_exit','wrong_pid'])
def test_ipc_identity_and_cleanup_fail_closed(tmp_path,fault):
    session='CPU_IPC_'+uuid.uuid4().hex;d=tmp_path/'session';d.mkdir();owner=prepare_owner(d,session);root=pathlib.Path(owner['root'])
    try:
        if fault=='reuse':
            with pytest.raises(FileExistsError):prepare_owner(d,session)
        elif fault=='permission':
            root.chmod(0o755)
            with pytest.raises(IPCError):IPCPolicy(root,d/'tmp',session,d)
            root.chmod(0o700)
        elif fault=='root_symlink':
            alias=tmp_path/'alias';alias.symlink_to(root,target_is_directory=True)
            with pytest.raises(IPCError):IPCPolicy(alias,d/'tmp',session,d)
        elif fault=='foreign_residual':
            p=root/'unrecognized.txt';p.write_text('fixture')
            with pytest.raises(IPCError,match='FOREIGN_RESIDUAL'):cleanup_owner(owner,True,True,[])
            assert p.exists();p.unlink()
        elif fault=='cleanup_before_exit':
            with pytest.raises(IPCError,match='BEFORE_CHILD_EXIT'):cleanup_owner(owner,False,True,[])
        elif fault=='wrong_pid':
            p=root/'pym-999999-abcd1234';p.write_text('fixture');p.chmod(0o600)
            with pytest.raises(IPCError):cleanup_owner(owner,True,True,[os.getpid()])
            p.unlink()
    finally:
        root.chmod(0o700);assert cleanup_owner(owner,True,True,[])['root_removed']

@pytest.mark.parametrize('fault',['fallback_exists','marker_open_failure'])
def test_partial_owner_setup_removes_only_owned_new_paths(tmp_path,monkeypatch,fault):
    import ipc_runtime
    session='CPU_IPC_'+uuid.uuid4().hex;d=tmp_path/'session';d.mkdir();root=expected_root(session)
    if fault=='fallback_exists':(d/'tmp').mkdir();(d/'tmp'/'keep.txt').write_text('PRESERVE_PREEXISTING_FIXTURE')
    else:
        original=ipc_runtime.os.open
        def fail_marker(path,*args,**kwargs):
            if pathlib.Path(path)==root/ipc_runtime.MARKER:raise OSError('INJECTED_MARKER_OPEN_FAILURE')
            return original(path,*args,**kwargs)
        monkeypatch.setattr(ipc_runtime.os,'open',fail_marker)
    with pytest.raises(OSError):prepare_owner(d,session)
    assert not root.exists()
    if fault=='fallback_exists':assert (d/'tmp'/'keep.txt').read_text()=='PRESERVE_PREEXISTING_FIXTURE'
    else:assert not (d/'tmp').exists()
    assert json.loads((d/'ipc_owner_events.jsonl').read_text().splitlines()[-1])['event']=='IPC_ROOT_SETUP_FAILED'

@pytest.mark.parametrize('fault',['owned_residual','foreign_residual','replaced_directory'])
def test_fallback_cleanup_is_bound_and_fail_closed(tmp_path,fault):
    session='CPU_IPC_'+uuid.uuid4().hex;d=tmp_path/'session';d.mkdir();owner=prepare_owner(d,session);fallback=d/'tmp';preserved=None
    if fault=='replaced_directory':
        preserved=d/'tmp-original';fallback.rename(preserved);fallback.mkdir(mode=0o700)
        with pytest.raises(IPCError,match='FALLBACK_REPLACED'):cleanup_owner(owner,True,True,[])
        fallback.rmdir();preserved.rename(fallback)
    else:
        p=fallback/('pym-'+str(os.getpid())+'-abcd1234' if fault=='owned_residual' else 'unrecognized.txt');p.write_text('CPU_FIXTURE');p.chmod(0o600)
        if fault=='foreign_residual':
            with pytest.raises(IPCError,match='FOREIGN_RESIDUAL'):cleanup_owner(owner,True,True,[])
            assert p.exists() and pathlib.Path(owner['root']).exists();p.unlink()
    result=cleanup_owner(owner,True,True,[]);assert result['root_removed'] and result['fallback_empty']

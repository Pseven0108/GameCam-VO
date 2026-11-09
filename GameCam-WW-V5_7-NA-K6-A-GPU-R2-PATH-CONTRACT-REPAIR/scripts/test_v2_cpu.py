"""CPU-only adversarial tests. All authorizations and GPU samples below are in-memory fakes."""
import copy,csv,hashlib,importlib,json,os,pathlib,socket,subprocess,sys,time,types
import pytest
import runtime_dependency_pins as runtime
from runtime_dependency_pins import RuntimePins,PinError,LoaderGate
import runner_core as core
from launch_authorization import SCOPE,LaunchContext,validate_authorization
from model_io_boundary_v2 import ModelIOBoundary

def sha(raw):return hashlib.sha256(raw).hexdigest()
def record(path,data,loader='torch.load',url=None):
    return dict(id=path.name,path_linux=str(path),path_windows=str(path),real_linux=str(path.resolve()),real_windows=str(path.resolve()),allowed_root_linux=str(path.parent),allowed_root_windows=str(path.parent),allowed_root_real_linux=str(path.parent.resolve()),allowed_root_real_windows=str(path.parent.resolve()),bytes=len(data),sha256=sha(data),loader=loader,url=url)

@pytest.fixture
def loader_fixture(tmp_path,monkeypatch):
    saved={n:m for n,m in sys.modules.items() if n=='torch' or n.startswith(('torch.','safetensors','huggingface_hub'))}
    assert not saved,'Loader tests must start without real model dependencies'
    gates=[]
    def create(install=True):
        root=tmp_path/'pins';(root/'config').mkdir(parents=True)
        revision='fixture_revision_123';records=[]
        for i in range(4):
            path=(tmp_path/'hf'/'hub'/'snapshots'/revision/'model.safetensors') if i==3 else tmp_path/'weights'/f'fake_{i}.pth'
            path.parent.mkdir(parents=True,exist_ok=True);data=f'FAKE_WEIGHT_NO_DESERIALIZATION_{i}'.encode();path.write_bytes(data)
            records.append(record(path,data,'safetensors.torch.load_file' if i==3 else 'torch.load',f'https://approved.invalid/fake_{i}.pth' if i<3 else None))
        frozen=root/'config/frozen_weight_manifest.csv'
        fields=['dependency_id','expected_sha256','sha256','bytes','path_linux','path_windows','real_linux','allowed_root_linux','allowed_root_real_linux']
        with frozen.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            for r in records:writer.writerow({k:(r['id'] if k=='dependency_id' else r['sha256'] if k=='expected_sha256' else r[k]) for k in fields})
        ref=tmp_path/'hf'/'ref';ref.parent.mkdir(exist_ok=True);ref.write_text(revision)
        ref_record=record(ref,revision.encode())
        env={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HOME':str(tmp_path/'hf'),'TORCH_HOME':str(tmp_path/'torch_cache')}
        spec=dict(version=runtime.SPEC_VERSION,checks={k:True for k in runtime.CHECKS},weights=records,files={'frozen_weight_manifest.csv':{'path':'config/frozen_weight_manifest.csv','bytes':frozen.stat().st_size,'sha256':sha(frozen.read_bytes())}},environment=env,hub_models={'fixture_model':str(tmp_path/'repo')},hf=dict(repo_id='fixture/repo',filename='model.safetensors',revision=revision,weight_id=records[3]['id'],ref_path_linux=str(ref),ref_path_windows=str(ref),ref_real_linux=str(ref),ref_real_windows=str(ref),ref_allowed_root_linux=str(ref.parent),ref_allowed_root_windows=str(ref.parent),ref_allowed_root_real_linux=str(ref.parent),ref_allowed_root_real_windows=str(ref.parent),ref_bytes=len(revision),ref_sha256=sha(revision.encode())))
        raw=json.dumps(spec).encode();(root/'config/dependency_pins.json').write_bytes(raw);monkeypatch.setattr(runtime,'FROZEN_SPEC_SHA256',sha(raw))
        for k,v in env.items():monkeypatch.setenv(k,v)
        monkeypatch.setenv('CUDA_VISIBLE_DEVICES','')
        modules=tmp_path/'fake_modules';modules.mkdir()
        sources={'torch/__init__.py':'from . import serialization,hub\ndef load(f,**kwargs): return serialization.load(f,**kwargs)\n',
                 'torch/serialization.py':'def load(f,**kwargs):\n if kwargs.get("explode"): raise ValueError("fixture loader failure")\n return {"fixture_only":True,"path":str(f)}\n',
                 'torch/hub.py':'import os\ndef load_state_dict_from_url(url,model_dir=None,map_location=None,progress=True,check_hash=False,file_name=None):\n import torch\n return torch.load(os.path.join(model_dir,file_name or url.rsplit("/",1)[-1]))\ndef load(repo_or_dir,model,source="github",**kwargs): return {"repo":repo_or_dir,"model":model}\ndef download_url_to_file(*args,**kwargs): raise AssertionError("unguarded network download")\n',
                 'safetensors/__init__.py':'',
                 'safetensors/torch.py':'def load_file(filename,**kwargs):return {"fixture_only":True,"path":str(filename)}\n',
                 'huggingface_hub/__init__.py':'from .file_download import hf_hub_download\nfrom ._snapshot_download import snapshot_download\n',
                 'huggingface_hub/file_download.py':f'RETURN_PATH={str(records[3]["path_linux"])!r}\ndef hf_hub_download(repo_id,filename,revision=None,cache_dir=None,force_download=False,local_files_only=False,subfolder=None):return RETURN_PATH\n',
                 'huggingface_hub/_snapshot_download.py':'def snapshot_download(*args,**kwargs):raise AssertionError("unguarded snapshot download")\n'}
        for rel,text in sources.items():
            path=modules/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        monkeypatch.syspath_prepend(str(modules));pins=RuntimePins(root)
        if install:gates.append(pins.install_before_import())
        return pins,records
    yield create
    for gate in reversed(gates):gate.close()
    for n in list(sys.modules):
        if n=='torch' or n.startswith(('torch.','safetensors','huggingface_hub')):sys.modules.pop(n,None)

class TestLoaderGate:
    @pytest.mark.parametrize('api,index',[('torch.load',0),('torch.serialization.load',1),('safetensors.torch.load_file',3)])
    def test_registered_fake_weight_actual_wrapped_call(self,loader_fixture,api,index):
        pins,records=loader_fixture();module,attr=api.rsplit('.',1);func=getattr(importlib.import_module(module),attr)
        result=func(records[index]['path_linux']);assert result['fixture_only'];assert any(e['event']=='weight_load_completed' for e in pins.events)
        if api=='torch.load':assert sum(e['event']=='weight_load_started' for e in pins.events)==2
    @pytest.mark.parametrize('api',[('torch','load'),('torch.serialization','load'),('safetensors.torch','load_file')])
    def test_unregistered_weight_rejected(self,loader_fixture,tmp_path,api):
        pins,_=loader_fixture();func=getattr(importlib.import_module(api[0]),api[1]);bad=tmp_path/'unregistered.fake';bad.write_bytes(b'fake')
        with pytest.raises(PinError,match='UNREGISTERED_WEIGHT'):func(str(bad))
        assert pins.gate.failed
    @pytest.mark.parametrize('index,api',[(0,('torch','load')),(3,('safetensors.torch','load_file'))])
    def test_sha_mismatch_rejected(self,loader_fixture,index,api):
        pins,records=loader_fixture();func=getattr(importlib.import_module(api[0]),api[1]);path=pathlib.Path(records[index]['path_linux']);path.write_bytes(b'X'*path.stat().st_size)
        with pytest.raises(PinError,match='FILE_SHA_MISMATCH'):func(str(path))
    def test_unknown_symlink_rejected(self,loader_fixture,tmp_path):
        pins,r=loader_fixture();torch=importlib.import_module('torch');alias=tmp_path/'unknown.pth';alias.symlink_to(r[0]['path_linux'])
        with pytest.raises(PinError,match='UNREGISTERED_WEIGHT'):torch.load(str(alias))
    def test_registered_symlink_retarget_rejected(self,loader_fixture,tmp_path):
        pins,r=loader_fixture();torch=importlib.import_module('torch');p=pathlib.Path(r[0]['path_linux']);other=tmp_path/'other';other.write_bytes(p.read_bytes());p.unlink();p.symlink_to(other)
        with pytest.raises(PinError,match='SYMLINK_TARGET_CHANGED'):torch.load(str(p))
    @pytest.mark.parametrize('which',['hub_url','hub_download','hf_snapshot','hf_revision','hf_force_download','hf_cache_root','socket'])
    def test_network_or_cache_fallback_rejected(self,loader_fixture,which,tmp_path):
        pins,r=loader_fixture();hub=importlib.import_module('torch.hub');hf=importlib.import_module('huggingface_hub')
        def call():
            if which=='hub_url':return hub.load_state_dict_from_url('https://unapproved.invalid/model.pth')
            if which=='hub_download':return hub.download_url_to_file('https://invalid.invalid',str(tmp_path/'file'))
            if which=='hf_snapshot':return hf.snapshot_download('fixture/repo')
            if which=='socket':return socket.create_connection(('127.0.0.1',9))
            kw={'repo_id':'fixture/repo','filename':'model.safetensors','local_files_only':True}
            if which=='hf_revision':kw['revision']='unapproved_revision'
            if which=='hf_force_download':kw['force_download']=True
            if which=='hf_cache_root':kw['cache_dir']=str(tmp_path/'other_cache')
            return hf.hf_hub_download(**kw)
        with pytest.raises(PinError):call()
        assert pins.gate.failed
    def test_cached_hub_and_hf_registered_weight_allowed(self,loader_fixture):
        pins,r=loader_fixture();hub=importlib.import_module('torch.hub');hf=importlib.import_module('huggingface_hub')
        assert hub.load_state_dict_from_url(r[0]['url'],model_dir=str(pathlib.Path(r[0]['path_linux']).parent),file_name=pathlib.Path(r[0]['path_linux']).name)['fixture_only']
        assert hf.hf_hub_download('fixture/repo','model.safetensors',local_files_only=True)==r[3]['path_linux']
        assert hub.load(pins.spec['hub_models']['fixture_model'],'fixture_model',source='local')['model']=='fixture_model'
    def test_hf_returned_unregistered_cache_rejected(self,loader_fixture,tmp_path):
        pins,_=loader_fixture();hf=importlib.import_module('huggingface_hub');module=importlib.import_module('huggingface_hub.file_download');module.RETURN_PATH=str(tmp_path/'wrong_cache')
        with pytest.raises(PinError):hf.hf_hub_download('fixture/repo','model.safetensors',local_files_only=True)
    def test_repeated_patch_preserves_original_and_closes(self,loader_fixture):
        pins,_=loader_fixture();torch=importlib.import_module('torch');original=pins.gate.originals[('torch','load')];wrapper=torch.load
        pins.gate.patch(torch);assert torch.load is wrapper;assert pins.gate.originals[('torch','load')] is original
        pins.gate.close();assert torch.load is original
        with pytest.raises(PinError):wrapper('unused')
    def test_duplicate_install_rejected(self,loader_fixture):
        pins,_=loader_fixture()
        with pytest.raises(PinError,match='HOOK_GATE_ALREADY_INSTALLED'):pins.install_before_import()
    def test_gate_uninitialized_rejected(self,loader_fixture):
        pins,_=loader_fixture(install=False)
        with pytest.raises(PinError,match='LOADER_GATE_MISSING'):pins.assert_hooks()
    def test_prebound_loader_before_gate_rejected(self,loader_fixture):
        pins,_=loader_fixture(install=False);importlib.import_module('torch')
        with pytest.raises(PinError,match='LOADERS_BOUND_BEFORE_PIN_INSTALL'):pins.install_before_import()
    def test_replaced_hook_latches_failure(self,loader_fixture):
        pins,_=loader_fixture();torch=importlib.import_module('torch');wrapper=torch.load;torch.load=lambda *_:None
        with pytest.raises(PinError,match='LOADER_CHECKER_DISABLED'):pins.assert_hooks()
        torch.load=wrapper
        with pytest.raises(PinError,match='LOADER_GATE_PREVIOUSLY_FAILED'):pins.assert_hooks()
    def test_no_public_unwrapped_alias(self,loader_fixture):
        pins,_=loader_fixture();torch=importlib.import_module('torch');assert not hasattr(torch.load,'__wrapped__')
    def test_deserializer_exception_is_fail_closed(self,loader_fixture):
        pins,r=loader_fixture();torch=importlib.import_module('torch')
        with pytest.raises(ValueError,match='fixture loader failure'):torch.load(r[0]['path_linux'],explode=True)
        with pytest.raises(PinError,match='LOADER_GATE_PREVIOUSLY_FAILED'):torch.load(r[0]['path_linux'])

def auth_fixture():
    now=time.time();c={'scope':dict(SCOPE),'maximum_authorizable_attempts':1,'automatic_retry':False};a={'candidate_sha256':'a'*64,'scope':dict(SCOPE),'model_execution_authorized':True,'attempt_limit':1,'automatic_retry':False,'consumed':False,'nonce':'fixture-only-in-memory-nonce','issued_unix':now-5,'expires_unix':now+60,'gpu_environment_verified':True,'visible_device_count':1}
    return c,a,{'CUDA_VISIBLE_DEVICES':'0'}
class TestAuthorization:
    def test_valid_in_memory_fixture(self):
        c,a,e=auth_fixture();assert validate_authorization(c,'a'*64,a,e)
    @pytest.mark.parametrize('scenario,reason',[('no_auth','NO_FRESH'),('wrong_sha','CANDIDATE_SHA'),('wrong_worker','UNAUTHORIZED_WORKER'),('not_authorized','WORKER_NOT'),('expired','EXPIRED'),('future','NOT_YET'),('consumed','ALREADY_CONSUMED'),('limit_zero','ATTEMPT_LIMIT'),('retry','AUTOMATIC_RETRY'),('no_gpu','GPU_ENVIRONMENT'),('invisible','GPU_INVISIBLE'),('two_gpu','GPU_ENVIRONMENT'),('missing_nonce','NONCE')])
    def test_rejected_before_spawn(self,scenario,reason):
        c,a,e=auth_fixture()
        if scenario=='no_auth':a=None
        elif scenario=='wrong_sha':a['candidate_sha256']='0'*64
        elif scenario=='wrong_worker':a['scope']['method']='wildgs'
        elif scenario=='not_authorized':a['model_execution_authorized']=False
        elif scenario=='expired':a['expires_unix']=time.time()-1
        elif scenario=='future':a['issued_unix']=time.time()+60
        elif scenario=='consumed':a['consumed']=True
        elif scenario=='limit_zero':a['attempt_limit']=0
        elif scenario=='retry':a['automatic_retry']=True
        elif scenario=='no_gpu':a['gpu_environment_verified']=False
        elif scenario=='invisible':e['CUDA_VISIBLE_DEVICES']=''
        elif scenario=='two_gpu':a['visible_device_count']=2
        elif scenario=='missing_nonce':a.pop('nonce')
        with pytest.raises(PinError,match=reason):validate_authorization(c,'a'*64,a,e)
    def test_context_no_auth_does_not_read_or_write(self,tmp_path):
        ctx=LaunchContext(tmp_path/'nonexistent_candidate','a'*64,None)
        with pytest.raises(PinError,match='NO_FRESH'):ctx.validate(tmp_path/'out','fixture',[],[],{'CUDA_VISIBLE_DEVICES':''})
        assert not (tmp_path/'out').exists()
    @pytest.mark.parametrize('script',['launcher_v2.py','native_child_v2.py'])
    def test_production_entry_refuses_current_unarmed_request(self,script,tmp_path):
        command=[sys.executable,'-B',str(pathlib.Path(__file__).with_name(script)),'--candidate',str(tmp_path/'missing.json'),'--candidate-sha','0'*64,'--session','CPU_TEST_NO_AUTH']
        r=subprocess.run(command,capture_output=True,text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
        assert r.returncode==3;data=json.loads(r.stdout);assert data['torch_imported'] is False;assert not (tmp_path/'missing.json').exists()

class TestModelIO:
    @pytest.mark.parametrize('name',['state.csv','skeleton.npz','camera_pose.csv','NPC.csv','Monster.csv','gt_pose.csv'])
    def test_analysis_data_rejected(self,name,tmp_path):
        boundary=ModelIOBoundary([],[],[tmp_path/'project'],[tmp_path/'output'])
        with pytest.raises(RuntimeError):boundary.check_path(tmp_path/'project'/name)
    def test_whitelist_rgb_and_isolated_output(self,tmp_path):
        image=tmp_path/'project'/'frame.png';b=ModelIOBoundary([image],[],[tmp_path/'project'],[tmp_path/'output'])
        assert b.check_path(image);assert b.check_path(tmp_path/'output'/'result.json',True)
        with pytest.raises(RuntimeError):b.check_path(tmp_path/'project'/'source.py',True)
        with pytest.raises(RuntimeError):b.check_path(tmp_path/'elsewhere'/'frame.png')
    def test_real_python_open_is_blocked_without_reading_gt_values(self,tmp_path):
        # No GT file is created or read; the audit hook rejects before open resolves a nonexistent path.
        script='from model_io_boundary_v2 import ModelIOBoundary;import pathlib;root=pathlib.Path('+repr(str(tmp_path))+');b=ModelIOBoundary([],[],[root],[root/"out"]);b.install();open(root/"state.csv").read()'
        r=subprocess.run([sys.executable,'-B','-c',script],cwd=pathlib.Path(__file__).parent,capture_output=True,text=True)
        assert r.returncode!=0 and 'MODEL_UNAPPROVED_PROJECT_READ' in r.stderr

class FakeClock:
    def __init__(self):self.now=10000.0
    def monotonic(self):return self.now
    def time(self):return 1794000000.0+self.now
    def sleep(self,t):self.now+=t

def sample(kind,session,seq,now,pid=777):
    row={'kind':kind,'session':session,'sample_seq':seq,'monotonic_time':now,'ok':True,'gpu_uuid':core.EXPECTED_UUID}
    if kind=='nvml':row.update(nvml_free_MiB=4096.,nvml_used_MiB=4096.,CPU_MemAvailable_MiB=16000.,CPU_MemTotal_MiB=32000.,data_disk_free_fraction=.8,temperature_C=40.,utilization_percent=0.,memory_utilization_percent=0.,gpu_processes=[],cgroup_memory_current_bytes=1000000,cgroup_remaining_MiB=16000.)
    else:row.update(cuda_free_MiB=4096.,allocated_MiB=100.,reserved_MiB=200.,worker_pid=pid)
    return row

class TestDroidSupervisor:
    @pytest.mark.parametrize('fault,reason',[('normal',None),('unknown_process','UNKNOWN_GPU_COMPUTE_PROCESS'),('worker_start_failure','fixture Popen failure'),('worker_exit','WORKER_NONZERO_EXIT:23'),('monitor_exit','MONITOR_SUBPROCESS_EXITED:17')])
    def test_actual_droidw_branch_with_mock_process(self,tmp_path,monkeypatch,fault,reason):
        out=tmp_path/'session';session='CPU_DROIDW_BRANCH_FIXTURE';clock=FakeClock();events=[];processes=[]
        monkeypatch.setattr(core,'time',clock)
        original_validate=core.validate_sample
        monkeypatch.setattr(core,'validate_sample',lambda row,kind,sid:original_validate(row,kind,sid,now=clock.now))
        c,a,e=auth_fixture()
        class Context:
            claimed=False
            def validate(self,*args,consume=False):
                validate_authorization(c,'a'*64,a,e);events.append('claim' if consume else 'validate')
                if consume:self.claimed=True
        context=Context()
        class FakeProcess:
            def __init__(self,command,**kw):
                self.role=command[0];self.pid=777 if self.role=='fixture_worker' else 778;self.returncode=None;self.seq=0;self.sent=False;self.last_time=None
                if self.role=='fixture_worker':
                    assert events[-1]=='claim','Worker spawn occurred before authorization claim'
                    if fault=='worker_start_failure':raise OSError('fixture Popen failure')
                events.append('spawn_'+self.role);processes.append(self)
            def poll(self):
                if self.returncode is not None:return self.returncode
                if self.role=='fixture_monitor':
                    if (out/'monitor.stop').exists():self.returncode=0;return 0
                    if fault=='monitor_exit':self.returncode=17;return 17
                    if self.last_time==clock.now:return None
                    self.last_time=clock.now;self.seq+=1;n=sample('nvml',session,self.seq,clock.now)
                    if fault=='unknown_process':n['gpu_processes']=[{'pid':999,'used_MiB':100}]
                    core.atomic_json(out/'nvml.latest.json',n);return None
                self.seq+=1;core.atomic_json(out/'cuda.latest.json',sample('cuda',session,self.seq,clock.now))
                if fault=='worker_exit':self.returncode=23;return 23
                if (out/'work.permit.json').exists() and not self.sent:
                    for i in range(3):
                        row=sample('cuda',session,i+1,clock.now);row['frame_ordinal']=i;core.append_json(out/'frame_samples.jsonl',row)
                    self.sent=True;self.returncode=0;return 0
                return None
            def wait(self,timeout=None):
                if self.role=='fixture_monitor' and (out/'monitor.stop').exists():self.returncode=0
                return self.returncode
        monkeypatch.setattr(core.subprocess,'Popen',FakeProcess)
        def stop(proc,why,folder,label,kind):proc.returncode=-15;return {'signals':['MOCK_SIGTERM'],'fully_exited':True,'exit_code':-15}
        monkeypatch.setattr(core,'stop_owned',stop)
        r=core.supervise_once(out,session,['fixture_worker'],['fixture_monitor'],'droidw',env=e,expected_frames=3 if fault=='normal' else None,launch_context=context)
        if reason is None:assert r['passed'] and r['completed_frame_samples']==3
        else:assert reason in r['reason'] and not r['passed']
        assert r['automatic_retries']==0 and all(p.poll() is not None for p in processes)
        if fault in ('unknown_process','monitor_exit'):assert not r['worker_started'] and not context.claimed
        if fault in ('normal','worker_exit'):assert events.index('claim')<events.index('spawn_fixture_worker')
    def test_missing_context_rejected_before_monitor_and_output(self,tmp_path,monkeypatch):
        calls=[];monkeypatch.setattr(core.subprocess,'Popen',lambda *_a,**_k:calls.append('spawn'))
        with pytest.raises(core.SafetyStop,match='CONTEXT_REQUIRED'):core.supervise_once(tmp_path/'never-created','fixture',[],[],'droidw')
        assert not calls and not (tmp_path/'never-created').exists()
    def test_missing_authorization_rejected_before_monitor(self,tmp_path,monkeypatch):
        calls=[];monkeypatch.setattr(core.subprocess,'Popen',lambda *_a,**_k:calls.append('spawn'));ctx=LaunchContext(tmp_path/'no-candidate','0'*64,None)
        with pytest.raises(PinError,match='NO_FRESH'):core.supervise_once(tmp_path/'never-created','fixture',[],[],'droidw',launch_context=ctx)
        assert not calls and not (tmp_path/'never-created').exists()

    @pytest.mark.parametrize('fault',['wrong_sha','expired','consumed','limit_zero','retry','invisible','no_gpu','missing_nonce','wrong_worker'])
    def test_invalid_authorization_blocks_droidw_branch_before_spawn(self,tmp_path,monkeypatch,fault):
        c,a,e=auth_fixture();out=tmp_path/'not-created';calls=[]
        if fault=='wrong_sha':a['candidate_sha256']='0'*64
        elif fault=='expired':a['expires_unix']=time.time()-1
        elif fault=='consumed':a['consumed']=True
        elif fault=='limit_zero':a['attempt_limit']=0
        elif fault=='retry':a['automatic_retry']=True
        elif fault=='invisible':e['CUDA_VISIBLE_DEVICES']=''
        elif fault=='no_gpu':a['gpu_environment_verified']=False
        elif fault=='missing_nonce':a.pop('nonce')
        elif fault=='wrong_worker':a['scope']['method']='pi3mos'
        # Actual LaunchContext/actual supervise_once; only authorization file IO is mocked in memory.
        ctx=LaunchContext(tmp_path/'candidate','a'*64,tmp_path/'IN_MEMORY_FIXTURE_NOT_AN_AUTHORIZATION_FILE')
        monkeypatch.setattr(ctx,'validate_candidate',lambda:c)
        real_read=pathlib.Path.read_text
        monkeypatch.setattr(pathlib.Path,'read_text',lambda p,*args,**kwargs:json.dumps(a) if p==ctx.authorization_path else real_read(p,*args,**kwargs))
        monkeypatch.setattr(core.subprocess,'Popen',lambda *_args,**_kwargs:calls.append('spawn'))
        with pytest.raises(PinError):core.supervise_once(out,'fixture',[],[],'droidw',env=e,launch_context=ctx)
        assert not calls and not out.exists() and not ctx.claimed

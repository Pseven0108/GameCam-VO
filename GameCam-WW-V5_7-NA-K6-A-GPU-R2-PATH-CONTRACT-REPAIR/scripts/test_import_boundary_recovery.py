"""Targeted recovery checks; all model permissions are mock-only and CUDA hidden."""
import hashlib,importlib,json,os,pathlib,subprocess,sys,time,types
import pytest
from diagnostic_import_policy import IMPORT_POLICY,sanitized_worker_environment,VerifiedSourceFinder
from diagnostic_early_failure import publish_pre_model_failure
from diagnostic_authorization import DiagnosticContext,DIAGNOSTIC_SCOPE
from linux_safety import atomic_json
from worker_terminal import read_terminal
from model_io_boundary_v2 import ModelIOBoundary

def test_inherited_cache_prefix_removed():
 env=sanitized_worker_environment({'PYTHONPYCACHEPREFIX':'/POISON','X':'1'},{'PYTHONDONTWRITEBYTECODE':'1'})
 assert 'PYTHONPYCACHEPREFIX' not in env and env['X']=='1'
@pytest.mark.parametrize('pinned',[{'PYTHONPYCACHEPREFIX':'/session/pycache','PYTHONDONTWRITEBYTECODE':'1'},{}, {'PYTHONDONTWRITEBYTECODE':'0'}])
def test_invalid_cache_policy_rejected(pinned):
 with pytest.raises(RuntimeError):sanitized_worker_environment({},pinned)

def test_verified_source_ignores_poisoned_pyc_and_rejects_source_change(tmp_path):
 source=tmp_path/'cpu_sealed_module.py';source.write_text('VALUE=42\n');cache=tmp_path/'__pycache__';cache.mkdir();(cache/'cpu_sealed_module.cpython-310.pyc').write_bytes(b'UNTRUSTED')
 finder=VerifiedSourceFinder(tmp_path,[{'path':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]);spec=finder.find_spec('cpu_sealed_module',[str(tmp_path)]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);assert module.VALUE==42 and sum(e['event']=='source_bytes_verified' for e in finder.events)==1
 source.write_text('VALUE=999\n')
 with pytest.raises(RuntimeError,match='IMPORT_SOURCE_SHA_DRIFT'):spec.loader.exec_module(module)

def test_sealed_source_symlink_rejected(tmp_path):
 source=tmp_path/'real.py';source.write_text('VALUE=42\n');(tmp_path/'alias.py').symlink_to(source)
 finder=VerifiedSourceFinder(tmp_path,[{'path':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}])
 with pytest.raises(RuntimeError,match='IMPORT_SOURCE_SYMLINK'):finder.find_spec('alias',[str(tmp_path)])

@pytest.mark.parametrize('message',['CPU_EARLY_IMPORT_FAILURE','MODEL_SESSION_READ_OUTSIDE_ALLOWLIST:/blocked'])
def test_failure_terminal_preserves_first_cause_and_scope(tmp_path,message):
 out=tmp_path/'model';out.mkdir();r={}
 try:raise ImportError(message)
 except ImportError as e:publish_pre_model_failure(r,out,tmp_path,'CPU_FAILURE_BINDING',e,'TORCH_IMPORT')
 t=read_terminal(tmp_path,'CPU_FAILURE_BINDING',os.getpid(),'droidw_diagnostic');ctx=DiagnosticContext(tmp_path/'mock-candidate','0'*64,None);ctx._candidate={'diagnostic_scope':DIAGNOSTIC_SCOPE}
 assert ctx.validate_terminal(tmp_path,t) is False and t['primary_failure']==message
 assert 'ImportError: '+message in r['traceback'] and r['frames_submitted']==0 and r['diagnostic_loaded_weights']==[]
 r['frames_submitted']=1;atomic_json(out/'result.json',r)
 with pytest.raises(Exception):ctx.validate_terminal(tmp_path,t)

@pytest.mark.parametrize('case',['allowed_remove','allowed_rmdir','outside_fd','parent_escape','symlink_escape','hardlink_deny','session_read_deny','session_write_deny','cache_write_deny'])
def test_import_scratch_boundary_actual_operations(tmp_path,case):
 script=r'''
import json,os,pathlib,sys
from model_io_boundary_v2 import ModelIOBoundary
root=pathlib.Path(sys.argv[1]);case=sys.argv[2];root.mkdir();out=root/'model';out.mkdir();scratch=out/'import_tmp';scratch.mkdir();outside=root/'outside';outside.mkdir();(outside/'secret').write_text('preserved');target=scratch/'file';target.write_text('scratch');(scratch/'sub').mkdir();(scratch/'escape').symlink_to(outside,target_is_directory=True);(root/'secret').write_text('session');cache=root/'env';cache.mkdir()
fd=os.open(scratch if case!='outside_fd' else outside,os.O_RDONLY);b=ModelIOBoundary([],[],[],[out],[cache],worker_root=root,import_scratch_root=scratch);b.install();denied=False
try:
 if case=='allowed_remove':os.unlink('file',dir_fd=fd)
 elif case=='allowed_rmdir':os.rmdir('sub',dir_fd=fd)
 elif case=='outside_fd':os.unlink('secret',dir_fd=fd)
 elif case=='parent_escape':os.unlink('../secret',dir_fd=fd)
 elif case=='symlink_escape':(scratch/'escape/secret').unlink()
 elif case=='hardlink_deny':os.link(target,scratch/'hardlink')
 elif case=='session_read_deny':(root/'secret').read_text()
 elif case=='session_write_deny':(root/'supervisor_stop.json').write_text('bad')
 elif case=='cache_write_deny':(cache/'fake.pyc').write_bytes(b'bad')
except (RuntimeError,PermissionError):denied=True
os.close(fd)
print(json.dumps({'denied':denied,'target_exists':target.exists(),'sub_exists':(scratch/'sub').exists(),'outside_preserved':(outside/'secret').exists(),'hardlink_exists':(scratch/'hardlink').exists()}))
'''
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1');env.pop('PYTHONPYCACHEPREFIX',None);r=subprocess.run([sys.executable,'-B','-c',script,str(tmp_path/'case'),case],env=env,capture_output=True,text=True,check=True);x=json.loads(r.stdout)
 assert x['denied']==(case not in ['allowed_remove','allowed_rmdir']) and x['outside_preserved'] and not x['hardlink_exists']

@pytest.mark.parametrize('mode',['plain','original_boundary'])
def test_real_supervisor_receives_pre_cuda_failure(tmp_path,mode):
 from runner_core import supervise_once
 from ipc_runtime import expected_root
 class MockContext:
  claimed=False
  def __init__(self,session):self._candidate={'planned_ipc_root':str(expected_root(session)),'diagnostic_scope':DIAGNOSTIC_SCOPE}
  def validate(self,*args,consume=False,**kw):
   if consume:self.claimed=True
  def validate_terminal(self,out,terminal):return DiagnosticContext.validate_terminal(self,out,terminal)
 session='CPU_RECOVERY_TERMINAL_'+str(os.getpid())+'_'+mode;out=tmp_path/'session';env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1');env.pop('PYTHONPYCACHEPREFIX',None)
 monitor=[sys.executable,'-B',str(pathlib.Path(__file__).with_name('diagnostic_fake_worker.py')),'--role','monitor','--out',str(out),'--session',session]
 worker=[sys.executable,'-B',str(pathlib.Path(__file__).with_name('import_failure_cpu_fixture.py')),'--out',str(out),'--session',session,'--mode',mode]
 r=supervise_once(out,session,worker,monitor,'droidw_diagnostic',env=env,expected_frames=0,launch_context=MockContext(session))
 expected='MODEL_SESSION_READ_OUTSIDE_ALLOWLIST:' if mode=='original_boundary' else 'CPU_INJECTED_EARLY_IMPORT_FAILURE'
 assert not r['passed'] and r['primary_failure'].startswith(expected) and r['reason'].startswith(expected) and r['terminal_result'] is not None
 assert r['supervisor_cleanup_reason']=='TERMINAL_FAILURE_EXIT' and r['worker_fully_exited'] and r['monitor_fully_exited'] and r['ipc_cleanup']['passed']
 assert r['automatic_retries']==0 and r['completed_frame_samples']==0 and not r['startup_barrier_passed']


def test_traceback_formatting_failure_cannot_replace_primary(tmp_path,monkeypatch):
 import diagnostic_early_failure as early
 monkeypatch.setattr(early.traceback,'format_exc',lambda:(_ for _ in ()).throw(RuntimeError('SECONDARY_TRACEBACK_READ_DENIED')))
 out=tmp_path/'model';out.mkdir();r={}
 try:raise ImportError('ORIGINAL_CAUSAL_ERROR')
 except ImportError as e:early.publish_pre_model_failure(r,out,tmp_path,'CPU_TRACEBACK_FALLBACK',e,'TORCH_IMPORT')
 t=read_terminal(tmp_path,'CPU_TRACEBACK_FALLBACK',os.getpid(),'droidw_diagnostic')
 assert t['primary_failure']=='ORIGINAL_CAUSAL_ERROR' and 'SECONDARY_TRACEBACK_READ_DENIED' in r['traceback']


def test_phase_telemetry_failure_cannot_mask_causal_import_error(tmp_path,monkeypatch):
 from diagnostic_phases import PhaseRecorder
 recorder=PhaseRecorder(tmp_path,tmp_path,'CPU_PHASE_PRIMARY')
 def emit(*args,**kwargs):
  if len(args)>1 and args[1]=='error':raise RuntimeError('SECONDARY_MONITOR_STALE')
 monkeypatch.setattr(recorder,'emit',emit)
 with pytest.raises(ImportError,match='ORIGINAL_IMPORT_FAILURE'):
  with recorder.span('TORCH_IMPORT'):raise ImportError('ORIGINAL_IMPORT_FAILURE')
 assert recorder.error_reporting_failures[0]['primary_failure']=='ORIGINAL_IMPORT_FAILURE'

def test_early_failure_does_not_overwrite_existing_result(tmp_path):
 out=tmp_path/'model';out.mkdir();(out/'result.json').write_text('PRESERVE_ORIGINAL')
 try:raise ImportError('CPU_IMPORT_FAILURE')
 except ImportError as exc:
  with pytest.raises(RuntimeError,match='EARLY_FAILURE_RESULT_ALREADY_EXISTS'):publish_pre_model_failure({},out,tmp_path,'CPU_NO_OVERWRITE',exc,'TORCH_IMPORT')
 assert (out/'result.json').read_text()=='PRESERVE_ORIGINAL'

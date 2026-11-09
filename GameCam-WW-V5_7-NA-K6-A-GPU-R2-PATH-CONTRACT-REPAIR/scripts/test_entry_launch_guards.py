"""Synthetic in-memory authorization only, real supervisor pre-spawn rejects."""
import copy,hashlib,json,os,pathlib,sys,time
import pytest
import launch_authorization as la
import runner_core as core
from runtime_dependency_pins import PinError,RuntimePins
from test_v2_cpu import auth_fixture

@pytest.mark.parametrize('fault',['missing','candidate_sha','gpu_uuid','live_gpu','weight_sha','input_sha','session','nonce_reused','expired','limit_zero','consumed','input_contract_static'])
def test_entry_rejection_before_any_process(tmp_path,monkeypatch,fault):
 c,a,e=auth_fixture();c=copy.deepcopy(c);a=copy.deepcopy(a);out=tmp_path/'must-not-exist';sid='CPU_ENTRY_GATE_FIXTURE';sha='a'*64
 c.update(schema='gamecam-droidw-entry-candidate-v1',entry_admission_status='DROIDW_ENTRY_READY_WAITING_FOR_USER_AUTHORIZATION',expected_gpu_uuid=core.EXPECTED_UUID,planned_session_id=sid,planned_session_directory=str(out),planned_authorization_ledger=str(out/'authorization.claim.json'),nonce_registry_root=str(tmp_path/'nonce-records'),worker_command_prefix=['fake_worker'],monitor_command_prefix=['fake_monitor'])
 a.update(gpu_uuid=core.EXPECTED_UUID,session=sid)
 if fault=='candidate_sha':a['candidate_sha256']='0'*64
 if fault=='gpu_uuid':a['gpu_uuid']='GPU-UNAUTHORIZED-SYNTHETIC'
 if fault=='expired':a['expires_unix']=time.time()-1
 if fault=='limit_zero':a['attempt_limit']=0
 if fault=='consumed':a['consumed']=True
 session='WRONG_ENTRY_SESSION' if fault=='session' else sid
 ctx=la.LaunchContext(tmp_path/'candidate-manifest',sha,None if fault=='missing' else tmp_path/'IN_MEMORY_ONLY_NOT_A_CREDENTIAL')
 def candidate_validation():
  if fault in ('weight_sha','input_sha'):
   p=tmp_path/('synthetic.pth' if fault=='weight_sha' else 'synthetic.png');p.write_bytes(b'actual bytes')
   row={'id':'CPU_ONLY_FIXTURE','path_linux':str(p),'real_linux':str(p),'allowed_root_linux':str(tmp_path),'allowed_root_real_linux':str(tmp_path),'bytes':len(b'actual bytes'),'sha256':hashlib.sha256(b'different expected bytes').hexdigest()}
   pins=object.__new__(RuntimePins);pins.events=[];pins.event_sink=None
   pins.checked_file(row)
  if fault=='live_gpu':raise PinError('LIVE_GPU_UUID_MISMATCH','BLOCKED_BY_AUTHORIZATION_GUARD')
  if fault=='input_contract_static':raise PinError('INPUT_SHA_CHANGED','BLOCKED_BY_CONFIG_PIN')
  return c
 monkeypatch.setattr(ctx,'validate_candidate',candidate_validation)
 original_read=pathlib.Path.read_text;monkeypatch.setattr(pathlib.Path,'read_text',lambda p,*args,**kw:json.dumps(a) if p==ctx.authorization_path else original_read(p,*args,**kw))
 if fault=='nonce_reused':
  target=pathlib.Path(c['nonce_registry_root'])/(hashlib.sha256(a['nonce'].encode()).hexdigest()+'.json');original_exists=pathlib.Path.exists;monkeypatch.setattr(pathlib.Path,'exists',lambda p:True if p==target else original_exists(p))
 commands=['fake_worker','--candidate',str(ctx.candidate_path),'--candidate-sha',sha,'--authorization',str(ctx.authorization_path),'--session-dir',str(out),'--session',session]
 monitors=['fake_monitor','--monitor',str(out),'--session',session];spawns=[]
 monkeypatch.setattr(core.subprocess,'Popen',lambda *args,**kw:spawns.append(args))
 with pytest.raises(PinError):core.supervise_once(out,session,commands,monitors,'droidw',env=e,launch_context=ctx)
 assert not spawns and not out.exists() and not ctx.claimed

def test_entry_identity_rejects_static_mismatch(monkeypatch):
 c={'schema':'gamecam-droidw-entry-candidate-v1','source_root':'/synthetic','runtime_phase_relative':'phase'}
 class Pins:
  def __init__(self,*a):pass
  def static_check(self):raise PinError('SYNTHETIC_WEIGHT_SHA_MISMATCH')
 monkeypatch.setattr('runtime_dependency_pins.RuntimePins',Pins)
 with pytest.raises(PinError,match='WEIGHT_SHA'):la.validate_entry_identity(c)

def test_worker_root_cannot_be_output(tmp_path):
 from model_io_boundary_v2 import ModelIOBoundary
 with pytest.raises(RuntimeError,match='SESSION_ROOT_AS_OUTPUT'):
  ModelIOBoundary([],[],[],[tmp_path],worker_root=tmp_path,worker_files=[tmp_path/'cuda_samples.jsonl'])


def test_entry_identity_rejects_actual_nvml_identity_adapter(monkeypatch):
 c={'schema':'gamecam-droidw-entry-candidate-v1','source_root':'/synthetic','runtime_phase_relative':'phase','expected_gpu_uuid':core.EXPECTED_UUID}
 class Pins:
  def __init__(self,*a):pass
  def static_check(self):return {'input_frames_verified':True,'weights':[{}, {}, {}, {}]}
 class WrongGPU:
  def sample(self):return {'gpu_uuid':'GPU-SYNTHETIC-WRONG-UUID'}
  def close(self):pass
 monkeypatch.setattr('runtime_dependency_pins.RuntimePins',Pins);monkeypatch.setattr('linux_safety.Nvml',WrongGPU)
 with pytest.raises(PinError,match='LIVE_GPU_UUID_MISMATCH'):la.validate_entry_identity(c)


def test_partial_candidate_cannot_be_self_armed():
 c,a,e=auth_fixture();c.update(schema='gamecam-droidw-entry-candidate-v1',entry_admission_status='DROIDW_ENTRY_PARTIAL_PASS',expected_gpu_uuid=core.EXPECTED_UUID);a['gpu_uuid']=core.EXPECTED_UUID
 with pytest.raises(PinError,match='DROIDW_ENTRY_NOT_ADMITTED'):la.validate_authorization(c,'a'*64,a,e)

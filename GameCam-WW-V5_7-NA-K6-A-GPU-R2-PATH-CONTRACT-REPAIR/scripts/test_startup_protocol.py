"""Targeted phase/deadline regressions; no CUDA or checkpoint execution."""
import math,pytest
from startup_protocol import StartupGate,PROTOCOL,validate_permit
from linux_safety import SafetyStop

def record(phase='WORKER_IMPORTING',ts=101.,seq=1,cs=None):
 return dict(schema=PROTOCOL,kind='worker_startup',session='UNIT',worker_pid=123,sample_seq=seq,monotonic_time=ts,unix_time=0.,phase=phase,cuda_started_monotonic=cs,ok=True)
@pytest.mark.parametrize('seconds',[1,5,10,13,13.5,13.977,14,14.5,14.9])
def test_import_then_distinct_cuda_deadline(seconds):
 g=StartupGate(100,123,'UNIT');t=100+seconds
 g.observe(record('CUDA_INITIALIZING',t,1,t),t);g.check_deadline(t+2.99)
 with pytest.raises(SafetyStop,match='STALE'):g.check_deadline(t+3.01)
 g.observe(record('CUDA_CONTEXT_READY',t+14.99,2,t),t+14.99)
 with pytest.raises(SafetyStop,match='CUDA_STARTUP_BARRIER_TIMEOUT'):g.check_deadline(t+15.001)
@pytest.mark.parametrize('cs',[115.0001,116,200])
def test_heartbeats_cannot_extend_preparation(cs):
 g=StartupGate(100,123,'UNIT')
 with pytest.raises(SafetyStop,match='WORKER_PREPARATION_TIMEOUT'):g.observe(record('CUDA_INITIALIZING',cs,1,cs),cs)
def test_prepare_timeout_without_any_status():
 g=StartupGate(100,123,'UNIT')
 with pytest.raises(SafetyStop,match='WORKER_PREPARATION_TIMEOUT'):g.check_deadline(115.01)
def test_healthy_import_heartbeat_cannot_extend_deadline():
 g=StartupGate(100,123,'UNIT');g.observe(record(ts=115.1),115.1)
 with pytest.raises(SafetyStop,match='WORKER_PREPARATION_TIMEOUT'):g.check_deadline(115.1)
@pytest.mark.parametrize('field,value',[('session','WRONG'),('worker_pid',999),('kind','cuda'),('schema','wrong'),('ok',False),('sample_seq',0),('monotonic_time',float('nan')),('monotonic_time',float('inf')),('phase','MODEL_LOADING')])
def test_invalid_status_rejected(field,value):
 g=StartupGate(100,123,'UNIT');r=record();r[field]=value
 with pytest.raises(SafetyStop):g.observe(r,101)
def test_cuda_epoch_immutable():
 g=StartupGate(100,123,'UNIT');g.observe(record('CUDA_INITIALIZING',101,1,101),101)
 with pytest.raises(SafetyStop,match='CHANGED'):g.observe(record('CUDA_CONTEXT_READY',102,2,102),102)
def test_no_rollback():
 g=StartupGate(100,123,'UNIT');g.observe(record('CUDA_CONTEXT_READY',102,2,101),102)
 with pytest.raises(SafetyStop):g.observe(record('CUDA_INITIALIZING',103,3,101),103)
def test_cuda_sample_is_not_early_progress():
 g=StartupGate(100,123,'UNIT');g.observe(record(),101)
 with pytest.raises(SafetyStop,match='BEFORE_CONTEXT'):g.check_cuda({'monotonic_time':101})
 g.observe(record('CUDA_CONTEXT_READY',102,2,101.5),102)
 with pytest.raises(SafetyStop,match='PREDATES'):g.check_cuda({'monotonic_time':101})
 g.check_cuda({'monotonic_time':102})
@pytest.mark.parametrize('kind',['droidw','droidw_diagnostic','cpu_dummy'])
def test_permit_classes_cannot_be_swapped(kind):
 p=dict(session='UNIT',execution_kind=kind,model_execution_authorized=kind!='cpu_dummy',diagnostic_only=kind=='droidw_diagnostic',cpu_dummy_only=kind=='cpu_dummy');validate_permit(p,'UNIT',kind)
 p['model_execution_authorized']=not p['model_execution_authorized']
 with pytest.raises(SafetyStop):validate_permit(p,'UNIT',kind)

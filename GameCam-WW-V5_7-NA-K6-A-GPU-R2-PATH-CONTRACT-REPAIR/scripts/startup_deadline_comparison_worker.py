"""CPU-only startup protocol stress fixture; all telemetry is explicitly mock."""
import argparse,os,pathlib,sys,time,threading,json
from linux_safety import atomic_json,append_json,EXPECTED_UUID
from startup_protocol import StartupReporter
from worker_terminal import publish_terminal
p=argparse.ArgumentParser();p.add_argument('--role',required=True);p.add_argument('--out',required=True);p.add_argument('--session',required=True);p.add_argument('--delay',type=float,default=1);p.add_argument('--fault',default='none');p.add_argument('--cuda-delay',type=float,default=0);a=p.parse_args();out=pathlib.Path(a.out)
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and 'torch' not in sys.modules
if a.role=='monitor':
 if a.fault=='monitor_exit':raise SystemExit(17)
 seq=0
 while not (out/'monitor.stop').exists():
  if a.fault=='nvml_never':time.sleep(.1);continue
  seq+=1;x=dict(kind='nvml',session=a.session,sample_seq=seq,monotonic_time=time.monotonic(),unix_time=time.time(),ok=a.fault!='nvml_error',error='MOCK_NVML_INITIALIZATION_FAILURE' if a.fault=='nvml_error' else None,gpu_uuid=EXPECTED_UUID,nvml_free_MiB=4096.,nvml_used_MiB=1024.,CPU_MemAvailable_MiB=8192.,CPU_MemTotal_MiB=16384.,cgroup_memory_current_bytes=1024,cgroup_remaining_MiB=8192.,data_disk_free_fraction=.8,temperature_C=40.,utilization_percent=0.,memory_utilization_percent=0.,gpu_processes=[],fixture_only=True)
  append_json(out/'nvml_samples.jsonl',x);atomic_json(out/'nvml.latest.json',x)
  if a.fault=='nvml_stale' and seq>=2:
   while not (out/'monitor.stop').exists():time.sleep(.1)
   break
  time.sleep(.25)
 raise SystemExit(0)
reporter=StartupReporter(out,a.session).start()
def terminal(error=None):
 atomic_json(out/'fake_result.json',dict(status='RUN_COMPLETED' if error is None else 'MOCK_FAILURE',error=error,frames_submitted=0,frames_completed=0));publish_terminal(out,a.session,out/'fake_result.json','cpu_dummy')
if a.fault=='early_exception':terminal('MOCK_EARLY_IMPORT_EXCEPTION');reporter.finish();raise SystemExit(2)
if a.fault=='startup_stale':reporter.finish();time.sleep(30)
if a.fault=='silent_hang':reporter.finish();(out/'worker_startup.latest.json').unlink();time.sleep(30)
time.sleep(a.delay);reporter.set_phase('CUDA_INITIALIZING')
if a.fault=='cuda_init_error':terminal('MOCK_CUDA_INITIALIZATION_FAILURE');reporter.finish();raise SystemExit(2)
if a.fault=='cuda_never':time.sleep(30)
time.sleep(a.cuda_delay);reporter.set_phase('CUDA_CONTEXT_READY');seq=0
while not (out/'work.permit.json').exists():
 seq+=1;x=dict(kind='cuda',session=a.session,sample_seq=seq,monotonic_time=time.monotonic(),unix_time=time.time(),ok=True,gpu_uuid=EXPECTED_UUID,cuda_free_MiB=511. if a.fault=='low_cuda' else 4096.,allocated_MiB=0.,reserved_MiB=0.,worker_pid=os.getpid(),fixture_only=True)
 atomic_json(out/'cuda.latest.json',x);append_json(out/'cuda_samples.jsonl',x);reporter.set_phase('CUDA_MONITOR_READY');time.sleep(.2)
reporter.set_phase('WORKER_READY');reporter.finish()
if a.fault=='cuda_stale':time.sleep(30)
terminal()
if a.fault=='terminal_hang':time.sleep(30)
raise SystemExit(0)

"""Independent CPU diagnostic protocol fixture. No real credential or model."""
import argparse,json,os,pathlib,signal,sys,time
from linux_safety import atomic_json,append_json,EXPECTED_UUID
from worker_terminal import publish_terminal
p=argparse.ArgumentParser();p.add_argument('--role',required=True);p.add_argument('--out',required=True);p.add_argument('--session',required=True);p.add_argument('--fault',default='normal');a=p.parse_args();out=pathlib.Path(a.out)
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and 'torch' not in sys.modules
seq=0;released=None
if a.role=='monitor':
    while not (out/'monitor.stop').exists():
        if (out/'work.permit.json').exists() and released is None:released=time.monotonic()
        if a.fault=='nvml_stale' and released is not None:time.sleep(.1);continue
        seq+=1;x={'kind':'nvml','session':a.session,'sample_seq':seq,'monotonic_time':time.monotonic(),'unix_time':time.time(),'ok':True,'gpu_uuid':EXPECTED_UUID,'nvml_free_MiB':4096.,'nvml_used_MiB':1024.,'CPU_MemAvailable_MiB':8192.,'CPU_MemTotal_MiB':16384.,'cgroup_memory_current_bytes':1024,'cgroup_remaining_MiB':8192.,'data_disk_free_fraction':.8,'temperature_C':40.,'utilization_percent':0.,'memory_utilization_percent':0.,'gpu_processes':[],'fixture_only':True}
        append_json(out/'nvml_samples.jsonl',x);atomic_json(out/'nvml.latest.json',x);time.sleep(.25)
    raise SystemExit(0)
# Never create GPU context or import a real model in this fixture.
while released is None:
    seq+=1;x=dict(kind='cuda',session=a.session,sample_seq=seq,monotonic_time=time.monotonic(),unix_time=time.time(),ok=True,gpu_uuid=EXPECTED_UUID,cuda_free_MiB=4096.,allocated_MiB=64.,reserved_MiB=128.,worker_pid=os.getpid(),fixture_only=True)
    atomic_json(out/'cuda.latest.json',x);append_json(out/'cuda_samples.jsonl',x)
    if (out/'work.permit.json').exists():
        permit=json.loads((out/'work.permit.json').read_text());assert permit['diagnostic_only'] and permit['execution_kind']=='droidw_diagnostic';released=time.monotonic()
    time.sleep(.15)
if a.fault=='cuda_stale' or a.fault=='nvml_stale':
    while True:
        if a.fault=='nvml_stale':
            seq+=1;x.update(sample_seq=seq,monotonic_time=time.monotonic(),unix_time=time.time());atomic_json(out/'cuda.latest.json',x)
        time.sleep(.15)
if a.fault=='low_memory':
    x.update(sample_seq=seq+1,monotonic_time=time.monotonic(),cuda_free_MiB=511.);atomic_json(out/'cuda.latest.json',x);time.sleep(10)
if a.fault=='crash':os._exit(23)
(out/'model').mkdir(mode=0o700)
r=dict(status='DIAGNOSTIC_STOP_COMPLETED',error=None,diagnostic_stop_phase='TRACKER_CONSTRUCTION_DONE',frames_submitted=0,frames_completed=0,tracker_run_called=False,BA_executed=False,diagnostic_loaded_weights=['MOCK_A','MOCK_B','MOCK_C','MOCK_D'])
if a.fault=='scope_escape':r['frames_submitted']=1
atomic_json(out/'model/result.json',r);publish_terminal(out,a.session,out/'model/result.json','droidw_diagnostic')
if a.fault=='terminal_hang':
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    while True:time.sleep(.2)
if a.fault=='terminal_delay':time.sleep(4.)
raise SystemExit(0)

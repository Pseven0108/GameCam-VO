"""CPU-only independent telemetry producer / worker used by the production supervisor."""
import argparse,json,os,pathlib,signal,sys,time
from linux_safety import atomic_json,append_json,EXPECTED_UUID
p=argparse.ArgumentParser();p.add_argument('--role',choices=['nvml','worker'],required=True);p.add_argument('--out',required=True);p.add_argument('--session',required=True);p.add_argument('--fault',required=True);a=p.parse_args();out=pathlib.Path(a.out);session=a.session;fault=a.fault
assert 'torch' not in sys.modules
if fault=='ignore_SIGTERM' and a.role=='worker':signal.signal(signal.SIGTERM,signal.SIG_IGN)
def sample(kind,seq):
    common={'kind':kind,'session':session,'sample_seq':seq,'monotonic_time':time.monotonic(),'unix_time':time.time(),'ok':True,'gpu_uuid':EXPECTED_UUID,'fixture_only':True}
    if kind=='nvml':common.update(nvml_free_MiB=4096.,CPU_MemAvailable_MiB=8192.,CPU_MemTotal_MiB=16384.,cgroup_memory_current_bytes=1024**3,cgroup_memory_max_bytes=8*1024**3,cgroup_remaining_MiB=7168.,data_disk_free_fraction=.8,temperature_C=40.,utilization_percent=0.,memory_utilization_percent=0.,gpu_processes=[])
    else:common.update(cuda_free_MiB=4096.,allocated_MiB=100.,reserved_MiB=128.,worker_pid=os.getpid())
    return common
if a.role=='nvml':
    seq=0;released=None
    while not (out/'monitor.stop').exists():
        seq+=1
        if (out/'work.permit.json').exists() and released is None:released=time.monotonic()
        active=released is not None and time.monotonic()-released>.35
        if active and fault=='monitor_exit':print('CPU mock monitor exits 17',flush=True);raise SystemExit(17)
        if fault=='startup_barrier_stall' and seq>1:time.sleep(.1);continue
        if active and fault=='nvml_stale':time.sleep(.1);continue
        x=sample('nvml',seq)
        if active and fault=='nvml_low':x['nvml_free_MiB']=511.999
        if active and fault=='uuid_drift':x['gpu_uuid']='GPU-mock-unexpected-device'
        if active and fault=='nvml_error':x.update(ok=False,error='MOCK_NVML_QUERY_FAILED')
        append_json(out/'nvml_samples.jsonl',x);atomic_json(out/'nvml.latest.json',x);time.sleep(.25)
    print(json.dumps({'cpu_mock_monitor_exit':0,'torch_imported':False}));raise SystemExit(0)
seq=0;released=None;last=time.monotonic();frames_written=False
while True:
    seq+=1
    if (out/'work.permit.json').exists() and released is None:
        permit=json.loads((out/'work.permit.json').read_text());assert permit['cpu_dummy_only'] and not permit['model_execution_authorized'];released=time.monotonic()
    active=released is not None and time.monotonic()-released>.35
    if active and fault=='worker_exit':print('CPU dummy exits 23',flush=True);raise SystemExit(23)
    if not (active and fault=='cuda_stale'):
        x=sample('cuda',seq)
        if active and fault in {'cuda_low','ignore_SIGTERM'}:x['cuda_free_MiB']=511.999
        if active and fault=='cuda_error':x.update(ok=False,error='MOCK_CUDA_QUERY_FAILED')
        append_json(out/'cuda_samples.jsonl',x);atomic_json(out/'cuda.latest.json',x)
    if active and not frames_written:
        count=30 if fault=='growth_30' else 3
        for i in range(count):
            x=sample('cuda',i+1);x.update(frame_ordinal=i,allocated_MiB=100.+20*i if fault=='growth_30' else 100.)
            append_json(out/'frame_samples.jsonl',x)
        frames_written=True
    if fault=='normal' and released is not None and time.monotonic()-released>1.0:
        print(json.dumps({'CPU_dummy_exit':0,'synthetic_frame_samples':3,'model_attempts':0,'torch_imported':False}));raise SystemExit(0)
    time.sleep(.2)
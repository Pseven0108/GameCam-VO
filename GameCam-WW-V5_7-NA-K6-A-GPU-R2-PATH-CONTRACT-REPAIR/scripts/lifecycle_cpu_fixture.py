"""CPU-only independent worker/monitor, exercising the real supervisor protocol."""
import argparse,json,os,pathlib,signal,subprocess,sys,time
from linux_safety import atomic_json,append_json,EXPECTED_UUID
from worker_terminal import publish_terminal
p=argparse.ArgumentParser();p.add_argument('--role',required=True);p.add_argument('--out',required=True);p.add_argument('--session',required=True);p.add_argument('--fault',default='normal');p.add_argument('--expected-parent',type=int);a=p.parse_args();out=pathlib.Path(a.out);fault=a.fault
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and 'torch' not in sys.modules
if a.role=='parent_escape':
    command=[sys.executable,'-B',__file__,'--role','parent_probe','--out',str(out),'--session',a.session,'--expected-parent',str(os.getpid())]
    child=subprocess.Popen(command,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    atomic_json(out/'orphan_child.json',{'pid':child.pid,'expected_parent':os.getpid()});time.sleep(.2);os._exit(0)
if a.role=='parent_probe':
    os.environ['GAMECAM_SUPERVISOR_PID']=str(a.expected_parent)
    while os.getppid()==a.expected_parent:time.sleep(.02)
    from native_linux_guard_v2 import ModelHeartbeat
    try:ModelHeartbeat(None,out,a.session).sample()
    except Exception as e:atomic_json(out/'parent_loss_result.json',{'error':str(e),'torch_imported':'torch' in sys.modules,'pid':os.getpid()})
    raise SystemExit(0)
def sample(kind,seq):
    row={'kind':kind,'session':a.session,'sample_seq':seq,'monotonic_time':time.monotonic(),'unix_time':time.time(),'ok':True,'gpu_uuid':EXPECTED_UUID,'fixture_only':True}
    if kind=='nvml':row.update(nvml_free_MiB=4096.,nvml_used_MiB=1024.,CPU_MemAvailable_MiB=8192.,CPU_MemTotal_MiB=16384.,cgroup_memory_current_bytes=1024**3,cgroup_memory_max_bytes=8*1024**3,cgroup_remaining_MiB=7168.,data_disk_free_fraction=.8,temperature_C=40.,utilization_percent=0.,memory_utilization_percent=0.,gpu_processes=[])
    else:row.update(cuda_free_MiB=4096.,allocated_MiB=100.,reserved_MiB=128.,worker_pid=os.getpid())
    return row
if a.role=='nvml':
    seq=0;released=None
    while not (out/'monitor.stop').exists():
        if (out/'work.permit.json').exists() and released is None:released=time.monotonic()
        active=released is not None and time.monotonic()-released>.6
        term=(out/'worker_terminal.json').exists()
        if active and fault=='monitor_exit':raise SystemExit(17)
        if (active and fault=='nvml_stale') or (term and fault=='nvml_stale_terminal'):time.sleep(.1);continue
        seq+=1;x=sample('nvml',seq);append_json(out/'nvml_samples.jsonl',x);atomic_json(out/'nvml.latest.json',x);time.sleep(.25)
    raise SystemExit(0)
seq=0;released=None;terminal=False;terminal_time=None
if fault=='terminal_hang_sigkill':signal.signal(signal.SIGTERM,signal.SIG_IGN)
while True:
    if (out/'work.permit.json').exists() and released is None:
        permit=json.loads((out/'work.permit.json').read_text());assert permit['cpu_dummy_only'] and not permit['model_execution_authorized'];released=time.monotonic()
    active=released is not None and time.monotonic()-released>.4
    if not terminal and not(active and fault=='running_stale'):
        seq+=1;x=sample('cuda',seq);append_json(out/'cuda_samples.jsonl',x);atomic_json(out/'cuda.latest.json',x)
    if active and fault=='crash':os._exit(23)
    if active and fault=='sigterm':os.kill(os.getpid(),signal.SIGTERM)
    if active and fault=='sigkill':os.kill(os.getpid(),signal.SIGKILL)
    if active and not terminal and fault not in ['running_stale','monitor_exit','nvml_stale','supervisor_exception']:
        error=None if fault in ['normal','terminal_delay','ipc_residual','terminal_wrong_session','terminal_tamper'] else 'SYNTHETIC_PRIMARY_ERROR'
        result={'status':'RUN_COMPLETED' if error is None else 'SYNTHETIC_TERMINAL_ERROR','error':error,'frames_submitted':0,'frames_completed':0,'model_attempts':0,'torch_imported':False}
        atomic_json(out/'fake_result.json',result);t=publish_terminal(out,a.session,out/'fake_result.json','cpu_dummy');terminal=True;terminal_time=time.monotonic()
        if fault=='terminal_wrong_session':t['session']='WRONG_CPU_SESSION';atomic_json(out/'worker_terminal.json',t)
        if fault=='terminal_tamper':result['tampered']=True;atomic_json(out/'fake_result.json',result)
        if fault in ['ipc_residual','ipc_cleanup_failure']:
            from ipc_runtime import expected_root
            root=expected_root(a.session)
            if fault=='ipc_residual':
                fd=os.open(root/('pym-'+str(os.getpid())+'-abcd1234'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
            else:(root/'foreign_fixture.txt').write_text('INTENTIONALLY_UNRECOGNIZED_TEST_RESIDUAL')
        if fault in ['normal','terminal_error','ipc_residual','ipc_cleanup_failure']:raise SystemExit(0 if error is None else 2)
    if terminal and fault in ['terminal_delay','nvml_stale_terminal'] and time.monotonic()-terminal_time>4.0:raise SystemExit(0 if fault=='terminal_delay' else 2)
    time.sleep(.15)

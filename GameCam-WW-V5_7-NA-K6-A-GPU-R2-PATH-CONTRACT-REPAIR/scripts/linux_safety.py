"""Linux telemetry and fail-closed supervisor for synthetic preflight only."""
import argparse, ctypes, datetime, json, math, os, pathlib, shutil, signal, subprocess, sys, threading, time, traceback
MIB=1048576
FLOOR_MIB=512
MAX_AGE=3.0
FUTURE_TOLERANCE=1.0
NVML_PERIOD=.25
CUDA_PERIOD=.2
SUPERVISOR_PERIOD=.2
EXPECTED_UUID='GPU-f74ae3f4-b00f-dce5-e20b-40d5f90ddfcf'
class SafetyStop(RuntimeError):pass

def atomic_json(path,data):
    path=pathlib.Path(path);temp=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    temp.write_text(json.dumps(data,allow_nan=False)+'\n');os.replace(temp,path)
def append_json(path,data):
    with pathlib.Path(path).open('a') as f:f.write(json.dumps(data,allow_nan=False)+'\n')
def read_json(path):
    try:return json.loads(pathlib.Path(path).read_text())
    except (OSError,ValueError) as e:raise SafetyStop('MONITOR_DATA_UNREADABLE:'+str(e)) from e

def validate_sample(sample,kind,session,now=None):
    now=time.monotonic() if now is None else now
    if not isinstance(sample,dict):raise SafetyStop('MONITOR_INVALID_RECORD')
    if sample.get('session')!=session:raise SafetyStop('MONITOR_SESSION_MISMATCH')
    if sample.get('kind')!=kind:raise SafetyStop('MONITOR_KIND_MISMATCH')
    ts=sample.get('monotonic_time');seq=sample.get('sample_seq')
    if type(ts) not in (int,float) or not math.isfinite(ts):raise SafetyStop('MONITOR_INVALID_TIME')
    if now-ts>MAX_AGE:raise SafetyStop(kind.upper()+'_MONITOR_STALE_OVER_3_SECONDS')
    if ts-now>FUTURE_TOLERANCE:raise SafetyStop('MONITOR_FUTURE_TIMESTAMP')
    if type(seq) is not int or seq<1:raise SafetyStop('MONITOR_INVALID_SAMPLE_SEQ')
    if sample.get('ok') is not True:raise SafetyStop(kind.upper()+'_QUERY_FAILED:'+str(sample.get('error')))
    if kind=='nvml':
        if sample.get('gpu_uuid')!=EXPECTED_UUID:raise SafetyStop('GPU_UUID_DRIFT')
        free=sample.get('nvml_free_MiB')
        if type(free) not in (int,float) or not math.isfinite(free):raise SafetyStop('NVML_INVALID_FREE')
        if free<FLOOR_MIB:raise SafetyStop('NVML_FREE_BELOW_512_MiB')
        for key in ['CPU_MemAvailable_MiB','CPU_MemTotal_MiB','data_disk_free_fraction','temperature_C','utilization_percent','memory_utilization_percent']:
            if type(sample.get(key)) not in (int,float) or not math.isfinite(sample[key]):raise SafetyStop('NVML_INVALID_REQUIRED_METRIC:'+key)
        if not isinstance(sample.get('gpu_processes'),list):raise SafetyStop('GPU_PROCESS_MONITOR_UNAVAILABLE')
        if type(sample.get('cgroup_memory_current_bytes')) is not int or sample['cgroup_memory_current_bytes']<0:raise SafetyStop('CGROUP_MEMORY_MONITOR_UNAVAILABLE')
        if sample['CPU_MemAvailable_MiB']<768:raise SafetyStop('CPU_AVAILABLE_RAM_BELOW_768_MiB')
        remaining=sample.get('cgroup_remaining_MiB')
        if remaining is not None:
            if type(remaining) not in (int,float) or not math.isfinite(remaining):raise SafetyStop('CGROUP_INVALID_REMAINING')
            if remaining<768:raise SafetyStop('CGROUP_AVAILABLE_RAM_BELOW_768_MiB')
        if sample.get('data_disk_free_fraction',0)<.20:raise SafetyStop('DATA_DISK_FREE_BELOW_20_PERCENT')
    elif kind=='cuda':
        free=sample.get('cuda_free_MiB')
        if type(free) not in (int,float) or not math.isfinite(free):raise SafetyStop('CUDA_INVALID_FREE')
        if free<FLOOR_MIB:raise SafetyStop('CUDA_FREE_BELOW_512_MiB')
        if any(type(sample.get(k)) not in (int,float) or not math.isfinite(sample[k]) for k in ['allocated_MiB','reserved_MiB']):raise SafetyStop('CUDA_INVALID_ALLOCATOR_SAMPLE')
    return sample

class PairReader:
    def __init__(self,session):self.session=session;self.previous={}
    def check(self,nvml,cuda,now=None):
        now=time.monotonic() if now is None else now
        for kind,x in [('nvml',nvml),('cuda',cuda)]:
            validate_sample(x,kind,self.session,now)
            old=self.previous.get(kind)
            if old:
                if x['sample_seq']<old['sample_seq'] or x['monotonic_time']<old['monotonic_time']:raise SafetyStop('MONITOR_ROLLBACK')
                if x['sample_seq']==old['sample_seq'] and x['monotonic_time']!=old['monotonic_time']:raise SafetyStop('MONITOR_SAME_SEQ_CHANGED_TIME')
                if x['sample_seq']>old['sample_seq'] and x['monotonic_time']<=old['monotonic_time']:raise SafetyStop('MONITOR_NONINCREASING_TIME')
            self.previous[kind]=dict(x)
        return True

class MemoryInfo(ctypes.Structure):_fields_=[('total',ctypes.c_ulonglong),('free',ctypes.c_ulonglong),('used',ctypes.c_ulonglong)]
class Utilization(ctypes.Structure):_fields_=[('gpu',ctypes.c_uint),('memory',ctypes.c_uint)]
class Nvml:
    def __init__(self):
        self.lib=ctypes.CDLL('libnvidia-ml.so.1')
        if self.lib.nvmlInit_v2()!=0:raise SafetyStop('NVML_INIT_FAILED')
        self.handle=ctypes.c_void_p()
        self.lib.nvmlDeviceGetHandleByIndex_v2.argtypes=[ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p)]
        self.lib.nvmlDeviceGetMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(MemoryInfo)]
        self.lib.nvmlDeviceGetUUID.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint]
        self.lib.nvmlDeviceGetTemperature.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_uint)]
        self.lib.nvmlDeviceGetUtilizationRates.argtypes=[ctypes.c_void_p,ctypes.POINTER(Utilization)]
        self.require(self.lib.nvmlDeviceGetHandleByIndex_v2(0,ctypes.byref(self.handle)),'HANDLE')
    def require(self,code,name):
        if code:raise SafetyStop('NVML_'+name+'_FAILED:'+str(code))
    def sample(self):
        memory=MemoryInfo();self.require(self.lib.nvmlDeviceGetMemoryInfo(self.handle,ctypes.byref(memory)),'MEMORY')
        uid=ctypes.create_string_buffer(96);self.require(self.lib.nvmlDeviceGetUUID(self.handle,uid,len(uid)),'UUID')
        temp=ctypes.c_uint();self.require(self.lib.nvmlDeviceGetTemperature(self.handle,0,ctypes.byref(temp)),'TEMPERATURE')
        util=Utilization();self.require(self.lib.nvmlDeviceGetUtilizationRates(self.handle,ctypes.byref(util)),'UTILIZATION')
        return {'gpu_uuid':uid.value.decode(),'nvml_total_MiB':memory.total/MIB,'nvml_free_MiB':memory.free/MIB,'nvml_used_MiB':memory.used/MIB,'temperature_C':temp.value,'utilization_percent':util.gpu,'memory_utilization_percent':util.memory}
    def close(self):self.lib.nvmlShutdown()

def cgroup_info():
    root=pathlib.Path('/sys/fs/cgroup');p=root/'memory.current';limit=root/'memory.max'
    if not p.is_file() or not limit.is_file():raise SafetyStop('CGROUP_V2_MEMORY_METRICS_UNAVAILABLE')
    used=int(p.read_text());raw=limit.read_text().strip();max_bytes=None if raw=='max' else int(raw)
    events=(root/'memory.events').read_text() if (root/'memory.events').is_file() else None
    return {'cgroup_memory_current_bytes':used,'cgroup_memory_max_bytes':max_bytes,'cgroup_remaining_MiB':None if max_bytes is None else (max_bytes-used)/MIB,'cgroup_memory_events':events}

def external_sample(nvml,session,seq):
    start=time.monotonic();r=nvml.sample()
    ram={x.split(':')[0]:int(x.split()[1])*1024 for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith(('MemAvailable:','MemTotal:'))}
    q=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2)
    if q.returncode:raise SafetyStop('GPU_PROCESS_QUERY_FAILED:'+q.stderr)
    processes=[]
    for line in q.stdout.strip().splitlines():
        fields=[v.strip() for v in line.split(',')]
        if len(fields)!=3:raise SafetyStop('GPU_PROCESS_QUERY_INVALID')
        processes.append({'pid':int(fields[0]),'name':fields[1],'used_memory_MiB':fields[2]})
    disk=shutil.disk_usage('/root/rivermind-data')
    r.update(kind='nvml',session=session,sample_seq=seq,query_start_monotonic=start,monotonic_time=time.monotonic(),unix_time=time.time(),ok=True,CPU_MemAvailable_MiB=ram['MemAvailable']/MIB,CPU_MemTotal_MiB=ram['MemTotal']/MIB,data_disk_free_bytes=disk.free,data_disk_total_bytes=disk.total,data_disk_free_fraction=disk.free/disk.total,gpu_processes=processes)
    r.update(cgroup_info());validate_sample(r,'nvml',session);return r

def monitor_main(out,session):
    out=pathlib.Path(out);seq=0;nvml=None;rc=0
    try:
        nvml=Nvml()
        while not (out/'monitor.stop').exists():
            seq+=1;x=external_sample(nvml,session,seq)
            append_json(out/'nvml_samples.jsonl',x);atomic_json(out/'nvml.latest.json',x)
            time.sleep(NVML_PERIOD)
    except BaseException as e:
        rc=2;x={'kind':'nvml','session':session,'sample_seq':seq+1,'monotonic_time':time.monotonic(),'unix_time':time.time(),'ok':False,'error':str(e)}
        append_json(out/'nvml_samples.jsonl',x);atomic_json(out/'nvml.latest.json',x)
    finally:
        if nvml:nvml.close()
        atomic_json(out/'nvml.exit.json',{'session':session,'exit_code':rc,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'normal_stop_requested':(out/'monitor.stop').exists()})
    return rc

class CudaHeartbeat:
    def __init__(self,torch,out,session):
        self.torch=torch;self.out=pathlib.Path(out);self.session=session;self.stop=threading.Event();self.failure=None;self.seq=0;self.phase='initializing';self.progress=0
        self.thread=threading.Thread(target=self.run,name='cuda-telemetry',daemon=True)
    def sample(self):
        t=self.torch;free,total=t.cuda.mem_get_info()
        return {'kind':'cuda','session':self.session,'sample_seq':self.seq,'monotonic_time':time.monotonic(),'unix_time':time.time(),'ok':True,'cuda_free_MiB':free/MIB,'cuda_total_MiB':total/MIB,'allocated_MiB':t.cuda.memory_allocated()/MIB,'reserved_MiB':t.cuda.memory_reserved()/MIB,'peak_allocated_MiB':t.cuda.max_memory_allocated()/MIB,'peak_reserved_MiB':t.cuda.max_memory_reserved()/MIB,'worker_pid':os.getpid(),'phase':self.phase,'completed_synthetic_tests':self.progress,'worker_RSS_bytes':int(pathlib.Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')}
    def run(self):
        while not self.stop.is_set():
            try:
                self.seq+=1;x=self.sample();validate_sample(x,'cuda',self.session)
                append_json(self.out/'cuda_samples.jsonl',x);atomic_json(self.out/'cuda.latest.json',x)
            except BaseException as e:
                self.failure=str(e);atomic_json(self.out/'cuda.latest.json',{'kind':'cuda','session':self.session,'sample_seq':self.seq,'monotonic_time':time.monotonic(),'ok':False,'error':self.failure});return
            self.stop.wait(CUDA_PERIOD)
    def check(self):
        if self.failure:raise SafetyStop(self.failure)
        self.seq=max(1,self.seq);validate_sample(self.sample(),'cuda',self.session)
        validate_sample(read_json(self.out/'nvml.latest.json'),'nvml',self.session)
    def finish(self):self.stop.set();self.thread.join(timeout=3)

def stop_owned_process(process,reason,out):
    start=time.monotonic();sent=[]
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM);sent.append('SIGTERM')
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);sent.append('SIGKILL');process.wait(timeout=5)
    result={'reason':reason,'owned_child_pid':process.pid,'signals':sent,'exit_code':process.poll(),'fully_exited':process.poll() is not None,'stop_latency_seconds':time.monotonic()-start,'no_model_child':True}
    atomic_json(pathlib.Path(out)/'safety_stop.json',result);return result

def supervise(child,monitor_alive,provider,out,session,permit=False,timeout=120):
    reader=PairReader(session);start=time.monotonic();reason=None;permit_written=False;iterations=0;first_cuda=None
    while child.poll() is None:
        iterations+=1
        try:
            if not monitor_alive():raise SafetyStop('MONITOR_SUBPROCESS_EXITED')
            if time.monotonic()-start>timeout:raise SafetyStop('SYNTHETIC_WORKER_TIMEOUT')
            pair=provider()
            if pair is None:
                if time.monotonic()-start>15:raise SafetyStop('CUDA_TELEMETRY_STARTUP_TIMEOUT')
            else:
                reader.check(*pair)
                if first_cuda is None:first_cuda=pair[1]
                if permit and not permit_written and pair[1]['sample_seq']>first_cuda['sample_seq']:
                    atomic_json(pathlib.Path(out)/'gpu_tests.permit.json',{'session':session,'synthetic_tests_only':True,'model_execution_authorized':False,'monotonic_time':time.monotonic()});permit_written=True
            append_json(pathlib.Path(out)/'supervisor_heartbeat.jsonl',{'monotonic_time':time.monotonic(),'unix_time':time.time(),'iteration':iterations,'child_pid':child.pid,'monitor_alive':True,'permit_written':permit_written})
        except BaseException as e:
            reason=str(e);stop_owned_process(child,reason,out);break
        time.sleep(SUPERVISOR_PERIOD)
    rc=child.wait(timeout=5)
    result={'exit_code':rc,'fully_exited':True,'stop_reason':reason,'iterations':iterations,'duration_seconds':time.monotonic()-start,'synthetic_only':True,'permit_written':permit_written,'passed':reason is None and rc==0}
    atomic_json(pathlib.Path(out)/'supervisor_result.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--monitor');p.add_argument('--session');p.add_argument('--dummy',type=float)
    a=p.parse_args()
    if a.dummy is not None:time.sleep(a.dummy);raise SystemExit(0)
    raise SystemExit(monitor_main(a.monitor,a.session))

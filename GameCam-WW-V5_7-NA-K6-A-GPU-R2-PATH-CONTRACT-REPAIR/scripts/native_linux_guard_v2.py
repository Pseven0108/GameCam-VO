"""Linux safety adapter for the inherited native Tracker; never instantiated by Launch Audit."""
import ctypes,json,os,pathlib,resource,time,uuid
from linux_safety import CudaHeartbeat,EXPECTED_UUID,MIB,read_json,validate_sample,append_json,SafetyStop
from runner_core import GrowthGuard
class ModelHeartbeat(CudaHeartbeat):
    def sample(self):
        if os.getppid()!=int(os.environ['GAMECAM_SUPERVISOR_PID']):raise SafetyStop('SUPERVISOR_PARENT_LOST')
        p=self.out/'supervisor_heartbeat.jsonl'
        if not p.exists() or time.time()-p.stat().st_mtime>3:raise SafetyStop('SUPERVISOR_HEARTBEAT_STALE')
        r=super().sample();r['gpu_uuid']=EXPECTED_UUID;r['completed_frames']=self.progress;r.pop('completed_synthetic_tests',None);return r
class Guard:
    def __init__(self,session_dir,out,torch,monitor_session_id,execution_kind='droidw',diagnostic=None):
        self.session_dir=pathlib.Path(session_dir);self.out=pathlib.Path(out);self.torch=torch;self.session=monitor_session_id
        self.phase='pre_model';self.frame=None;self.failure=None;self.latest=None;self.growth=GrowthGuard();self.min_cuda=self.min_nvml=float('inf');self.peak_nvml=0
        if diagnostic:diagnostic.emit('CUDA_CONTEXT','start')
        torch.cuda.init()
        if diagnostic:diagnostic.emit('CUDA_CONTEXT','end')
        p=torch.cuda.get_device_properties(0)
        if torch.cuda.device_count()!=1 or (p.major,p.minor)!=(7,5) or '2080 Ti' not in p.name:raise SafetyStop('CUDA_DEVICE_CONTRACT_MISMATCH')
        class CUuuid(ctypes.Structure):_fields_=[('bytes',ctypes.c_ubyte*16)]
        d=ctypes.CDLL('libcuda.so.1');device=ctypes.c_int();u=CUuuid()
        if d.cuDeviceGet(ctypes.byref(device),0)!=0:raise SafetyStop('CUDA_DEVICE_QUERY_FAILED')
        fn=getattr(d,'cuDeviceGetUuid_v2',None) or d.cuDeviceGetUuid
        if fn(ctypes.byref(u),device)!=0 or 'GPU-'+str(uuid.UUID(bytes=bytes(u.bytes)))!=EXPECTED_UUID:raise SafetyStop('CUDA_DRIVER_UUID_MISMATCH')
        self.hb=ModelHeartbeat(torch,self.session_dir,self.session);self.hb.thread.start();start=time.monotonic()
        if diagnostic:diagnostic.emit('CUDA_HEARTBEAT_STARTED')
        while not (self.session_dir/'work.permit.json').exists():
            self.check('waiting_for_parent_barrier')
            if time.monotonic()-start>15:raise SafetyStop('MODEL_STARTUP_PERMIT_TIMEOUT')
            time.sleep(.02)
        permit=read_json(self.session_dir/'work.permit.json')
        if permit.get('session')!=self.session or permit.get('execution_kind')!=execution_kind or permit.get('model_execution_authorized') is not True:raise SafetyStop('MODEL_STARTUP_PERMIT_INVALID')
        if execution_kind=='droidw_diagnostic' and permit.get('diagnostic_only') is not True:raise SafetyStop('DIAGNOSTIC_PERMIT_KIND_INVALID')
        if diagnostic:diagnostic.emit('STARTUP_PERMIT_RECEIVED')
    def check(self,label='',record=False):
        if self.hb.failure:self.failure=self.hb.failure;raise SafetyStop(self.failure)
        self.hb.phase=self.phase;self.hb.seq=max(1,self.hb.seq)
        x=self.hb.sample();validate_sample(x,'cuda',self.session)
        n=read_json(self.session_dir/'nvml.latest.json');validate_sample(n,'nvml',self.session);self.latest=n
        self.min_cuda=min(self.min_cuda,x['cuda_free_MiB']);self.min_nvml=min(self.min_nvml,n['nvml_free_MiB']);self.peak_nvml=max(self.peak_nvml,n['nvml_used_MiB'])
        x.update(label=label,frame=self.frame,phase=self.phase)
        if record:append_json(self.out/'memory_events.jsonl',x)
        return x
    def frame_boundary(self):
        x=self.check('frame_completed',True);x['frame_ordinal']=self.frame;x['sample_seq']=self.growth.next_ordinal+1
        append_json(self.session_dir/'frame_samples.jsonl',x)
        self.growth.append(self.frame,x['allocated_MiB']);self.hb.progress=self.growth.next_ordinal
    def snapshot(self):
        return {'min_CUDA_free_MiB':None if self.min_cuda==float('inf') else self.min_cuda,'min_NVML_free_MiB':None if self.min_nvml==float('inf') else self.min_nvml,'peak_NVML_used_MiB':self.peak_nvml,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'monitor_failure':self.hb.failure,'completed_frame_memory_samples':self.growth.next_ordinal,'Windows_DXGI_used':False}
    def finish(self):
        self.hb.finish()
        return self.snapshot()

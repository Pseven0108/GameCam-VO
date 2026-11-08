"""Read-only telemetry and fail-closed K6-A operational guards."""
import ctypes, json, resource, subprocess, threading, time
from pathlib import Path
from monitor_transport import MonitorReader
M=1048576
class SafetyStop(RuntimeError):pass
class Mem(ctypes.Structure):_fields_=[('total',ctypes.c_ulonglong),('free',ctypes.c_ulonglong),('used',ctypes.c_ulonglong)]
class Guard:
 def __init__(self,root,out,torch,monitor_session_id):
  self.root,self.out,self.torch=root,out,torch
  self.reader=MonitorReader(root/'logs/windows_monitor.jsonl',monitor_session_id)
  self.phase='preflight';self.frame=None;self.failure=None;self.latest=None
  self.stop=threading.Event();self.lock=threading.RLock();self.events=[];self.frame_alloc=[]
  self.min_cuda=self.min_nvml=self.min_smi=float('inf');self.peak_nvml=0;self.peak_smi=0;self.peak_rss=0
  self.lib=ctypes.CDLL('libnvidia-ml.so.1')
  if self.lib.nvmlInit_v2()!=0:raise SafetyStop('NVML_INIT_FAILED')
  self.handle=ctypes.c_void_p()
  self.lib.nvmlDeviceGetHandleByIndex_v2.argtypes=[ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p)]
  self.lib.nvmlDeviceGetMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Mem)]
  self.lib.nvmlDeviceGetUUID.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_uint]
  assert self.lib.nvmlDeviceGetHandleByIndex_v2(0,ctypes.byref(self.handle))==0
  b=ctypes.create_string_buffer(96);assert self.lib.nvmlDeviceGetUUID(self.handle,b,len(b))==0
  assert b.value.decode()=='GPU-4f328619-7836-134a-2b41-9069f6f90763','GPU UUID drift'
  self.thread=threading.Thread(target=self.sample,daemon=True);self.thread.start()
 def emit(self,x):
  with self.lock:
   self.events.append(x)
   with (self.out/'memory_events.jsonl').open('a') as f:f.write(json.dumps(x,allow_nan=False)+'\n')
 def host(self):
  try:return self.reader.read_last()
  except Exception as e:raise SafetyStop(str(e)) from e
 def ram(self):
  available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
  if available<768*M:raise SafetyStop('WSL_AVAILABLE_RAM_BELOW_768_MiB:'+str(available/M))
  return available/M
 def nvml(self):
  m=Mem();code=self.lib.nvmlDeviceGetMemoryInfo(self.handle,ctypes.byref(m))
  if code:raise SafetyStop('NVML_MEMORY_FAILED:'+str(code))
  self.min_nvml=min(self.min_nvml,m.free/M);self.peak_nvml=max(self.peak_nvml,m.used/M)
  return dict(total_MiB=m.total/M,free_MiB=m.free/M,used_MiB=m.used/M)
 def sample(self):
  while not self.stop.is_set():
   try:
    started=time.time();n=self.nvml();w=self.host();ram=self.ram()
    if self.torch.cuda.is_initialized():
     cf,ct=self.torch.cuda.mem_get_info();self.min_cuda=min(self.min_cuda,cf/M)
     if cf<512*M:raise SafetyStop('CUDA_FREE_BELOW_512_MiB_ASYNC:'+str(cf/M))
    p=subprocess.run(['/usr/lib/wsl/lib/nvidia-smi','--query-gpu=memory.total,memory.used,memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,check=True)
    nums=[float(v.strip()) for v in p.stdout.strip().split(',')];assert len(nums)==4
    self.min_smi=min(self.min_smi,nums[2]);self.peak_smi=max(self.peak_smi,nums[1])
    x=dict(unix_time=time.time(),query_start_unix=started,phase=self.phase,frame=self.frame,nvml=n,smi=dict(total_MiB=nums[0],used_MiB=nums[1],free_MiB=nums[2],utilization_percent=nums[3]),windows_unix_time=w['unix_time'],monitor_session_id=w['monitor_session_id'],sample_seq=w['sample_seq'],WSL_MemAvailable_MiB=self.ram(),allocated_MiB_async=self.torch.cuda.memory_allocated()/M if self.torch.cuda.is_initialized() else 0,reserved_MiB_async=self.torch.cuda.memory_reserved()/M if self.torch.cuda.is_initialized() else 0)
    if n['free_MiB']<512:raise SafetyStop('NVML_FREE_BELOW_512_MiB:'+str(n))
    # nvidia-smi is independently recorded, not substituted for CUDA/NVML.
    self.latest=x
    with (self.out/'gpu_samples.jsonl').open('a') as f:f.write(json.dumps(x)+'\n')
   except BaseException as e:
    self.failure=str(e);self.emit(dict(unix_time=time.time(),label='ASYNC_MONITOR_STOP',phase=self.phase,frame=self.frame,error=str(e)));return
   self.stop.wait(.2)
 def check(self,label='',record=False):
  if self.failure:raise SafetyStop(self.failure)
  w=self.host();n=self.nvml()
  free,total=self.torch.cuda.mem_get_info()
  self.min_cuda=min(self.min_cuda,free/M)
  x=dict(unix_time=time.time(),label=label,phase=self.phase,frame=self.frame,cuda_free_MiB=free/M,cuda_total_MiB=total/M,nvml=n,allocated_MiB=self.torch.cuda.memory_allocated()/M,reserved_MiB=self.torch.cuda.memory_reserved()/M,peak_allocated_MiB=self.torch.cuda.max_memory_allocated()/M,peak_reserved_MiB=self.torch.cuda.max_memory_reserved()/M,windows_unix_time=w['unix_time'],monitor_session_id=w['monitor_session_id'],sample_seq=w['sample_seq'],WSL_MemAvailable_MiB=self.ram(),allocated_MiB_async=self.torch.cuda.memory_allocated()/M if self.torch.cuda.is_initialized() else 0,reserved_MiB_async=self.torch.cuda.memory_reserved()/M if self.torch.cuda.is_initialized() else 0)
  if self.latest is None:
   if time.time()-w['unix_time']>3:raise SafetyStop('NO_FRESH_EXTERNAL_GPU_SAMPLE')
  elif time.time()-self.latest['unix_time']>3:raise SafetyStop('NVML_SMI_MONITOR_STALE')
  if free<512*M or n['free_MiB']<512:
   self.failure='CUDA_OR_NVML_FREE_BELOW_512_MiB';x['hard_stop']=self.failure;self.emit(x);raise SafetyStop(self.failure)
  if record:self.emit(x)
  self.peak_rss=max(self.peak_rss,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
  return x
 def frame_boundary(self):
  x=self.check('frame_completed',True);self.frame_alloc.append(x['allocated_MiB'])
  if len(self.frame_alloc)>=30:
   v=self.frame_alloc[-30:]
   if v[-1]-v[0]>512 and all(b>a for a,b in zip(v,v[1:])):raise SafetyStop('SUSTAINED_MONOTONIC_ALLOCATED_GROWTH_30_FRAMES_512_MiB')
  values={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')}
  if values['MemAvailable']<768*M:raise SafetyStop('WSL_AVAILABLE_RAM_BELOW_768_MiB')
 def finish(self):
  self.stop.set();self.thread.join(timeout=3)
  def finite(v):return None if v==float('inf') else v
  return dict(min_CUDA_free_MiB=finite(self.min_cuda),min_NVML_free_MiB=finite(self.min_nvml),min_smi_free_MiB=finite(self.min_smi),peak_NVML_used_MiB=self.peak_nvml,peak_smi_used_MiB=self.peak_smi,peak_RSS_bytes=max(self.peak_rss,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),monitor_failure=self.failure)
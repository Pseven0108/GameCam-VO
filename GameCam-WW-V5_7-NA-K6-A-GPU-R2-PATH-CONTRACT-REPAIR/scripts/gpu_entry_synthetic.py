"""Isolated CUDA tensors/extensions only; no model or checkpoint."""
import argparse,ctypes,gc,json,os,pathlib,sys,time,traceback,uuid
from linux_safety import atomic_json,CudaHeartbeat,EXPECTED_UUID,read_json,validate_sample,MIB

def main(a):
 d=pathlib.Path(a.directory);start=time.monotonic();import torch,safetensors.torch
 for mod,name in [(torch,'load'),(torch.serialization,'load'),(safetensors.torch,'load_file')]:setattr(mod,name,lambda *a,**k:(_ for _ in ()).throw(AssertionError('REAL_CHECKPOINT_FORBIDDEN')))
 torch.cuda.init();props=torch.cuda.get_device_properties(0);assert '2080 Ti' in props.name and (props.major,props.minor)==(7,5)
 class CUuuid(ctypes.Structure):_fields_=[('bytes',ctypes.c_ubyte*16)]
 lib=ctypes.CDLL('libcuda.so.1');dev=ctypes.c_int();u=CUuuid();assert lib.cuDeviceGet(ctypes.byref(dev),0)==0;fn=getattr(lib,'cuDeviceGetUuid_v2',None) or lib.cuDeviceGetUuid;assert fn(ctypes.byref(u),dev)==0;actual='GPU-'+str(uuid.UUID(bytes=bytes(u.bytes)));assert actual==EXPECTED_UUID
 hb=CudaHeartbeat(torch,d,a.session);hb.thread.start();rows=[];report={'status':'FAIL','gpu_uuid':actual,'torch':str(torch.__version__),'cuda':torch.version.cuda,'torch_import_and_cuda_seconds':time.monotonic()-start,'real_checkpoint_loaded':False,'tracker_constructed':False,'tracker_run_called':False,'real_ba_executed':False,'GT_values_read':False,'worker_pid':os.getpid()}
 try:
  while not (d/'gpu_tests.permit.json').exists():
   hb.check();assert time.monotonic()-start<15;time.sleep(.02)
  permit=read_json(d/'gpu_tests.permit.json');assert permit['synthetic_tests_only'] and not permit['model_execution_authorized'];torch.manual_seed(43);torch.cuda.reset_peak_memory_stats()
  def test(name,fn):
   hb.check();t=time.monotonic();fn();torch.cuda.synchronize();hb.check();rows.append({'name':name,'status':'PASS','seconds':time.monotonic()-t});hb.progress+=1
  def transfer():
   x=torch.arange(256,dtype=torch.float32);torch.testing.assert_close(x.to('cuda').cpu(),x)
  def matmul():
   x=torch.randn(64,64);y=torch.randn(64,64);torch.testing.assert_close((x.cuda()@y.cuda()).cpu(),x@y,rtol=1e-4,atol=1e-4)
  test('CPU_GPU_transfer',transfer);test('CUDA_small_matmul',matmul)
  def scatter():
   from torch_scatter import scatter_sum
   torch.testing.assert_close(scatter_sum(torch.tensor([1.,2.,3.],device='cuda'),torch.tensor([0,1,0],device='cuda')),torch.tensor([4.,2.],device='cuda'))
  test('torch_scatter.scatter_sum',scatter)
  def lie():
   import lietorch_backends
   from lietorch import SE3
   x=torch.tensor([[.2,-.1,.3,.02,.04,-.03]],device='cuda');torch.testing.assert_close(SE3.exp(x).log(),x,rtol=1e-5,atol=1e-6)
  test('lietorch_backends.SE3_exp_log',lie)
  def extras():
   import lietorch_extras
   volume=torch.ones((1,1,1,4,4),device='cuda');coords=torch.ones((1,2,1,1),device='cuda');value,=lietorch_extras.corr_index_forward(volume,coords,0);assert torch.isfinite(value).all() and torch.allclose(value,torch.ones_like(value))
  test('lietorch_extras.corr_index_forward',extras)
  def droid():
   import droid_backends
   # Explicitly prohibit all BA entry points, including accidental use in this fixture.
   droid_backends.ba=lambda *a,**k:(_ for _ in ()).throw(AssertionError('BA_FORBIDDEN'))
   p=torch.zeros(2,7,device='cuda');p[:,6]=1;disp=torch.ones(2,16,16,device='cuda');K=torch.tensor([10.,10.,8.,8.],device='cuda');i=torch.tensor([0],device='cuda');j=torch.tensor([1],device='cuda');dist=droid_backends.frame_distance(p,disp,K,i,j,.3);torch.testing.assert_close(dist,torch.zeros_like(dist))
  test('droid_backends.frame_distance_NO_BA',droid)
  def attention():
   import xformers.ops
   from xformers.ops.fmha.dispatch import _set_use_fa3
   _set_use_fa3(False)
   for dtype in (torch.float16,torch.float32):
    q=torch.randn(1,16,2,32,device='cuda',dtype=dtype);v=xformers.ops.memory_efficient_attention(q,q,q);ref=torch.nn.functional.scaled_dot_product_attention(q.transpose(1,2),q.transpose(1,2),q.transpose(1,2)).transpose(1,2);torch.testing.assert_close(v,ref,rtol=.02 if dtype==torch.float16 else 1e-4,atol=.02 if dtype==torch.float16 else 1e-5)
  test('xformers.attention_FP16_FP32',attention)
  report.update(status='PASS',tests=rows,peak_allocated_MiB=torch.cuda.max_memory_allocated()/MIB,peak_reserved_MiB=torch.cuda.max_memory_reserved()/MIB,cuda_free_MiB=torch.cuda.mem_get_info()[0]/MIB)
  gc.collect();torch.cuda.empty_cache();torch.cuda.synchronize();report['allocated_after_release_MiB']=torch.cuda.memory_allocated()/MIB;report['reserved_after_release_MiB']=torch.cuda.memory_reserved()/MIB
 except BaseException as e:report.update(error=str(e),traceback=traceback.format_exc(),tests=rows)
 finally:
  report['seconds']=time.monotonic()-start;atomic_json(d/'GPU_SYNTHETIC_RUNTIME_REPORT.json',report);hb.finish()
 print(json.dumps(report));return 0 if report['status']=='PASS' else 2
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--session',required=True);a=p.parse_args();raise SystemExit(main(a))

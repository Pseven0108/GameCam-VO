"""Read-only BA entry interception. No native update at the capture boundary."""
import os,time,json,pathlib,hashlib,random
import numpy as np
from checkpoint_io import NAMES,TENSOR_COUNT,save_array,new_json,gate,common_digest
class PrefixCaptured(Exception):pass

def install(video,out,arm,stream):
 import torch,droid_backends
 from task003_observer import recorder
 original=droid_backends.ba
 def intercept(*args,**kw):
  ob=recorder()
  if ob.frame_id!=328 or ob.stage!='frontend_local_predecision':return original(*args,**kw)
  assert not kw and len(args)==len(NAMES)
  assert stream.seen==328 and len(stream)==328
  n=video.counter.value
  elig=gate(video.timestamp[:n].cpu().numpy(),args[11].cpu().numpy(),args[12].cpu().numpy(),args[13],args[14])
  torch.cuda.synchronize();start=time.monotonic()
  folder=pathlib.Path(out)/'checkpoint';folder.mkdir()
  m=dict(schema='TASK004C_COMPLETE_NATIVE_INPUT_V1',state_id=pathlib.Path(out).name+'_'+arm+'_NEW_PREFIX_RGB328',historical_state_reconstruction=False,arm=arm,trigger_rgb=328,observer_ba_id=ob.ba_id,stage=ob.stage,active_count=n,eligibility=elig,arrays={},scalars=dict(zip(NAMES[13:],args[13:])),native_extension_file=droid_backends.__file__,selected_prior_at_capture='mono_disps' if arm=='E0' else 'zeros',scope='ONE_NATIVE_BA_CALL_FIXED_NETWORK_TARGETS',frontend_restart_complete=False)
  for name,t in list(zip(NAMES[:13],args[:13]))+[('mono_disps',video.mono_disps),('zeros',video.zeros),('timestamp',video.timestamp)]:
   assert torch.is_tensor(t)
   a=t.detach().cpu().numpy()
   m['arrays'][name]=save_array(folder,name,a,dict(stride=list(t.stride()),torch_dtype=str(t.dtype),source_device=str(t.device),storage_offset=t.storage_offset(),contiguous=t.is_contiguous()))
  m['common_input_digest']=common_digest(m)
  m['scaled_prefix_rgb_sha256']=stream.rgb_hash.hexdigest()
  m['captured_seconds']=time.monotonic()-start
  new_json(folder/'CHECKPOINT.json',m)
  new_json(pathlib.Path(out)/'CAPTURE_COMPLETE.json',dict(state_id=m['state_id'],observer_ba_id=ob.ba_id,active_count=n,read_frames=stream.seen,final_ba=False,filler=False,checkpoint_sha256=hashlib.sha256((folder/'CHECKPOINT.json').read_bytes()).hexdigest(),raw_saved_bytes=sum(r['bytes'] for r in m['arrays'].values()),gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated(),gpu_peak_reserved_bytes=torch.cuda.max_memory_reserved(),capture_seconds=m['captured_seconds'],eligibility=elig))
  print('TASK004C_CAPTURE_COMPLETE',arm,ob.ba_id,n,flush=True)
  raise PrefixCaptured('complete native entry saved; no target BA executed')
 droid_backends.ba=intercept
 return original

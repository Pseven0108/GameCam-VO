"""CPU equivalence checks for offline resource and lossless artifact I/O only."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import ast,copy,hashlib,json,pathlib,sys,tempfile,types,unittest
from unittest.mock import patch
ROOT=pathlib.Path(os.environ['GAMECAM_NATIVE_WORKSPACE'])
sys.path[:0]=[str(ROOT/'overlay'),str(ROOT/'source_candidate')]
import numpy as np
import runtime_io as rio
from io_import_overlay import transformed
from native_control import admission

def array_identity(a):
 return {'shape':list(a.shape),'dtype':a.dtype.str,'sha256':hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()}

class RecoveryTests(unittest.TestCase):
 def test_ast_only_restore_entry_changes(self):
  raw=(ROOT/'source_candidate/native_control/native_driver.py').read_bytes()
  changed=transformed(raw);before=ast.parse(raw);after=ast.parse(changed)
  nodes=lambda t:{x.name:ast.dump(x,include_attributes=False) for x in t.body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
  a,b=nodes(before),nodes(after);self.assertEqual([k for k in a if a[k]!=b[k]],['restore_and_continue'])
 def test_cached_priors_precedes_restore_and_cuda(self):
  text=transformed((ROOT/'source_candidate/native_control/native_driver.py').read_bytes())
  func=next(x for x in ast.parse(text).body if isinstance(x,ast.FunctionDef) and x.name=='restore_and_continue')
  calls=[ast.unparse(x.func) for x in ast.walk(func) if isinstance(x,ast.Call)]
  # Textual order is used because ast.walk does not guarantee execution order.
  a=ast.unparse(func);self.assertLess(a.index('cached_priors()'),a.index('restore_c0('));self.assertLess(a.index('cached_priors()'),a.index('torch.cuda.set_device('))
 def test_frozen_cached_hub_routing_and_unknown_rejection(self):
  raw=(ROOT/'source_candidate/native_control/native_driver.py').read_text();fn=next(x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name=='cached_priors')
  calls=[];fake=types.SimpleNamespace(hub=types.SimpleNamespace(set_dir=lambda p:None,load=lambda *a,**kw:calls.append((a,kw)) or 'LOCAL_PROBE'))
  ns={'pathlib':pathlib,'os':os,'torch':fake,'ControlError':RuntimeError};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<frozen cached_priors>','exec'),ns)
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as tmp:
   for repo in ('yvanyin_metric3d_main','ywyue_FiT3D_main'):
    p=pathlib.Path(tmp)/repo;p.mkdir();(p/'hubconf.py').write_text('# CPU fake only')
   with patch.dict(os.environ,TORCH_HOME=tmp):
    ns['cached_priors']();self.assertEqual(fake.hub.load('yvanyin/metric3d','m'),'LOCAL_PROBE');self.assertEqual(fake.hub.load('ywyue/FiT3D','f'),'LOCAL_PROBE')
    with self.assertRaises(RuntimeError):fake.hub.load('unknown/repository','x')
    (pathlib.Path(tmp)/'ywyue_FiT3D_main/hubconf.py').unlink()
    with self.assertRaises(RuntimeError):fake.hub.load('ywyue/FiT3D','f')
  self.assertEqual(len(calls),2);self.assertTrue(all(kw['source']=='local' for a,kw in calls))
 def run_resource(self,disk,shm,issues=()):
  original={'issues':list(issues),'admitted':not issues,'data_disk':{'free':disk},'shared_memory':{'free':shm}}
  with patch.object(admission,'continuation_preflight',lambda *a:copy.deepcopy(original)):
   rio.install_resource_accounting(ROOT);return admission.continuation_preflight(ROOT,{})
 def test_storage_boundary_pass(self):self.assertTrue(self.run_resource(11*rio.GIB,10*rio.GIB+rio.CPU_BYTES+64*1024**2)['admitted'])
 def test_data_floor_failure(self):self.assertFalse(self.run_resource(11*rio.GIB-1,24*rio.GIB)['admitted'])
 def test_tmpfs_floor_failure(self):self.assertFalse(self.run_resource(12*rio.GIB,10*rio.GIB+rio.CPU_BYTES+64*1024**2-1)['admitted'])
 def test_original_identity_and_gpu_failures_preserved(self):
  for issue in ('IDENTITY_CHANGED','GPU_COMPUTE_OCCUPIED_OR_UNKNOWN','REQUIRED_SINGLE_RTX3090_NOT_CONFIRMED'):
   a=self.run_resource(14*rio.GIB,24*rio.GIB,[issue]);self.assertFalse(a['admitted']);self.assertIn(issue,a['issues'])
 def test_only_relocated_reservation_replaced(self):
  issue='DATA_DISK_BELOW_RESTORE_ARENA_LOGS_AND_FLOOR';a=self.run_resource(12*rio.GIB,24*rio.GIB,[issue]);self.assertTrue(a['admitted']);self.assertIn(issue,a['original_issues'])
 def test_arena_paths_owned_distinct_formal_modes(self):
  paths=[rio.arena_for(ROOT,x) for x in ('B1','B2','B4','B3')];self.assertEqual(len(set(paths)),4);self.assertTrue(all(x.parent==rio.TMPFS_BASE for x in paths))
  for bad in ('capture','restore_check','../B1'):
   with self.assertRaises(RuntimeError):rio.arena_for(ROOT,bad)
 def test_real_failed_video_lossless_round_trip(self):
  src=pathlib.Path('/root/rivermind-data/DROID_W_TASK004C_B_IO_COMPAT_20261124_R2_READY/attempts/B1/native/video.npz')
  out=ROOT/'artifacts/R3_VIDEO_IO_PROOF';out.mkdir(exist_ok=False)
  release=json.loads((ROOT/'evidence/CPU_STAGE_RELEASE.json').read_text());original=np.savez
  data={}
  with np.load(src,allow_pickle=False) as z:
   data={k:z[k] for k in z.files}
  before={k:array_identity(v) for k,v in data.items()}
  try:
   with patch.dict(os.environ,GAMECAM_NATIVE_ATTEMPT=str(out),TORCH_HOME=release['asset_root']+'/torch_hub',GAMECAM_FILE_BACKED_CPU_ROOT='CPU_PROBE_NO_ALLOC'):
    rio.install_lossless_video_io();np.savez(out/'video.npz',**data)
    np.savez(out/'other.npz',a=np.arange(5,dtype=np.int32))
  finally:np.savez=original
  with np.load(out/'video.npz',allow_pickle=False) as z:after={k:array_identity(z[k]) for k in z.files}
  self.assertEqual(before,after)
  import zipfile
  with zipfile.ZipFile(out/'other.npz') as z:self.assertTrue(all(x.compress_type==zipfile.ZIP_STORED for x in z.infolist()))
  with zipfile.ZipFile(out/'video.npz') as z:self.assertTrue(all(x.compress_type==zipfile.ZIP_DEFLATED for x in z.infolist()))
  proof={'source_bytes':src.stat().st_size,'compressed_bytes':(out/'video.npz').stat().st_size,'arrays':before,'all_array_hashes_shape_dtype_match':True,'other_outputs_unchanged':True,'models_imported':False,'cuda_initialized':False,'PASS':True}
  (out/'VIDEO_LOSSLESS_PROOF.json').write_text(json.dumps(proof,indent=2))

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryTests);result=unittest.TextTestRunner(verbosity=2).run(suite)
 report={'total':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors),'failures':[(str(a),b) for a,b in result.failures+result.errors],'cuda_initialized':False,'model_constructed':False,'original_source_changed':False,'PASS':result.wasSuccessful()}
 (ROOT/'evidence/R3_RECOVERY_CPU_REPORT.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));sys.exit(0 if result.wasSuccessful() else 1)

"""Real RGB_NoPose CPU path plus adversarial zero-placeholder contract cases."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import contextlib,copy,hashlib,io,json,pathlib,sys,time,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'source_candidate')]
import torch,yaml
assert not torch.cuda.is_initialized()
def forbidden(*a,**kw):raise RuntimeError('MODEL_OR_CUDA_FORBIDDEN_IN_REAL_LOADER_CPU_TEST')
torch.cuda._lazy_init=forbidden;torch.load=forbidden
from native_control.dataset import NativeViperRGB
from src.utils.datasets import RGB_NoPose
from control_common import ControlError,file_sha
CFG_PATH=pathlib.Path('/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/release/candidates/r2_sealed_config.yaml')
INPUT=pathlib.Path('/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1/inputs/val_007_full_00001-00487/INPUT.json')
OUT=ROOT/'artifacts/REAL_LOADER_CPU';OUT.mkdir(exist_ok=False)
CFG=yaml.safe_load(CFG_PATH.read_text());records=[];sequential=[]

def stream():
 cfg=copy.deepcopy(CFG);cfg['data']['output']=str(OUT);cfg['data']['input_folder']=str(INPUT.parent)
 (OUT/cfg['scene']).mkdir(parents=True,exist_ok=True)
 return NativeViperRGB(cfg,INPUT,OUT)

class RealLoaderTests(unittest.TestCase):
 def setUp(self):self.s=stream()
 def actual(self):return RGB_NoPose.__getitem__(self.s,0)
 def reject(self,item):
  with patch.object(RGB_NoPose,'__getitem__',return_value=item):
   with self.assertRaises(ControlError):self.s[0]
  self.assertEqual(self.s.seen,0)
 def test_RGB001_real_decode(self):
  ts,color,depth,pose=self.s[0];self.assertEqual(ts,0);self.assertEqual(tuple(color.shape),(1,3,360,640))
  self.assertEqual(color.device.type,'cpu');self.assertIsNone(pose);self.assertEqual(self.s.seen,1)
 def test_real_zero_placeholder_is_accepted(self):
  item=self.s[0];self.assertEqual(item[2].dtype,torch.float32);self.assertEqual(item[2].device.type,'cpu')
  self.assertEqual(tuple(item[2].shape),(360,640));self.assertEqual(int(torch.count_nonzero(item[2])),0)
 def test_parent_tuple_and_tensor_identity_preserved(self):
  item=self.actual()
  with patch.object(RGB_NoPose,'__getitem__',return_value=item):result=self.s[0]
  self.assertIs(result,item);self.assertIs(result[1],item[1]);self.assertIs(result[2],item[2])
 def test_depth_None_rejected_by_strict_Tensor_only_contract(self):
  ts,c,d,p=self.actual();self.reject((ts,c,None,p))
 def test_nonzero_depth_rejected(self):
  ts,c,d,p=self.actual();d=d.clone();d[0,0]=1;self.reject((ts,c,d,p))
 def test_NaN_depth_rejected(self):
  ts,c,d,p=self.actual();d=d.clone();d[0,0]=float('nan');self.reject((ts,c,d,p))
 def test_Inf_depth_rejected(self):
  ts,c,d,p=self.actual();d=d.clone();d[0,0]=float('inf');self.reject((ts,c,d,p))
 def test_nonempty_pose_rejected(self):
  ts,c,d,p=self.actual();self.reject((ts,c,d,torch.eye(4)))
 def test_depth_shape_rejected(self):
  ts,c,d,p=self.actual();self.reject((ts,c,d[:-1],p))
 def test_depth_dtype_rejected(self):
  ts,c,d,p=self.actual();self.reject((ts,c,d.double(),p))
 def test_nonCPU_meta_depth_rejected_without_CUDA(self):
  ts,c,d,p=self.actual();self.reject((ts,c,torch.zeros(d.shape,device='meta'),p));self.assertFalse(torch.cuda.is_initialized())
 def test_RGB_shape_rejected(self):
  ts,c,d,p=self.actual();self.reject((ts,c[:,:,:-1,:],d,p))
 def test_timestamp_rejected(self):
  ts,c,d,p=self.actual();self.reject((ts+1,c,d,p))
 def test_timestamp_bool_rejected(self):
  ts,c,d,p=self.actual();self.reject((False,c,d,p))
 def test_frame_ID_rejected_before_parent_read(self):
  self.s.frames[0]['rgb_id']=2
  with patch.object(RGB_NoPose,'__getitem__') as parent:
   with self.assertRaises(ControlError):self.s[0]
   parent.assert_not_called()
  self.assertEqual(self.s.seen,0)
 def test_depth_label_source_rejected_before_parent_read(self):
  self.s.depth_paths=['/MUST_NOT_READ_ANY_GT']
  with patch.object(RGB_NoPose,'__getitem__') as parent:
   with self.assertRaises(ControlError):self.s[0]
   parent.assert_not_called()
  self.assertEqual(self.s.seen,0)
 def test_pose_label_source_rejected_before_parent_read(self):
  self.s.poses=[torch.eye(4)]
  with patch.object(RGB_NoPose,'__getitem__') as parent:
   with self.assertRaises(ControlError):self.s[0]
   parent.assert_not_called()
  self.assertEqual(self.s.seen,0)
 def test_failed_observation_does_not_advance_seen(self):
  ts,c,d,p=self.actual();self.reject((ts+1,c,d,p));self.assertEqual(self.s[0][0],0);self.assertEqual(self.s.seen,1)
 def test_skipped_index_rejected(self):
  with self.assertRaises(ControlError):self.s[1]
  self.assertEqual(self.s.seen,0)
 def test_above_authorized_range_rejected(self):
  with self.assertRaises(ControlError):self.s[80]
  self.assertEqual(self.s.seen,0)
 def test_RGB001_through_RGB018_real_sequential(self):
  for i in range(18):
   item=self.s[i];ts,c,d,p=item
   self.assertEqual(ts,i);self.assertEqual(tuple(c.shape),(1,3,360,640));self.assertEqual(self.s.seen,i+1)
   self.assertIsNone(p);self.assertIsNone(self.s.depth_paths);self.assertIsNone(self.s.poses)
   self.assertEqual(d.dtype,torch.float32);self.assertEqual(d.device.type,'cpu');self.assertEqual(int(torch.count_nonzero(d)),0)
   row={'rgb_id':i+1,'timestamp':ts,'RGB_file_sha256':file_sha(self.s.color_paths[i]),
        'processed_color_sha256':hashlib.sha256(c.contiguous().numpy().tobytes()).hexdigest(),
        'color_shape':list(c.shape),'depth_shape':list(d.shape),'depth_dtype':str(d.dtype),'depth_device':str(d.device),
        'depth_all_zero':True,'pose_is_None':True,'seen_after':self.s.seen}
   sequential.append(row)

class RecordedResult(unittest.TextTestResult):
 def startTest(self,test):
  self.started=time.perf_counter();self.stdout=io.StringIO();self.stderr=io.StringIO();self.actual='PASS';self.detail=''
  self.o=contextlib.redirect_stdout(self.stdout);self.e=contextlib.redirect_stderr(self.stderr);self.o.__enter__();self.e.__enter__()
  super().startTest(test)
 def addFailure(self,test,error):self.actual='FAIL';self.detail=self._exc_info_to_string(error,test);super().addFailure(test,error)
 def addError(self,test,error):self.actual='ERROR';self.detail=self._exc_info_to_string(error,test);super().addError(test,error)
 def stopTest(self,test):
  self.e.__exit__(None,None,None);self.o.__exit__(None,None,None)
  stdout=self.stdout.getvalue();stderr=self.stderr.getvalue()+self.detail
  records.append({'test_id':test.id(),'input':'real RGB001 or RGB001-RGB018 using actual RGB_NoPose; adversarial return mutations for negative cases',
   'seed':43,'expected':'real zero placeholders accepted; invalid label/shape/type/frame inputs rejected before cursor advance',
   'actual':self.actual,'exit_code':0 if self.actual=='PASS' else 1,'seconds':time.perf_counter()-self.started,
   'stdout':stdout,'stderr':stderr,'stdout_sha256':hashlib.sha256(stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(stderr.encode()).hexdigest()})
  super().stopTest(test)

if __name__=='__main__':
 started=time.time()
 with (OUT/'unittest.stderr.txt').open('x') as log:
  result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=RecordedResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(RealLoaderTests))
 report={'scope':'REAL_PARENT_REAL_RGB_CPU_ONLY_NO_MODELS','total':result.testsRun,'passed':sum(r['actual']=='PASS' for r in records),
  'failures':len(result.failures),'errors':len(result.errors),'seconds':time.time()-started,'cuda_initialized':torch.cuda.is_initialized(),
  'checkpoint_deserialized':False,'GT_sources_read':False,'first_18_real_frames_checked':len(sequential),'tests':records,
  'None_depth_policy':'rejected, per explicitly required Tensor-only contract','nonCPU_negative_device':'meta; no real CUDA tensor created',
  'input_manifest_sha256':file_sha(INPUT),'dataset_source_sha256':file_sha(ROOT/'source_candidate/native_control/dataset.py')}
 (OUT/'CPU_TEST_REPORT.json').write_text(json.dumps(report,indent=2));(OUT/'RGB001_018_MANIFEST.json').write_text(json.dumps(sequential,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!='tests'}))
 raise SystemExit(0 if result.wasSuccessful() and len(sequential)==18 and not report['cuda_initialized'] else 1)

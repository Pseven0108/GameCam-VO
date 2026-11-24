import unittest,tempfile,pathlib,json,hashlib
from unittest.mock import patch
from collections import namedtuple
import numpy as np
from checkpoint_io import gate,save_array,sha_file,common_digest,NAMES
class ContractTests(unittest.TestCase):
 def test_exact_endpoints(self):
  t=np.array([0,311,327]);r=gate(t,np.array([1,2]),np.array([2,1]),1,3);self.assertEqual(r['rgb328_slot'],2)
 def test_not_retained(self):
  with self.assertRaises(ValueError):gate(np.array([0,311,326]),np.array([1,2]),np.array([2,1]),1,3)
 def test_outside_window(self):
  with self.assertRaises(ValueError):gate(np.array([0,311,327]),np.array([1,2]),np.array([2,1]),2,3)
 def test_missing_reverse_edge(self):
  with self.assertRaises(ValueError):gate(np.array([0,311,327]),np.array([1]),np.array([2]),1,3)
 def test_duplicate_rgb(self):
  with self.assertRaises(ValueError):gate(np.array([311,311,327]),np.array([0,2]),np.array([2,0]),0,3)
 def test_nonpickle_roundtrip_hash(self):
  # Use the current approved output drive rather than a low-space system temporary directory.
  with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).resolve().parent.parent/'test_logs') as d, patch('checkpoint_io.shutil.disk_usage',return_value=namedtuple('Usage','total used free')(10**12,0,10**12)):
   a=np.arange(24,dtype=np.float32).reshape(3,8)[:,::2];r=save_array(d,'strided',a);p=pathlib.Path(d)/r['file']
   b=np.load(p,allow_pickle=False);np.testing.assert_array_equal(a,b);self.assertEqual(hashlib.sha256(b.tobytes()).hexdigest(),r['data_sha256'])
   z=p.read_bytes();p.write_bytes(z[:-1]+bytes([z[-1]^1]));self.assertNotEqual(sha_file(p),r['file_sha256'])
 def test_independent_clones(self):
  a=np.arange(8,dtype=np.float32);b=a.copy();c=a.copy();b[0]=-5;self.assertEqual(c[0],0);self.assertFalse(np.shares_memory(b,c))
 def test_d_only_digest(self):
  r=dict(dtype='<f4',shape=[1],data_sha256='a',stride=[1]);m=dict(arrays={n:dict(r) for n in NAMES[:13]+['mono_disps','zeros','timestamp']},scalars={'use_uba':True,'update_u':True});h=common_digest(m);m['arrays']['selected_prior']['data_sha256']='b';self.assertEqual(h,common_digest(m));m['arrays']['eta']['data_sha256']='c';self.assertNotEqual(h,common_digest(m))
 def test_storage_floor_blocks(self):
  with tempfile.TemporaryDirectory(dir=pathlib.Path(__file__).resolve().parent.parent/'test_logs') as d, patch('checkpoint_io.shutil.disk_usage',return_value=namedtuple('Usage','total used free')(10**12,10**12-1,1)):
   with self.assertRaises(RuntimeError):save_array(d,'denied',np.zeros(1))
   self.assertFalse((pathlib.Path(d)/'denied.npy').exists())
 def test_native_argument_count(self):
  self.assertEqual(len(NAMES),30);self.assertEqual(NAMES[25:27],['update_u','use_uba']);self.assertEqual(NAMES[3],'selected_prior')
if __name__=='__main__':unittest.main(verbosity=2)

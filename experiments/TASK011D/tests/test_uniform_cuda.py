import sys,unittest
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uniform_control import torch_uniform_for_call,uniform_for_call
import test_source_gather as source_fixture

class CUDAContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not torch.cuda.is_available():raise RuntimeError('CUDA required: no silent skipped acceptance tests')
    def test_buffer64_and500_multiple_noncontinuous_source_counts(self):
        rng=np.random.default_rng(44)
        for buffer in (64,500):
            for count in (1,7,32):
                with self.subTest(buffer=buffer,sources=count):
                    a=rng.uniform(.001,.999,(buffer,45,80)).astype(np.float32)
                    nv=rng.random(a.shape)>.1;a[~nv]=0;dm=(rng.random(a.shape)>.2).astype(np.float32)
                    ix=np.sort(rng.choice(64,count,replace=False)).astype(np.int64)
                    expected,_=uniform_for_call(a,nv,dm,ix)
                    x=[torch.as_tensor(v,device='cuda') for v in (a,nv,dm,ix)];before=[v.clone() for v in x]
                    out,p=torch_uniform_for_call(*x)
                    np.testing.assert_allclose(out.cpu().numpy(),expected,atol=1e-6,rtol=0)
                    self.assertTrue(all(torch.equal(v,b) for v,b in zip(x,before)))
                    self.assertTrue(all(r['eligible_and_positive_support_equal'] for r in p['frames']))
    def test_full_source_gather_reordered_timestamps(self):
        from uniform_control import gather_source_strength
        v,args,c,n=source_fixture.SourceGather().fixture('cuda')
        out,p=gather_source_strength(v,args,c,n)
        self.assertEqual([r['input_timestamp'] for r in p['frames']],[63,61,60,57,0])
        self.assertEqual(out.shape,(500,45,80))
    def test_cuda_empty_mask_and_invalid_support(self):
        a=torch.ones((500,45,80),device='cuda');ix=torch.tensor([1,17],device='cuda')
        out,p=torch_uniform_for_call(a,a.bool(),torch.zeros_like(a),ix)
        self.assertTrue(all(x['A7_mean'] is None for x in p['frames']))
        a[1,0,0]=0
        with self.assertRaises(ValueError):torch_uniform_for_call(a,a.bool()|True,torch.ones_like(a),ix)

if __name__=='__main__':unittest.main(verbosity=2)

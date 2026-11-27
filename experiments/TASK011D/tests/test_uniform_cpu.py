import sys,unittest
from pathlib import Path
import numpy as np
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uniform_control import torch_uniform_for_call,uniform_for_call

class CPUContracts(unittest.TestCase):
    def test_independent_FP32_reference_mask_means(self):
        r=np.random.default_rng(43);a=r.uniform(.001,.999,(64,45,80)).astype('float32')
        nv=r.random(a.shape)>.2;a[~nv]=0;dm=(r.random(a.shape)>.3).astype('float32');ix=np.array([0,8,31,63])
        expected,_=uniform_for_call(a,nv,dm,ix)
        got,p=torch_uniform_for_call(*(torch.from_numpy(x) for x in (a,nv,dm,ix)))
        np.testing.assert_allclose(got.numpy(),expected,rtol=0,atol=1e-6)
        self.assertLessEqual(max(x['absolute_mean_difference'] for x in p['frames']),1e-6)
    def test_empty_support_is_null(self):
        a=torch.full((64,45,80),.4);nv=torch.ones_like(a,dtype=torch.bool);dm=torch.zeros_like(a)
        out,p=torch_uniform_for_call(a,nv,dm,torch.tensor([1,23]))
        self.assertFalse(out.any());self.assertTrue(all(x['A5_mean'] is None for x in p['frames']))
    def test_nonfinite_or_zero_support_stops(self):
        for bad in (float('nan'),float('inf'),0.,-.1):
            a=torch.ones((64,2,3));a[1,0,0]=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                torch_uniform_for_call(a,torch.ones_like(a,dtype=torch.bool),torch.ones_like(a),torch.tensor([1]))
    def test_duplicate_sources_stop(self):
        a=torch.ones((64,2,3))
        with self.assertRaises(ValueError):torch_uniform_for_call(a,a.bool(),a,torch.tensor([1,1]))
    def test_inputs_are_unchanged(self):
        a=torch.rand((64,2,3))+.01;nv=torch.ones_like(a,dtype=torch.bool);dm=torch.ones_like(a)
        before=[x.clone() for x in (a,nv,dm)]
        torch_uniform_for_call(a,nv,dm,torch.tensor([0,2,63]))
        for x,y in zip((a,nv,dm),before):self.assertTrue(torch.equal(x,y))

if __name__=='__main__':unittest.main(verbosity=2)

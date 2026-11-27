import sys,unittest,types
from pathlib import Path
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from uniform_control import gather_source_strength,source_slots_gpu

class SourceGather(unittest.TestCase):
    def test_union_is_sorted_includes_ii_before_t0(self):
        x=source_slots_gpu(torch.tensor([0,6,6]),2,4,8)
        self.assertEqual(x.tolist(),[0,2,3,6])
    def fixture(self,device='cpu',buffer=500):
        v=types.SimpleNamespace(counter=types.SimpleNamespace(value=64),timestamp=torch.arange(64,device=device).float().flip(0),disps=torch.ones((buffer,45,80),device=device))
        cache=torch.arange(1,65,device=device).float()[:,None,None].expand(64,45,80)/65
        valid=torch.ones_like(cache,dtype=torch.bool)
        args=[None]*30;args[3]=torch.ones_like(v.disps);args[11]=torch.tensor([0,6,63],device=device);args[13:15]=[2,4]
        return v,args,cache,valid
    def test_noncontinuous_slots_and_permuted_timestamps(self):
        v,args,c,n=self.fixture();out,p=gather_source_strength(v,args,c,n)
        self.assertEqual([r['source_slot'] for r in p['frames']],[0,2,3,6,63])
        self.assertEqual([r['input_timestamp'] for r in p['frames']],[63,61,60,57,0])
        for r in p['frames']:self.assertAlmostEqual(out[r['source_slot'],0,0].item(),(r['input_timestamp']+1)/65,places=6)
        self.assertFalse(out[64:].any())
    def test_native_valid_intersects_actual_mono(self):
        v,args,c,n=self.fixture();c=c.clone();n=n.clone();n[63,0,0]=False;c[63,0,0]=0;args[3][0,0,1]=0
        out,p=gather_source_strength(v,args,c,n)
        self.assertEqual(out[0,0,0],0);self.assertEqual(out[0,0,1],0)
    def test_invalid_timestamp_fails_before_solver(self):
        v,args,c,n=self.fixture();v.timestamp[0]=float('nan')
        with self.assertRaises(ValueError):gather_source_strength(v,args,c,n)
    def test_invalid_source_fails_without_out_of_bounds_kernel(self):
        v,args,c,n=self.fixture();args[11][0]=-1
        with self.assertRaises(ValueError):gather_source_strength(v,args,c,n)

if __name__=='__main__':unittest.main(verbosity=2)

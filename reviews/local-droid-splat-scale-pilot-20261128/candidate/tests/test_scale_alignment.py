import pathlib,sys,unittest
import torch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from scale_alignment import fit_prior,apply_prior

class Tests(unittest.TestCase):
    def setUp(self):self.p=torch.linspace(.05,2,480,dtype=torch.float64).reshape(20,24)
    def test_identity(self):
        r=fit_prior(self.p,self.p,torch.ones_like(self.p));self.assertTrue(r.accepted);self.assertEqual(r.scale,1.)
    def test_known_scale(self):
        r=fit_prior(self.p,self.p*2.3,torch.ones_like(self.p));self.assertAlmostEqual(r.scale,2.3,places=12)
    def test_known_affine(self):
        r=fit_prior(self.p,self.p*1.7+.2,torch.ones_like(self.p),affine=True)
        self.assertAlmostEqual(r.scale,1.7,places=12);self.assertAlmostEqual(r.shift,.2,places=12)
    def test_insufficient(self):self.assertFalse(fit_prior(self.p,self.p,torch.zeros_like(self.p)).accepted)
    def test_shape(self):
        with self.assertRaises(ValueError):fit_prior(self.p,self.p[:1],torch.ones_like(self.p))
    def test_degenerate_affine(self):
        p=torch.ones_like(self.p);self.assertFalse(fit_prior(p,p,p,affine=True).accepted)
    def test_preserve_zero(self):
        p=self.p.clone();p[0,0]=0;r=fit_prior(p,self.p*2,torch.ones_like(p))
        q=apply_prior(p,r);self.assertEqual(float(q[0,0]),0.);self.assertEqual(q.dtype,p.dtype)
    def test_outlier_mask(self):
        t=self.p*2;t[0,:]=1000;w=torch.ones_like(t);w[0,:]=0
        self.assertAlmostEqual(fit_prior(self.p,t,w).scale,2.,places=12)
    def test_no_input_mutation(self):
        p=self.p.clone();t=p*2;r=fit_prior(p,t,torch.ones_like(p));apply_prior(p,r)
        self.assertTrue(torch.equal(p,self.p))
    def test_invalid_fallback(self):
        p=torch.zeros_like(self.p);r=fit_prior(p,self.p,torch.ones_like(p))
        self.assertTrue(torch.equal(apply_prior(p,r),p))
    def test_bad_values_excluded(self):
        p=self.p.clone();p[0,0]=float('nan');r=fit_prior(p,self.p*2,torch.ones_like(p))
        self.assertTrue(r.accepted);self.assertEqual(r.valid_pixels,479)
    def test_independent_weighted_reference(self):
        torch.manual_seed(4);w=torch.rand_like(self.p);t=self.p*1.8+torch.randn_like(self.p)*.01
        r=fit_prior(self.p,t,w)
        reference=torch.linalg.lstsq((self.p*w.sqrt()).reshape(-1,1),(t*w.sqrt()).reshape(-1,1)).solution.item()
        self.assertAlmostEqual(r.scale,reference,places=12)

if __name__=='__main__':unittest.main(verbosity=2)

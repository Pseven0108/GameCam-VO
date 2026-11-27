"""Independent numerical contracts for sign, units, neutrality, and degeneracy."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
import sys
from pathlib import Path
import unittest
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'experiments/TASK010-A/scripts')]
from task010_fusion import neutral_severity,native_source_weight
from flow_geometry import geometry_score,sampson_error,camera_flow
from infer_candidates import resize_size,empty_parameters


class FusionContracts(unittest.TestCase):
    def test_dead_zone_exact_neutral(self):
        p=torch.linspace(0,.4,1024);self.assertTrue(torch.equal(neutral_severity(p),torch.zeros_like(p)))
    def test_monotone_severity(self):
        v=neutral_severity(torch.linspace(0,1,1024));self.assertTrue(bool((v[1:]>=v[:-1]).all()))
    def test_high_probability_floor(self):
        g=1-.75*neutral_severity(torch.ones(10));self.assertTrue(torch.equal(g,torch.full_like(g,.25)))
    def test_uba_formula_transition(self):
        u=torch.tensor([0.,.5,.8,1.,2.]);w=native_source_weight(u)
        np.testing.assert_allclose(w.numpy(),[1.,1.,1.,.1,1/55],rtol=1e-6)
    def test_fusion_does_not_further_crush_low_uba(self):
        g=1-.75*native_source_weight(torch.tensor([.5,2.]))
        self.assertGreater(float(g[1]),float(g[0]))
    def test_mask_disabled_is_bit_neutral(self):
        w=torch.randn(64).abs();g=1-.75*neutral_severity(torch.zeros(64));self.assertTrue(torch.equal(w*g,w))
    def test_horizontal_epipolar_flow(self):
        F=np.array([[0.,0.,0.],[0.,0.,-1.],[0.,1.,0.]])
        yy,xx=np.mgrid[:8,:10];xy=np.stack([xx,yy],-1);q=xy+[4.,0.]
        np.testing.assert_array_equal(sampson_error(F,xy,q),0)
    def test_epipolar_vertical_violation(self):
        F=np.array([[0.,0.,0.],[0.,0.,-1.],[0.,1.,0.]])
        xy=np.zeros((5,2));q=xy+[0,2.]
        np.testing.assert_allclose(sampson_error(F,xy,q),np.sqrt(2))
    def test_fb_inconsistent_is_not_admitted_motion(self):
        f=np.zeros((32,48,2),np.float32);f[...,0]=4
        score,valid,_,_,_,_=geometry_score(f,f)
        self.assertFalse(valid.any());self.assertFalse(score.any())
    def test_camera_identity_is_zero(self):
        pose=np.array([0.,0.,0.,0.,0.,0.,1.]);f,v=camera_flow(np.ones((8,10)),pose,pose,[10,10,5,4])
        np.testing.assert_allclose(f,0,atol=1e-12);self.assertTrue(v.all())
    def test_camera_motion_translation_sign(self):
        pose=np.array([0.,0.,0.,0.,0.,0.,1.]);other=pose.copy();other[0]=-1
        f,v=camera_flow(np.ones((8,10))*.1,pose,other,[100,100,5,4])
        np.testing.assert_allclose(f[...,0],-10,atol=1e-12);np.testing.assert_allclose(f[...,1],0,atol=1e-12)
    def test_floor_disparity_not_motion_evidence(self):
        pose=np.array([0.,0.,0.,0.,0.,0.,1.]);f,v=camera_flow(np.ones((8,10))*1e-5,pose,pose,[10,10,5,4])
        self.assertFalse(v.any())
    def test_blank_flow_no_false_geometry(self):
        f=np.zeros((32,48,2),np.float32);score,*_=geometry_score(f,f)
        self.assertTrue(np.isfinite(score).all());self.assertFalse(score.any())
    def test_preprocess_pixel_bound(self):
        for w,h in [(1920,1080),(1600,1200),(300,150)]:
            ww,hh=resize_size(w,h,255000);self.assertEqual(ww%14,0);self.assertEqual(hh%14,0);self.assertLessEqual(ww*hh,255000)
    def test_empty_initialization_strict_recovery(self):
        torch.manual_seed(1);normal=torch.nn.Sequential(torch.nn.Linear(4,5),torch.nn.LayerNorm(5))
        with empty_parameters():empty=torch.nn.Sequential(torch.nn.Linear(4,5),torch.nn.LayerNorm(5))
        self.assertTrue(all(p.is_meta for p in empty.parameters()))
        empty.load_state_dict(normal.state_dict(),strict=True,assign=True)
        x=torch.randn(8,4);self.assertTrue(torch.equal(empty(x),normal(x)))
    def test_cpu_only(self):self.assertFalse(torch.cuda.is_initialized())


if __name__=='__main__':unittest.main(verbosity=2)

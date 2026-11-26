import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
from gamecam.modules.dynamic_prior import DynamicObservationGate, GateConfig, Pi3Cache, install_video_gate
from gamecam.modules.dynamic_prior.feature_alignment import ImageGeometry
from gamecam.modules.motion_decomposition import backproject, static_rigid_pose


class GateTests(unittest.TestCase):
    def fixture(self):
        m=torch.zeros(1,4,8);xy=torch.zeros(1,2,3,2);w=torch.ones(1,1,2,3,2)
        return w,m,xy

    def test_disabled_object_identity(self):
        w,m,xy=self.fixture();out,_=DynamicObservationGate(GateConfig(enabled=False))(w,None,None,None,None)
        self.assertIs(out,w)

    def test_static_identity(self):
        w,m,xy=self.fixture();out,_=DynamicObservationGate()(w,m,m,xy,xy)
        self.assertTrue(torch.equal(w,out))

    def test_target_correspondence_not_source_pixel(self):
        w,m,xy=self.fixture();m[:,:,5:]=1;target=xy.clone();target[...,0]=6
        out,_=DynamicObservationGate()(w,m,m,xy,target)
        torch.testing.assert_close(out,w*0.1)

    def test_bilinear_noninteger(self):
        w,m,xy=self.fixture();m[:,:,1]=1;target=xy.clone();target[...,0]=0.5
        out,_=DynamicObservationGate(GateConfig(min_gate=0))(w,m,m,xy,target)
        torch.testing.assert_close(out,w*0.5)

    def test_outside_neutral(self):
        w,m,xy=self.fixture();m.fill_(1);target=xy.clone();target[...,0]=100
        out,s=DynamicObservationGate(GateConfig(alpha=0))(w,m,m,xy,target)
        self.assertTrue(torch.equal(out,w));self.assertEqual(s['target_outside_fraction'],1)

    def test_invalid_probability_rejected(self):
        w,m,xy=self.fixture();m[0,0,0]=float('nan')
        with self.assertRaises(ValueError):DynamicObservationGate()(w,m,m,xy,xy)

    def test_native_weight_not_mutated(self):
        w,m,xy=self.fixture();m.fill_(0.8);clone=w.clone()
        DynamicObservationGate()(w,m,m,xy,xy);self.assertTrue(torch.equal(w,clone))

    def test_anisotropic_channels_same_factor(self):
        w,m,xy=self.fixture();w[...,1]=2;m.fill_(0.5)
        out,_=DynamicObservationGate()(w,m,m,xy,xy)
        torch.testing.assert_close(out[...,1],2*out[...,0])

    def test_halfpixel_geometry(self):
        g=ImageGeometry((180,320),(378,672));xy=torch.tensor([[[[1.,2.]]]])
        expected=(xy*8+0.5)*2.1-0.5;torch.testing.assert_close(g.feature_to_map(xy),expected)

    def test_negative_parameter(self):
        with self.assertRaises(ValueError):GateConfig(alpha=-1)

    def test_shape_rejected(self):
        w,m,xy=self.fixture()
        with self.assertRaises(ValueError):DynamicObservationGate()(w.squeeze(0),m,m,xy,xy)

    def test_cache_id_and_hook_u_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'p.npz';np.savez(p,target_rgb_id=301,context_rgb_ids=[291,296,301],
                dynamic_probability_model=np.full((4,8),0.5,np.float32),confidence_model=np.ones((4,8),np.float32))
            cache=Pi3Cache({301:p},(16,24));u=torch.randn(2,4,8);saved=u.clone();called=[]
            def ba(target,weight,eta,ii,jj,*args,**kw):called.append(weight.clone());return 42
            v=SimpleNamespace(ba=ba,timestamp=torch.tensor([0.]),down_scale=8,uncertainties=u)
            w,m,xy=self.fixture();logs=install_video_gate(v,cache,{0:301})
            result=v.ba(xy[None],w,None,torch.tensor([0]),torch.tensor([0]))
            self.assertEqual(result,42);self.assertTrue(torch.equal(u,saved));self.assertEqual(len(logs),1)
            torch.testing.assert_close(called[0],w*0.25)
            with self.assertRaises(RuntimeError):install_video_gate(v,cache,{0:301})
            with self.assertRaises(KeyError):cache.read(302)

    def test_rigid_pose_known_translation(self):
        rng=np.random.default_rng(43);p=rng.normal(size=(30,3));p[:,2]=abs(p[:,2])+5
        t=np.array([.1,-.2,.3]);q=p+t;K=[500,500,320,180]
        def project(p):return p[:,:2]/p[:,2:]*500+np.array([320,180])
        R,tr,res=static_rigid_pose(project(p),project(q),p[:,2],q[:,2],K)
        np.testing.assert_allclose(R,np.eye(3),atol=1e-12);np.testing.assert_allclose(tr,t,atol=1e-12)
        self.assertLess(res.max(),1e-12)


if __name__=='__main__':unittest.main(verbosity=2)

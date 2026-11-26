import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from gamecam.modules.motion_decomposition.droid_adapter import StaticTrackCache,install_static_targets


class StaticTargetContract(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def cache(self,xy=None,depth=3.,dynamic=0.,input_hw=(64,64)):
        if xy is None:xy=np.array([[[16.,16.]],[[24.,16.]]])
        xy=np.asarray(xy)
        static=np.concatenate([xy,np.full((*xy.shape[:2],1),depth)],-1)
        np.savez(self.root/'predictions.npz',total_xy=xy[None],static_xyz=static[None],
                 visibility=np.ones((1,*xy.shape[:2])),dynamic_probability=np.full((1,*xy.shape[:2]),dynamic),rgb_ids=[301,302])
        (self.root/'statistics.json').write_text(json.dumps({'status':'INDEPENDENT_INFERENCE_COMPLETE','input_shape':[1,2,4,*input_hw]}))
        return StaticTrackCache(self.root,(64,64))

    def test_known_camera_only_displacement(self):
        rows=self.cache().observations(301,302,(8,8))
        self.assertEqual(len(rows),1)
        y,x,dst,c=rows[0]
        self.assertEqual((y,x),(2,2))
        np.testing.assert_allclose(dst,[3,2],atol=1e-12)
        self.assertEqual(c,.15)

    def test_reverse_edge(self):
        y,x,dst,c=self.cache().observations(302,301,(8,8))[0]
        self.assertEqual((y,x),(2,3))
        np.testing.assert_allclose(dst,[2,2],atol=1e-12)

    def test_invalid_depth_and_dynamic_points_rejected(self):
        self.assertEqual(self.cache(depth=-.2).observations(301,302,(8,8)),[])
        self.assertEqual(self.cache(dynamic=.8).observations(301,302,(8,8)),[])

    def test_half_pixel_resize_before_feature_grid(self):
        rows=self.cache(np.array([[[7.75,7.75]],[[11.75,7.75]]]),input_hw=(32,32)).observations(301,302,(8,8))
        self.assertEqual(rows[0][:2],(2,2))
        np.testing.assert_allclose(rows[0][2],[3,2],atol=1e-12)

    def test_duplicate_source_cell_not_double_counted(self):
        xy=np.array([[[16.,16.],[16.,16.]],[[24.,16.],[24.,16.]]])
        self.assertEqual(len(self.cache(xy).observations(301,302,(8,8))),1)

    def test_native_weight_and_uncertainty_unchanged(self):
        class Video:
            timestamp=torch.tensor([0.,1.])
            down_scale=8
            uncertainties=torch.tensor([.7,.8])
            def ba(self,*args,**kwargs):return args
        video=Video()
        old_u=video.uncertainties.clone()
        yy,xx=torch.meshgrid(torch.arange(8),torch.arange(8),indexing='ij')
        target=torch.stack([xx,yy],-1).float()[None,None]
        before=target.clone();weight=torch.ones_like(target)
        install_static_targets(video,self.cache(),{0:301,1:302},self.root/'calls.jsonl')
        result=video.ba(target,weight,torch.ones(2),torch.tensor([0]),torch.tensor([1]))
        self.assertAlmostEqual(result[0][0,0,2,2,0].item(),2.15,places=6)
        self.assertIs(result[1],weight)
        self.assertTrue(torch.equal(target,before))
        self.assertTrue(torch.equal(video.uncertainties,old_u))

    def test_vectorized_blend_matches_scalar_multiple_edges(self):
        class Video:
            timestamp=torch.tensor([0.,1.])
            down_scale=8
            def ba(self,*args,**kwargs):return args
        xy=np.array([[[16.,16.],[32.,32.]],[[24.,16.],[40.,32.]]])
        cache=self.cache(xy)
        target=torch.randn(1,2,8,8,2,generator=torch.Generator().manual_seed(43))
        expected=target.clone()
        for edge,(a,b) in enumerate([(301,302),(302,301)]):
            for y,x,dst,coefficient in cache.observations(a,b,(8,8)):
                expected[0,edge,y,x]+=coefficient*(torch.as_tensor(dst,dtype=target.dtype)-expected[0,edge,y,x])
        video=Video()
        install_static_targets(video,cache,{0:301,1:302},self.root/'vectorized.jsonl')
        result=video.ba(target,torch.ones_like(target),torch.ones(2),torch.tensor([0,1]),torch.tensor([1,0]))
        self.assertTrue(torch.equal(result[0],expected))

    def test_cache_key_preserves_feature_geometry_and_direction(self):
        cache=self.cache()
        forward=cache.observations(301,302,(8,8))
        self.assertIs(forward,cache.observations(301,302,(8,8)))
        self.assertNotEqual(forward[0][:2],cache.observations(302,301,(8,8))[0][:2])
        self.assertEqual(cache.observations(301,302,(2,2)),[])


if __name__=='__main__':unittest.main()

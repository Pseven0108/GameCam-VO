"""Exercise the actual adapter on synthetic correspondences, not a copied formula."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'experiments/TASK010-A/scripts')]
import task010_fusion_v2 as fusion


class FakeCache:
    score=.2
    def __init__(self,name,model):self.model=model
    def get(self,fid,device):return torch.full((24,32),self.score,device=device)


class AdapterStateContracts(unittest.TestCase):
    def execute(self,method,score=.2,u=.5):
        calls=[]
        def native(target,weight,eta,ii,jj,*args,**kwargs):
            calls.append((target,weight,eta,ii,jj,args,kwargs));return 'native-result'
        video=SimpleNamespace(ba=native,timestamp=torch.tensor([0.,1.]),down_scale=8,
            uncertainties=torch.full((2,3,4),u),_task010_phase='FRONTEND_LOCAL')
        d={'name':'synthetic_not_real_data','rgb_ids':[101,102],'hw':[24,32]}
        y,x=torch.meshgrid(torch.arange(3),torch.arange(4),indexing='ij')
        target=torch.stack([x,y],-1).float()[None,None]
        weight=torch.linspace(.1,1,24).reshape(1,1,3,4,2)
        eta=torch.ones(1,3,4);ii=torch.tensor([0]);jj=torch.tensor([1])
        values=[target,weight,eta,ii,jj,video.uncertainties,video.timestamp]
        copies=[x.clone() for x in values];FakeCache.score=score
        with tempfile.TemporaryDirectory(dir='D:/aaa/tmp/gamecam-vo') as temp:
            with patch.object(fusion,'ScoreCache',FakeCache):
                fusion.install_fusion(video,d,method,Path(temp)/'calls.jsonl')
                answer=video.ba(target,weight,eta,ii,jj,motion_only=True)
            log=json.loads((Path(temp)/'calls.jsonl').read_text())
        for original,before in zip(values,copies):self.assertTrue(torch.equal(original,before))
        self.assertIs(calls[0][0],target);self.assertIs(calls[0][2],eta)
        self.assertIs(calls[0][3],ii);self.assertIs(calls[0][4],jj)
        self.assertTrue(calls[0][6]['motion_only']);self.assertEqual(answer,'native-result')
        return weight,calls[0][1],log

    def test_actual_neutral_adapter_leaves_weights_equal(self):
        before,after,log=self.execute('neutral',.2)
        self.assertTrue(torch.equal(before,after));self.assertEqual(log['neutral_fraction'],1)
    def test_actual_high_score_gate_floor(self):
        before,after,log=self.execute('gmos',1.)
        torch.testing.assert_close(after,before*.25,rtol=0,atol=0)
    def test_full_geomotion_adapter_same_contract(self):
        before,after,log=self.execute('geomotion_full',1.)
        torch.testing.assert_close(after,before*.25,rtol=0,atol=0)
    def test_missing_geometry_is_neutral(self):
        before,after,log=self.execute('geometry',1.)
        self.assertTrue(torch.equal(before,after));self.assertEqual(log['neutral_fraction'],1)
    def test_fusion_requires_independent_geometry(self):
        before,after,log=self.execute('fusion',1.)
        self.assertTrue(torch.equal(before,after))
    def test_legacy_mean_matches_actual_legacy_total(self):
        before,a,_=self.execute('legacy',.2)
        _,b,_=self.execute('legacy_mean',.2)
        torch.testing.assert_close(a,b,rtol=1e-6,atol=1e-7)
    def test_cpu_test_did_not_initialize_cuda(self):self.assertFalse(torch.cuda.is_initialized())


if __name__=='__main__':unittest.main(verbosity=2)

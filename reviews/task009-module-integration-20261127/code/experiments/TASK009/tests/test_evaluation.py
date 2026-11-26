import unittest
import numpy as np
from experiments.TASK009.scripts.evaluate_trajectories import alignment,score


class EvaluationContract(unittest.TestCase):
    def test_known_sim3_and_rotation(self):
        rng=np.random.default_rng(9)
        truth=np.repeat(np.eye(4)[None],32,axis=0)
        truth[:,:3,3]=np.cumsum(rng.normal(size=(32,3)),axis=0)
        angle=.4;r=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
        estimate=truth.copy();estimate[:,:3,:3]=r.T@truth[:,:3,:3]
        estimate[:,:3,3]=(truth[:,:3,3]-[2,3,4])@r/2.5
        metrics,aligned,error=score(estimate,truth,np.arange(301,333))
        self.assertAlmostEqual(metrics['sim3_scale'],2.5,places=11)
        np.testing.assert_allclose(aligned,truth,atol=2e-14)
        self.assertLess(metrics['sim3_ate_game_units'],1e-12)
        self.assertLess(metrics['rpe_translation_offset15_game_units'],1e-12)

    def test_constant_translation_cannot_receive_finite_scale(self):
        with self.assertRaises(ValueError):alignment(np.zeros((32,3)),np.ones((32,3)))


if __name__=='__main__':unittest.main()

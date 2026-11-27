"""Known transformed trajectories verify units, global scale and RPE conventions."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('frozen_scorer',ROOT/'experiments/TASK009/scripts/evaluate_trajectories.py')
metric=importlib.util.module_from_spec(spec);spec.loader.exec_module(metric)


class MetricInvariants(unittest.TestCase):
    def reference(self):
        t=np.linspace(0,2,32);p=np.tile(np.eye(4),(32,1,1))
        p[:,:3,3]=np.c_[t,np.sin(2*t),np.cos(3*t)]
        p[:,:3,:3]=Rotation.from_euler('y',t).as_matrix()
        return p,np.arange(1001,1033)
    def test_exact_reference_has_zero_errors(self):
        truth,ids=self.reference();r,_,_=metric.score(truth,truth,ids)
        self.assertLess(r['sim3_ate_game_units'],1e-12)
        self.assertLess(r['rpe_translation_offset15_game_units'],1e-12)
    def test_one_global_similarity_recovers_entire_shape(self):
        truth,ids=self.reference();rot=Rotation.from_euler('xyz',[.4,-.2,.7]).as_matrix()
        estimate=metric.transform(truth,2.,rot,np.array([3.,-4.,1.]))
        r,_,_=metric.score(estimate,truth,ids)
        self.assertAlmostEqual(r['sim3_scale'],.5,places=12)
        self.assertLess(r['sim3_ate_game_units'],1e-12)
        self.assertLess(r['rpe_translation_offset5_game_units'],1e-12)
        self.assertLess(r['rpe_rotation_offset5_deg'],1e-5)
        self.assertGreater(r['se3_ate_game_units'],.1)
    def test_collapsed_translation_is_not_false_pass(self):
        truth,ids=self.reference();estimate=truth.copy();estimate[:,:3,3]=0
        with self.assertRaisesRegex(ValueError,'No estimated translation'):metric.score(estimate,truth,ids)


if __name__=='__main__':unittest.main(verbosity=2)

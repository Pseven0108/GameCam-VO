"""Independent linear-system equivalence and epipolar observability boundary."""
import sys
from pathlib import Path
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/TASK010-A/scripts'))
from schur_gate_counterexample import solve
from flow_geometry import sampson_error


class AlgebraLimits(unittest.TestCase):
    def test_schur_equals_full_block_solve(self):
        for gate in [1.,.94,.25]:
            self.assertLess(solve(gate,.5,.1,1e-4)['block_vs_Schur_max_abs'],1e-12)
    def test_uniform_gate_without_fixed_prior_is_invariant(self):
        a=solve(1,0,0,1e-4);b=solve(.25,0,0,1e-4)
        np.testing.assert_allclose(a['dx'],b['dx'],rtol=1e-12,atol=1e-12)
    def test_fixed_prior_breaks_invariance(self):
        a=solve(1,.5,.1,1e-4);b=solve(.25,.5,.1,1e-4)
        self.assertGreater(np.linalg.norm(np.array(a['dx'])-b['dx']),1e-5)
    def test_independent_along_epipolar_motion_is_unobservable(self):
        F=np.array([[0.,0.,0.],[0.,0.,-1.],[0.,1.,0.]])
        yy,xx=np.mgrid[:8,:8];source=np.stack([xx,yy],-1).astype(float)
        target=source+[2,0];target[2:6,2:6,0]+=8  # known synthetic independent motion
        np.testing.assert_array_equal(sampson_error(F,source,target),0)


if __name__=='__main__':unittest.main(verbosity=2)

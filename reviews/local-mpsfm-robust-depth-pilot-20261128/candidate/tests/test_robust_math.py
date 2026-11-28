import json,pathlib,sys,unittest
import numpy as np
TASK=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(TASK/'src'))
from robust_math import terms,quadratic,surrogate

class MathTests(unittest.TestCase):
    def test_gradient_finite_difference(self):
        for dm in [.001,.1,1.,20.]:
            for r in [-2.,-.3,0.,.02,.1,1.,5.]:
                d=dm*(1+r);h=max(dm*1e-5,1e-10)
                x=terms(1,0,.1,dm,d,.37)
                f=lambda z:terms(1,0,.1,dm,z,.37)['objective']
                np.testing.assert_allclose((f(d+h)-f(d-h))/(2*h),x['gradient'],atol=1e-11,rtol=2e-7)
    def test_q_range(self):
        x=terms(1,0,.3,1,np.linspace(-50,50,1001),1)
        self.assertTrue(((x['q']>0)&(x['q']<=1)).all())
    def test_zero_residual_native_curvature(self):
        x=terms(2,3,.7,1,1,.4);c,b=quadratic(2,3,.7,1,1,.4)
        self.assertEqual(float(x['C']),float(c));self.assertEqual(float(x['b']),float(b))
    def test_zero_strength_d0(self):
        x=terms(2,3,.7,1,200,0);self.assertEqual(float(x['C']),2.7);self.assertEqual(float(x['b']),3.)
    def test_missing_prior_retains_eta(self):
        x=terms(2,3,.7,0,200,1);self.assertEqual(float(x['C']),2.7);self.assertEqual(float(x['b']),3.)
    def test_no_eta_leakage_under_robustification(self):
        a=np.linspace(0,1,31);x=terms(2,3,.7,1,200,a)
        np.testing.assert_allclose(x['damping'],(1-a)*.7,atol=0,rtol=0)
    def test_outlier_influence_bounded(self):
        r=np.geomspace(1e-6,1e6,1000);x=terms(1,0,1,1,1+r,1)
        self.assertLessEqual(float(np.max(abs(x['gradient']))),.01*.1/2+1e-14)
    def test_symmetry(self):
        for r in [.01,.1,1,4]:
            a=terms(1,0,.1,1,1+r,1);b=terms(1,0,.1,1,1-r,1)
            np.testing.assert_allclose(a['q'],b['q']);np.testing.assert_allclose(a['gradient'],-b['gradient'])
    def test_majorizer_global_bound(self):
        for at in [.03,.4,1.,2.,10.]:
            v=np.linspace(-10,20,1001);f=terms(1,0,.1,1,v,1)['objective']
            self.assertTrue(np.all(surrogate(v,at,1)>=f-1e-12))
    def test_majorizer_tangent(self):
        for at in [-2.,0.,1.,10.]:
            np.testing.assert_allclose(surrogate(at,at,1),terms(1,0,.1,1,at,1)['objective'],atol=1e-14)
    def test_schur_joint_system(self):
        rng=np.random.default_rng(43);J=rng.normal(size=(50,11));H=J.T@J+np.eye(11);E=H[:4,4:];A=H[:4,:4]
        # Dense positive depth diagonal, matching DROID-W's independent depths.
        Cd=np.diag(np.diag(H[4:,4:]));v=rng.normal(size=4);b=rng.normal(size=7)
        Q=np.diag(1/np.diag(Cd));S=A-E@Q@E.T;damp=.1+.001*np.diag(S)
        dx=np.linalg.solve(S+np.diag(damp),v-E@Q@b);dz=Q@(b-E.T@dx)
        joint=np.block([[A+np.diag(damp),E],[E.T,Cd]])
        np.testing.assert_allclose(np.r_[dx,dz],np.linalg.solve(joint,np.r_[v,b]),rtol=1e-12,atol=1e-12)
    def test_units_scale(self):
        x=terms(0,0,0,2,3,1);y=terms(0,0,0,20,30,1)
        np.testing.assert_allclose(x['q'],y['q']);np.testing.assert_allclose(y['gradient'],10*x['gradient'])
    def test_scale_is_fixed_official_source(self):
        p=json.loads((TASK/'configs/PROTOCOL.json').read_text());self.assertEqual(p['robust_relative_scale'],.1)
    def test_no_new_parameter_search(self):
        p=json.loads((TASK/'configs/PROTOCOL.json').read_text());self.assertEqual(p['arms'],['BASE','A5','ROBUST','ROBUST_A5'])
    def test_reweighting_changes_each_iteration(self):
        first=terms(0,0,0,1,2,1)['q'];second=terms(0,0,0,1,1.01,1)['q'];self.assertGreater(second,first)
    def test_invalid_scale(self):
        for c in [0,-1,np.nan,np.inf]:
            with self.assertRaises(ValueError):terms(0,0,0,1,1,1,relative_scale=c)
    def test_invalid_coeff(self):
        for a in [-.1,1.1,np.nan]:
            with self.assertRaises(ValueError):terms(0,0,0,1,1,a)
    def test_tiny_prior_finite(self):
        x=terms(1,0,1,1e-20,2e-20,.5)
        self.assertTrue(all(np.isfinite(v).all() for v in x.values()))
    def test_negative_disparity_diagnosed_not_silently_clamped(self):
        x=terms(1,0,1,.1,-.2,1);self.assertGreater(float(x['b']),0)
    def test_native_baseline_limit(self):
        for a in [0,.3,1]:
            x=terms(1,2,.7,1,2,a,relative_scale=1e12);c,b=quadratic(1,2,.7,1,2,a)
            np.testing.assert_allclose(x['C'],c,rtol=1e-13);np.testing.assert_allclose(x['b'],b,rtol=1e-13)
    def test_prior_alone_does_not_bound_update(self):
        # An important limitation: bounded influence does not bound dz when
        # the same q rescales both scalar curvature and gradient.
        x=terms(0,0,0,1,20,1)
        np.testing.assert_allclose(20+x['b']/x['C'],1,atol=1e-13)
    def test_naive_product_changes_damping(self):
        x=terms(1,0,.4,1,5,.6)
        naive=(1-.6*x['q'])*.4
        self.assertGreater(float(naive),float(x['damping']))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(MathTests)
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    (TASK/'reports/CPU_MATH_TESTS.json').write_text(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful()),indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())

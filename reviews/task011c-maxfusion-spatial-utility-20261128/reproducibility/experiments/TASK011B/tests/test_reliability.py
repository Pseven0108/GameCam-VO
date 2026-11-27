"""Executable contracts for numerical masks, ranking and native prior algebra."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from reliability import validity,disagreements,percentile,build_scores,prior_terms,geometry_depth_covariance,geometry_need,fast_risk_coverage


class CurveTest(unittest.TestCase):
    def test_frozen_reference_equivalence_with_ties(self):
        from common import load_metrics
        m=load_metrics();rng=np.random.default_rng(11)
        for size in (1,2,100,1500):
            e=rng.random(size);s=rng.integers(0,9,size)
            old=m.risk_coverage(e,s);new=fast_risk_coverage(e,s)
            for k in ('coverage','risk','oracle','random','AUSE_raw_AbsRel','AURG_raw_AbsRel'):
                np.testing.assert_allclose(new[k],old[k],rtol=1e-12,atol=1e-12)

    def test_constant_score_random_curve(self):
        e=np.arange(100,dtype=float)
        rc=fast_risk_coverage(e,np.ones(100))
        np.testing.assert_allclose(rc['risk'],np.full(101,e.mean()),rtol=1e-14,atol=1e-14)

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):fast_risk_coverage([],[])


class ValidityTest(unittest.TestCase):
    def setUp(self):
        self.a=np.array([[0.,1e-8,-1.,np.nan,np.inf,2.,3.,4.]])
        self.b=np.array([[1.,1.,1.,1.,1.,0.,3.,4.]])
        self.tt=np.array([[False,True,True,False,False,False,False,True]])
        self.mask=validity(self.a,self.b,self.tt)

    def test_native_zero_near_zero_negative_nan_inf_rejected(self):
        np.testing.assert_array_equal(self.mask['native_valid'],[[0,0,0,0,0,1,1,1]])

    def test_boolean_mask_statistics(self):
        from audit_and_evaluate import stats
        row=stats(np.array([True,False],dtype=bool))
        self.assertEqual(row['q0.5'],.5)
        self.assertEqual(row['dtype'],'bool')

    def test_original_false_preserved(self):
        self.assertFalse(self.mask['pair_valid'][0,6])

    def test_pair_requires_both_depths(self):
        np.testing.assert_array_equal(self.mask['pair_valid'],[[0,0,0,0,0,0,0,1]])

    def test_original_mask_type_rejected(self):
        with self.assertRaises(ValueError):validity(self.a,self.b,self.tt.astype(int))

    def test_grid_mismatch_rejected(self):
        with self.assertRaises(ValueError):validity(self.a,self.b[:,:2],self.tt)

    def test_invalid_lower_bound_rejected(self):
        with self.assertRaises(ValueError):validity(self.a,self.b,self.tt,-1)

    def test_invalid_pair_scores_are_undefined(self):
        for v in disagreements(self.a,self.b,self.mask['pair_valid']).values():
            self.assertTrue(np.isnan(v[~self.mask['pair_valid']]).all())

    def test_no_invalid_zero_disagreement(self):
        v=disagreements(self.a,self.b,self.mask['pair_valid'])['SymmetricRelative']
        self.assertTrue(np.isnan(v[0,0]))

    def test_no_positive_pair_fabricated(self):
        with self.assertRaises(ValueError):disagreements(self.a,self.b,np.ones_like(self.tt))

    def test_confidence_missing_rejects_native_prior(self):
        c=np.ones_like(self.a);c[0,7]=np.nan
        s=build_scores(c,disagreements(self.a,self.b,self.mask['pair_valid'])['SymmetricRelative'],self.mask)
        self.assertFalse(s['NativeOnly']['prior_allowed'][0,7])


class DisagreementTest(unittest.TestCase):
    def setUp(self):
        self.a=np.array([[1e-5,1.,100.,2.]])
        self.b=np.array([[100.,2.,1.,2.]])
        self.m=np.ones(self.a.shape,dtype=bool)

    def test_symmetric_bounded(self):
        x=disagreements(self.a,self.b,self.m)['SymmetricRelative']
        self.assertTrue(((x>=0)&(x<1)).all())

    def test_symmetric_exchange(self):
        x=disagreements(self.a,self.b,self.m)['SymmetricRelative']
        y=disagreements(self.b,self.a,self.m)['SymmetricRelative']
        np.testing.assert_array_equal(x,y)

    def test_log_exchange(self):
        x=disagreements(self.a,self.b,self.m)['LogDisagreement']
        y=disagreements(self.b,self.a,self.m)['LogDisagreement']
        np.testing.assert_array_equal(x,y)

    def test_absolute_native_units(self):
        np.testing.assert_array_equal(disagreements(self.a,self.b,self.m)['AbsoluteDifference'],abs(self.a-self.b))

    def test_log_not_same_as_symmetric(self):
        v=disagreements(self.a,self.b,self.m)
        self.assertFalse(np.allclose(v['LogDisagreement'],v['SymmetricRelative']))

    def test_identity_all_four_zero(self):
        for v in disagreements(self.a,self.a,self.m).values():np.testing.assert_array_equal(v,np.zeros_like(v))

    def test_legacy_extreme_remains_auditable(self):
        self.assertGreater(disagreements(self.a,self.b,self.m)['LegacyRelative'].max(),1e6)

    def test_invalid_epsilon(self):
        with self.assertRaises(ValueError):disagreements(self.a,self.b,self.m,0)


class FusionTest(unittest.TestCase):
    def setUp(self):
        self.a=np.array([[1.,2.,0.,1.]])
        self.b=np.array([[1.2,0.,1.,1.1]])
        self.m=validity(self.a,self.b,np.array([[True,False,False,True]]))
        self.c=np.array([[.1,.7,100.,.9]])
        self.t=disagreements(self.a,self.b,self.m['pair_valid'])['SymmetricRelative']
        self.s=build_scores(self.c,self.t,self.m)

    def test_fallback_equals_native_risk(self):
        self.assertEqual(self.s['ValidityAwareFusion']['risk'][0,1],self.s['NativeOnly']['risk'][0,1])

    def test_invalid_native_all_methods_zero_prior(self):
        for v in self.s.values():self.assertEqual(v['reliability'][0,2],0)

    def test_invalid_native_all_methods_rejection(self):
        for v in self.s.values():self.assertEqual(v['policy_diagnostic_risk'][0,2],1)

    def test_pair_fusion_never_includes_missing_tta(self):
        self.assertTrue(np.isnan(self.s['RankFusion']['risk'][0,1]))
        self.assertFalse(self.s['RankFusion']['prior_allowed'][0,1])

    def test_rank_fusion_exact_equal_weight(self):
        m=self.m['pair_valid'];n=self.s['NativeOnly']['risk'];f=self.s['FlipOnly']['risk']
        np.testing.assert_array_equal(self.s['RankFusion']['risk'][m],.5*n[m]+.5*f[m])

    def test_max_fusion(self):
        m=self.m['pair_valid'];n=self.s['NativeOnly']['risk'];f=self.s['FlipOnly']['risk']
        np.testing.assert_array_equal(self.s['MaxFusion']['risk'][m],np.maximum(n[m],f[m]))

    def test_fusion_weight_endpoints(self):
        s=build_scores(self.c,self.t,self.m,1.)
        m=self.m['pair_valid']
        np.testing.assert_array_equal(s['RankFusion']['risk'][m],s['NativeOnly']['risk'][m])

    def test_reliability_range(self):
        for v in self.s.values():self.assertTrue(((v['reliability']>=0)&(v['reliability']<=1)).all())

    def test_no_gt_argument_in_scores(self):
        import inspect
        self.assertNotIn('gt',inspect.signature(build_scores).parameters)

    def test_empty_pair_still_native_fallback(self):
        m=validity(np.ones((2,2)),np.zeros((2,2)),np.zeros((2,2),bool))
        s=build_scores(np.ones((2,2)),np.full((2,2),np.nan),m)
        self.assertTrue(s['ValidityAwareFusion']['native_fallback'].all())
        self.assertFalse(s['FlipOnly']['prior_allowed'].any())

    def test_ties_have_no_pixel_index_advantage(self):
        np.testing.assert_array_equal(percentile(np.ones((2,3)),np.ones((2,3),bool)),np.full((2,3),.5))


class PriorAndGeometryTest(unittest.TestCase):
    def setUp(self):
        self.cg=np.array([.3,.5,0.]);self.bg=np.array([.2,-.5,.1]);self.eta=np.array([.1,.2,.3])
        self.d=np.array([1.,3.,1.]);self.dm=np.array([2.,0.,3.]);self.alpha=.01

    def test_D0_exact(self):
        c,b=prior_terms(self.cg,self.bg,self.eta,self.d,self.dm,np.zeros(3))
        np.testing.assert_array_equal(c,self.cg+self.eta);np.testing.assert_array_equal(b,self.bg)

    def test_D1_original_mask_and_gradient(self):
        c,b=prior_terms(self.cg,self.bg,self.eta,self.d,self.dm,np.ones(3))
        m=self.dm>0
        np.testing.assert_array_equal(c,self.cg+m*.01+(1-m)*self.eta)
        np.testing.assert_array_equal(b,self.bg-m*.01*(self.d-self.dm))

    def test_fractional_is_convex_endpoint_blend(self):
        c0,b0=prior_terms(self.cg,self.bg,self.eta,self.d,self.dm,np.zeros(3))
        c1,b1=prior_terms(self.cg,self.bg,self.eta,self.d,self.dm,np.ones(3))
        c,b=prior_terms(self.cg,self.bg,self.eta,self.d,self.dm,np.full(3,.3))
        np.testing.assert_allclose(c,.7*c0+.3*c1,rtol=1e-14,atol=1e-14)
        np.testing.assert_allclose(b,.7*b0+.3*b1,rtol=1e-14,atol=1e-14)

    def test_invalid_coefficient_rejected(self):
        with self.assertRaises(ValueError):prior_terms(self.cg,self.bg,self.eta,self.d,self.dm,np.full(3,1.01))

    def test_gradient_energy_sign(self):
        _,b=prior_terms(self.cg,self.bg,self.eta,self.d,self.dm,np.ones(3))
        expected=-.01*(self.d-self.dm)*(self.dm>0)
        np.testing.assert_allclose(b-self.bg,expected)

    def test_full_joint_inverse_matches_block_diagonal(self):
        rng=np.random.default_rng(43);E=rng.normal(size=(6,12))*.05;cg=np.ones(12);eta=np.full(12,.1)
        A=np.eye(6)*2+E@E.T
        v,hd=geometry_depth_covariance(A,E,cg,eta,chunk=3)
        h0=A-(E/(cg+eta))@E.T
        damp=np.diag(.1+1e-4*np.diag(h0))
        joint=np.block([[A+damp,E],[E.T,np.diag(cg+eta)]])
        np.testing.assert_allclose(v,np.diag(np.linalg.inv(joint))[6:],rtol=1e-12,atol=1e-12)

    def test_geometry_chunk_invariance(self):
        rng=np.random.default_rng(2);E=rng.normal(size=(6,11))*.01;A=np.eye(6)
        a,_=geometry_depth_covariance(A,E,np.ones(11),np.ones(11),chunk=1)
        b,_=geometry_depth_covariance(A,E,np.ones(11),np.ones(11),chunk=11)
        np.testing.assert_allclose(a,b,rtol=1e-14,atol=1e-14)

    def test_geometry_need_monotone(self):
        d=np.ones(5);m=np.ones(5,bool)
        a,_=geometry_need(np.ones(5),d,m);b,_=geometry_need(np.full(5,4.),d,m)
        self.assertTrue(0<a<b<1)

    def test_geometry_has_no_depth_prior_argument(self):
        import inspect
        names=inspect.signature(geometry_depth_covariance).parameters
        self.assertNotIn('mono_disparity',names);self.assertNotIn('confidence',names)

    def test_nonpositive_geometry_curvature_rejected(self):
        with self.assertRaises(ValueError):geometry_depth_covariance(np.eye(2),np.zeros((2,3)),np.zeros(3),np.zeros(3))


if __name__=='__main__':unittest.main(verbosity=2)

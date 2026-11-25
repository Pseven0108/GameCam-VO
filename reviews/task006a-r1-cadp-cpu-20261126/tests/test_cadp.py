import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
import traceback
import unittest
from dataclasses import asdict
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from cadp_cpu import (DomainError, NumericalError, Geometry, factor_schur, prior_off,
    full_covariance, blocked_diagonal, covariance_block, joint_precision,
    native_depth_terms, cadp_depth_terms, solve_ba_step, stable_sigmoid,
    frame_statistics, broadcast_frame_rho, assemble_cross_blocks,native_guarded_backsub,build_adaptive_plan)
from synthetic import make_fixture


class CovarianceTests(unittest.TestCase):
    def test_zero_pose_has_exact_conditional_variance(self):
        fac=prior_off(Geometry(np.empty((0,0)),np.empty((0,3)),np.array([0.,1.,2.]),np.ones(3)))
        np.testing.assert_array_equal(full_covariance(fac),np.diag(1/np.array([1.,2.,3.])))
        np.testing.assert_array_equal(blocked_diagonal(fac,1),fac.q)

    def test_zero_coupling_diagonal(self):
        fac=prior_off(Geometry(np.eye(2),np.zeros((2,4)),np.ones(4),np.ones(4)))
        np.testing.assert_array_equal(full_covariance(fac),np.eye(4)*0.5)

    def test_one_dimensional_analytic(self):
        fac=prior_off(Geometry(np.array([[2.]]),np.array([[0.5]]),np.array([1.]),np.array([0.1])))
        expected=1/1.1+(0.5/1.1)**2/(2-0.25/1.1+0.1+1e-4*(2-0.25/1.1))
        self.assertAlmostEqual(full_covariance(fac)[0,0],expected,places=14)

    def test_conditional_only_is_not_marginal(self):
        fac=prior_off(make_fixture().geometry)
        self.assertTrue(np.all(blocked_diagonal(fac)>fac.q))

    def test_post_schur_damping_not_pre_schur(self):
        g=make_fixture().geometry
        fac=prior_off(g,lm=0.5,ep=0.1)
        wrong=g.A+np.diag(0.1+0.5*np.diag(g.A))-(g.E*fac.q)@g.E.T
        self.assertGreater(np.max(np.abs(wrong-fac.Hd)),1e-3)
        np.testing.assert_allclose(fac.Hd,fac.H+np.diag(0.1+0.5*np.diag(fac.H)),atol=0,rtol=0)

    def test_prior_off_api_has_no_mono_or_rho(self):
        import inspect
        self.assertEqual(set(inspect.signature(prior_off).parameters),{'geometry','lm','ep','max_condition'})
        x=make_fixture()
        before=blocked_diagonal(prior_off(x.geometry))
        x.mono_disparity[:]=1e12
        x.bg[:]=-1e9
        np.testing.assert_array_equal(before,blocked_diagonal(prior_off(x.geometry)))

    def test_selected_covariance_block_preserves_cross_frame_terms(self):
        fac=prior_off(make_fixture().geometry)
        cov=full_covariance(fac)
        rows=np.array([0,5,17,17]); cols=np.array([2,5,19])
        np.testing.assert_allclose(covariance_block(fac,rows,cols),cov[np.ix_(rows,cols)],rtol=2e-13,atol=1e-13)

    def test_pseudoinverse_not_silently_used(self):
        with self.assertRaises(NumericalError):
            prior_off(Geometry(np.zeros((2,2)),np.zeros((2,1)),np.ones(1),np.ones(1)),ep=0,lm=0)

    def test_empty_depth_rejected(self):
        with self.assertRaises(DomainError):
            prior_off(Geometry(np.eye(1),np.zeros((1,0)),np.array([]),np.array([])))

    def test_zero_depth_curvature_rejected(self):
        with self.assertRaises(DomainError):
            prior_off(Geometry(np.eye(1),np.zeros((1,2)),np.zeros(2),np.zeros(2)))

    def test_near_singular_guard(self):
        with self.assertRaises(NumericalError):
            factor_schur(np.diag([1.,1e-14]),np.zeros((2,1)),np.ones(1),ep=0,lm=0)

    def test_gauge_regularization_is_not_identifiability(self):
        g=Geometry(np.zeros((2,2)),np.zeros((2,3)),np.zeros(3),np.ones(3)*0.001)
        fac=prior_off(g)
        np.testing.assert_allclose(fac.Hd,np.eye(2)*0.1)
        self.assertEqual(np.linalg.matrix_rank(fac.H),0)

    def test_weight_and_eta_units_affect_uncertainty(self):
        g=make_fixture().geometry
        a=blocked_diagonal(prior_off(g))
        b=blocked_diagonal(prior_off(Geometry(g.A*100,g.E*100,g.Cg*100,g.eta)))
        self.assertGreater(np.max(np.abs(a-b)),1.0)

    def test_disparity_reparameterization_with_consistent_units(self):
        g=make_fixture().geometry; s=7.0
        base=blocked_diagonal(prior_off(g))
        transformed=blocked_diagonal(prior_off(Geometry(g.A,g.E/s,g.Cg/s**2,g.eta/s**2)))
        np.testing.assert_allclose(transformed,base*s**2,rtol=3e-13,atol=1e-12)

    def test_native_depth_backsub_index_zero_is_distinct_operator(self):
        x=make_fixture(npose=6)
        c,b=native_depth_terms(x.geometry.Cg,x.bg,x.geometry.eta,x.disparity,x.mono_disparity,False)
        dx,dz,fac=solve_ba_step(x.geometry,x.bx,b,c)
        # All six coordinates of first free pose excluded by native ix<=0 branch.
        native_like=native_guarded_backsub(x.geometry.E,fac.q,b,dx)
        self.assertGreater(np.max(np.abs(native_like-dz)),1e-6)
        np.testing.assert_allclose(joint_precision(fac)@np.r_[dx,dz],np.r_[x.bx,b],rtol=1e-12,atol=1e-12)

    def test_depth_marginal_diagonal_not_identified_by_Schur_alone(self):
        # With equal q, an orthogonal mixing of E's columns keeps E Q E^T
        # unchanged but redistributes per-depth marginal variances.
        a=np.array([[3.,0.2],[0.2,2.]])
        e=np.array([[0.3,0.1],[0.2,0.05]])
        rotation=np.array([[1.,1.],[-1.,1.]])/np.sqrt(2)
        f1=prior_off(Geometry(a,e,np.ones(2),np.ones(2)*0.1))
        f2=prior_off(Geometry(a,e@rotation,np.ones(2),np.ones(2)*0.1))
        np.testing.assert_allclose(f1.H,f2.H,atol=1e-15,rtol=1e-15)
        self.assertGreater(np.max(np.abs(blocked_diagonal(f1)-blocked_diagonal(f2))),1e-3)

    def test_full_covariance_cap_is_enforced(self):
        f=prior_off(Geometry(np.eye(1),np.zeros((1,2049)),np.ones(2049),np.ones(2049)))
        with self.assertRaises(DomainError): full_covariance(f)


def covariance_case(seed,npose,ndepth,block):
    def test(self):
        x=make_fixture(seed,npose,ndepth)
        fac=prior_off(x.geometry)
        full=full_covariance(fac)
        precision=joint_precision(fac)
        direct=np.linalg.solve(precision,np.eye(precision.shape[0]))[npose:,npose:]
        sparse=spsolve(csc_matrix(precision),csc_matrix(np.eye(precision.shape[0]))).toarray()[npose:,npose:]
        np.testing.assert_allclose(full,direct,rtol=3e-12,atol=2e-12)
        np.testing.assert_allclose(full,sparse,rtol=3e-12,atol=2e-12)
        np.testing.assert_allclose(blocked_diagonal(fac,block),np.diag(direct),rtol=3e-12,atol=2e-12)
        self.assertGreater(np.linalg.eigvalsh(full)[0],0)
    return test


for i,(p,d,b) in enumerate([(1,1,1),(2,7,1),(6,24,5),(12,37,16),(18,72,13),(24,96,128)]):
    for seed in (43,44,45):
        setattr(CovarianceTests,f'test_joint_inverse_oracle_p{p}_d{d}_seed{seed}',covariance_case(seed,p,d,b))


class EndpointTests(unittest.TestCase):
    def test_gamma_zero_is_not_D0(self):
        x=make_fixture(); g=x.geometry
        c0,b0=native_depth_terms(g.Cg,x.bg,g.eta,x.disparity,x.mono_disparity,False)
        c,b=native_depth_terms(g.Cg,x.bg,g.eta,x.disparity,x.mono_disparity,True,alpha=0)
        self.assertGreater(np.max(np.abs(c-c0)),1e-5)
        np.testing.assert_array_equal(b,b0)

    def test_eta_is_replaced_not_added(self):
        x=make_fixture(); g=x.geometry
        c,_=cadp_depth_terms(g.Cg,x.bg,g.eta,x.disparity,x.mono_disparity,0.5)
        wrong=g.Cg+g.eta+(x.mono_disparity>0)*0.5*0.01
        self.assertGreater(np.max(np.abs(c-wrong)),1e-4)

    def test_curvature_can_decrease_with_rho(self):
        x=make_fixture(); g=x.geometry
        eta=np.full_like(g.eta,0.1)
        c0,_=cadp_depth_terms(g.Cg,x.bg,eta,x.disparity,x.mono_disparity,0)
        c1,_=cadp_depth_terms(g.Cg,x.bg,eta,x.disparity,x.mono_disparity,1)
        self.assertTrue(np.all(c1[x.mono_disparity>0]<c0[x.mono_disparity>0]))

    def test_zero_or_negative_mono_never_activates_prior(self):
        x=make_fixture(); g=x.geometry; dm=np.zeros_like(x.disparity)-2
        c,b=cadp_depth_terms(g.Cg,x.bg,g.eta,x.disparity,dm,0.7)
        np.testing.assert_array_equal(c,g.Cg+g.eta)
        np.testing.assert_array_equal(b,x.bg)

    def test_intermediate_rho_not_linear_pose_interpolation(self):
        x=make_fixture(); g=x.geometry; poses=[]
        for rho in (0.,0.5,1.):
            c,b=cadp_depth_terms(g.Cg,x.bg,g.eta,x.disparity,x.mono_disparity,rho)
            dx,dz,_=solve_ba_step(g,x.bx,b,c)
            poses.append(dx)
        self.assertGreater(np.linalg.norm(poses[1]-(poses[0]+poses[2])*0.5),1e-6)

    def test_frame_weights_broadcast_only_by_actual_frame_ID(self):
        stats=frame_statistics(np.ones(4),np.ones(4),np.array([7,9,7,9]),np.ones(4,dtype=int),np.zeros(4),k=2,tau=1)
        pixels=broadcast_frame_rho(stats,np.array([9,7,9,7]))
        np.testing.assert_allclose(pixels,0.5,atol=1e-6)


def endpoint_case(seed,rho,eta_scale):
    def test(self):
        x=make_fixture(seed,eta_scale=eta_scale); g=x.geometry
        original=[v.copy() for v in (g.A,g.E,g.Cg,g.eta,x.disparity,x.mono_disparity)]
        c,b=cadp_depth_terms(g.Cg,x.bg,g.eta,x.disparity,x.mono_disparity,rho)
        cn,bn=native_depth_terms(g.Cg,x.bg,g.eta,x.disparity,x.mono_disparity,bool(rho))
        np.testing.assert_array_equal(c,cn)
        np.testing.assert_array_equal(b,bn)
        dx,dz,fac=solve_ba_step(g,x.bx,b,c)
        dxn,dzn,fn=solve_ba_step(g,x.bx,bn,cn)
        np.testing.assert_array_equal(dx,dxn)
        np.testing.assert_array_equal(dz,dzn)
        guard=native_guarded_backsub(g.E,fac.q,b,dx,pose_dim=1 if dx.size%6 else 6)
        guardn=native_guarded_backsub(g.E,fn.q,bn,dxn,pose_dim=1 if dx.size%6 else 6)
        np.testing.assert_array_equal(guard,guardn)
        direct=np.linalg.solve(joint_precision(fn),np.r_[x.bx,bn])
        np.testing.assert_allclose(np.r_[dx,dz],direct,rtol=2e-12,atol=2e-12)
        for before,after in zip(original,(g.A,g.E,g.Cg,g.eta,x.disparity,x.mono_disparity)):
            np.testing.assert_array_equal(before,after)
    return test


for seed in (43,44,45):
    for rho in (0.,1.):
        for eta in (0.001,0.1):
            setattr(EndpointTests,f'test_endpoint_seed{seed}_rho{int(rho)}_eta{str(eta).replace(".","_")}',endpoint_case(seed,rho,eta))


class UncertaintyTests(unittest.TestCase):
    def test_end_to_end_adaptive_plan_has_no_prior_input(self):
        x=make_fixture()
        plan=build_adaptive_plan(x.geometry,x.disparity,x.frame_ids,x.observation_count,k=2,tau=2)
        for dm in (x.mono_disparity,x.mono_disparity*10):
            c,b=cadp_depth_terms(x.geometry.Cg,x.bg,x.geometry.eta,x.disparity,dm,plan.pixel_rho)
            dx,dz,_=solve_ba_step(x.geometry,x.bx,b,c)
            self.assertTrue(np.isfinite(np.r_[dx,dz]).all())
        import inspect
        self.assertNotIn('mono_disparity',inspect.signature(build_adaptive_plan).parameters)

    def test_rho_plan_is_readonly_between_iterations(self):
        x=make_fixture()
        plan=build_adaptive_plan(x.geometry,x.disparity,x.frame_ids,x.observation_count,k=2,tau=2)
        with self.assertRaises(ValueError): plan.pixel_rho[0]=0
        with self.assertRaises(ValueError): plan.variance[0]=0

    def test_adaptive_plan_no_empty_frame_fallback(self):
        x=make_fixture()
        with self.assertRaises(DomainError):
            build_adaptive_plan(x.geometry,x.disparity,x.frame_ids,np.zeros_like(x.observation_count),k=2,tau=2)

    def test_plan_block_size_does_not_change_rho(self):
        x=make_fixture()
        a=build_adaptive_plan(x.geometry,x.disparity,x.frame_ids,x.observation_count,k=2,tau=2,block_size=1)
        b=build_adaptive_plan(x.geometry,x.disparity,x.frame_ids,x.observation_count,k=2,tau=2,block_size=128)
        np.testing.assert_allclose(a.pixel_rho,b.pixel_rho,rtol=3e-13,atol=3e-13)

    def test_sigmoid_monotonic_and_half_at_tau(self):
        x=np.linspace(0,10,1001)
        y=stable_sigmoid(x,3,5)
        self.assertTrue(np.all(np.diff(y)>0))
        self.assertEqual(y[500],0.5)

    def test_sigmoid_overflow_safe(self):
        np.testing.assert_array_equal(stable_sigmoid(np.array([-1e308,0,1e308]),1e308,0),[0,0.5,1])

    def test_even_median_is_explicit_midpoint(self):
        s=frame_statistics(np.array([1.,9.]),np.ones(2),np.zeros(2,dtype=int),np.ones(2,dtype=int),np.ones(2),k=1,tau=0)
        self.assertAlmostEqual(s[0].uncertainty,2/(1+1e-6))
        self.assertNotAlmostEqual(s[0].uncertainty,1/(1+1e-6))

    def test_empty_frame_no_fallback(self):
        s=frame_statistics(np.ones(3),np.array([0.,np.nan,-1]),np.zeros(3,dtype=int),np.ones(3,dtype=int),np.zeros(3),k=1,tau=1)
        self.assertIsNone(s[0].rho)
        self.assertEqual(s[0].status,'NO_VALID_PIXELS')
        with self.assertRaises(DomainError): broadcast_frame_rho(s,np.array([0]))

    def test_observed_zero_Cg_included(self):
        s=frame_statistics(np.array([1.,10000.,10000.]),np.ones(3),np.zeros(3,dtype=int),np.ones(3,dtype=int),np.array([1.,0.,0.]),k=1,tau=1)
        self.assertEqual(s[0].valid_pixels,3)
        self.assertEqual(s[0].weak_curvature_pixels_included,2)
        self.assertGreater(s[0].uncertainty,99.)

    def test_unobserved_count_is_reported(self):
        s=frame_statistics(np.ones(4),np.ones(4),np.zeros(4,dtype=int),np.array([1,0,0,1]),np.zeros(4),k=1,tau=1)
        self.assertEqual(s[0].unsupported_pixels,2)
        self.assertEqual(s[0].valid_pixels,2)

    def test_insufficient_support_returns_none(self):
        s=frame_statistics(np.ones(2),np.ones(2),np.zeros(2,dtype=int),np.array([1,0]),np.zeros(2),k=1,tau=1,min_valid=2)
        self.assertEqual(s[0].status,'INSUFFICIENT_SUPPORT')
        self.assertIsNone(s[0].rho)

    def test_disparity_sign_invalid_not_abs_repaired(self):
        s=frame_statistics(np.ones(4),np.array([-1,0,np.inf,2.]),np.zeros(4,dtype=int),np.ones(4,dtype=int),np.zeros(4),k=1,tau=1)
        self.assertEqual(s[0].valid_pixels,1)
        self.assertEqual(s[0].nonpositive_or_nonfinite_disparity,3)

    def test_outlier_robustness_has_majority_limit(self):
        ids=np.zeros(5,dtype=int); d=np.ones(5); counts=np.ones(5,dtype=int)
        a=frame_statistics(np.array([1.,1.,1.,1e8,1e8]),d,ids,counts,np.zeros(5),k=1,tau=1)[0]
        b=frame_statistics(np.array([1.,1.,1e8,1e8,1e8]),d,ids,counts,np.zeros(5),k=1,tau=1)[0]
        self.assertLess(a.uncertainty,2)
        self.assertGreater(b.uncertainty,1000)

    def test_no_prior_truth_claim_for_high_rho(self):
        # rho has no access to mono accuracy: equally high weights for good/bad priors.
        x=make_fixture(); fac=prior_off(x.geometry)
        stats=frame_statistics(blocked_diagonal(fac),x.disparity,x.frame_ids,x.observation_count,x.geometry.Cg,k=1,tau=1)
        r=broadcast_frame_rho(stats,x.frame_ids)
        c1,b1=cadp_depth_terms(x.geometry.Cg,x.bg,x.geometry.eta,x.disparity,x.disparity,r)
        c2,b2=cadp_depth_terms(x.geometry.Cg,x.bg,x.geometry.eta,x.disparity,x.disparity*100,r)
        np.testing.assert_array_equal(c1,c2)
        self.assertGreater(np.linalg.norm(b1-b2),1)

    def test_high_uncertainty_can_weight_an_inaccurate_prior(self):
        g=Geometry(np.array([[0.002]]),np.array([[0.003]]),np.array([0.005]),np.array([0.001]))
        v=blocked_diagonal(prior_off(g))
        stat=frame_statistics(v,np.ones(1),np.array([0]),np.array([2]),g.Cg,k=2,tau=2)[0]
        self.assertGreater(stat.rho,0.999)
        values=[]
        for rho,dm in ((0.,8.),(stat.rho,8.)):
            c,b=cadp_depth_terms(g.Cg,np.array([-0.0004]),g.eta,np.ones(1),np.array([dm]),rho)
            dx,dz,_=solve_ba_step(g,np.array([-0.0002]),b,c)
            values.append(abs(float(dx[0])-0.2))
        self.assertGreater(values[1],values[0])

    def test_uncertainty_scalar_not_native_U_state(self):
        import inspect
        self.assertNotIn('uncertainties',inspect.signature(frame_statistics).parameters)
        self.assertNotIn('affine_weights',inspect.signature(frame_statistics).parameters)


class IndexTests(unittest.TestCase):
    def test_duplicate_rows_accumulate_and_K_not_P(self):
        rows=np.array([[[1.,2.]],[[3.,4.]],[[5.,6.]],[[7.,8.]]])
        e=assemble_cross_blocks(rows,np.array([2,2,3,1]),np.array([0,0,4,5]),np.array([0,4,5]),2,4,pose_dim=1)
        np.testing.assert_array_equal(e,[[4,6,0,0,0,0],[0,0,5,6,0,0]])

    def test_exclusive_t1_is_fail_closed(self):
        with self.assertRaises(DomainError):
            assemble_cross_blocks(np.ones((1,6,2)),np.array([4]),np.array([0]),np.array([0]),2,4)

    def test_missing_source_ID_stops(self):
        with self.assertRaises(DomainError):
            assemble_cross_blocks(np.ones((1,6,2)),np.array([2]),np.array([9]),np.array([0]),2,4)

    def test_no_E_reconstruction_from_pose_Schur(self):
        x=make_fixture(); fac=prior_off(x.geometry)
        e2=x.geometry.E.copy(); e2[:,0]*=-1
        fac2=prior_off(Geometry(x.geometry.A,e2,x.geometry.Cg,x.geometry.eta))
        np.testing.assert_array_equal(fac.H,fac2.H)
        self.assertGreater(np.max(np.abs(full_covariance(fac)-full_covariance(fac2))),1e-6)

    def test_six_DOF_exclusive_boundary_with_realistic_ID_range(self):
        rng=np.random.default_rng(1729)
        target=np.array([52,53,52,51,54,53])
        source=np.array([49,52,49,53,52,51])
        depth=np.array([49,51,52,53])
        jp=rng.normal(size=(6,6))
        jd=rng.normal(size=(6,3))
        rows=np.einsum('ra,rp->rap',jp,jd)
        with self.assertRaises(DomainError):
            assemble_cross_blocks(rows,target,source,depth,52,54)

    def test_six_DOF_repeated_ID_aggregation_and_permutation(self):
        rng=np.random.default_rng(1729)
        target=np.array([52,53,52,51,55,53])
        source=np.array([49,52,49,53,52,51])
        depth=np.array([49,51,52,53])
        jp=rng.normal(size=(6,6)); jd=rng.normal(size=(6,3))
        rows=np.einsum('ra,rp->rap',jp,jd)
        e=assemble_cross_blocks(rows,target,source,depth,52,54)
        big_pose=np.zeros((6,12)); big_depth=np.zeros((6,12))
        for r in range(6):
            if 52<=target[r]<54: big_pose[r,6*(target[r]-52):6*(target[r]-51)]=jp[r]
            start=3*int(np.flatnonzero(depth==source[r])[0])
            big_depth[r,start:start+3]=jd[r]
        np.testing.assert_allclose(e,big_pose.T@big_depth,rtol=1e-14,atol=1e-14)
        order=np.array([5,3,1,4,0,2])
        perm=assemble_cross_blocks(rows[order],target[order],source[order],depth,52,54)
        np.testing.assert_allclose(e,perm,rtol=1e-14,atol=1e-14)


class InvalidInputTests(unittest.TestCase):
    def test_wrong_shape(self):
        g=make_fixture().geometry
        with self.assertRaises(DomainError): prior_off(Geometry(g.A,g.E[:,:-1],g.Cg,g.eta))

    def test_asymmetric_A(self):
        g=make_fixture().geometry; a=g.A.copy(); a[0,1]+=0.1
        with self.assertRaises(DomainError): prior_off(Geometry(a,g.E,g.Cg,g.eta))

    def test_negative_eta(self):
        g=make_fixture().geometry
        with self.assertRaises(DomainError): prior_off(Geometry(g.A,g.E,g.Cg,-g.eta))

    def test_inconsistent_indefinite_geometry(self):
        with self.assertRaises(NumericalError):
            factor_schur(np.eye(2),np.ones((2,1))*10,np.ones(1))

    def test_invalid_rho(self):
        x=make_fixture(); g=x.geometry
        for rho in (-0.1,1.1,np.nan,np.inf):
            with self.subTest(rho=str(rho)),self.assertRaises(DomainError):
                cadp_depth_terms(g.Cg,x.bg,g.eta,x.disparity,x.mono_disparity,rho)

    def test_nonfinite_prior_is_not_zero_times_nan_fixed(self):
        x=make_fixture(); g=x.geometry; dm=x.mono_disparity.copy(); dm[0]=np.nan
        with self.assertRaises(DomainError): cadp_depth_terms(g.Cg,x.bg,g.eta,x.disparity,dm,0)

    def test_invalid_sigmoid_parameters(self):
        for k,tau in ((0,1),(-1,1),(np.nan,1),(1,np.inf)):
            with self.subTest(k=str(k),tau=str(tau)),self.assertRaises(DomainError): stable_sigmoid(np.array([1]),k,tau)

    def test_invalid_block_sizes(self):
        fac=prior_off(make_fixture().geometry)
        for b in (0,-1,1.5,True):
            with self.subTest(b=b),self.assertRaises(DomainError): blocked_diagonal(fac,b)

    def test_invalid_covariance_indices(self):
        fac=prior_off(make_fixture().geometry)
        with self.assertRaises(DomainError): covariance_block(fac,np.array([-1]),np.array([1]))

    def test_invalid_variance_not_clamped(self):
        with self.assertRaises(DomainError):
            frame_statistics(np.array([-1.]),np.ones(1),np.array([0]),np.array([1]),np.ones(1),k=1,tau=1)


def invalid_nonfinite_case(value,field):
    def test(self):
        g=make_fixture().geometry
        values={n:getattr(g,n).copy() for n in ('A','E','Cg','eta')}
        values[field].flat[0]=value
        with self.assertRaises(DomainError): prior_off(Geometry(**values))
    return test


for name,value in [('nan',np.nan),('pinf',np.inf),('ninf',-np.inf)]:
    for field in ('A','E','Cg','eta'):
        setattr(InvalidInputTests,f'test_{field}_{name}_rejected',invalid_nonfinite_case(value,field))


class RecordingResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.records=[]
    def startTest(self,test):
        super().startTest(test); self.started=time.perf_counter(); self.current_status='PASS'; self.detail=None
    def addFailure(self,test,err):
        self.current_status='FAIL'; self.detail=self._exc_info_to_string(err,test); super().addFailure(test,err)
    def addError(self,test,err):
        self.current_status='ERROR'; self.detail=self._exc_info_to_string(err,test); super().addError(test,err)
    def addSubTest(self,test,subtest,err):
        if err is not None:
            self.current_status='FAIL'; self.detail=self._exc_info_to_string(err,test)
        super().addSubTest(test,subtest,err)
    def stopTest(self,test):
        self.records.append({'id':test.id(),'status':self.current_status,'elapsed_seconds':time.perf_counter()-self.started,'detail':self.detail})
        super().stopTest(test)


def run_suite(out_dir):
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    buf=io.StringIO()
    runner=unittest.TextTestRunner(stream=buf,verbosity=2,resultclass=RecordingResult)
    result=runner.run(suite)
    (out_dir/'unit_tests.stdout.txt').write_text(buf.getvalue(),encoding='utf-8')
    report={'tests_run':result.testsRun,'passed':sum(x['status']=='PASS' for x in result.records),
            'failures':len(result.failures),'errors':len(result.errors),'success':result.wasSuccessful(),
            'records':result.records,'seed_scope':'Synthetic RNG seeds 43/44/45; no training or model RNG',
            'torch_imported':'torch' in sys.modules}
    (out_dir/'UNIT_TEST_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    unittest.main()

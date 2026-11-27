"""Numerical and failure-mode tests; synthetic inputs are never VO evidence."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
import unittest

import numpy as np

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK))
from uniform_control import (FORMAL_ARMS, MEAN_ATOL, arm_config, coefficient_map,
                             frozen, source_indices, timestamp_slots, uniform_for_call)


class UniformMathematics(unittest.TestCase):
    def setUp(self):
        self.a = np.array([[[.1,.9,.2],[.6,.7,.8]],[[.2,.3,.4],[.6,.8,.9]],
                           [[.9,.8,.7],[.3,.2,.1]]],dtype=np.float32)
        self.nv = np.ones_like(self.a,dtype=bool)
        self.dm = np.ones_like(self.a)
        self.ix = np.array([0,2],dtype=np.int64)

    def run_uniform(self):
        return uniform_for_call(self.a,self.nv,self.dm,self.ix)

    def test_mean_is_per_source_not_one_global_scalar(self):
        out,proof = self.run_uniform()
        self.assertNotEqual(out[0,0,0],out[2,0,0])
        for slot in self.ix:
            np.testing.assert_array_equal(out[slot],np.full((2,3),self.a[slot].mean(dtype=np.float32)))
        self.assertLessEqual(proof['eligible_mean_difference'],MEAN_ATOL)

    def test_only_actual_native_sources_are_active(self):
        out,_ = self.run_uniform()
        self.assertEqual(np.count_nonzero(out[1]),0)

    def test_prior_mask_changes_the_mean(self):
        self.dm[0,0,:] = 0
        out,proof = self.run_uniform()
        self.assertEqual(out[0,0,0],0)
        self.assertAlmostEqual(float(out[0,1,0]),float(self.a[0,1].mean()),places=6)
        self.assertEqual(proof['frames'][0]['eligible_pixels'],3)

    def test_changed_BA_call_recomputes_mean(self):
        out,_ = self.run_uniform()
        self.dm[0,0,1] = 0
        other,_ = self.run_uniform()
        self.assertNotEqual(out[0,0,0],other[0,0,0])

    def test_native_valid_is_intersected_with_positive_mono(self):
        self.nv[0,0,0] = False
        self.a[0,0,0] = 0
        out,_ = self.run_uniform()
        self.assertEqual(out[0,0,0],0)
        self.assertAlmostEqual(float(out[0,0,1]),float(self.a[0][self.nv[0]].mean()),places=6)

    def test_zero_and_negative_native_prior_are_not_enabled(self):
        self.dm[0,0] = [0,-1,-.1]
        out,_ = self.run_uniform()
        np.testing.assert_array_equal(out[0,0],0)

    def test_empty_source_support_has_no_invented_mean(self):
        self.dm[0] = 0
        out,proof = self.run_uniform()
        self.assertFalse(out[0].any())
        self.assertIsNone(proof['frames'][0]['A7_mean'])
        self.assertTrue(proof['frames'][0]['empty_support'])

    def test_all_empty_support_has_no_nan(self):
        self.dm[:] = 0
        out,proof = self.run_uniform()
        self.assertTrue(np.isfinite(out).all())
        self.assertEqual(proof['eligible_pixels'],0)

    def test_inputs_are_not_mutated(self):
        before = [v.copy() for v in (self.a,self.nv,self.dm,self.ix)]
        self.run_uniform()
        for a,b in zip(before,(self.a,self.nv,self.dm,self.ix)):
            np.testing.assert_array_equal(a,b)

    def test_positive_support_and_mask_are_identical(self):
        self.dm[2,1,1] = 0
        out,_ = self.run_uniform()
        for slot in self.ix:
            np.testing.assert_array_equal(out[slot]>0,(self.a[slot]>0)&self.nv[slot]&(self.dm[slot]>0))

    def test_zero_r5_inside_M_stops_instead_of_changing_support(self):
        self.a[0,0,0] = 0
        with self.assertRaisesRegex(ValueError,'positive support'):
            self.run_uniform()

    def test_malformed_A5_native_valid_mask_stops(self):
        self.nv[0,0,0] = False
        with self.assertRaisesRegex(ValueError,'invalid native depth'):
            self.run_uniform()

    def test_nonfinite_mono_stops_without_repair(self):
        for value in (float('nan'),float('inf'),-float('inf')):
            with self.subTest(value=value):
                self.dm[0,0,0] = value
                with self.assertRaises(ValueError):
                    self.run_uniform()

    def test_nonfinite_or_unbounded_A5_stops(self):
        for value in (float('nan'),float('inf'),-.1,1.1):
            with self.subTest(value=value):
                self.a[0,0,0] = value
                with self.assertRaises(ValueError):
                    self.run_uniform()

    def test_float64_cannot_silently_change_formal_precision(self):
        with self.assertRaises(ValueError):
            uniform_for_call(self.a.astype(np.float64),self.nv,self.dm,self.ix)

    def test_nonboolean_native_valid_is_rejected(self):
        with self.assertRaises(ValueError):
            uniform_for_call(self.a,self.nv.astype(int),self.dm,self.ix)

    def test_grid_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            uniform_for_call(self.a,self.nv[:,:,:2],self.dm,self.ix)

    def test_duplicate_or_invalid_source_indices_stop(self):
        for ix in (np.array([0,0]),np.array([-1,2]),np.array([0,3]),np.array([0.,2.]),np.array([],dtype=int)):
            with self.subTest(ix=ix.tolist()),self.assertRaises(ValueError):
                uniform_for_call(self.a,self.nv,self.dm,ix)

    def test_full_native_45x80_grid_FP32_mean_contract(self):
        rng = np.random.default_rng(43)
        a = rng.uniform(1e-7,1,(17,45,80)).astype(np.float32)
        nv = rng.random(a.shape)>.12
        a[~nv] = 0
        dm = np.where(rng.random(a.shape)>.15,1,0).astype(np.float32)
        out,proof = uniform_for_call(a,nv,dm,np.arange(17))
        self.assertEqual(out.dtype,np.float32)
        self.assertLess(proof['dense_mean_difference'],1e-6)
        self.assertTrue(all(x['absolute_mean_difference']<=1e-6 for x in proof['frames']))

    def test_alpha_mean_matching_does_not_assert_identical_gradient(self):
        out,_ = self.run_uniform()
        mask = self.dm[0]>0
        self.assertAlmostEqual(float(self.a[0][mask].sum()),float(out[0][mask].sum()),places=5)
        residual = np.arange(6).reshape(2,3)
        self.assertNotAlmostEqual(float((self.a[0]*residual).sum()),float((out[0]*residual).sum()))


class SourceIdentity(unittest.TestCase):
    def test_native_union_includes_graph_sources_before_t0(self):
        np.testing.assert_array_equal(source_indices(np.array([0,4,4]),2,4,5),[0,2,3,4])

    def test_native_union_never_uses_target_jj(self):
        np.testing.assert_array_equal(source_indices(np.array([1]),2,3,4),[1,2])

    def test_bad_native_bounds_stop(self):
        for bounds in ((0,6,5),(3,2,5),(1,1,5),(-1,2,5),(0.,2,5),(False,2,5)):
            with self.subTest(bounds=bounds),self.assertRaises(ValueError):
                source_indices(np.array([1]),*bounds)

    def test_noninteger_graph_and_out_of_range_stop(self):
        for ii in (np.array([1.]),np.array([[1]]),np.array([-1]),np.array([4])):
            with self.subTest(ii=ii.tolist()),self.assertRaises(ValueError):
                source_indices(ii,0,2,4)

    def test_timestamp_to_cache_mapping_uses_exact_input_identity(self):
        np.testing.assert_array_equal(timestamp_slots(np.array([12.,3.,18.]),set(range(64))),[12,3,18])

    def test_duplicate_fractional_nan_or_unknown_timestamp_stops(self):
        for ts in ([0,0],[1.5,2],[float('nan')],[64],[-1]):
            with self.subTest(ts=ts),self.assertRaises(ValueError):
                timestamp_slots(np.array(ts),set(range(64)))


class FrozenRiskRegression(unittest.TestCase):
    def setUp(self):
        self.d = np.array([[0,np.nan,np.inf,-1,1,2,3,4]],dtype=float)
        self.f = np.array([[1,1,1,1,0,2.2,6,4.1]],dtype=float)
        self.c = np.array([[.1,.2,.3,.4,.6,.7,-2,4]],dtype=float)
        self.t = np.array([[False,False,False,False,False,True,True,True]])

    def test_five_arms_only_no_geometry(self):
        self.assertEqual(FORMAL_ARMS,('A0','A1','A4','A5','A7'))
        for arm in FORMAL_ARMS:
            self.assertFalse(arm_config(arm).GEOMETRY_NEED_ENABLE)
        for arm in ('A2','A3','A6'):
            with self.assertRaises(ValueError):arm_config(arm)

    def test_existing_configs_are_exact_not_retuned(self):
        for arm in FORMAL_ARMS[:-1]:
            self.assertEqual(asdict(arm_config(arm)),asdict(frozen().arm_config(arm)))

    def test_A7_cache_is_bitwise_A5_not_full_image_uniform(self):
        a,_ = coefficient_map(self.d,self.f,self.c,self.t,arm_config('A5'))
        b,proof = coefficient_map(self.d,self.f,self.c,self.t,arm_config('A7'))
        np.testing.assert_array_equal(a,b)
        self.assertGreater(np.std(b[0,4:]),0)
        self.assertTrue(proof['uniformization_deferred_until_actual_BA'])

    def test_old_arms_return_exact_frozen_coefficients(self):
        for arm in FORMAL_ARMS[:-1]:
            a,ma = coefficient_map(self.d,self.f,self.c,self.t,arm_config(arm))
            b,mb = frozen().coefficient_map(self.d,self.f,self.c,self.t,frozen().arm_config(arm))
            np.testing.assert_array_equal(a,b)
            self.assertEqual(ma,mb)

    def test_pair_invalid_retains_native_fallback_before_uniformization(self):
        native,_ = frozen().coefficient_map(self.d,self.f,self.c,self.t,frozen().arm_config('A2'))
        a,_ = coefficient_map(self.d,self.f,self.c,self.t,arm_config('A7'))
        self.assertEqual(a[0,4],native[0,4])

    def test_invalid_native_depths_remain_zero(self):
        a,_ = coefficient_map(self.d,self.f,self.c,self.t,arm_config('A7'))
        np.testing.assert_array_equal(a[0,:4],0)

    def test_A7_cannot_change_alpha_geometry_or_fusion(self):
        for update in ({'DEPTH_PRIOR_ALPHA':.001},{'GEOMETRY_NEED_ENABLE':True},
                       {'RELIABILITY_FUSION_WEIGHT':.9},{'TTA_VALIDITY_ENABLE':False}):
            with self.subTest(update=update),self.assertRaises(ValueError):
                replace(arm_config('A7'),**update).validate()

    def test_all_frozen_files_still_match_fixed_commit_lock(self):
        import hashlib
        lock = json.loads((TASK/'intake/INITIAL_ASSET_PROTECTION.json').read_text())
        root = TASK.parents[1]
        for record in lock['inherited']:
            self.assertEqual(hashlib.sha256((root/record['path']).read_bytes()).hexdigest(),record['sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)

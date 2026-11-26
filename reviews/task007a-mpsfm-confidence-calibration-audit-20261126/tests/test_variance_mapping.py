"""Software contract checks on synthetic scalars/grids, never substitute GT."""
import pathlib
import sys
import unittest

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "code"))
from mpsfm_variance import mp_sfm_raw_variance as raw, mp_sfm_single_prior_variance as scene


class VarianceMappingTests(unittest.TestCase):
    def test_exact_reference_formula(self):
        np.testing.assert_array_equal(raw([2., 4., 8.], [0., .5, .75]), [4., 4., 4.])

    def test_negative_confidence_is_clipped_not_sigmoid(self):
        self.assertEqual(float(raw(3., -2.)), 9.)

    def test_superunit_confidence_raw_zero_is_exposed(self):
        self.assertEqual(float(raw(3., 6.)), 0.)

    def test_confidence_one_raw_zero(self):
        self.assertEqual(float(raw(3., 1.)), 0.)

    def test_relative_variance_invariant_to_depth(self):
        np.testing.assert_array_equal(raw([2., 8.], [.5, .5]) / np.square([2., 8.]), [.25, .25])

    def test_variance_scales_quadratically_with_depth_unit(self):
        np.testing.assert_allclose(raw([20., 30.], [.3, .7]), 100 * raw([2., 3.], [.3, .7]))

    def test_reference_relative_floor_after_saturation(self):
        self.assertAlmostEqual(float(scene(10., 2.)), (10 * .0263)**2)

    def test_reference_absolute_floor(self):
        self.assertEqual(float(scene(.1, 1.)), .02**2)

    def test_prior_multiplier_is_on_std_not_variance(self):
        self.assertAlmostEqual(float(scene(10., .5)), (3.33 * 5)**2)

    def test_std_multiplier_order(self):
        self.assertAlmostEqual(float(scene(10., .5, std_multiplier=2)), 4 * float(scene(10., .5)))

    def test_max_std_before_final_multiplier(self):
        self.assertEqual(float(scene(10., .5, max_std=.1, std_multiplier=2)), .1**2 * 4)

    def test_float64(self):
        self.assertEqual(raw(np.ones((2, 3), dtype=np.float32), np.zeros((2, 3))).dtype, np.float64)

    def test_no_input_mutation(self):
        d = np.array([1., 4.]); c = np.array([-1., 2.])
        dc, cc = d.copy(), c.copy(); scene(d, c)
        np.testing.assert_array_equal(d, dc); np.testing.assert_array_equal(c, cc)

    def test_broadcasting_rejected(self):
        with self.assertRaises(ValueError): raw(np.ones((2, 3)), np.ones((1, 3)))

    def test_empty_rejected(self):
        with self.assertRaises(ValueError): raw([], [])

    def test_bad_prediction_is_not_masked(self):
        for d in [0., -1., np.nan, np.inf]:
            with self.subTest(d=d), self.assertRaises(ValueError): raw(d, .5)

    def test_bad_confidence_rejected(self):
        for c in [np.nan, np.inf, -np.inf]:
            with self.subTest(c=c), self.assertRaises(ValueError): raw(1., c)

    def test_invalid_parameters_rejected(self):
        for key in ["prior_std_multiplier", "depth_uncertainty", "inherent_noise", "std_multiplier", "max_std"]:
            with self.subTest(key=key), self.assertRaises(ValueError): scene(1., .5, **{key: -1.})

    def test_inconsistent_bounds_rejected(self):
        with self.assertRaises(ValueError): scene(1., .5, max_std=.001)

    def test_monotonic_before_clipping(self):
        self.assertTrue((np.diff(raw(np.full(11, 10.), np.linspace(0, 1, 11))) <= 0).all())

    def test_scene_variance_is_positive_for_reference_defaults(self):
        self.assertTrue((scene(np.logspace(-9, 9, 25), np.linspace(-3, 7, 25)) > 0).all())

    def test_clipping_order_cannot_be_swapped_with_interpolation(self):
        # A two-neighbor average represents a bilinear midpoint. Upstream clips
        # AFTER restoration: clip(mean([-1,1]))=0 vs mean(clip([-1,1]))=.5.
        self.assertEqual(float(raw(2., np.mean([-1., 1.]))), 4.)
        self.assertEqual(float(raw(2., np.mean(np.clip([-1., 1.], 0, 1)))), 1.)


if __name__ == "__main__":
    unittest.main()

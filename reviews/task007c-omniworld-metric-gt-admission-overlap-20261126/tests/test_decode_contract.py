import pathlib
import sys
import unittest
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "code"))
from decode_contract import decode


class DecodeTests(unittest.TestCase):
    def test_source_near_boundary(self):
        _, m = decode(np.array([[0, 98, 99, 100]], np.uint16))
        np.testing.assert_array_equal(m, [[False, False, True, True]])
    def test_source_far_boundary(self):
        _, m = decode(np.array([[65499, 65500, 65501, 65535]], np.uint16))
        np.testing.assert_array_equal(m, [[True, True, False, False]])
    def test_invalid_sentinel_not_metric_scaled(self):
        d, _ = decode(np.array([[0, 65535]], np.uint16), 200.)
        np.testing.assert_array_equal(d, [[-1., -1.]])
    def test_scale_applies_to_valid_only(self):
        a = np.array([[1000, 2000]], np.uint16); x, m = decode(a); y, _ = decode(a, 2.)
        np.testing.assert_array_equal(y[m], x[m] * 2)
    def test_monotonic_relative_depth(self):
        a = np.linspace(99, 65500, 1000, dtype=np.uint16)[None]
        d, m = decode(a); self.assertTrue(m.all()); self.assertTrue((np.diff(d) > 0).all())
    def test_no_uint16_overflow(self):
        d, m = decode(np.array([[65500]], np.uint16), 400.)
        self.assertTrue(np.isfinite(d).all() and m.all())
    def test_float32_output(self):
        self.assertEqual(decode(np.array([[1000]], np.uint16))[0].dtype, np.float32)
    def test_boolean_mask(self):
        self.assertEqual(decode(np.array([[1000]], np.uint16))[1].dtype, np.bool_)
    def test_wrong_dtype_stops(self):
        with self.assertRaises(ValueError): decode(np.array([[100]], np.uint8))
    def test_wrong_shape_stops(self):
        with self.assertRaises(ValueError): decode(np.ones((2, 3, 3), np.uint16))
    def test_empty_stops(self):
        with self.assertRaises(ValueError): decode(np.empty((0, 0), np.uint16))
    def test_bad_scales_stop(self):
        for s in [0, -1, np.nan, np.inf]:
            with self.subTest(scale=s), self.assertRaises(ValueError): decode(np.ones((1, 1), np.uint16), s)
    def test_no_input_mutation(self):
        a = np.array([[0, 100, 65535]], np.uint16); before = a.copy(); decode(a, 3.)
        np.testing.assert_array_equal(a, before)
    def test_65500_not_removed_by_extra_percentile(self):
        self.assertTrue(decode(np.array([[100, 65500]], np.uint16))[1].all())
    def test_large_finite_depth_not_automatic_GT_accuracy(self):
        d, m = decode(np.array([[65500]], np.uint16), 400.)
        self.assertGreater(float(d[0, 0]), 60000.); self.assertTrue(m[0, 0])
    def test_not_plain_divide_by_1000(self):
        d, _ = decode(np.array([[32768]], np.uint16))
        self.assertNotAlmostEqual(float(d[0, 0]), 32.768, places=2)


if __name__ == "__main__": unittest.main()

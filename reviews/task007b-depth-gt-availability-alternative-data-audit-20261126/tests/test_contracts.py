import pathlib
import sys
import unittest
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "code"))
from data_contracts import member_modality, viper_member, scale_invariant_log_shape_error as shape, vkitti_scene_partition as split


class Contracts(unittest.TestCase):
    def test_dense_rgb_is_not_depth(self):
        self.assertEqual(member_modality("train/img/001/001_00002.jpg"), "RGB_IMAGE")

    def test_depth_in_arbitrary_zip_name(self):
        self.assertEqual(member_modality("val/depth/007/007_00001.pfm"), "POTENTIAL_DEPTH_REQUIRES_PROVENANCE")

    def test_unknown_png_kept_ambiguous(self):
        self.assertEqual(member_modality("unrecognized/data.png"), "AMBIGUOUS_ARRAY_OR_IMAGE_REQUIRES_INSPECTION")

    def test_flow_not_depth(self):
        self.assertEqual(member_modality("train/flow/030/030_00010.npz"), "OPTICAL_FLOW_NOT_DEPTH_GT")

    def test_exr_is_candidate_not_auto_gt(self):
        self.assertEqual(member_modality("anything/0001.exr"), "POTENTIAL_DEPTH_REQUIRES_PROVENANCE")

    def test_camera_not_pixel_gt(self):
        self.assertEqual(member_modality("train/camera/001.csv"), "CAMERA_OR_TABLE_NOT_PIXEL_DEPTH")

    def test_viper_layout_in_nested_archive(self):
        self.assertTrue(viper_member("nested/train/img/001/001_00001.jpg"))

    def test_windows_separator(self):
        self.assertTrue(viper_member("train\\img\\001\\001_00001.jpg"))

    def test_unrelated_dataset_not_viper(self):
        self.assertFalse(viper_member("Scene01/clone/frames/depth/Camera_0/depth_00000.png"))

    def test_shape_unit_invariance(self):
        g = np.array([1., 2., 4., 8.]); p = np.array([1.2, 1.8, 5., 7.]); m = np.ones(4, bool)
        self.assertAlmostEqual(shape(p, g, m)["rms_log_shape"], shape(p * 7, g * 91, m)["rms_log_shape"], places=13)

    def test_global_scale_error_is_deliberately_removed(self):
        g = np.array([1., 2., 4.]); m = np.ones(3, bool)
        self.assertLess(shape(g * 100, g, m)["rms_log_shape"], 1e-14)

    def test_bad_prediction_not_silently_masked(self):
        with self.assertRaises(ValueError): shape([1., 0.], [1., 2.], np.ones(2, bool))

    def test_bad_gt_inside_mask_stops(self):
        with self.assertRaises(ValueError): shape([1., 2.], [1., np.inf], np.ones(2, bool))

    def test_mask_required_boolean(self):
        with self.assertRaises(ValueError): shape([1.], [1.], [1])

    def test_empty_mask_stops(self):
        with self.assertRaises(ValueError): shape([1.], [1.], [False])

    def test_base_scene_grouping(self):
        self.assertEqual(split("Scene01"), "CALIBRATION")
        self.assertEqual(split("01"), "CALIBRATION")
        self.assertEqual(split("20"), "EVALUATION")

    def test_groups_do_not_overlap(self):
        groups = {k: split(k) for k in ["01", "02", "06", "18", "20"]}
        self.assertEqual(list(groups.values()).count("CALIBRATION"), 2)
        self.assertEqual(list(groups.values()).count("EVALUATION"), 2)

    def test_unknown_scene_stops(self):
        with self.assertRaises(ValueError): split("99")


if __name__ == "__main__": unittest.main()

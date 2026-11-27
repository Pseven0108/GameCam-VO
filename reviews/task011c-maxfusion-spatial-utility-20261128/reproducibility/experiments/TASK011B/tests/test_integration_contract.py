"""CPU integration contracts. These do not certify CUDA numerical equivalence."""
import importlib.util
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

TASK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK/'CADP_DR_EXPERIMENTAL_BRANCH'))
from controller import arm_config,should_intervene,coefficient_map,MAIN,PASSTHROUGH,ARMS


class StageContract(unittest.TestCase):
    def test_all_seven_configs_consistent(self):
        for arm in ARMS:self.assertEqual(arm_config(arm).arm,arm)

    def test_disabled_original_no_intervention(self):
        self.assertFalse(should_intervene(arm_config('A0'),None,False,True))

    def test_missing_marker_stops(self):
        with self.assertRaises(RuntimeError):should_intervene(arm_config('A6'),None,False,True)

    def test_unknown_marker_stops(self):
        with self.assertRaises(RuntimeError):should_intervene(arm_config('A2'),'LOCAL_MAYBE',False,True)

    def test_motion_only_never_intervenes(self):
        for arm in ARMS:self.assertFalse(should_intervene(arm_config(arm),MAIN,True,True))

    def test_initialization_and_final_and_filler_unchanged(self):
        for arm in ARMS:
            for phase in PASSTHROUGH:self.assertFalse(should_intervene(arm_config(arm),phase,False,True))

    def test_native_final_depth_disabled_preserved(self):
        self.assertFalse(should_intervene(arm_config('A6'),MAIN,False,False))

    def test_main_loop_control(self):
        for arm in list(ARMS)[1:]:self.assertTrue(should_intervene(arm_config(arm),MAIN,False,True))

    def test_gamma_cannot_be_retuned(self):
        with self.assertRaises(ValueError):replace(arm_config('A6'),DEPTH_PRIOR_ALPHA=.001).validate()

    def test_matrix_arm_cannot_be_relabelled(self):
        with self.assertRaises(ValueError):replace(arm_config('A2'),GEOMETRY_NEED_ENABLE=True).validate()


class CoefficientContract(unittest.TestCase):
    def setUp(self):
        self.d=np.array([[0.,1.,2.,3.]])
        self.f=np.array([[1.,0.,2.5,3.1]])
        self.c=np.array([[20.,.8,.6,.9]])
        self.t=np.array([[False,False,True,True]])

    def test_A0_A1_native_endpoint_same(self):
        a,_=coefficient_map(self.d,self.f,self.c,self.t,arm_config('A0'))
        b,_=coefficient_map(self.d,self.f,self.c,self.t,arm_config('A1'))
        np.testing.assert_array_equal(a,b)

    def test_all_controlled_arms_disable_invalid_native(self):
        for arm in list(ARMS)[2:]:
            s,_=coefficient_map(self.d,self.f,self.c,self.t,arm_config(arm));self.assertEqual(s[0,0],0)

    def test_all_runtime_TTA_arms_fallback_to_native(self):
        baseline,_=coefficient_map(self.d,self.f,self.c,self.t,arm_config('A2'))
        for arm in ('A3','A4','A5','A6'):
            s,_=coefficient_map(self.d,self.f,self.c,self.t,arm_config(arm));self.assertEqual(s[0,1],baseline[0,1])

    def test_A4_A6_share_same_depth_reliability(self):
        a,_=coefficient_map(self.d,self.f,self.c,self.t,arm_config('A4'))
        b,_=coefficient_map(self.d,self.f,self.c,self.t,arm_config('A6'))
        np.testing.assert_array_equal(a,b)

    def test_all_coefficients_bounded(self):
        for arm in ARMS:
            s,_=coefficient_map(self.d,self.f,self.c,self.t,arm_config(arm))
            self.assertTrue(np.isfinite(s).all() and ((s>=0)&(s<=1)).all())


class NativeSourceContract(unittest.TestCase):
    def setUp(self):self.native=TASK/'CADP_DR_EXPERIMENTAL_BRANCH/native'

    def test_native_U_body_exact(self):
        a=(self.native/'upstream_droid_kernels.cu.txt').read_text().split('    if (enable_update_uncer)',1)[1].split('  return {dx, dz};',1)[0]
        b=(self.native/'droid_kernels.cu').read_text().split('    if (enable_update_uncer)',1)[1].split('  return {dx, dz, geometry_trace};',1)[0]
        self.assertEqual(a,b)

    def test_existing_kernels_and_solver_preserved(self):
        a=(self.native/'upstream_droid_kernels.cu.txt').read_text().split('std::vector<torch::Tensor> ba_cuda(',1)[0]
        b=(self.native/'droid_kernels.cu').read_text()
        self.assertTrue(b.startswith(a))

    def test_geometry_helper_no_monocular_prior_input(self):
        b=(self.native/'droid_kernels.cu').read_text().split('torch::Tensor task011b_geometry_statistics(',1)[1].split('std::vector<torch::Tensor> ba_cuda(',1)[0]
        for word in ('disps_sens','prior_strength','gamma_depth','Metric3D'):
            self.assertNotIn(word,b)

    def test_no_installed_module_replacement(self):
        p=json.loads((self.native.parent/'SOURCE_PROVENANCE.json').read_text())
        self.assertFalse(p['installed_extension_replaced'])
        self.assertEqual(p['endpoint_numeric_GPU_verification'],'PASS_REAL_FIRST_LOCAL_NATIVE_AMP_V2_CONTEXT_ONLY')
        receipt=TASK/p['endpoint_numeric_evidence']
        evidence=json.loads(receipt.read_text())
        self.assertEqual(evidence['status'],'PASS')
        self.assertEqual(evidence['input_sha256'],p['endpoint_input_sha256'])
        self.assertTrue(evidence['two_iterations_preserved'])
        self.assertTrue(evidence['U_native_update'])
        self.assertTrue(p['endpoint_certificate_not_global_native_determinism'])

    def test_real_GPU_not_claimed_by_CPU_contracts(self):
        self.assertNotIn('torch',sys.modules)


if __name__=='__main__':unittest.main(verbosity=2)

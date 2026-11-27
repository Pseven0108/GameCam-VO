"""Exercise the actual adapter with CPU torch tensors and stub BA backends.

This verifies signature/argument routing, never native CUDA numerical output.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import numpy as np
import torch

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TASK))
from uniform_control import (arm_config, frozen, install, source_indices,
                             torch_uniform_for_call, uniform_for_call)

droid_backends = None


def video_ba(self, *args):
    return droid_backends.ba(*args)


class ActualAdapterCPU(unittest.TestCase):
    def setUp(self):
        global droid_backends
        self.native_calls = []
        self.candidate_calls = []
        def native(*args):
            self.native_calls.append(args)
            return torch.zeros((1,6)),torch.zeros((1,6))
        def candidate(*args):
            self.candidate_calls.append(args)
            return torch.zeros((1,6)),torch.zeros((1,6)),torch.zeros((2,1,4))
        droid_backends = types.SimpleNamespace(ba=native)
        self.original_backend = droid_backends
        self.candidate = types.SimpleNamespace(ba=candidate)
        self.video = types.SimpleNamespace(ht=4,wd=6,slice_h=slice(0,None,2),slice_w=slice(0,None,2),
            disps=torch.ones((500,2,3)),device='cpu',counter=types.SimpleNamespace(value=4),
            timestamp=torch.tensor([12.,3.,18.,7.]),metric_depth_reg=True,
            _task011b_phase=frozen().MAIN)
        self.video.ba = types.MethodType(video_ba,self.video)
        rng = np.random.default_rng(45)
        self.fields = {i:rng.uniform(.01,.99,(4,6)) for i in range(64)}
        self.valids = {i:np.ones((4,6),dtype=bool) for i in range(64)}
        self.tmp = tempfile.TemporaryDirectory(dir='D:/aaa/tmp/gamecam-vo')
        self.log = Path(self.tmp.name)/'calls.jsonl'
        self.args = [torch.zeros(1) for _ in range(30)]
        self.args[1] = self.video.disps
        self.args[3] = torch.ones_like(self.video.disps)
        self.args[6] = torch.zeros_like(self.video.disps)
        self.args[11] = torch.tensor([0,2,2],dtype=torch.long)
        self.args[12] = torch.tensor([1,3,0],dtype=torch.long)
        self.args[13:16] = [1,3,2]
        self.args[20] = .01
        self.args[23] = False
        self.args[25:30] = [True,True,True,False,False]

    def tearDown(self):
        self.tmp.cleanup()
        self.assertFalse(torch.cuda.is_initialized())

    def attach(self,arm='A7'):
        return install(self.video,self.candidate,arm_config(arm),self.fields,self.log,
                       native_valid_by_timestamp=self.valids)

    def test_active_A7_forwards_30_original_arguments_by_identity(self):
        self.attach()
        self.video.ba(*self.args)
        self.assertEqual(len(self.native_calls),0)
        call = self.candidate_calls[0]
        self.assertEqual(len(call),33)
        for x,y in zip(call[:30],self.args):self.assertIs(x,y)
        self.assertEqual(call[-2:],(True,False))

    def test_native_U_UBA_iteration_and_weight_tensors_unchanged(self):
        self.attach()
        before = [v.clone() if torch.is_tensor(v) else v for v in self.args]
        self.video.ba(*self.args)
        for a,b in zip(self.args,before):
            if torch.is_tensor(a):self.assertTrue(torch.equal(a,b))
            else:self.assertEqual(a,b)
        receipt = json.loads(self.log.read_text())
        self.assertTrue(receipt['enable_update_uncer'])
        self.assertTrue(receipt['enable_udba'])
        self.assertEqual(receipt['iterations'],2)

    def test_source_union_and_timestamp_reordering_are_respected(self):
        self.attach()
        self.video.ba(*self.args)
        strength = self.candidate_calls[0][-3]
        for slot,ts in enumerate([12,3,18]):
            self.assertAlmostEqual(float(strength[slot,0,0]),float(self.fields[ts][::2,::2].mean()),places=6)
        self.assertFalse(strength[3:].any())
        receipt = json.loads(self.log.read_text())
        self.assertEqual(receipt['source_input_indices'],[12,3,18])

    def test_mean_is_after_native_grid_sampling_not_full_RGB_mean(self):
        for value in self.fields.values():
            value[:] = .01
            value[::2,::2] = .9
        self.attach()
        self.video.ba(*self.args)
        self.assertAlmostEqual(float(self.candidate_calls[0][-3][0,0,0]),.9,places=6)

    def test_actual_mono_mask_is_read_on_every_call(self):
        self.attach()
        self.video.ba(*self.args)
        first = self.candidate_calls[0][-3].clone()
        self.args[3][0,0,0] = 0
        self.video.ba(*self.args)
        second = self.candidate_calls[1][-3]
        self.assertEqual(second[0,0,0],0)
        self.assertNotEqual(first[0,1,1],second[0,1,1])

    def test_all_nonlocal_stages_use_installed_native(self):
        self.attach()
        for phase in frozen().PASSTHROUGH:
            self.video._task011b_phase = phase
            self.video.ba(*self.args)
        self.assertEqual(len(self.native_calls),len(frozen().PASSTHROUGH))
        self.assertEqual(len(self.candidate_calls),0)

    def test_motion_only_has_no_D_intervention(self):
        self.attach()
        self.args[23] = True
        self.video.ba(*self.args)
        self.assertEqual(len(self.native_calls),1)
        self.assertFalse(self.candidate_calls)

    def test_metric_depth_reg_false_is_passthrough(self):
        self.attach()
        self.video.metric_depth_reg = False
        self.video.ba(*self.args)
        self.assertEqual(len(self.native_calls),1)

    def test_missing_stage_stops_without_calling_any_solver(self):
        self.attach()
        del self.video._task011b_phase
        with self.assertRaises(RuntimeError):self.video.ba(*self.args)
        self.assertFalse(self.candidate_calls or self.native_calls)
        self.assertIs(droid_backends,self.original_backend)

    def test_wrong_signature_stops_before_solver(self):
        self.attach()
        with self.assertRaises(RuntimeError):self.video.ba(*self.args[:-1])
        self.assertFalse(self.candidate_calls or self.native_calls)

    def test_gamma_change_stops_before_solver(self):
        self.attach()
        self.args[20] = .001
        with self.assertRaises(RuntimeError):self.video.ba(*self.args)
        self.assertFalse(self.candidate_calls or self.native_calls)

    def test_malformed_timestamp_stops(self):
        self.attach()
        self.video.timestamp[1] = 3.5
        with self.assertRaises(ValueError):self.video.ba(*self.args)

    def test_unknown_source_stops(self):
        self.attach()
        self.args[11][0] = 4
        with self.assertRaises(ValueError):self.video.ba(*self.args)

    def test_uncertainty_flags_are_never_silently_enabled(self):
        self.attach()
        self.args[25:27] = [False,False]
        self.video.ba(*self.args)
        self.assertFalse(self.candidate_calls[0][25])
        self.assertFalse(self.candidate_calls[0][26])

    def test_backend_restored_if_native_or_candidate_throws(self):
        def fail(*args):raise RuntimeError('synthetic native failure')
        self.candidate.ba = fail
        self.attach()
        with self.assertRaisesRegex(RuntimeError,'synthetic native failure'):self.video.ba(*self.args)
        self.assertIs(droid_backends,self.original_backend)

    def test_existing_receipt_or_second_install_is_protected(self):
        self.log.write_text('historical')
        with self.assertRaises(FileExistsError):self.attach()
        self.log.unlink()
        self.attach()
        with self.assertRaises(RuntimeError):self.attach()

    def test_missing_or_nonboolean_native_valid_cache_stops(self):
        self.valids.pop(0)
        with self.assertRaises(ValueError):self.attach()

    def test_not_all_64_input_ids_stops(self):
        self.fields.pop(63)
        self.valids.pop(63)
        with self.assertRaises(ValueError):self.attach()

    def test_A0_uses_frozen_native_controller_and_no_candidate(self):
        self.attach('A0')
        self.video.ba(*self.args)
        self.assertEqual(len(self.native_calls),1)
        self.assertFalse(self.candidate_calls)

    def test_A1_native_D1_endpoint_still_uses_all_one_coefficients(self):
        fields = {i:np.ones((4,6)) for i in range(64)}
        install(self.video,self.candidate,arm_config('A1'),fields,self.log)
        self.video.ba(*self.args)
        self.assertTrue(torch.all(self.candidate_calls[0][-3][:4]==1))

    def test_adapter_does_not_import_Metric3D_or_DINO(self):
        self.attach()
        self.video.ba(*self.args)
        self.assertFalse(any(name.startswith(('mono.model','dinov2','metric3d','src.slam')) for name in sys.modules))


class TorchIndependentReference(unittest.TestCase):
    def test_FP32_CPU_tensor_adapter_matches_independent_numpy_reference(self):
        rng = np.random.default_rng(44)
        a = rng.uniform(.001,.999,(9,45,80)).astype(np.float32)
        nv = rng.random(a.shape)>.1
        a[~nv] = 0
        dm = (rng.random(a.shape)>.3).astype(np.float32)
        ix = np.array([0,2,5,8],dtype=np.int64)
        expected,_ = uniform_for_call(a,nv,dm,ix)
        actual,proof = torch_uniform_for_call(torch.from_numpy(a),torch.from_numpy(nv),torch.from_numpy(dm),torch.from_numpy(ix))
        np.testing.assert_allclose(actual.numpy(),expected,rtol=0,atol=1e-6)
        self.assertEqual(proof['compute_device'],'cpu')
        self.assertFalse(torch.cuda.is_initialized())


if __name__ == '__main__':
    unittest.main(verbosity=2)

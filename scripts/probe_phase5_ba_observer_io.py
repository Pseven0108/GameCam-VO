"""CPU fault-injection checks of the optional recorder, not a model run."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import types
from unittest.mock import patch

import numpy as np
from scipy.spatial.transform import Rotation
import torch

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if torch.cuda.is_initialized():
        raise RuntimeError("This observer fixture is CPU-only and must not share the inference GPU")
    source = ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T105134Z_person_tracking"
    archive = source / "native_camera_prefix_recovery/complete_native_camera_fields.npz"
    with np.load(archive, allow_pickle=False) as z:
        poses, timestamps = z["cams_T_world"].copy(), z["tstamps"].copy()
    context = json.loads((source / "motion_decomposition/frontend_calls.jsonl").read_text().strip().splitlines()[-1])
    xyzw = Rotation.from_matrix(poses[:, :3, :3]).as_quat()
    native_pair = (np.c_[poses[:, :3, 3], xyzw[:, [3, 0, 1, 2]]], timestamps)
    original_bytes = [value.tobytes() for value in native_pair]
    retained = np.asarray(context["online_window_poses_T_cw_xyzw"], np.float32)
    keys = np.asarray(context["observed_window_input_indices"], np.int64)

    class NeverForward(torch.nn.Module):
        def forward(self, *args, **kwargs):
            raise AssertionError("A recorder fixture must not execute a network")

    class NativeFixture:
        def __init__(self, *, fail_native=False):
            self.network = NeverForward()
            self.n = len(keys)
            self.poses_ = torch.from_numpy(retained.copy())
            self.tstamps_ = torch.from_numpy(keys.copy())
            self.native_calls, self.fail_native = 0, fail_native

        def terminate(self):
            self.native_calls += 1
            if self.fail_native:
                raise RuntimeError("INJECTED_NATIVE_TERMINATE_FAILURE")
            return native_pair

    # Fake only the optional wrapper's backend boundary in this fresh process.
    # No model modules, GPU tensors, checkpoints or baseline files are modified.
    package = types.ModuleType("main")
    package.__path__ = []
    backend = types.ModuleType("main.batrack")
    backend.BATRACK = NativeFixture
    package.batrack = backend
    sys.modules.update({"main": package, "main.batrack": backend})
    sys.path.insert(0, str(ROOT / "baselines/runtime_hooks"))
    from ba_track_observer import install_observer
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = ROOT / "logs/PHASE5" / (stamp+"_BA_observer_IO_fault_probe")
    folder.mkdir(parents=True, exist_ok=False)
    outcomes = []
    for mode in ("normal_snapshot", "injected_snapshot_IO_failure", "archive_disabled", "native_exception"):
        backend.BATRACK = NativeFixture
        out = folder / mode
        out.mkdir()
        install_observer(out)
        instance = backend.BATRACK(fail_native=mode == "native_exception")
        os.environ["GAMECAM_BA_SAVE_TERMINATED_CAMERA"] = "0" if mode == "archive_disabled" else "1"
        if mode == "injected_snapshot_IO_failure":
            with patch("numpy.savez_compressed", side_effect=OSError("INJECTED_OPTIONAL_OUTPUT_DISK_ERROR")) as call:
                returned = instance.terminate()
                assert call.call_count == 1
            error = json.loads((out / "native_terminated_camera_error.json").read_text())
            assert error["status"] == "OPTIONAL_CAMERA_ARCHIVE_FAILED_ORIGINAL_NATIVE_RETURN_PRESERVED"
        elif mode == "native_exception":
            try:
                instance.terminate()
            except RuntimeError as error:
                assert str(error) == "INJECTED_NATIVE_TERMINATE_FAILURE"
            else:
                raise AssertionError("A native failure must propagate unchanged")
            returned = None
        else:
            returned = instance.terminate()
        assert instance.native_calls == 1
        if mode != "native_exception":
            assert returned is native_pair and [v.tobytes() for v in native_pair] == original_bytes
        if mode == "normal_snapshot":
            receipt = json.loads((out / "native_terminated_camera.json").read_text())
            file = out / "native_terminated_camera.npz"
            assert digest(file) == receipt["sha256"]
            expected = {"native_T_wc_translation_quaternion_WXYZ": native_pair[0], "native_input_indices": timestamps,
                "final_retained_T_cw_translation_quaternion_XYZW": retained, "final_retained_input_indices": keys}
            with np.load(file, allow_pickle=False) as z:
                assert set(z.files) == set(expected)
                for name, value in expected.items():
                    assert z[name].dtype == value.dtype and z[name].shape == value.shape and z[name].tobytes() == value.tobytes()
        elif mode == "archive_disabled":
            assert not (out / "native_terminated_camera.npz").exists()
        outcomes.append({"case": mode, "status": "PASS", "native_terminate_calls": instance.native_calls})
    assert not torch.cuda.is_initialized()
    hook = ROOT / "baselines/runtime_hooks/ba_track_observer.py"
    shutil.copy2(hook, folder / "ba_track_observer.py.tested_source")
    shutil.copy2(__file__, folder / "probe_phase5_ba_observer_io.py.executed_source")
    result = {"status": "OPTIONAL_OBSERVER_RETURN_IDENTITY_AND_IO_FAULT_PROPAGATION_PROBE_PASS", "directory": str(folder),
        "cases": outcomes, "new_model_execution": False, "GPU_initialized": False, "GT_used": False,
        "fixture": "Previously accepted actual Person camera values and independent last12 frontend states; fake native backend used only to test optional IO contract",
        "CUDA_index_copy_in_active_model_tested": False, "CPU_torch_long_index_serialization_value_bytes_unchanged": True,
        "source_camera_archive_sha256": digest(archive), "observer_source_sha256": digest(hook), "probe_source_sha256": digest(Path(__file__))}
    (folder / "probe.json").write_text(json.dumps(result, indent=2)+"\n")
    (ROOT / "reports/PHASE5/ba_observer_IO_fault_probe.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

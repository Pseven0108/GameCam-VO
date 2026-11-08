"""Check legacy recorder exception encoding; CPU fixture, not active model data."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    probe = json.loads((ROOT / "reports/PHASE5/ba_observer_IO_fault_probe.json").read_text())
    fixture = Path(probe["directory"]) / "normal_snapshot/native_terminated_camera.npz"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = ROOT / "logs/PHASE5" / (stamp+"_BA_legacy_npz_exception_probe")
    folder.mkdir(parents=True, exist_ok=False)
    child = folder / "legacy_numpy_exception_fixture.py"
    child.write_text('''import sys
import numpy as np
class RejectedCudaIndexFixture:
    def __array__(self, *args, **kwargs):
        raise TypeError("SIMULATED_CUDA_INDEX_NUMPY_CONVERSION_FAILURE_NOT_A_MODEL_RUN")
with np.load(sys.argv[1], allow_pickle=False) as z:
    values = {k: z[k].copy() for k in z.files}
np.savez_compressed(sys.argv[2],
    native_T_wc_translation_quaternion_WXYZ=values["native_T_wc_translation_quaternion_WXYZ"],
    native_input_indices=values["native_input_indices"],
    final_retained_T_cw_translation_quaternion_XYZW=values["final_retained_T_cw_translation_quaternion_XYZW"],
    final_retained_input_indices=RejectedCudaIndexFixture())
''', encoding="utf-8")
    failed = folder / "legacy_failed_snapshot.npz"
    with (folder / "expected_child_exception.log").open("w") as stream:
        code = subprocess.run([sys.executable, str(child), str(fixture), str(failed)], stdout=stream, stderr=subprocess.STDOUT).returncode
    if code != 1:
        raise ValueError("The controlled legacy recorder fixture did not raise the expected error")
    names = ["native_T_wc_translation_quaternion_WXYZ", "native_input_indices", "final_retained_T_cw_translation_quaternion_XYZW"]
    with zipfile.ZipFile(failed) as z:
        if z.testzip() is not None or z.namelist() != [k+".npy" for k in names]:
            raise ValueError("Expected exactly three complete CRC-valid pre-exception fields")
    with np.load(fixture, allow_pickle=False) as original, np.load(failed, allow_pickle=False) as z:
        for key in names:
            a, b = original[key], z[key]
            if a.dtype != b.dtype or a.shape != b.shape or a.tobytes() != b.tobytes():
                raise ValueError("A complete preceding field changed during the controlled exception")
    result = {"status": "LEGACY_NUMPY_EXCEPTION_LEAVES_THREE_COMPLETE_CRC_VALID_FIELDS_IN_CPU_FIXTURE",
        "directory": str(folder), "numpy_version": np.__version__, "child_exit_code": code,
        "source_fixture_sha256": digest(fixture), "three_field_archive_sha256": digest(failed),
        "complete_fields": names, "missing_field": "final_retained_input_indices",
        "new_model_execution": False, "GPU_used": False, "GT_used": False,
        "active_Crowd_archive_existence_or_recoverability_claim": False,
        "scope": "Controlled fourth-field array-conversion exception using the already declared CPU IO fixture; active model must independently produce and pass its own actual archive/direction checks",
        "probe_source_sha256": digest(Path(__file__))}
    shutil.copy2(__file__, folder / "probe_phase5_ba_legacy_npz.py.executed_source")
    (folder / "probe.json").write_text(json.dumps(result, indent=2)+"\n")
    (ROOT / "reports/PHASE5/ba_legacy_npz_exception_probe.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

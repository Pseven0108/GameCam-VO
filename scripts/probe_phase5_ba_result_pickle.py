"""Existing NumPy runtime serialization roundtrip, no model or GT inference."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import pickle
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "baselines/runtime_hooks"))
from ba_track_result_pickle import install_result_pickle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-archive", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    with np.load(args.camera_archive) as z:
        values = {key: z[key].copy() for key in z.files}
    # Layout fixtures test the codec, not scientific model outputs or scenes.
    values.update(boolean_layout=np.array([[True, False], [False, True]]),
        strided_layout=np.arange(80, dtype=np.float64).reshape(8, 10)[::2, ::3],
        fortran_layout=np.asfortranarray(np.arange(20, dtype=np.float32).reshape(4, 5)))
    before = {key: value.tobytes() for key, value in values.items()}
    encoded4 = pickle.dumps(values, protocol=4)
    with tempfile.TemporaryDirectory(prefix="gamecam-pickle-probe-") as temporary:
        original = install_result_pickle(Path(temporary) / "receipt.jsonl")
        try:
            stream = io.BytesIO()
            result = pickle.dump(values, stream)
            encoded5 = stream.getvalue()
            assert result is None and encoded5[:2] == b"\x80\x05"
            fallback = io.BytesIO()
            pickle.dump({"unrelated": [1, 2, 3]}, fallback)
            assert fallback.getvalue()[:2] == bytes([128, pickle.DEFAULT_PROTOCOL])
            explicit4 = io.BytesIO()
            pickle.dump(values, explicit4, protocol=4)
            assert explicit4.getvalue() == encoded4
        finally:
            pickle.dump = original
    left, right = pickle.loads(encoded4), pickle.loads(encoded5)
    for key in values:
        assert left[key].dtype == right[key].dtype == values[key].dtype
        assert left[key].shape == right[key].shape == values[key].shape
        assert left[key].tobytes() == right[key].tobytes() == before[key] == values[key].tobytes()
    if args.output_directory:
        args.output_directory.mkdir(parents=True, exist_ok=False)
        (args.output_directory / "protocol4_codec_fixture.pkl").write_bytes(encoded4)
        (args.output_directory / "protocol5_codec_fixture.pkl").write_bytes(encoded5)
    report = {"status": "NATIVE_CAMERA_ARRAYS_AND_LAYOUTS_PROTOCOL4_5_EXACT_ROUNDTRIP_PASS", "Python": sys.version, "NumPy": np.__version__,
        "arrays_checked": list(values), "explicit_protocol_preserved": True, "unrelated_dictionary_default_preserved": True,
        "model_arrays_mutated": False, "model_or_GT_inference": False, "native_full_pipeline_success_or_memory_reduction_claim": False}
    report["codec_fixture_directory"] = str(args.output_directory) if args.output_directory else None
    (ROOT / "reports/PHASE5/ba_result_pickle_roundtrip_probe.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

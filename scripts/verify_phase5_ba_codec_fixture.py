"""Cross-runtime readback of the owned small NumPy codec fixture, no NN calls."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path
import pickle
import sys

import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture_directory", type=Path)
    args = parser.parse_args()
    folder = args.fixture_directory.resolve()
    if not folder.is_relative_to(PROJECT / "logs/PHASE5"):
        raise ValueError("Only this task's locally generated codec fixtures are accepted")
    files = [folder / ("protocol"+str(protocol)+"_codec_fixture.pkl") for protocol in (4, 5)]
    for file in files:
        if file.stat().st_size > 2*1024**2:
            raise ValueError("This bounded compatibility fixture must be small")
    arrays = []
    for file in files:
        with file.open("rb") as stream:
            arrays.append(pickle.load(stream))
    if set(arrays[0]) != set(arrays[1]):
        raise ValueError("Codec field sets differ")
    for key in arrays[0]:
        a, b = arrays[0][key], arrays[1][key]
        if a.dtype != b.dtype or a.shape != b.shape or a.tobytes() != b.tobytes():
            raise ValueError("Cross-runtime numeric codec readback differs: "+key)
    result = {"status": "WSL_NUMPY124_TO_WINDOWS_NUMPY22_PROTOCOL4_5_READBACK_PASS", "Python": sys.version, "NumPy": np.__version__,
        "files": [{"file": str(file), "sha256": sha256(file)} for file in files], "arrays_checked": list(arrays[0]),
        "all_shapes_dtypes_and_value_bytes_equal": True, "model_execution_or_full_pipeline_success_claim": False}
    write_json(PROJECT / "reports/PHASE5/ba_result_pickle_cross_runtime_probe.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

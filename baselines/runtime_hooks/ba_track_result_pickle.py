"""Opt-in IO encoding for large native NumPy result dictionaries only."""
from __future__ import annotations

import json
from pathlib import Path
import pickle
import time

import numpy as np


def install_result_pickle(destination):
    destination = Path(destination)
    original = pickle.dump

    def recorded_dump(obj, file, protocol=None, *, fix_imports=True, buffer_callback=None):
        selected = (protocol is None and isinstance(obj, dict) and {"cams_T_world", "tstamps"}.issubset(obj)
            and isinstance(obj["cams_T_world"], np.ndarray) and isinstance(obj["tstamps"], np.ndarray))
        if not selected:
            return original(obj, file, protocol=protocol, fix_imports=fix_imports, buffer_callback=buffer_callback)
        row = {"event": "NATIVE_RESULT_SERIALIZATION_STARTED", "file": str(getattr(file, "name", "<stream>")),
            "protocol": 5, "native_default_protocol": pickle.DEFAULT_PROTOCOL,
            "arrays": {key: {"shape": list(value.shape), "dtype": str(value.dtype)} for key, value in obj.items() if isinstance(value, np.ndarray)},
            "model_inputs_or_outputs_modified": False, "out_of_band_buffers": False,
            "scope": "Result-file encoding only; original dump called once, return value unchanged; no model/RNG call"}
        destination.parent.mkdir(parents=True, exist_ok=True)
        def append(value):
            with destination.open("a") as stream:
                stream.write(json.dumps(value)+"\n")
        append(row)
        started = time.monotonic()
        result = original(obj, file, protocol=5, fix_imports=fix_imports, buffer_callback=buffer_callback)
        append({"event": "NATIVE_RESULT_SERIALIZATION_RETURNED", "file": row["file"], "protocol": 5, "wall_seconds": time.monotonic()-started})
        return result

    pickle.dump = recorded_dump
    return original

"""Verify saved source identities and9 cached pairs; no inference or fitting."""
import ast
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np
from PIL import Image
from decode_contract import decode

ROOT = Path(__file__).resolve().parents[1]


def h(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
def dump(name, data):
    p = ROOT / name; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False); f.write("\n")


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1" and "torch" not in sys.modules
    source_records = []
    for r in json.loads((ROOT / "sources/SOURCE_PROVENANCE.json").read_text("utf-8"))["files"]:
        p = ROOT / "sources" / r["path"]; b = p.read_bytes()
        if blob(b) != r["git_blob_sha"]:
            assert b.endswith(b"\n") and blob(b[:-1]) == r["git_blob_sha"]
            b = b[:-1]; p.write_bytes(b)  # New snapshots only.
        source_records.append({**r, "bytes": len(b), "sha256": h(b), "git_blob_match": True})
    dump("evidence/SOURCE_BLOB_VERIFICATION.json", {"files": source_records, "all_match": True})
    intake = json.loads((ROOT / "evidence/CANDIDATE_INTAKE.json").read_text("utf-8"))["candidates"]
    transfer = json.loads((ROOT / "evidence/ACQUISITION_RECEIPT.json").read_text("utf-8"))
    assert transfer["status"] == "EXACT_MINIMAL_PAIRS_ACQUIRED_BASIC_SOURCE_CONTRACT_ONLY"
    for r in transfer["files"]:
        b = Path(r["path"]).read_bytes(); assert len(b) == r["bytes"] and h(b) == r["sha256"]
    # Isolate ONLY the verified upstream pure depth function. No module imports,
    # model code, original file I/O or other upstream functions are executed.
    src = (ROOT / "sources/omniworld/utils.py").read_text("utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "load_depth")
    module = ast.Module(body=[fn], type_ignores=[])
    rows = []; image_hashes = {"rgb": {}, "depth": {}}; current_raw = None
    namespace = {"np": np, "imageio": SimpleNamespace(v2=SimpleNamespace(imread=lambda _: current_raw.copy())), "float": float}
    exec(compile(ast.fix_missing_locations(module), "verified_omniworld_load_depth_only", "exec"), namespace)
    for c in intake:
        cam = json.loads((ROOT / "raw_inputs" / c["uid"] / "camera/split_0.json").read_text("utf-8"))
        q = np.asarray(cam["quats"], np.float64)
        if not np.isfinite(q).all() or not np.isfinite(np.asarray(cam["trans"], float)).all(): raise RuntimeError("Invalid camera values")
        for frame in c["frames"]:
            base = ROOT / "raw_inputs" / c["uid"]
            with Image.open(base / "depth" / f"{frame:06d}.png") as im: current_raw = np.asarray(im).copy()
            with Image.open(base / "color" / f"{frame:06d}.png") as im: rgb = np.asarray(im).copy()
            actual, mask = decode(current_raw, c["metric_scale"])
            reference, reference_mask = namespace["load_depth"]("in_memory_uint16_fixture", c["metric_scale"])
            if not np.array_equal(actual, reference) or not np.array_equal(mask, reference_mask):
                raise RuntimeError("Independent decoder differs from exact source function; stop")
            for kind, a in [("rgb", rgb), ("depth", current_raw)]:
                ah = h(a.dtype.str.encode() + str(a.shape).encode() + a.tobytes())
                image_hashes[kind].setdefault(ah, []).append({"uid": c["uid"], "frame": frame})
            rows.append({"uid": c["uid"], "RGB_ID": frame, "Depth_ID": frame, "camera_split": 0,
                "camera_list_position": frame, "source_frame_list_verified": True,
                "depth_dtype": str(current_raw.dtype), "RGB_height": rgb.shape[0], "RGB_width": rgb.shape[1],
                "depth_height": current_raw.shape[0], "depth_width": current_raw.shape[1],
                "official_function_depth_bitwise_equal": True, "official_function_mask_bitwise_equal": True,
                "source_valid_pixels": int(mask.sum()), "source_invalid_pixels": int((~mask).sum()),
                "raw_zeros": int((current_raw == 0).sum()), "raw_65535": int((current_raw == 65535).sum()),
                "selected_quaternion_norm": float(np.linalg.norm(q[frame])),
                "declared_meter_factor": c["metric_scale"], "physical_accuracy_verified": False,
                "NLL_or_coverage_computed": False})
    with (ROOT / "evidence/FRAME_PAIRING_AND_DECODE.csv").open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    dump("evidence/DECODE_AND_DUPLICATE_VERIFICATION.json", {"actual_pairs_checked": len(rows),
         "official_reader_function_depth_and_mask_exact": True, "source_valid_pixels": sum(r["source_valid_pixels"] for r in rows),
         "source_invalid_pixels": sum(r["source_invalid_pixels"] for r in rows),
         "duplicate_decoded_RGB_groups": [r for r in image_hashes["rgb"].values() if len(r) > 1],
         "duplicate_decoded_depth_groups": [r for r in image_hashes["depth"].values() if len(r) > 1],
         "scope": "Pixel-array identity and source decoder equivalence only, not scene/pretraining independence or metric accuracy"})
    stream = io.StringIO(); result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT / "tests")))
    (ROOT / "logs").mkdir(exist_ok=True)
    with (ROOT / "logs/CPU_UNIT_TESTS.txt").open("x", encoding="utf-8") as f: f.write(stream.getvalue())
    report = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "status": "PASS" if result.wasSuccessful() else "FAIL", "device": "CPU", "torch_imported": "torch" in sys.modules,
              "actual_cached_pairs_separately_verified": 9, "real_model_forwards": 0,
              "scope": "Synthetic decoder contracts; actual9-pair validation is separate, neither is a metric calibration accuracy result"}
    dump("tests/CPU_TEST_REPORT.json", report)
    assert result.wasSuccessful()
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()

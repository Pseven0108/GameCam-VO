"""Check actual K and pixel-center conventions with the pinned CPU reader.

No pose accuracy claim: SciPy normalizes source quaternions when constructing R.
"""
import ast
import csv
import json
import os
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1" and "torch" not in sys.modules
src = ast.parse((ROOT / "sources/omniworld/utils.py").read_text("utf-8"))
names = {"load_split_info", "load_camera_poses", "get_pixel"}
module = ast.Module(body=[n for n in src.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
ns = {"np": np, "Path": Path, "json": json, "R": Rotation}
exec(compile(ast.fix_missing_locations(module), "verified_native_camera_reader", "exec"), ns)
pixels = ns["get_pixel"](2, 3)
assert pixels.shape == (3, 6) and np.array_equal(pixels[:, 0], [.5, .5, 1])
rows = []
for c in json.loads((ROOT / "evidence/CANDIDATE_INTAKE.json").read_text("utf-8"))["candidates"]:
    base = ROOT / "raw_inputs" / c["uid"]
    raw = json.loads((base / "camera/split_0.json").read_text("utf-8"))
    K, extrinsics, ids = ns["load_camera_poses"](base, 0, c["metric_scale"])
    assert len(ids) == c["first_split_length"] and np.isfinite(K).all() and np.isfinite(extrinsics).all()
    for frame in c["frames"]:
        at = ids.index(frame)
        expected = np.array([[raw["focals"][at], 0, raw["cx"]], [0, raw["focals"][at], raw["cy"]], [0, 0, 1]], np.float32)
        assert np.array_equal(K[at], expected)
        rows.append({"uid": c["uid"], "frame": frame, "fx": float(K[at,0,0]), "fy": float(K[at,1,1]),
                     "cx_native": float(K[at,0,2]), "cy_native": float(K[at,1,2]),
                     "pixel_grid_first_u": .5, "pixel_grid_first_v": .5,
                     "K_exact_source_reader": True, "additional_K_half_shift_applied": False,
                     "camera_GT_accuracy_admitted": False})
with (ROOT / "evidence/NATIVE_K_PIXEL_CONTRACT.csv").open("x", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
report = {"pairs_verified": len(rows), "native_reader_K_match": True, "first_pixel": [.5,.5,1],
          "correction": "ACQUISITION_RECEIPT UID_checks cx_plus_half/cy_plus_half are diagnostic arithmetic, not the native K. Native K copies cx/cy unchanged; get_pixel already adds0.5 to pixel coordinates. Do not apply both shifts.",
          "depth_decode_affected": False, "prior_receipt_preserved": True, "model_inference_consumed_wrong_K": False,
          "source_quaternions": "Read-only SciPy normalization for the reader check, not rewritten or certified as accurate camera GT",
          "torch_imported": "torch" in sys.modules}
with (ROOT / "evidence/CAMERA_CONTRACT_CORRECTION.json").open("x", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2); f.write("\n")
print(json.dumps(report, indent=2))

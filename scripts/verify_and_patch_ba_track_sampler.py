"""Prove direct diagonal indexing against the original sampler before applying.

The official 5D sampler first materializes B*N*N*C values, then keeps the N
diagonal entries. Joint indexing selects those identical entries directly.
All interpolation arithmetic, coordinate clipping and model settings remain
unchanged. The actual prior Demo OOM is the reason for this bounded patch.
"""
from __future__ import annotations

import ast
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

import torch


ROOT = Path("/mnt/d/aaa/GameCam-VO")


def sampler(source):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "bilinear_sample2d")
    namespace = {"torch": torch}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<recorded-sampler>", "exec"), namespace)
    return namespace["bilinear_sample2d"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-current-against", type=Path)
    args = parser.parse_args()
    upstream = ROOT / "baselines/ba_track/upstream"
    trigger = ROOT / "results/E9_BA_TRACK/20261031T095625Z_official_demo_tennis/sparse_tracker_and_BA.log"
    text = trigger.read_text()
    if "bilinear_sample2d" not in text or "torch.OutOfMemoryError" not in text:
        raise RuntimeError("An actual sampler OOM is required")
    branch = subprocess.check_output(["git", "-C", str(upstream), "branch", "--show-current"], text=True).strip()
    if branch != "repro/2026-10-31-sm120":
        raise RuntimeError("Use the reproduction branch")
    path = upstream / "main/frontend/core/model_utils.py"
    initial_source = path.read_bytes()
    if args.verify_current_against:
        previous = json.loads(args.verify_current_against.read_text())
        if hashlib.sha256(initial_source).hexdigest() != previous["after_sha256"]:
            raise ValueError("Current source differs from the recorded candidate")
        old = (Path(previous["directory"]) / "source_before.py").read_bytes()
    else:
        old = initial_source
    pattern = rb"torch\.diagonal\(im_flat\[(idx_y[01]_x[01])\.long\(\)\], dim1=1, dim2=2\)\.permute\(\s*0, 2, 1\s*\)"
    new, count = re.subn(pattern, rb"im_flat[\1.long(), torch.arange(N, device=im_flat.device)[None, :]]", old)
    if count != 4:
        raise ValueError("Expected exactly four original 5D diagonal gathers")
    out = ROOT / "logs/SOTA_setup" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_ba_sampler_equivalence")
    out.mkdir(exist_ok=False)
    (out / "source_before.py").write_bytes(old)
    (out / "source_candidate.py").write_bytes(new)
    original, candidate = sampler(old.decode()), sampler(new.decode())
    torch.manual_seed(47)
    cases = []
    for device in ("cpu", "cuda"):
        for dtype in (torch.float16, torch.float32, torch.float64):
            for dims in (4, 5):
                for strided in (False, True):
                    b, n, c, h, w = 2, 17, 3, 5, 7
                    shape = (b, n, c, h, w * (2 if strided else 1)) if dims == 5 else (b, c, h, w * (2 if strided else 1))
                    image = torch.randn(shape, device=device, dtype=dtype)
                    if strided:
                        image = image[..., ::2]
                    x = torch.rand(b, n, device=device) * (w+3) - 2
                    y = torch.rand(b, n, device=device) * (h+3) - 2
                    x[:, :5] = torch.tensor([-1., -.5, 0., w-1., w+.5], device=device)
                    y[:, :5] = torch.tensor([-1., -.5, 0., h-1., h+.5], device=device)
                    observations = []
                    for function in (original, candidate):
                        im = image.detach().requires_grad_(True)
                        if strided and im.is_contiguous():
                            raise ValueError("The strided proof case lost its noncontiguous storage")
                        xx, yy = x.detach().clone().requires_grad_(True), y.detach().clone().requires_grad_(True)
                        value, inbound = function(im, xx, yy, return_inbounds=True)
                        gradients = torch.autograd.grad(value.sum(), (im, xx, yy))
                        observations.append((value.detach(), inbound, *gradients))
                    for a, bvalue in zip(*observations, strict=True):
                        if not torch.equal(a, bvalue):
                            raise ValueError(f"Sampler output or gradient differs: {device}/{dtype}/{dims}/{strided}")
                    cases.append({"device": device, "dtype": str(dtype), "dimensions": dims, "strided_input": strided,
                                  "values_inbounds_and_image_xy_gradients_bitwise_identical": True})
    memory = []
    im = torch.randn(1, 512, 32, 8, 8, device="cuda")
    x = torch.rand(1, 512, device="cuda") * 7
    y = torch.rand_like(x) * 7
    for name, function in (("original", original), ("direct_diagonal_gather", candidate)):
        torch.cuda.synchronize()
        baseline = torch.cuda.memory_allocated()
        torch.cuda.reset_peak_memory_stats()
        with torch.no_grad():
            value = function(im, x, y)
        torch.cuda.synchronize()
        memory.append({"implementation": name, "synthetic_input_shape": list(im.shape),
                       "peak_allocated_bytes_above_existing_tensors": torch.cuda.max_memory_allocated()-baseline})
        del value
    if path.read_bytes() != initial_source:
        raise RuntimeError("Source changed during proof")
    if not args.verify_current_against:
        path.write_bytes(new)
    elif new != initial_source:
        raise ValueError("Current patch differs from the independently reconstructed candidate")
    record = {"status": "BA_TRACK_SAMPLER_LOCAL_EQUIVALENCE_PASSED_PATCH_APPLIED", "directory": str(out),
              "branch": branch, "trigger": str(trigger), "changes": 4, "file": str(path),
              "before_sha256": hashlib.sha256(old).hexdigest(), "after_sha256": hashlib.sha256(new).hexdigest(),
              "cases": cases, "memory_setup_check": memory, "model_hyperparameters_changed": False,
              "interpolation_arithmetic_changed": False, "full_tracker_bitwise_equivalence_claim": False,
              "verification_only_no_source_mutation": bool(args.verify_current_against),
              "patch_risk": "medium: inference memory access implementation; exact local values and gradients proved against original, full Demo validation still required"}
    (out / "status.json").write_text(json.dumps(record, indent=2))
    (ROOT / "reports/SOTA/ba_track_sampler_equivalence.json").write_text(json.dumps(record, indent=2))
    print(json.dumps({"status": record["status"], "cases": len(cases), "memory_setup_check": memory, "directory": str(out)}))


if __name__ == "__main__":
    main()

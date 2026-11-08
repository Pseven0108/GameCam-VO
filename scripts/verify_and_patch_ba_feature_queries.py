"""Prove query-frame sampling without materializing one feature map per point.

The original 5D sample is compared bitwise to grouping identical query-frame
indices and calling the unchanged 4D sampler. The new branch is inference-only;
the gradient-enabled branch retains its previous computation.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import time

import torch


ROOT = Path("/mnt/d/aaa/GameCam-VO")
HELPER = '''def bilinear_sample2d_by_frame(feature_maps, frame_indices, x, y):
    """Inference-only equivalent sampling; no per-query feature-map copy."""
    if torch.is_grad_enabled():
        raise RuntimeError("Use the original sampling path when gradients are enabled")
    B, S, C, H, W = feature_maps.shape
    if x.shape != y.shape or x.shape[0] != B or frame_indices.ndim != 1 or frame_indices.numel() != x.shape[1]:
        raise ValueError("Query frame and coordinate dimensions differ")
    if x.shape[1] == 0:
        return bilinear_sample2d(feature_maps[:, 0], x, y)
    output = None
    for frame in torch.unique(frame_indices, sorted=True).tolist():
        selected = torch.nonzero(frame_indices == frame, as_tuple=False).flatten()
        values = bilinear_sample2d(feature_maps[:, frame], x[:, selected], y[:, selected])
        if output is None:
            output = values.new_empty((B, C, x.shape[1]))
        output[:, :, selected] = values
    return output
'''


def load_function(source, name, extra=None):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {"torch": torch, **(extra or {})}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<recorded-function>", "exec"), scope)
    return scope[name]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def main():
    upstream = ROOT / "baselines/ba_track/upstream"
    trigger = ROOT / "results/E9_BA_TRACK/20261031T100753Z_official_demo_tennis/sparse_tracker_and_BA.log"
    evidence = trigger.read_text()
    if "fmaps_sample = fmaps[" not in evidence or "14.06 GiB" not in evidence:
        raise RuntimeError("The actual per-query feature-map allocation failure is required")
    branch = subprocess.check_output(["git", "-C", str(upstream), "branch", "--show-current"], text=True).strip()
    if branch != "repro/2026-10-31-sm120":
        raise RuntimeError("Use the explicit reproduction branch")
    utils = upstream / "main/frontend/core/model_utils.py"
    tracker = upstream / "main/frontend/md_tracker.py"
    old_utils, old_tracker = utils.read_bytes(), tracker.read_bytes()
    if b"def bilinear_sample2d_by_frame" in old_utils:
        raise RuntimeError("The candidate is already applied; never replay this source edit automatically")
    reference_source = subprocess.check_output(["git", "-C", str(upstream), "show", "456e094ee3ca7fbd9884ba18e68e7c0717d49a67:main/frontend/core/model_utils.py"]).decode()
    original = load_function(reference_source, "bilinear_sample2d")
    current = load_function(old_utils.decode(), "bilinear_sample2d")
    grouped = load_function(HELPER, "bilinear_sample2d_by_frame", {"bilinear_sample2d": current})
    out = ROOT / "logs/SOTA_setup" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_ba_feature_query_equivalence")
    out.mkdir(exist_ok=False)
    (out / "model_utils_before.py").write_bytes(old_utils)
    (out / "md_tracker_before.py").write_bytes(old_tracker)
    (out / "original_sampler_source.py").write_text(reference_source)
    (out / "candidate_helper.py").write_text(HELPER)
    torch.manual_seed(418)
    cases = []
    with torch.no_grad():
        for device in ("cpu", "cuda"):
            for dtype in (torch.float16, torch.float32, torch.float64):
                for batch in (1, 2):
                    for strided in (False, True):
                        s, c, h, w, n = 3, 8, 6, 8, 31
                        maps = torch.randn(batch, s, c, h, w*(2 if strided else 1), device=device, dtype=dtype)
                        if strided:
                            maps = maps[..., ::2]
                            assert not maps.is_contiguous()
                        frames = torch.randint(s, (n,), device=device)
                        frames[:3] = torch.tensor([2, 0, 2], device=device)
                        x = torch.rand(batch, n, device=device)*(w+3)-2
                        y = torch.rand(batch, n, device=device)*(h+3)-2
                        x[:, :6] = torch.tensor([-1., -.5, 0., w-1., w, w+.5], device=device)
                        y[:, :6] = torch.tensor([-1., -.5, 0., h-1., h, h+.5], device=device)
                        baseline = original(maps[:, frames], x, y)
                        result = grouped(maps, frames, x, y)
                        if not torch.equal(baseline, result):
                            raise ValueError(f"Inference sample values differ: {device}/{dtype}/{batch}/{strided}")
                        cases.append({"device": device, "dtype": str(dtype), "batch": batch, "noncontiguous_maps": strided,
                                      "duplicate_unsorted_frame_indices": True, "clipped_and_integer_coordinates": True,
                                      "original_5D_and_grouped_4D_values_bitwise_equal": True})
        maps = torch.randn(1, 12, 128, 96, 128, device="cuda")
        frames = torch.arange(2400, device="cuda") % 12
        x, y = torch.rand(1, 2400, device="cuda")*127, torch.rand(1, 2400, device="cuda")*95
        torch.cuda.synchronize()
        before = torch.cuda.memory_allocated()
        torch.cuda.reset_peak_memory_stats()
        result = grouped(maps, frames, x, y)
        torch.cuda.synchronize()
        memory = {"input_maps_shape": list(maps.shape), "queries": 2400,
                  "input_maps_bytes": maps.numel()*maps.element_size(),
                  "legacy_per_query_feature_copy_bytes_formula_not_allocated": 1*2400*128*96*128*4,
                  "grouped_peak_allocated_bytes_above_existing_tensors": torch.cuda.max_memory_allocated()-before,
                  "output_shape": list(result.shape), "output_finite": bool(torch.isfinite(result).all())}
    nl = b"\r\n" if b"\r\n" in old_utils else b"\n"
    new_utils = old_utils + nl*2 + HELPER.replace("\n", nl.decode()).encode()
    old_import = b"from main.frontend.core.model_utils import meshgrid2d, bilinear_sample2d, smart_cat"
    if old_tracker.count(old_import) != 1:
        raise ValueError("Unexpected model utility import")
    nlt = b"\r\n" if b"\r\n" in old_tracker else b"\n"
    begin = old_tracker.index(b"                fmaps_sample = fmaps[")
    end = old_tracker.index(b"                feat_init_ = feat_init_.unsqueeze", begin)
    old_block = old_tracker[begin:end]
    original_path = b"".join(b"    "+line if line.strip() else nlt for line in old_block.splitlines(keepends=True))
    new_branch = ("                if torch.is_grad_enabled():\n").replace("\n", nlt.decode()).encode() + original_path
    alternative = '''                else:
                    feat_init_ = bilinear_sample2d_by_frame(
                        fmaps,
                        first_positive_sorted_inds[prev_wind_idx:wind_idx] - ind,
                        coords_init_[:, 0, prev_wind_idx:wind_idx, 0],
                        coords_init_[:, 0, prev_wind_idx:wind_idx, 1],
                    ).permute(0, 2, 1)

'''.replace("\n", nlt.decode()).encode()
    new_tracker = (old_tracker[:begin]+new_branch+alternative+old_tracker[end:]).replace(old_import, old_import+b", bilinear_sample2d_by_frame", 1)
    ast.parse(new_utils.decode())
    ast.parse(new_tracker.decode())
    if utils.read_bytes() != old_utils or tracker.read_bytes() != old_tracker:
        raise RuntimeError("Source changed during the proof")
    utils.write_bytes(new_utils)
    tracker.write_bytes(new_tracker)
    (out / "model_utils_candidate.py").write_bytes(new_utils)
    (out / "md_tracker_candidate.py").write_bytes(new_tracker)
    record = {"status": "BA_QUERY_FRAME_SAMPLING_BITWISE_EQUIVALENCE_PASSED_PATCH_APPLIED", "directory": str(out),
              "trigger": str(trigger), "branch": branch, "cases": cases, "memory_setup_check": memory,
              "source_hashes": {"utils_before": digest(old_utils), "utils_after": digest(new_utils), "tracker_before": digest(old_tracker), "tracker_after": digest(new_tracker)},
              "gradient_enabled_call_path_preserved": True, "new_helper_only_under_no_grad": True,
              "model_architecture_precision_window_query_count_iterations_thresholds_changed": False,
              "full_tracker_bitwise_equivalence_claim": False, "full_official_demo_still_requires_execution": True,
              "patch_risk": "medium: exact local inference memory implementation, not a model or protocol change"}
    (out / "status.json").write_text(json.dumps(record, indent=2))
    (ROOT / "reports/SOTA/ba_track_query_feature_equivalence.json").write_text(json.dumps(record, indent=2))
    print(json.dumps({"status": record["status"], "cases": len(cases), "memory": memory, "directory": str(out)}))


if __name__ == "__main__":
    main()

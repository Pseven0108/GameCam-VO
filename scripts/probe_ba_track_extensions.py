"""Actual numerical CUDA checks in BA-Track's independent environment.

This does not instantiate pretrained networks or claim a Demo reproduction.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch


def main():
    upstream = Path("/mnt/d/aaa/GameCam-VO/baselines/ba_track/upstream")
    sys.path[:0] = [str(upstream), str(upstream / "main"), str(upstream / "UniDepth"), str(upstream / "Depth-Anything"), str(upstream.parents[2] / "baselines/runtime_hooks")]
    from main.backend.lietorch import SE3
    from main.backend.altcorr import patchify, corr
    from torch_scatter import scatter_sum
    import xformers.ops
    from xformers.ops.fmha.dispatch import _set_use_fa3

    _set_use_fa3(False)
    tangent = torch.tensor([[.2, -.1, .3, .02, .04, -.03]], device="cuda")
    torch.testing.assert_close(SE3.exp(tangent).log(), tangent, rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(SE3.exp(tangent).matrix() @ SE3.exp(tangent).inv().matrix(), torch.eye(4, device="cuda")[None], rtol=1e-5, atol=1e-6)
    net = torch.arange(16, dtype=torch.float32, device="cuda").reshape(1, 1, 4, 4).requires_grad_(True)
    coordinates = torch.tensor([[[1.25, 1.5]]], device="cuda")
    patches = patchify(net, coordinates, 0)
    torch.testing.assert_close(patches.flatten(), torch.tensor([7.25], device="cuda"))
    patches.sum().backward()
    expected_gradient = torch.zeros_like(net)
    expected_gradient[0, 0, 1:3, 1:3] = torch.tensor([[.375, .125], [.375, .125]], device="cuda")
    torch.testing.assert_close(net.grad, expected_gradient)
    for dtype in (torch.float32, torch.float16):
        feature1 = torch.ones(1, 1, 8, 3, 3, device="cuda", dtype=dtype)
        feature2 = feature1 * 2
        sample_coordinates = torch.ones(1, 1, 2, 3, 3, device="cuda") * 1.25
        indices = torch.zeros(1, device="cuda", dtype=torch.long)
        correlation = corr(feature1, feature2, sample_coordinates, indices, indices, radius=0)
        torch.testing.assert_close(correlation, torch.full_like(correlation, 16.))
    summed = scatter_sum(torch.tensor([1., 2., 3.], device="cuda"), torch.tensor([0, 1, 0], device="cuda"))
    torch.testing.assert_close(summed, torch.tensor([4., 2.], device="cuda"))
    torch.manual_seed(42)
    q = torch.randn(1, 32, 4, 64, device="cuda", dtype=torch.float16)
    output = xformers.ops.memory_efficient_attention(q, q, q)
    reference = torch.nn.functional.scaled_dot_product_attention(q.transpose(1, 2), q.transpose(1, 2), q.transpose(1, 2)).transpose(1, 2)
    torch.testing.assert_close(output, reference, rtol=.02, atol=.02)
    # Imports are a distinct check; models are not constructed and no weights
    # should be fetched by these module definitions.
    from main.batrack import BATRACK
    from unidepth.models import UniDepthV2
    from depth_anything_v2.dpt import DepthAnythingV2
    from gamecam_legacy_nystrom import NystromAttention
    nystrom = NystromAttention(num_heads=2, num_landmarks=128, dropout=0.).cuda().eval()
    qn = torch.randn(2, 32, 16, device="cuda")
    result_nystrom = nystrom(qn, qn, qn)
    torch.testing.assert_close(result_nystrom, torch.nn.functional.scaled_dot_product_attention(qn, qn, qn), rtol=1e-4, atol=1e-5)
    uniform = torch.zeros(2, 256, 16, device="cuda")
    constant = nystrom(uniform, uniform, torch.ones_like(uniform))
    torch.testing.assert_close(constant, torch.ones_like(uniform), rtol=1e-4, atol=1e-5)
    torch.cuda.synchronize()
    result = {
        "status": "BA_TRACK_NATIVE_CUDA_CHECKS_PASSED", "torch": torch.__version__,
        "cuda": torch.version.cuda, "device": torch.cuda.get_device_name(),
        "SE3_nonzero_round_trip": True, "SE3_inverse_identity": True,
        "patchify_bilinear_value_and_gradient": True, "correlation_fp32_fp16": True,
        "scatter_sum": summed.tolist(), "attention_matches_sdpa": True,
        "xformers_fa3_disabled_after_same_stack_host_failure": True,
        "batrack_and_prior_entrypoint_imports": True, "model_inference_executed": False,
        "legacy_nystrom_exact_branch_matches_sdpa": True, "legacy_nystrom_approximate_branch_preserves_uniform_average": True,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()

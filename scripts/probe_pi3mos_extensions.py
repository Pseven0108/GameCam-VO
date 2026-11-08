"""Numerical native setup checks, never a pretrained Pi3MOS result."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys

import torch


def main():
    upstream = Path("/mnt/d/aaa/GameCam-VO/baselines/pi3mos/upstream")
    sys.path.insert(0, str(upstream))
    from dpvo.lietorch import SE3
    from dpvo.altcorr import patchify, corr
    from dpvo import fastba
    from torch_scatter import scatter_sum

    tangent = torch.tensor([[.2, -.1, .3, .02, .04, -.03]], device="cuda")
    torch.testing.assert_close(SE3.exp(tangent).log(), tangent, rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(SE3.exp(tangent).matrix() @ SE3.exp(tangent).inv().matrix(), torch.eye(4, device="cuda")[None], rtol=1e-5, atol=1e-6)
    net = torch.arange(16, dtype=torch.float32, device="cuda").reshape(1, 1, 4, 4).requires_grad_(True)
    coordinates = torch.tensor([[[1.25, 1.5]]], device="cuda")
    patches_sample = patchify(net, coordinates, 0)
    torch.testing.assert_close(patches_sample.flatten(), torch.tensor([7.25], device="cuda"))
    patches_sample.sum().backward()
    expected_gradient = torch.zeros_like(net)
    expected_gradient[0, 0, 1:3, 1:3] = torch.tensor([[.375, .125], [.375, .125]], device="cuda")
    torch.testing.assert_close(net.grad, expected_gradient)
    for dtype in (torch.float32, torch.float16):
        f1 = torch.ones(1, 1, 8, 3, 3, device="cuda", dtype=dtype)
        coords = torch.ones(1, 1, 2, 3, 3, device="cuda") * 1.25
        ix = torch.zeros(1, device="cuda", dtype=torch.long)
        result = corr(f1, f1 * 2, coords, ix, ix, radius=0)
        assert result.shape == (1, 1, 1, 1, 3, 3)
        torch.testing.assert_close(result, torch.full_like(result, 16.))
    summed = scatter_sum(torch.tensor([1., 2., 3.], device="cuda"), torch.tensor([0, 1, 0], device="cuda"))
    torch.testing.assert_close(summed, torch.tensor([4., 2.], device="cuda"))

    # Reprojection of the same 3x3 ray grids under two identical poses must be
    # identity. The BA target is that exact projection (zero residual). Shapes
    # follow PatchGraph and DPVO.update; no benchmark settings are altered.
    count, ppf = 2, 4
    pose_data = torch.zeros(1, count, 7, device="cuda")
    pose_data[..., 6] = 1
    patches = torch.ones(1, count * ppf, 3, 3, 3, device="cuda")
    gy, gx = torch.meshgrid(torch.arange(3, device="cuda"), torch.arange(3, device="cuda"), indexing="ij")
    for k in range(count * ppf):
        patches[0, k, 0] = gx + (k % 2) * 3 + 3
        patches[0, k, 1] = gy + ((k // 2) % 2) * 3 + 3
    intrinsics = torch.tensor([10., 10., 8., 8.], device="cuda").repeat(1, count, 1)
    ii = torch.zeros(ppf, dtype=torch.long, device="cuda")
    jj = torch.ones_like(ii)
    kk = torch.arange(ppf, dtype=torch.long, device="cuda")
    coords = fastba.reproject(pose_data, patches, intrinsics, ii, jj, kk)
    torch.testing.assert_close(coords, patches[:, :ppf, :2], rtol=1e-6, atol=1e-6)
    target = coords[..., 1, 1].contiguous()
    original_patches = patches.clone()
    original_poses = pose_data.clone()
    prior = torch.ones(count, ppf, 1, device="cuda")
    variance = fastba.BA(SE3(pose_data), patches, intrinsics, target, torch.ones_like(target), prior, prior,
                         torch.tensor([1e-4], device="cuda"), ii, jj, kk, 1, 2, M=ppf, iterations=1,
                         eff_impl=False, use_cov_adaptive=True, cov_steepness=10., cov_threshold=1.5)
    torch.testing.assert_close(pose_data, original_poses, rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(patches, original_patches, rtol=1e-5, atol=1e-6)
    assert variance[0].shape == (1, ppf) and torch.isfinite(variance[0]).all() and (variance[0] >= 0).all()
    # Module imports do not construct a network or download checkpoints.
    from pi3.models.pi3 import Pi3
    from dpvo.dpvo import DPVO
    from pi3.models.layers.pos_embed import RoPE2D
    rope = RoPE2D(freq=100.).cuda()
    q = torch.randn(1, 2, 4, 8, device="cuda")
    positions = torch.zeros(1, 4, 2, dtype=torch.long, device="cuda")
    torch.testing.assert_close(rope(q, positions), q)
    importlib.import_module("demo")
    torch.cuda.synchronize()
    print(json.dumps({"status": "PI3MOS_NATIVE_CUDA_CHECKS_PASSED", "torch": torch.__version__,
                      "cuda": torch.version.cuda, "device": torch.cuda.get_device_name(),
                      "SE3_nonzero_round_trip": True, "SE3_inverse_identity": True,
                      "patchify_bilinear_value_and_gradient": True, "correlation_fp32_fp16": True,
                      "scatter_sum": summed.tolist(), "identity_reprojection": True,
                      "zero_residual_BA_preserves_poses_and_depth": True,
                      "covariance_adaptive_branch_finite": True,
                      "BA_returned_relative_depth_std": variance[0].tolist(),
                      "rope_zero_position_identity": True,
                      "official_model_and_demo_entrypoint_imports": True,
                      "model_inference_executed": False,
                      "peak_allocated_bytes": torch.cuda.max_memory_allocated()}))


if __name__ == "__main__":
    main()

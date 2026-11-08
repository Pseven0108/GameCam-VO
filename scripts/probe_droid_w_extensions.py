"""Run inside the isolated Linux DROID-W environment after its native build.

These numerical CUDA checks prove kernel execution on the installed GPU. They
are setup checks, not SLAM or checkpoint reproduction metrics.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch


def main():
    from lietorch import SE3
    from torch_scatter import scatter_sum
    from simple_knn._C import distCUDA2
    import droid_backends
    import diff_gaussian_rasterization
    import xformers.ops
    from xformers.ops.fmha.dispatch import _set_use_fa3

    _set_use_fa3(False)

    device = "cuda"
    torch.cuda.reset_peak_memory_stats()
    transform = SE3.exp(torch.zeros(2, 6, device=device)).matrix()
    torch.testing.assert_close(transform, torch.eye(4, device=device).expand(2, 4, 4))
    tangent = torch.tensor([[.2, -.1, .3, .02, .04, -.03]], device=device)
    torch.testing.assert_close(SE3.exp(tangent).log(), tangent, rtol=1e-5, atol=1e-6)
    reduced = scatter_sum(torch.tensor([1., 2., 3.], device=device), torch.tensor([0, 1, 0], device=device))
    torch.testing.assert_close(reduced, torch.tensor([4., 2.], device=device))
    points = torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]], device=device)
    squared_distances = distCUDA2(points)
    torch.testing.assert_close(squared_distances, torch.tensor([1., 5/3, 5/3, 5/3], device=device))

    poses = torch.zeros(2, 7, device=device)
    poses[:, 6] = 1.
    disps = torch.ones(2, 16, 16, device=device)
    intrinsics = torch.tensor([10., 10., 8., 8.], device=device)
    ii, jj = torch.tensor([0], device=device), torch.tensor([1], device=device)
    distance = droid_backends.frame_distance(poses, disps, intrinsics, ii, jj, .3)
    torch.testing.assert_close(distance, torch.zeros_like(distance))

    q = torch.randn(1, 32, 6, 64, device=device, dtype=torch.float16)
    efficient_attention = xformers.ops.memory_efficient_attention(q, q, q)
    reference_attention = torch.nn.functional.scaled_dot_product_attention(q.transpose(1, 2), q.transpose(1, 2), q.transpose(1, 2)).transpose(1, 2)
    torch.testing.assert_close(efficient_attention, reference_attention, rtol=.02, atol=.02)
    q32 = q.float()
    attention32 = xformers.ops.memory_efficient_attention(q32, q32, q32)
    reference32 = torch.nn.functional.scaled_dot_product_attention(q32.transpose(1, 2), q32.transpose(1, 2), q32.transpose(1, 2)).transpose(1, 2)
    torch.testing.assert_close(attention32, reference32, rtol=1e-4, atol=1e-5)
    torch.cuda.synchronize()

    # Full entry-point import exposes eager GUI/mapping dependencies even when
    # the official selected config disables both at execution time.
    upstream = Path("/mnt/d/aaa/GameCam-VO/baselines/droid_w/upstream")
    sys.path.insert(0, str(upstream))
    import src.slam

    print(json.dumps({
        "status": "NATIVE_CUDA_CHECKS_PASSED",
        "torch": torch.__version__, "cuda": torch.version.cuda,
        "device": torch.cuda.get_device_name(),
        "lietorch_exp_identity": True, "torch_scatter_sum": reduced.tolist(),
        "lietorch_nonzero_exp_log_round_trip": True,
        "knn_mean_squared_distance": squared_distances.tolist(),
        "droid_identity_frame_distance": distance.tolist(),
        "xformers_matches_sdpa": True, "xformers_fa3_disabled": True,
        "xformers_fp32_matches_sdpa": True,
        "gaussian_extension_import": True,
        "slam_entrypoint_import": True,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "model_inference_executed": False,
    }))


if __name__ == "__main__":
    main()

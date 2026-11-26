"""Bounded local GPU validation with synthetic tensors only; no research models."""
from __future__ import annotations

import argparse
import gc
import importlib.metadata as metadata
import json
import multiprocessing as mp
import os
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")


def spawned_worker(connection) -> None:
    """Independent child context; deliberately do not exchange CUDA tensors."""
    try:
        import torch
        x = torch.arange(2048, dtype=torch.float32, device="cuda")
        value = float((x * x).sum().item())
        expected = float((torch.arange(2048, dtype=torch.float64) ** 2).sum().item())
        torch.cuda.synchronize()
        connection.send({"ok": abs(value - expected) / expected < 1e-6,
                         "device": torch.cuda.get_device_name(0), "value": value,
                         "relative_error": abs(value - expected) / expected,
                         "peak_allocated_bytes": torch.cuda.max_memory_allocated()})
    except BaseException:
        connection.send({"ok": False, "error": traceback.format_exc()})
    finally:
        connection.close()


def run(output: Path) -> int:
    import torch
    import torch.nn.functional as functional
    checks = []
    details = {}
    started = time.perf_counter()

    def check(name, operation):
        began = time.perf_counter()
        try:
            result = operation()
            checks.append({"name": name, "status": "PASS", "seconds": time.perf_counter() - began,
                           "details": result})
            print("PASS " + name, flush=True)
        except Exception:
            checks.append({"name": name, "status": "FAIL", "seconds": time.perf_counter() - began,
                           "error": traceback.format_exc()})
            print("FAIL " + name + "\n" + checks[-1]["error"], flush=True)

    def imports():
        import cv2
        import numpy
        import scipy
        import matplotlib
        import PIL
        import pytest
        import torchvision
        versions = {n: metadata.version(n) for n in ["torch", "torchvision", "numpy", "scipy",
                    "opencv-python-headless", "pillow", "matplotlib", "pytest"]}
        details["packages"] = versions
        return versions
    check("scientific_and_torchvision_imports", imports)

    available = torch.cuda.is_available()
    def hardware():
        assert available, "CUDA unavailable"
        device = torch.cuda.get_device_properties(0)
        capability = torch.cuda.get_device_capability(0)
        architectures = torch.cuda.get_arch_list()
        assert "RTX 5060" in device.name, device.name
        assert capability == (12, 0), capability
        assert "sm_120" in architectures, architectures
        assert 7 << 30 <= device.total_memory <= 9 << 30
        result = {"device_name": device.name, "capability": list(capability),
                  "build_architectures": architectures, "device_total_memory_bytes": device.total_memory,
                  "torch_cuda_runtime": torch.version.cuda, "cudnn_version": torch.backends.cudnn.version(),
                  "cudnn_benchmark": torch.backends.cudnn.benchmark,
                  "cudnn_deterministic": torch.backends.cudnn.deterministic,
                  "float32_matmul_precision": torch.get_float32_matmul_precision()}
        details["GPU"] = result
        return result
    check("sm120_native_build_and_hardware", hardware)
    if available:
        torch.cuda.reset_peak_memory_stats()
        details["free_total_bytes_before"] = list(torch.cuda.mem_get_info())
        generator = torch.Generator().manual_seed(43)
        a = torch.randn(256, 256, generator=generator) * 0.1
        b = torch.randn(256, 256, generator=generator) * 0.1
        for dtype, label, rtol, atol in [(torch.float32, "float32", 2e-4, 2e-5),
                                        (torch.float16, "float16", 3e-3, 5e-4),
                                        (torch.bfloat16, "bfloat16", 3e-2, 5e-3)]:
            def matmul(dtype=dtype, rtol=rtol, atol=atol):
                inputs = a.to(dtype), b.to(dtype)
                reference = inputs[0].double() @ inputs[1].double()
                actual = (inputs[0].cuda() @ inputs[1].cuda()).float().cpu()
                assert torch.isfinite(actual).all()
                torch.testing.assert_close(actual.double(), reference, rtol=rtol, atol=atol)
                return {"max_abs_error": (actual.double() - reference).abs().max().item(),
                        "rtol": rtol, "atol": atol}
            check("cuda_matmul_" + label, matmul)

        def convolution():
            x = torch.randn(1, 8, 90, 160, generator=generator) * 0.1
            kernel = torch.randn(16, 8, 3, 3, generator=generator) * 0.1
            ref = functional.conv2d(x, kernel, padding=1)
            with torch.inference_mode():
                result = functional.conv2d(x.cuda(), kernel.cuda(), padding=1).cpu()
                with torch.autocast(device_type="cuda", dtype=torch.float16):
                    mixed = functional.conv2d(x.cuda(), kernel.cuda(), padding=1).float().cpu()
            torch.testing.assert_close(result, ref, rtol=2e-4, atol=2e-5)
            torch.testing.assert_close(mixed, ref, rtol=5e-3, atol=5e-4)
            return {"shape": list(result.shape), "float32_max_abs_error": (result-ref).abs().max().item(),
                    "autocast_max_abs_error": (mixed-ref).abs().max().item(), "synthetic_only": True}
        check("cudnn_convolution_and_fp16_autocast", convolution)

        def interpolation():
            x = torch.rand(1, 1, 90, 160, generator=generator) + 0.05
            ref = functional.interpolate(x, size=(360, 640), mode="bilinear", align_corners=False)
            actual = functional.interpolate(x.cuda(), size=(360, 640), mode="bilinear", align_corners=False).cpu()
            torch.testing.assert_close(actual, ref, rtol=1e-5, atol=2e-6)
            assert (actual > 0).all()
            return {"shape": list(actual.shape), "max_abs_error": (actual-ref).abs().max().item()}
        check("depth_bilinear_restore_cpu_gpu", interpolation)

        def solve():
            base = torch.randn(48, 48, generator=generator).double()
            matrix = base.T @ base + torch.eye(48, dtype=torch.float64)
            right = torch.randn(48, 3, generator=generator).double()
            reference = torch.linalg.solve(matrix, right)
            actual = torch.linalg.solve(matrix.cuda(), right.cuda()).cpu()
            torch.testing.assert_close(actual, reference, rtol=1e-10, atol=1e-11)
            return {"max_abs_error": (actual-reference).abs().max().item(),
                    "relative_residual": (torch.linalg.norm(matrix@actual-right)/torch.linalg.norm(right)).item()}
        check("float64_spd_linear_solve", solve)

        def gradient():
            weight = torch.randn(16, 8, generator=generator, requires_grad=True)
            x = torch.randn(4, 8, generator=generator)
            ((x @ weight.T)**2).mean().backward()
            gpu_weight = weight.detach().cuda().requires_grad_(True)
            ((x.cuda() @ gpu_weight.T)**2).mean().backward()
            torch.testing.assert_close(gpu_weight.grad.cpu(), weight.grad, rtol=3e-4, atol=3e-5)
            return {"gradient_max_abs_error": (gpu_weight.grad.cpu()-weight.grad).abs().max().item(),
                    "research_model_loaded": False, "optimizer_steps": 0}
        check("synthetic_autograd_cpu_gpu", gradient)

        def nms():
            from torchvision.ops import nms
            boxes = torch.tensor([[0.,0.,10.,10.],[1.,1.,11.,11.],[20.,20.,30.,30.]])
            scores = torch.tensor([0.9,0.8,0.7])
            reference = nms(boxes, scores, 0.5)
            actual = nms(boxes.cuda(), scores.cuda(), 0.5).cpu()
            assert torch.equal(actual, reference) and actual.tolist() == [0,2]
            return {"selected": actual.tolist(), "native_torchvision_cuda_op": True}
        check("torchvision_compiled_cuda_nms", nms)

        def transfer():
            x = torch.arange(4096, dtype=torch.float32).pin_memory()
            result = x.to("cuda", non_blocking=True).cpu()
            assert torch.equal(x, result)
            return {"elements": x.numel(), "pinned": x.is_pinned()}
        check("pinned_memory_transfer", transfer)

        def spawn():
            context = mp.get_context("spawn")
            receive, send = context.Pipe(duplex=False)
            child = context.Process(target=spawned_worker, args=(send,))
            child.start()
            send.close()
            try:
                if not receive.poll(45):
                    raise TimeoutError("Independent spawn GPU child timed out")
                result = receive.recv()
                child.join(15)
                assert child.exitcode == 0, child.exitcode
                assert result["ok"], result
                return {**result, "cuda_tensor_IPC_tested": False, "one_independent_child": True}
            finally:
                if child.is_alive():
                    child.terminate()
                    child.join(10)
                receive.close()
        check("windows_spawn_independent_gpu_context", spawn)
        torch.cuda.synchronize()
        details["peak_allocated_bytes_parent"] = torch.cuda.max_memory_allocated()
        details["peak_reserved_bytes_parent"] = torch.cuda.max_memory_reserved()
        gc.collect()
        torch.cuda.empty_cache()
        details["free_total_bytes_after"] = list(torch.cuda.mem_get_info())
    passed = sum(check["status"] == "PASS" for check in checks)
    report = {"status": "PASS" if passed == len(checks) and available else "FAIL", "passed": passed,
              "total": len(checks), "checks": checks, "details": details,
              "python": sys.version, "python_executable": sys.executable, "platform": platform.platform(),
              "utc": datetime.now(timezone.utc).isoformat(), "seconds": time.perf_counter()-started,
              "scope": {"synthetic_GPU_operations": True, "research_model_loaded": False,
                        "checkpoint_deserialized": False, "real_RGB_read": False, "SLAM_executed": False,
                        "custom_CUDA_compiled": False, "remote_GPU_used": False,
                        "metric3d_inference_validated": False, "droidw_runtime_validated": False}}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError("Preserve prior check: " + str(output))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "passed": passed, "total": len(checks), "output": str(output)}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))

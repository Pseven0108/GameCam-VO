"""Minimal CUDA tensor sharing probe, independent of any SLAM/checkpoint."""
import json
import torch
import torch.multiprocessing as mp


def worker(tensor, queue):
    queue.put(float(tensor.sum().cpu()))


if __name__ == "__main__":
    mp.set_start_method("spawn")
    queue = mp.Queue()
    tensor = torch.ones(64, 64, device="cuda")
    child = mp.Process(target=worker, args=(tensor, queue))
    child.start()
    child.join(timeout=25)
    timed_out = child.is_alive()
    if timed_out:
        child.terminate()
        child.join()
    value = queue.get(timeout=2) if child.exitcode == 0 else None
    passed = child.exitcode == 0 and value == 4096.
    print(json.dumps({"status": "SMALL_CUDA_IPC_PASSED" if passed else "SMALL_CUDA_IPC_FAILED", "exit_code": child.exitcode, "timed_out": timed_out, "value": value, "model_inference_executed": False}), flush=True)
    raise SystemExit(int(not passed))

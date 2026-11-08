"""Opt-in process CUDA allocator telemetry; imported only by frozen run commands."""
import atexit
import json
import os
from pathlib import Path
import sys


def _capture_cuda_memory(reason):
    destination = os.environ.get("GAMECAM_CUDA_MEMORY_DIR")
    if not destination:
        return
    try:
        torch = sys.modules.get("torch")
        initialized = bool(torch is not None and torch.cuda.is_initialized())
        record = {"pid": os.getpid(), "ppid": os.getppid(), "reason": reason,
                  "cuda_initialized": initialized,
                  "scope": "This process's PyTorch allocator; shared CUDA IPC storage and other processes are not a dedicated combined model peak."}
        if initialized:
            record.update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                          peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                          allocated_bytes_at_capture=torch.cuda.memory_allocated(),
                          reserved_bytes_at_capture=torch.cuda.memory_reserved())
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=True)
        (path / f"cuda_memory_{os.getpid()}_{reason}.json").write_text(json.dumps(record, indent=2))
    except Exception as error:
        sys.stderr.write(f"GameCam CUDA telemetry unavailable: {error}\n")


if os.environ.get("GAMECAM_CUDA_MEMORY_DIR"):
    atexit.register(_capture_cuda_memory, "exit")
    _original_excepthook = sys.excepthook

    def _recording_excepthook(kind, value, traceback):
        _capture_cuda_memory("unhandled_exception")
        _original_excepthook(kind, value, traceback)

    sys.excepthook = _recording_excepthook

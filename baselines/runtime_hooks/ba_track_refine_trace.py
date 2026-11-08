"""Optional iteration observation; calls the original refinement step once."""
from __future__ import annotations

import json
import math
from pathlib import Path
import time


def install_refine_trace(directory):
    from model import trainer

    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    log_path = destination / "iterations.jsonl"
    if log_path.exists():
        raise FileExistsError("Refinement trace must use a new output directory")
    original = trainer.global_alignment_iter

    def observe(*args, **kwargs):
        started = time.monotonic()
        result = original(*args, **kwargs)
        loss, rate = result
        iteration = args[1] if len(args) > 1 else kwargs["cur_iter"]
        total = args[2] if len(args) > 2 else kwargs["niter"]
        record = {"iteration_zero_based": int(iteration), "total_iterations": int(total),
                  "native_loss": float(loss) if math.isfinite(float(loss)) else None,
                  "native_loss_finite": math.isfinite(float(loss)), "learning_rate": float(rate),
                  "native_step_wall_seconds": time.monotonic()-started,
                  "original_step_called_once_return_value_unchanged": True}
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record)+"\n")
        return result

    trainer.global_alignment_iter = observe

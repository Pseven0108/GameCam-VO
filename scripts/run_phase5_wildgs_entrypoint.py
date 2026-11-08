"""Run original WildGS entry point; optional explicit thread actor portability."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import sys
import threading
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


class ActorThread:
    """Process-shaped launcher for unchanged, pipe-synchronized native actors."""
    def __init__(self, target, args=(), **kwargs):
        self.target, self.args, self.exitcode = target, args, None
        self.thread = threading.Thread(target=self._run, daemon=True, name="WildGS_"+target.__name__)

    def _run(self):
        try:
            self.target(*self.args)
            self.exitcode = 0
        except BaseException:
            self.exitcode = 1
            traceback.print_exc()

    def start(self):
        self.thread.start()

    def join(self, timeout=None):
        self.thread.join(timeout)

    def is_alive(self):
        return self.thread.is_alive()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--actor-mode", choices=("native-process", "thread-portability"), default="native-process")
    args = parser.parse_args()
    root = ROOT / "baselines/wildgs_slam/upstream"
    os.chdir(root)
    sys.path.insert(0, str(root))
    import src.slam as slam_module
    if args.actor_mode == "thread-portability":
        import torch.multiprocessing as native_mp
        # Replace only this module's launcher namespace. Original SLAM.run,
        # tracking(), mapping(), per-keyframe Pipe handshakes, losses and kernels
        # stay intact. Native CPU Printer still uses the original subprocess API.
        slam_module.mp = SimpleNamespace(Process=ActorThread, Pipe=native_mp.Pipe, Queue=native_mp.Queue, active_children=native_mp.active_children)
        print(json.dumps({"execution_variant": "WildGS_native_math_thread_actor_portability",
            "reason": "Actual native CUDA shared-tensor process reconstruction fails on this host",
            "global_RNG_and_actor_scheduling_may_differ": True, "full_model_bitwise_or_paper_score_equivalence_claim": False}), flush=True)
    sys.argv = [str(root / "run.py"), str(Path(args.config).resolve())]
    runpy.run_path(str(root / "run.py"), run_name="__main__")


if __name__ == "__main__":
    main()

"""Execute identical cached WildGS code with original actor targets and checks."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--actor-mode", choices=("native-process", "thread-portability"), required=True)
    args = parser.parse_args()
    cache = Path(__file__).resolve().parent
    root = cache / "wildgs"
    os.chdir(root)
    sys.path.insert(0, str(root))
    import src.slam as slam_module
    if args.actor_mode == "thread-portability":
        import torch.multiprocessing as native_mp
        from run_phase5_wildgs_entrypoint import ActorThread
        slam_module.mp = SimpleNamespace(Process=ActorThread, Pipe=native_mp.Pipe, Queue=native_mp.Queue, active_children=native_mp.active_children)
    print(json.dumps({"source_execution_root": str(root), "actor_mode": args.actor_mode,
        "native_anomaly_and_NaN_checks_retained": True, "model_math_and_hyperparameters_unchanged": True,
        "actor_scheduling_RNG_deviation_still_applies": args.actor_mode == "thread-portability"}), flush=True)
    sys.argv = [str(root / "run.py"), str(Path(args.config).resolve())]
    runpy.run_path(str(root / "run.py"), run_name="__main__")


if __name__ == "__main__":
    main()

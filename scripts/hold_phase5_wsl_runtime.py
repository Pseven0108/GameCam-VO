"""Owned foreground lease: preserve WSL runtime between this task's GPU jobs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    if not out.is_relative_to((ROOT / "data/phase5_runtime").resolve()) or not out.is_dir():
        raise ValueError("Require an existing exact owned task-runtime directory")
    record = out / "lease.json"
    state = {"status": "OWNED_FOREGROUND_WSL_RUNTIME_LEASE_RUNNING", "PID": os.getpid(),
             "started_at_utc": datetime.now(timezone.utc).isoformat(),
             "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
             "stop_file": str(out / "STOP"), "maximum_duration_hours": 72,
             "scope": "Only sleeps while the current experiment is active; no model, CUDA, network, scheduled task or startup installation"}
    with record.open("x", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    print(json.dumps(state), flush=True)
    start = time.monotonic()
    try:
        while not (out / "STOP").exists() and time.monotonic() - start < 72 * 3600:
            time.sleep(5)
    finally:
        state.update(status="OWNED_FOREGROUND_WSL_RUNTIME_LEASE_STOPPED",
                     stopped_at_utc=datetime.now(timezone.utc).isoformat())
        record.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

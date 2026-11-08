"""Add one owned temporary swap file for an observed live RAM exhaustion."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path("/mnt/d/aaa/GameCam-VO")
OWNED = Path("/home/lsuser/.local/share/gamecam-vo/phase5_runtime")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--owning-run", type=Path, required=True)
    parser.add_argument("--pid", type=int, required=True)
    args = parser.parse_args()
    out = args.owning_run.resolve()
    if os.geteuid() != 0 or not out.is_relative_to(ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK"):
        raise RuntimeError("Only the diagnosed owned BA run, under WSL root, is allowed")
    command = Path(f"/proc/{args.pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode()
    if str(out) not in command or "run_ba_track_reviewed_entrypoint.py" not in command:
        raise ValueError("PID no longer identifies this dedicated model attempt")
    record_file = out / "memory_budget_intervention.json"
    if record_file.exists():
        raise FileExistsError("Preserve the existing resource intervention; do not repeat it")
    size = 8*1024**3
    free_c = shutil.disk_usage("/mnt/c").free
    if free_c < size+3*1024**3:
        raise RuntimeError("Not enough C-drive reserve for this fixed owned 8GiB file")
    OWNED.mkdir(parents=True, exist_ok=True)
    file = OWNED / "phase5_extra_swap_20261101_8GiB"
    if not file.resolve().is_relative_to(OWNED.resolve()) or file.exists():
        raise FileExistsError("Only a new exact owned swap path is accepted")
    record = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "status": "RESOURCE_CHANGE_STARTED", "native_PID": args.pid,
        "owning_run": str(out), "swap_file": str(file), "added_swap_bytes": size, "C_free_bytes_before": free_c,
        "reason": "Observed ~7.4GiB native RSS plus ~2GiB process swap, almost no MemAvailable, existing2GiB swap full; GPU idle during native compute",
        "before_meminfo": Path("/proc/meminfo").read_text(), "before_native_process_status": Path(f"/proc/{args.pid}/status").read_text(),
        "no_WSL_restart": True, "algorithm_or_weights_or_input_changed": False, "old_swap_and_environments_unchanged": True,
        "native_wall_time_contains_memory_pressure_and_resource_intervention": True, "exclusive_fair_FPS_comparison_claim": False,
        "commands": []}
    def write():
        record_file.write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    write()
    for argv in (["fallocate", "-l", str(size), str(file)], ["chmod", "600", str(file)], ["mkswap", str(file)], ["swapon", "--priority", "-3", str(file)]):
        result = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        record["commands"].append({"command": argv, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        write()
        if result.returncode:
            record["status"] = "RESOURCE_CHANGE_FAILED_RETAIN_OWNED_FILE_AND_LOG"
            write()
            raise RuntimeError("Owned resource command failed; original process not terminated")
    record.update(status="OWNED_EXTRA_8GIB_SWAP_ACTIVE", completed_at_utc=datetime.now(timezone.utc).isoformat(),
        after_meminfo=Path("/proc/meminfo").read_text(), C_free_bytes_after=shutil.disk_usage("/mnt/c").free,
        swap_listing=subprocess.check_output(["swapon", "--show", "--bytes"], text=True),
        cleanup_requirement="After all model processes stop and this exact file has zero used swap, swapoff only this file and remove only this owned file; do not remove the original WSL swap")
    write()
    print(json.dumps({key: record[key] for key in ("status", "swap_file", "added_swap_bytes", "C_free_bytes_after", "swap_listing")}))


if __name__ == "__main__":
    main()

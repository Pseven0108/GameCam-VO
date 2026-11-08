"""Prepare a fresh owned D-backed swap before resumed native experiments."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SIZE = 16*1024**3


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")


def memory():
    return {row.split(":")[0]+"_bytes": int(row.split()[1])*1024 for row in Path("/proc/meminfo").read_text().splitlines()
        if row.startswith(("MemTotal:", "MemAvailable:", "SwapTotal:", "SwapFree:"))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--activate-linux", type=Path)
    args = parser.parse_args()
    reports = ROOT / "reports/PHASE5"
    pointer = reports / "active_phase5_runtime_budget.json"
    if pointer.exists():
        raise FileExistsError("Audit the existing resource budget; never duplicate activation")
    resume_pointer = read(reports / "active_phase5_resume_20261102.json")
    resume_file = Path(str(resume_pointer["resume_file"]).replace("\\", "/").replace("D:/", "/mnt/d/", 1)) if os.name != "nt" else Path(resume_pointer["resume_file"])
    if not read(resume_file)["supersedes_previous_stop_for_future_E15_E16_E17_work"]:
        raise ValueError("The explicit user resume is required")
    if os.name == "nt":
        if args.activate_linux:
            raise RuntimeError("Native activation belongs to WSL")
        if shutil.disk_usage(ROOT).free < SIZE+12*1024**3:
            raise RuntimeError("Reserve D backing capacity and12GiB working headroom")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        folder = ROOT / "data/phase5_runtime" / (stamp+"_E15_D_sparse_swap_16GiB")
        folder.mkdir(exist_ok=False)
        file = folder / "owned_E15_D_sparse_16GiB.raw"
        with file.open("xb"):
            pass
        command = ["fsutil.exe", "sparse", "setflag", str(file)]
        result = subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        receipt = {"status": "NEW_OWNED_E15_SPARSE_FILE_CREATED", "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "file_created_exclusively_with_xb": True, "existing_file_overwritten": False,
            "Windows_file": str(file), "linux_file": "/mnt/d/"+file.as_posix()[3:], "logical_bytes": SIZE,
            "sparse_command": command, "sparse_command_exit_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr, "helper_source_sha256": digest(Path(__file__))}
        receipt_file = folder / "creation_receipt.json"
        write(receipt_file, receipt)
        if result.returncode:
            raise RuntimeError("Sparse flag failed; preserve the new empty file and receipt")
        with file.open("r+b") as stream:
            stream.truncate(SIZE)
        if file.stat().st_size != SIZE or not file.stat().st_file_attributes & 0x200:
            raise RuntimeError("NTFS sparse attribute or logical size check failed")
        shutil.copy2(__file__, folder / (Path(__file__).name+".executed_source"))
        command = ["wsl.exe", "-d", "Ubuntu", "-u", "root", "--exec", "/home/lsuser/.local/share/gamecam-vo/envs/ba-track/bin/python",
            "/mnt/d/aaa/GameCam-VO/scripts/prepare_phase5_resumed_D_swap.py", "--activate-linux", "/mnt/d/"+receipt_file.as_posix()[3:]]
        return subprocess.call(command)
    if os.geteuid() != 0 or str(ROOT) != "/mnt/d/aaa/GameCam-VO" or args.activate_linux is None:
        raise RuntimeError("Require the owned WSL-root activation branch")
    from cleanup_phase5_owned_runtime import owned_models
    from probe_phase5_D_loop_swap import run, swaps, verify_owned
    receipt_file = args.activate_linux.resolve()
    if not receipt_file.is_relative_to((ROOT / "data/phase5_runtime").resolve()):
        raise ValueError("Creation receipt escaped the exact owned runtime root")
    receipt = read(receipt_file)
    file = receipt_file.parent / "owned_E15_D_sparse_16GiB.raw"
    if (not receipt["file_created_exclusively_with_xb"] or receipt["existing_file_overwritten"]
        or receipt["sparse_command_exit_code"] or receipt["logical_bytes"] != SIZE
        or receipt["helper_source_sha256"] != digest(Path(__file__))
        or Path(receipt["linux_file"]) != file or file.is_symlink() or file.stat().st_size != SIZE or owned_models()):
        raise ValueError("Creation/source/ownership/idle-model guard failed")
    lease_pointer = read(reports / "active_E15_runtime_lease.json")
    lease_file = Path(lease_pointer["lease_file"].replace("\\", "/").replace("D:/", "/mnt/d/", 1))
    lease = read(lease_file)
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    lease_command = (Path("/proc") / str(lease["PID"]) / "cmdline").read_bytes()
    if lease["status"] != "OWNED_FOREGROUND_WSL_RUNTIME_LEASE_RUNNING" or lease["boot_id"] != boot or b"hold_phase5_wsl_runtime.py" not in lease_command:
        raise RuntimeError("Require the live owned foreground WSL lease")
    folder = ROOT / "logs/PHASE5" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")+"_E15_owned_D_swap")
    folder.mkdir(exist_ok=False)
    state_file = folder / "state.json"
    state = {"status": "OWNED_E15_D_SWAP_PREPARATION_STARTED", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "backing_file": str(file), "logical_bytes": SIZE, "creation_receipt": str(receipt_file), "creation_receipt_sha256": digest(receipt_file),
        "boot_id": boot, "runtime_lease_file": str(lease_file), "runtime_lease_sha256_at_activation": digest(lease_file),
        "memory_before": memory(), "swaps_before": swaps(), "commands": [], "model_math_inputs_weights_seeds_or_environments_changed": False,
        "original_swap_entries_modified_or_removed": False, "WSL_restarted": False, "preparation_before_any_E15_model_launch": True}
    write(state_file, state)
    attached = run(["losetup", "--find", "--show", "--nooverlap", str(file)])
    state["commands"].append(attached); write(state_file, state)
    if attached["exit_code"]:
        raise RuntimeError("Owned loop attachment failed; preserve state")
    loop = attached["stdout"].strip()
    state["loop"] = loop; state["verified_owned_loop_mapping"] = verify_owned(loop, file, SIZE)
    if any(row[0] == loop for row in swaps()):
        raise RuntimeError("Refuse formatting any active swap")
    payload = b"GameCam-E15-new-owned-D-swap-IO"*64
    with open(loop, "r+b", buffering=0) as stream:
        stream.seek(SIZE-16384)
        if stream.read(len(payload)) != bytes(len(payload)):
            raise ValueError("Fresh owned sparse hole failed zero-read check")
        stream.seek(SIZE-16384); stream.write(payload); os.fsync(stream.fileno())
        stream.seek(SIZE-16384)
        if stream.read(len(payload)) != payload:
            raise ValueError("Fresh owned sparse IO roundtrip failed")
    for command in (["mkswap", "--label", "GameCamP5E15D16", loop], ["swapon", "--priority", "-3", loop]):
        result = run(command); state["commands"].append(result); write(state_file, state)
        if result["exit_code"]:
            raise RuntimeError("Owned swap setup failed; never detach an active swap blindly")
    current = swaps()
    if not all(any(r[0] == old[0] and r[1:3] == old[1:3] and r[4] == old[4] for r in current) for old in state["swaps_before"]):
        raise RuntimeError("An original swap entry unexpectedly changed")
    state.update(status="OWNED_E15_D_LOOP_16GIB_SWAP_ACTIVE", activated_at_utc=datetime.now(timezone.utc).isoformat(),
        memory_after=memory(), swaps_after=current, cleanup="After all native work: verify this exact loop/backing, safely swapoff only the owned loop, detach it and remove only this task-created file; preserve original swap and environments")
    shutil.copy2(__file__, folder / (Path(__file__).name+".executed_source"))
    write(state_file, state)
    write(reports / "E15_runtime_resource_budget.json", state)
    write(pointer, {"state_file": str(state_file), "sha256": digest(state_file), "status": state["status"]})
    print(json.dumps({"status": state["status"], "loop": loop, "memory_after": state["memory_after"], "state_file": str(state_file)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

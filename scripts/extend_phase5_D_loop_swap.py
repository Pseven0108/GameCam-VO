"""Add an owned D-backed16GiB swap area without touching existing devices."""
from __future__ import annotations

from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

from probe_phase5_D_loop_swap import ROOT, run, swaps, verify_owned


def memory():
    fields = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            fields[key+"_bytes"] = int(value.split()[0])*1024
    return fields


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2)+"\n")


def main():
    if os.name != "posix" or os.geteuid() != 0 or str(ROOT) != "/mnt/d/aaa/GameCam-VO":
        raise RuntimeError("Require root in the exact existing WSL project")
    target_run = ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T152634Z_crowd"
    if (target_run / "status.json").exists() or not (target_run / "sparse_tracker_and_BA_process.json").exists():
        raise RuntimeError("The specifically observed active sparse run is required")
    probe = json.loads((ROOT / "reports/PHASE5/D_loop_swap_probe.json").read_text())
    if probe["status"] != "OWNED_D_LOOP_SWAP_ACTIVATION_PASS" or not probe["owned_probe_detached"] or not probe["prior_swap_entries_preserved"]:
        raise ValueError("Actual owned-device probe must pass first")
    size = 16*1024**3
    if shutil.disk_usage(ROOT).free < size+12*1024**3 or shutil.disk_usage("/mnt/c").free < 3*1024**3:
        raise RuntimeError("Preserve D/C workspace and system-drive headroom")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = ROOT / "data/phase5_runtime" / (stamp+"_D_loop_swap_16GiB")
    folder.mkdir(parents=True, exist_ok=False)
    if folder.resolve().parent != (ROOT / "data/phase5_runtime").resolve():
        raise ValueError("Owned backing-file path escaped workspace")
    file = folder / "phase5_extra_swap_D_16GiB.raw"
    log = ROOT / "logs/PHASE5" / (stamp+"_D_loop_swap_16GiB")
    log.mkdir(parents=True, exist_ok=False)
    for source in (Path(__file__), Path(__file__).with_name("probe_phase5_D_loop_swap.py")):
        shutil.copy2(source, log / (source.name+".executed_source"))
    state = {"status": "OWNED_D_SWAP_ALLOCATION_STARTED", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "MID_RUN_RESOURCE_BUDGET_EXTENSION_OWNED_D_LOOP_SWAP", "backing_file": str(file), "bytes": size,
        "memory_before": memory(), "swaps_before": swaps(), "D_free_before_bytes": shutil.disk_usage(ROOT).free,
        "C_free_before_bytes": shutil.disk_usage("/mnt/c").free, "native_run": str(target_run), "commands": [],
        "WSL_restarted": False, "native_model_or_hyperparameters_or_seed_or_input_changed": False,
        "original_swap_entries_modified_or_removed": False, "native_inference_replayed": False,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write(log / "state.json", state)
    print(json.dumps({"status": state["status"], "log": str(log), "backing_file": str(file)}), flush=True)
    with file.open("xb") as stream:
        try:
            os.posix_fallocate(stream.fileno(), 0, size)
            state["allocation_method"] = "posix_fallocate"
        except OSError as error:
            if error.errno not in (errno.ENOSYS, errno.EOPNOTSUPP, errno.EINVAL):
                raise
            state["allocation_method"] = "bounded_1MiB_zero_writes"
            block = bytes(1024**2)
            for i in range(size//len(block)):
                stream.write(block)
                if (i+1) % 1024 == 0:
                    stream.flush()
                    print(json.dumps({"allocated_GiB": (i+1)//1024}), flush=True)
        stream.flush(); os.fsync(stream.fileno())
    if file.stat().st_size != size or shutil.disk_usage(ROOT).free < 12*1024**3:
        raise RuntimeError("Owned raw-file allocation/remaining headroom failed")
    state["D_free_after_allocation_bytes"] = shutil.disk_usage(ROOT).free
    attached = run(["losetup", "--find", "--show", "--nooverlap", str(file)])
    state["commands"].append(attached)
    if attached["exit_code"]:
        write(log / "state.json", state)
        raise RuntimeError("Owned loop attach failed; do not touch existing disks")
    loop = attached["stdout"].strip()
    state["loop"] = loop
    state["verified_owned_mapping"] = verify_owned(loop, file, size)
    if any(r[0] == loop for r in swaps()):
        raise RuntimeError("Refuse to reinitialize an active swap device")
    write(log / "state.json", state)
    for command in (["mkswap", "--label", "GameCamP5D16", loop], ["swapon", "--priority", "-4", loop]):
        result = run(command)
        state["commands"].append(result)
        write(log / "state.json", state)
        if result["exit_code"]:
            raise RuntimeError("Owned swap setup failed; preserve the exact device/file evidence")
    current = swaps()
    active = next((r for r in current if r[0] == loop), None)
    if not active or int(active[2])*1024 < size-8192 or not all(any(r[0] == old[0] for r in current) for old in state["swaps_before"]):
        raise RuntimeError("New swap capacity or preservation of original entries failed")
    state.update(status="OWNED_D_LOOP_16_GIB_SWAP_ACTIVE", activated_at_utc=datetime.now(timezone.utc).isoformat(),
        memory_after=memory(), swaps_after=current, C_free_after_bytes=shutil.disk_usage("/mnt/c").free,
        summary="Active BA Crowd RAM/swap usage increased. Added16GiB lower-priority loop swap backed only by a verified new D-drive file; original2+8GiB swaps untouched. Native input, weights, math, seeds and active process unchanged; no WSL restart or model replay. Observed wall time includes this live resource/IO intervention and is not an isolated fair-FPS benchmark.",
        cleanup="After all model work, verify exact loop/backing-file ownership and zero swap use before swapoff/detach/removing only this newly created file; never detach active swap or touch original devices.")
    write(log / "state.json", state)
    write(target_run / "memory_budget_intervention.json", state)
    shutil.copy2(__file__, target_run / "memory_budget_intervention_D_loop.executed_source.py")
    write(ROOT / "reports/PHASE5/D_loop_swap_runtime.json", state)
    print(json.dumps({"status": state["status"], "loop": loop, "memory_after": state["memory_after"], "D_free_after_bytes": shutil.disk_usage(ROOT).free}), flush=True)


if __name__ == "__main__":
    main()

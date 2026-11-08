"""Activate only the already verified new owned NTFS-sparse16GiB loop file."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

from probe_phase5_D_loop_swap import ROOT, run, swaps, verify_owned
from extend_phase5_D_loop_swap import memory, write


def main():
    if os.geteuid() != 0 or str(ROOT) != "/mnt/d/aaa/GameCam-VO":
        raise RuntimeError("Require root in the existing WSL and exact owned project")
    folder = ROOT / "data/phase5_runtime/20261101T1659Z_D_sparse_loop_swap_16GiB"
    receipt_file = folder / "creation_receipt.json"
    receipt = json.loads(receipt_file.read_text())
    file = folder / "phase5_extra_swap_D_sparse_16GiB.raw"
    size = 16*1024**3
    if (folder.resolve().parent != (ROOT / "data/phase5_runtime").resolve()
        or Path(receipt["linux_file"]).resolve() != file.resolve() or receipt["logical_bytes"] != size
        or not receipt["file_created_exclusively_with_wx"] or receipt["existing_user_file_overwritten"]
        or receipt["NTFS_sparse_set_command_exit_code"] != 0 or file.stat().st_size != size):
        raise ValueError("Fresh owned file creation/identity/size checks failed")
    if shutil.disk_usage(ROOT).free < size+12*1024**3 or shutil.disk_usage("/mnt/c").free < 3*1024**3:
        raise RuntimeError("Reserve D backing capacity plus12GiB and C system headroom")
    target_run = ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T152634Z_crowd"
    old_failure = json.loads((target_run / "failure_review.json").read_text())
    if old_failure["classification"] != "NATIVE_FRAME_BUFFER_CAPACITY_1024_INSUFFICIENT_FOR_FULL_1268_INPUT":
        raise RuntimeError("Require the actual incomplete capacity-failure review")
    original_pointer = json.loads((ROOT / "reports/PHASE5/active_E14_batch.json").read_text())
    original_plan = json.loads(Path(str(original_pointer["plan"]).replace("\\", "/").replace("D:/", "/mnt/d/", 1)).read_text())
    first_person_file = ROOT / "logs/PHASE5/20261101T072721Z_E14_sequential_batch/wildgs_person_first_native_followup/state.json"
    first_person = json.loads(first_person_file.read_text())
    if original_plan["state"] != "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING" or not first_person["state"].startswith("FIRST_NATIVE_ATTEMPT_TERMINAL"):
        raise RuntimeError("Prepare this resource only between the terminal owned GPU queues and the capacity repair")
    native = run(["ps", "-eo", "pid,args"])
    active = [line for line in native["stdout"].splitlines() if str(ROOT) in line and any(name in line for name in (
        "run_ba_track_reviewed_entrypoint.py", "run_pi3mos_reviewed_entrypoint.py", "run_phase5_wildgs_observed_entrypoint.py", "run_phase5_neural.py", "run_phase5_wildgs.py"))]
    if active:
        raise RuntimeError("An owned model/controller is active; never share its GPU slot")
    probe = json.loads((ROOT / "reports/PHASE5/D_loop_swap_probe.json").read_text())
    if probe["status"] != "OWNED_D_LOOP_SWAP_ACTIVATION_PASS" or not probe["owned_probe_detached"]:
        raise RuntimeError("Actual owned loop probe must pass")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    log = ROOT / "logs/PHASE5" / (stamp+"_D_sparse_loop_swap_16GiB")
    log.mkdir(parents=True, exist_ok=False)
    state = {"status": "OWNED_D_SPARSE_SWAP_SETUP_STARTED", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "BEFORE_CAPACITY_REPAIR_RESOURCE_PREPARATION_OWNED_D_LOOP_SWAP", "backing_file": str(file), "logical_bytes": size,
        "backing_allocation": "Verified new NTFS sparse file; physical allocation occurs on actual swap writes; D headroom reserved before activation",
        "creation_receipt_sha256": hashlib.sha256(receipt_file.read_bytes()).hexdigest(), "owned_native_models_running_before": active,
        "memory_before": memory(), "swaps_before": swaps(), "D_free_before_bytes": shutil.disk_usage(ROOT).free,
        "C_free_before_bytes": shutil.disk_usage("/mnt/c").free, "commands": [], "native_run": str(target_run),
        "WSL_restarted": False, "native_model_or_hyperparameters_or_seed_or_input_changed": False,
        "original_swap_entries_modified_or_removed": False, "native_inference_replayed": False}
    write(log / "state.json", state)
    attached = run(["losetup", "--find", "--show", "--nooverlap", str(file)])
    state["commands"].append(attached)
    if attached["exit_code"]:
        raise RuntimeError("Owned loop attachment failed")
    loop = attached["stdout"].strip()
    state["loop"] = loop
    state["verified_owned_mapping"] = verify_owned(loop, file, size)
    if any(r[0] == loop for r in swaps()):
        raise RuntimeError("Never reformat an active swap area")
    # Verify a hole reads as zeros and a bounded final-page write roundtrips.
    # Every byte addressed belongs to the newly created owned sparse file.
    payload = b"GameCam-owned-sparse-D-swap-probe"*128
    with open(loop, "r+b", buffering=0) as stream:
        stream.seek(size-16384)
        if stream.read(len(payload)) != bytes(len(payload)):
            raise ValueError("Fresh sparse hole did not read as zero")
        stream.seek(size-16384); stream.write(payload); os.fsync(stream.fileno())
        stream.seek(size-16384)
        if stream.read(len(payload)) != payload:
            raise ValueError("Owned sparse loop read/write roundtrip failed")
    write(log / "state.json", state)
    for command in (["mkswap", "--label", "GameCamP5D16", loop], ["swapon", "--priority", "-4", loop]):
        result = run(command); state["commands"].append(result); write(log / "state.json", state)
        if result["exit_code"]:
            raise RuntimeError("Owned sparse swap initialization/activation failed")
    current = swaps()
    new = next((r for r in current if r[0] == loop), None)
    if not new or int(new[2])*1024 < size-8192 or not all(any(r[0] == old[0] for r in current) for old in state["swaps_before"]):
        raise RuntimeError("New swap capacity or preservation of prior entries failed")
    state.update(status="OWNED_D_LOOP_16_GIB_SWAP_ACTIVE", activated_at_utc=datetime.now(timezone.utc).isoformat(),
        memory_after=memory(), swaps_after=current, C_free_after_bytes=shutil.disk_usage("/mnt/c").free,
        D_free_after_bytes=shutil.disk_usage(ROOT).free,
        summary="Prepared16GiB lower-priority swap on an exactly verified newly created D-backed sparse loop file while all owned GPU jobs were terminal, before the failed-incomplete BA Crowd capacity repair. Existing swap entries untouched. No WSL restart or baseline math/input/weights/seed change. Original Crowd failure was the1024 buffer guard, not OOM; this is a separately disclosed resource budget for the larger buffer, not a mid-run intervention on that old attempt.",
        cleanup="After all model work, verify exact owned loop/backing identity and Used=0 before swapoff/detach/removing only the new file. Never detach active swap or touch original disks.")
    for source in (Path(__file__), Path(__file__).with_name("probe_phase5_D_loop_swap.py"), Path(__file__).with_name("extend_phase5_D_loop_swap.py")):
        shutil.copy2(source, log / (source.name+".executed_source"))
    write(log / "state.json", state)
    write(ROOT / "reports/PHASE5/D_loop_swap_runtime.json", state)
    print(json.dumps({"status": state["status"], "loop": loop, "memory_after": state["memory_after"], "D_free_after_bytes": state["D_free_after_bytes"], "C_free_after_bytes": state["C_free_after_bytes"]}))


if __name__ == "__main__":
    main()

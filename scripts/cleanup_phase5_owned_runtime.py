"""Release only the two proven-owned temporary swap files after stage stop."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil

from phase5_runtime import ROOT, digest, local, write
from probe_phase5_D_loop_swap import run, swaps, verify_owned


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def owned_models():
    names = {"run_phase5_neural.py", "run_ba_track_reviewed_entrypoint.py",
        "run_pi3mos_reviewed_entrypoint.py", "run_phase5_wildgs.py",
        "run_phase5_wildgs_cached_entrypoint.py", "run_phase5_wildgs_observed_entrypoint.py"}
    active = []
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            args = [x.decode(errors="replace") for x in (proc / "cmdline").read_bytes().split(b"\x00") if x]
            if len(args) > 1 and Path(args[1]).name in names:
                active.append({"PID": int(proc.name), "arguments": args})
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return active


def memory_support_for_owned_swapoff(owned):
    available = next(int(row.split()[1])*1024 for row in Path("/proc/meminfo").read_text().splitlines() if row.startswith("MemAvailable:"))
    used = sum(int(row[3])*1024 for row in swaps() if row[0] in owned)
    # Native work is already absent. Permit only a small, measured migration
    # with a2GiB reserve plus8x its pages; never disable the original swap.
    if used > 256*1024**2 or available < 2*1024**3 + 8*used:
        raise RuntimeError("Owned swap pages lack the reviewed RAM reserve; leave them intact")
    return {"owned_used_bytes": used, "MemAvailable_bytes": available,
        "maximum_owned_pages_allowed_bytes": 256*1024**2,
        "required_available_bytes": 2*1024**3+8*used,
        "scope": "Actual small owned-swap page migration only, with no native models; original swap is never disabled"}


def main():
    if os.name != "posix" or os.geteuid() != 0 or str(ROOT) != "/mnt/d/aaa/GameCam-VO":
        raise RuntimeError("Require the existing WSL root entry point and exact owned project")
    reports = ROOT / "reports/PHASE5"
    target = reports / "OWNED_RUNTIME_CLEANUP_20261102.json"
    if target.exists():
        raise FileExistsError("Inspect the recorded cleanup; never repeat deletion blindly")
    stop_file = reports / "USER_REQUESTED_STOP_20261102.json"
    stop = read(stop_file)
    gate_file = reports / "E13_E14_STAGE_DELIVERY.json"
    gate = read(gate_file)
    if (stop["new_model_launches_allowed"] or stop["new_dataset_acquisition_allowed"]
        or gate["status"] != "E13_E14_REVIEWED_STAGE_REPORT_WRITTEN"
        or digest(local(gate["report"])) != gate["report_sha256"] or owned_models()):
        raise RuntimeError("Require the actual requested stop, delivered stage and absence of native models")
    activation_file = reports / "D_loop_swap_runtime.json"
    activation = read(activation_file)
    if (activation["status"] != "OWNED_D_LOOP_16_GIB_SWAP_ACTIVE"
        or activation["boot_id"] != Path("/proc/sys/kernel/random/boot_id").read_text().strip()):
        raise RuntimeError("The exact recorded runtime activation must still belong to this WSL instance")
    d_file = ROOT / "data/phase5_runtime/20261101T1659Z_D_sparse_loop_swap_16GiB/phase5_extra_swap_D_sparse_16GiB.raw"
    c_file = Path("/home/lsuser/.local/share/gamecam-vo/phase5_runtime/phase5_extra_swap_20261101_8GiB")
    creation_file = d_file.parent / "creation_receipt.json"
    creation = read(creation_file)
    c_proof_file = ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T105134Z_person_tracking/memory_budget_intervention.json"
    c_proof = read(c_proof_file)
    if (digest(creation_file) != activation["creation_receipt_sha256"]
        or not creation["file_created_exclusively_with_wx"] or creation["existing_user_file_overwritten"]
        or local(activation["backing_file"]) != d_file or local(creation["linux_file"]) != d_file
        or d_file.is_symlink() or d_file.stat().st_size != 16*1024**3
        or activation["existing_owned_C_swap_file"] != str(c_file)
        or c_proof["status"] != "OWNED_EXTRA_8GIB_SWAP_ACTIVE"
        or c_proof["swap_file"] != str(c_file) or c_file.is_symlink() or c_file.stat().st_size != 8*1024**3):
        raise ValueError("Exact single-file creation, ownership or size proof is invalid")
    loop = activation["loop"]
    mapping = verify_owned(loop, d_file, 16*1024**3)
    before = swaps()
    owned = {loop, str(c_file)}
    selected = [r for r in before if r[0] in owned]
    preserved = [r for r in before if r[0] not in owned]
    if len(selected) != 2 or not preserved:
        raise RuntimeError("Require both exact owned swaps and preserve every other swap entry")
    migration_review = memory_support_for_owned_swapoff(owned)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = ROOT / "logs/PHASE5" / (stamp+"_owned_runtime_cleanup")
    folder.mkdir(exist_ok=False)
    shutil.copy2(__file__, folder / (Path(__file__).name+".executed_source"))
    shutil.copy2(activation_file, folder / "activation_before_cleanup.json")
    state = {"status": "OWNED_TEMPORARY_SWAP_CLEANUP_STARTED", "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "user_stop_request_sha256": digest(stop_file), "stage_gate_sha256": digest(gate_file),
        "activation_sha256": digest(activation_file), "C_ownership_proof_sha256": digest(c_proof_file),
        "D_creation_receipt_sha256": digest(creation_file), "verified_owned_loop_mapping": mapping,
        "swaps_before": before, "owned_swaps_Used_before_kib": {r[0]: int(r[3]) for r in selected},
        "owned_page_migration_review": migration_review,
        "commands": [], "removed_only_exact_temporary_files": [], "model_or_environment_or_dataset_removed": False,
        "original_swap_entries_modified_or_removed": False, "WSL_restart_or_VHDX_compaction": False}
    state_file = folder / "state.json"
    write(state_file, state)
    for command in (["swapoff", loop], ["swapoff", str(c_file)]):
        if owned_models():
            raise RuntimeError("A native model appeared; leave remaining resources intact")
        state.setdefault("per_swapoff_memory_checks", []).append(memory_support_for_owned_swapoff(owned))
        result = run(command)
        state["commands"].append(result); write(state_file, state)
        if result["exit_code"]:
            raise RuntimeError("Owned swapoff failed; refuse detachment or deletion")
    if any(r[0] in owned for r in swaps()):
        raise RuntimeError("An owned swap remains active; refuse deletion")
    verify_owned(loop, d_file, 16*1024**3)
    detached = run(["losetup", "--detach", loop])
    state["commands"].append(detached); write(state_file, state)
    if detached["exit_code"]:
        raise RuntimeError("Owned loop detachment failed; refuse backing-file deletion")
    associated = run(["losetup", "--associated", str(d_file)])
    state["commands"].append(associated); write(state_file, state)
    if associated["exit_code"] or associated["stdout"].strip():
        raise RuntimeError("The owned file is still attached; refuse deletion")
    for file, size in ((d_file, 16*1024**3), (c_file, 8*1024**3)):
        if file.is_symlink() or file.stat().st_size != size or any(r[0] == str(file) for r in swaps()):
            raise RuntimeError("A single-file identity or inactivity check changed")
        file.unlink()
        state["removed_only_exact_temporary_files"].append(str(file)); write(state_file, state)
    after = swaps()
    if not all(any(r[0] == old[0] and r[1:3] == old[1:3] and r[4] == old[4] for r in after) for old in preserved):
        raise RuntimeError("An original swap entry unexpectedly changed")
    state.update({"status": "OWNED_TEMPORARY_SWAPS_DEACTIVATED_DETACHED_AND_REMOVED", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "swaps_after": after, "owned_native_models_after": owned_models(), "WSL_runtime_lease_stop_pending": True,
        "C_host_free_after_bytes": shutil.disk_usage("/mnt/c").free, "D_host_free_after_bytes": shutil.disk_usage(ROOT).free,
        "scope": "Only the exact task-created8GiB ext4 and16GiB D-loop swap files were released. Historical receipts, data, models, Conda environments, original WSL swap and virtual disks remain preserved."})
    write(state_file, state); write(target, {**state, "state_file": str(state_file)})
    print(json.dumps({"status": state["status"], "report": str(target), "swaps_after": after}))


if __name__ == "__main__":
    main()

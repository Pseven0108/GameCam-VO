"""Reactivate existing owned swap after a reviewed interruption; never reformat."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

from probe_phase5_D_loop_swap import ROOT, run, swaps, verify_owned
from extend_phase5_D_loop_swap import memory, write


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lease", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("Only the verified owned resource restoration under root is allowed")
    lease_file = args.lease.resolve()
    if not lease_file.is_relative_to((ROOT / "data/phase5_runtime").resolve()):
        raise ValueError("Lease escaped the owned task directory")
    lease = json.loads(lease_file.read_text())
    boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    lease_cmd = Path(f"/proc/{lease['PID']}/cmdline").read_bytes()
    if (lease["status"] != "OWNED_FOREGROUND_WSL_RUNTIME_LEASE_RUNNING" or lease["boot_id"] != boot
        or b"hold_phase5_wsl_runtime.py" not in lease_cmd or str(lease_file.parent).encode() not in lease_cmd):
        raise RuntimeError("The same current-kernel owned runtime lease must be alive")
    review_file = ROOT / "reports/PHASE5/BA_crowd_external_interruption_review.json"
    review = json.loads(review_file.read_text())
    if review["status"] != "REVIEWED_EXTERNAL_CONTROL_INTERRUPTION_NO_NATIVE_TERMINAL_RECORD" or review["GT_scores_computed_for_interrupted_partial_output"]:
        raise ValueError("Require the actual reviewed incomplete interruption, not a score-selected rerun")
    listing = run(["ps", "-eo", "pid,args"])
    active = [line for line in listing["stdout"].splitlines() if str(ROOT) in line and any(name in line for name in (
        "run_ba_track_reviewed_entrypoint.py", "run_pi3mos_reviewed_entrypoint.py", "run_phase5_wildgs_observed_entrypoint.py",
        "run_phase5_neural.py", "run_phase5_wildgs.py"))]
    if active:
        raise RuntimeError("An owned native model is running; restoration is only before the reviewed continuation")
    c_record_file = ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T105134Z_person_tracking/memory_budget_intervention.json"
    c_record = json.loads(c_record_file.read_text())
    c_file = Path("/home/lsuser/.local/share/gamecam-vo/phase5_runtime/phase5_extra_swap_20261101_8GiB")
    d_file = ROOT / "data/phase5_runtime/20261101T1659Z_D_sparse_loop_swap_16GiB/phase5_extra_swap_D_sparse_16GiB.raw"
    receipt_file = d_file.parent / "creation_receipt.json"
    receipt = json.loads(receipt_file.read_text())
    historical_file = ROOT / "reports/PHASE5/D_loop_swap_runtime.json"
    historical = json.loads(historical_file.read_text())
    if (c_record["status"] != "OWNED_EXTRA_8GIB_SWAP_ACTIVE" or Path(c_record["swap_file"]).resolve() != c_file.resolve()
        or c_file.is_symlink() or c_file.stat().st_size != 8 * 1024**3
        or Path(receipt["linux_file"]).resolve() != d_file.resolve() or d_file.is_symlink()
        or d_file.stat().st_size != 16 * 1024**3 or not receipt["file_created_exclusively_with_wx"]
        or receipt["existing_user_file_overwritten"] or digest(receipt_file) != historical["creation_receipt_sha256"]):
        raise ValueError("Existing owned-file identity/receipt/size checks failed")
    for file in (c_file, d_file):
        with file.open("rb") as handle:
            handle.seek(os.sysconf("SC_PAGE_SIZE") - 10)
            if handle.read(10) != b"SWAPSPACE2":
                raise ValueError("Existing swap signature missing; never reformat or replace the file")
    if shutil.disk_usage(ROOT).free < 28 * 1024**3 or shutil.disk_usage("/mnt/c").free < 3 * 1024**3:
        raise RuntimeError("Insufficient D/C headroom for the already owned resource budget")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    log = ROOT / "logs/PHASE5" / (stamp + "_owned_swap_reactivation")
    log.mkdir(parents=True, exist_ok=False)
    shutil.copy2(historical_file, log / "previous_activation.json")
    state = {"status": "OWNED_RESOURCE_REACTIVATION_STARTED", "created_at_utc": datetime.now(timezone.utc).isoformat(),
             "boot_id": boot, "runtime_lease": str(lease_file), "runtime_lease_sha256_at_activation": digest(lease_file),
             "interruption_review_sha256": digest(review_file), "previous_activation_record": str(log / "previous_activation.json"),
             "previous_activation_sha256": digest(historical_file), "creation_receipt_sha256": digest(receipt_file),
             "backing_file": str(d_file), "logical_bytes": 16 * 1024**3, "existing_owned_C_swap_file": str(c_file),
             "memory_before": memory(), "swaps_before": swaps(), "commands": [], "owned_native_models_running_before": active,
             "mkswap_called": False, "backing_file_contents_cleared": False, "original_swap_entries_modified_or_removed": False,
             "WSL_restarted_by_this_helper": False, "native_inference_launched_by_this_helper": False}
    write(log / "state.json", state)
    def checked(command):
        result = run(command)
        state["commands"].append(result)
        write(log / "state.json", state)
        if result["exit_code"]:
            raise RuntimeError("Owned swap reactivation failed; preserve all files and actual command evidence")
        return result
    if not any(r[0] == str(c_file) for r in swaps()):
        checked(["swapon", "--priority", "-3", str(c_file)])
    loop = checked(["losetup", "--find", "--show", "--nooverlap", str(d_file)])["stdout"].strip()
    state["loop"] = loop
    state["verified_owned_mapping"] = verify_owned(loop, d_file, 16 * 1024**3)
    if not any(r[0] == loop for r in swaps()):
        checked(["swapon", "--priority", "-4", loop])
    current = swaps()
    if (memory()["SwapTotal_bytes"] < 25.99 * 1024**3
        or not all(any(r[0] == old[0] for r in current) for old in state["swaps_before"])):
        raise RuntimeError("Restored budget or preservation of original swap entries failed")
    state.update(status="OWNED_D_LOOP_16_GIB_SWAP_ACTIVE", activated_at_utc=datetime.now(timezone.utc).isoformat(),
                 memory_after=memory(), swaps_after=current,
                 summary="Reactivated the same existing owned8GiB ext4 and16GiB D-backed swap after reviewed control-process disappearance. No reformat, original-swap change, native call or baseline mathematical change. Historical activation record preserved.",
                 cleanup="After all native work, verify exact owned identities and Used=0 before releasing only the two owned additions. Leave original WSL swap untouched.")
    shutil.copy2(Path(__file__), log / (Path(__file__).name + ".executed_source"))
    write(log / "state.json", state)
    write(historical_file, state)
    print(json.dumps({"status": state["status"], "loop": loop, "memory_after": state["memory_after"], "evidence": str(log / "state.json")}))


if __name__ == "__main__":
    main()

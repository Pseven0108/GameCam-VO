"""One explicitly reviewed continuation after an incomplete control interruption."""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/PHASE5"


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def write(file, value):
    file.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def local(value):
    return Path(str(value).replace("/mnt/d/", "D:/", 1))


def main():
    if os.name != "nt":
        raise RuntimeError("Use the established Windows queue host")
    review_file = REPORTS / "BA_crowd_external_interruption_review.json"
    review = json.loads(review_file.read_text(encoding="utf-8"))
    if (review["status"] != "REVIEWED_EXTERNAL_CONTROL_INTERRUPTION_NO_NATIVE_TERMINAL_RECORD"
        or review["returned_frontend_calls"] != 88 or review["GT_scores_computed_for_interrupted_partial_output"]
        or review["native_exit_code"] is not None):
        raise ValueError("Require the exact independently reviewed incomplete interruption")
    old = local(review["directory"]).resolve()
    if old != (ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261102T043005Z_crowd").resolve() or (old / "status.json").exists():
        raise ValueError("This continuation is restricted to the actual interrupted unfinished case")
    for item in review["artifacts"]:
        if digest(local(item["file"])) != item["sha256"]:
            raise ValueError("Interrupted evidence changed; review it instead of launching")
    ctypes.windll.kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    ctypes.windll.kernel32.OpenProcess.restype = ctypes.c_void_p
    ctypes.windll.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    ctypes.windll.kernel32.CloseHandle.restype = ctypes.c_bool
    for pid in (80924, 19796):
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            raise RuntimeError("An old controller PID is present; recheck ownership before any launch")
    plan_file = REPORTS / "E14_BA_crowd_capacity_recovery_plan.json"
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    if plan["status"] != "ACTUAL_NATIVE_ATTEMPT_INTERRUPTED_REVIEWED_RESUME_PENDING":
        raise ValueError("A reviewed one-time continuation must be outstanding")
    resource = json.loads((REPORTS / "D_loop_swap_runtime.json").read_text(encoding="utf-8"))
    if resource["status"] != "OWNED_D_LOOP_16_GIB_SWAP_ACTIVE" or not resource.get("previous_activation_record"):
        raise RuntimeError("Require the actually restored owned resource budget")
    guard = '''from pathlib import Path
import json
m=dict((r.split(":")[0],int(r.split()[1])*1024) for r in Path("/proc/meminfo").read_text().splitlines() if r.startswith("SwapTotal:"))
assert m["SwapTotal"] >= 25.99*1024**3
active=[]
names={"run_phase5_neural.py","run_ba_track_reviewed_entrypoint.py","run_pi3mos_reviewed_entrypoint.py","run_phase5_wildgs.py","run_phase5_wildgs_cached_entrypoint.py","run_phase5_wildgs_observed_entrypoint.py"}
for p in Path("/proc").glob("[0-9]*"):
 try:
  a=[s.decode(errors="replace") for s in (p/"cmdline").read_bytes().split(b"\\x00") if s]
  if len(a)>1 and Path(a[1]).name in names: active.append(int(p.name))
 except (FileNotFoundError,ProcessLookupError,PermissionError): pass
assert not active, active
print(json.dumps({**m,"owned_native_models_running":active}))'''
    subprocess.check_call(["wsl.exe", "-d", "Ubuntu", "--exec", "/home/lsuser/.local/share/gamecam-vo/envs/ba-track/bin/python", "-c", guard])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    folder = ROOT / "logs/PHASE5" / (stamp + "_BA_crowd_reviewed_resume")
    folder.mkdir(parents=True, exist_ok=False)
    shutil.copy2(Path(__file__), folder / (Path(__file__).name + ".executed_source"))
    state_file = folder / "state.json"
    command = ["wsl.exe", "-d", "Ubuntu", "--exec", "/home/lsuser/.local/share/gamecam-vo/envs/ba-track/bin/python",
               "/mnt/d/aaa/GameCam-VO/scripts/run_phase5_neural.py", "BA_TRACK", "--experiment", "E14_WILD_DYNAMIC",
               "--input-pointer", "/mnt/d/aaa/GameCam-VO/reports/PHASE5/wild_crowd_input.json",
               "--reuse-prior-review", "/mnt/d/aaa/GameCam-VO/reports/PHASE5/BA_crowd_prior_reuse_review.json"]
    state = {"state": "REVIEWED_INCOMPLETE_CASE_CONTINUATION_RUNNING", "PID": os.getpid(), "command": command,
             "started_at_utc": datetime.now(timezone.utc).isoformat(), "interrupted_directory_preserved": str(old),
             "interruption_review_sha256": digest(review_file), "automatic_model_retry": False,
             "start_from_input_zero_because_no_complete_native_checkpoint": True,
             "full_frames": 1268, "native_buffer_capacity": 2048,
             "GT_score_or_successful_output_used_to_choose_continuation": False,
             "native_seed_windows_points_iterations_weights_inputs_changed": False,
             "visual_QA_or_stage_delivery_claim": False}
    write(state_file, state)
    write(REPORTS / "BA_crowd_reviewed_resume_controller.json", {"state_file": str(state_file), "PID": os.getpid()})
    plan.update(status="ACTUAL_REVIEWED_RESUME_NATIVE_ATTEMPT_RUNNING", reviewed_resume_state=str(state_file))
    write(plan_file, plan)
    print(json.dumps(state), flush=True)
    started = datetime.now(timezone.utc).timestamp()
    with (folder / "native_controller.log").open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        state["native_controller_PID"] = process.pid
        write(state_file, state)
        code = process.wait()
    state.update(state="REVIEWED_RESUME_NATIVE_TERMINAL_QA_PENDING", controller_exit_code=code,
                 completed_at_utc=datetime.now(timezone.utc).isoformat())
    pointer = REPORTS / "E14_WILD_DYNAMIC_BA_TRACK_crowd_native.json"
    if pointer.exists() and pointer.stat().st_mtime >= started:
        native = json.loads(pointer.read_text(encoding="utf-8"))
        result = local(native["directory"]).resolve()
        if result == old or not result.is_relative_to(ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK"):
            raise ValueError("Fresh result identity is invalid")
        state.update(native_status=native["status"], result_directory=str(result))
    else:
        state["native_status"] = "CONTROLLER_EXITED_WITHOUT_FRESH_NATIVE_TERMINAL_RECORD"
    write(state_file, state)
    plan.update(status="ACTUAL_REVIEWED_RESUME_NATIVE_TERMINAL_QA_PENDING", reviewed_resume_state=str(state_file))
    write(plan_file, plan)
    print(json.dumps(state), flush=True)
    return int(code != 0)


if __name__ == "__main__":
    raise SystemExit(main())

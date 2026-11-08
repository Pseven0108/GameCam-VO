"""Launch the first actual WildGS Person model after the original GPU queue.

The earlier failure occurred in the controller before native model launch.
This is a single predeclared outstanding case, not a failure-driven score retry.
The script never releases a stage gate, retries a model, or downloads data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/PHASE5"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main():
    if os.name != "nt":
        raise RuntimeError("Use the established Windows single-GPU queue host")
    recovery_file = REPORTS / "E14_case_recovery_plan.json"
    recovery = read(recovery_file)
    if recovery["status"] != "PLANNED_AFTER_EXISTING_E14_QUEUE_TERMINAL" or recovery["actual_native_GPU_model_previously_launched"]:
        raise ValueError("Outstanding first-real-launch plan is required; never automatically retry a model")
    plan_file = Path(read(REPORTS / "active_E14_batch.json")["plan"])
    folder = ROOT / "logs/PHASE5/20261101T072721Z_E14_sequential_batch/wildgs_person_first_native_followup"
    folder.mkdir(exist_ok=False)
    shutil_source = folder / "run_phase5_wildgs_person_followup.py.executed_source"
    shutil_source.write_bytes(Path(__file__).read_bytes())
    state_file = folder / "state.json"
    state = {"state": "WAITING_FOR_ORIGINAL_E14_QUEUE", "PID": os.getpid(), "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "original_plan": str(plan_file), "recovery_plan": str(recovery_file), "GPU_jobs_at_a_time": 1,
        "model_automatic_retry": False, "downloads_data": False, "stage_report_or_visual_QA_claim": False,
        "source_sha256": hashlib.sha256(shutil_source.read_bytes()).hexdigest()}
    write(state_file, state)
    print(json.dumps(state), flush=True)
    while True:
        # The existing queue rewrites its JSON journal in place. A concurrent
        # read can briefly see an incomplete file; this is not a model retry.
        try:
            plan = read(plan_file)
        except json.JSONDecodeError:
            time.sleep(.2)
            continue
        if plan["state"] == "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING":
            if len(plan["jobs"]) != 12 or any(j["state"] != "ATTEMPT_TERMINAL" for j in plan["jobs"]):
                raise ValueError("Original queue has inconsistent terminal support")
            break
        time.sleep(30)
    recovery = read(recovery_file)
    if recovery["status"] != "PLANNED_AFTER_EXISTING_E14_QUEUE_TERMINAL":
        raise RuntimeError("Recovery plan changed while waiting; audit before any launch")
    pointer_file = REPORTS / "E14_WILD_DYNAMIC_WILDGS_person_tracking_native.json"
    if pointer_file.exists():
        raise FileExistsError("A native terminal pointer already exists; inspect it rather than launch again")
    command = ["wsl.exe", "-d", "Ubuntu", "--exec", "/home/lsuser/.local/share/gamecam-vo/envs/wildgs_slam/bin/python",
        "/mnt/d/aaa/GameCam-VO/scripts/run_phase5_wildgs.py", "--target", "shared", "--sequence", "person_tracking",
        "--actor-mode", "thread-portability", "--source-cache", recovery["source_cache"], "--observe-native-returns"]
    state.update(state="FIRST_NATIVE_ATTEMPT_RUNNING", command=command, started_at_utc=datetime.now(timezone.utc).isoformat())
    write(state_file, state)
    recovery.update(status="ACTUAL_NATIVE_ATTEMPT_RUNNING", continuation_state=str(state_file))
    write(recovery_file, recovery)
    with (folder / "native_controller.log").open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        state["native_controller_PID"] = process.pid
        write(state_file, state)
        code = process.wait()
    state.update(state="FIRST_NATIVE_ATTEMPT_TERMINAL_REVIEW_PENDING", controller_exit_code=code, completed_at_utc=datetime.now(timezone.utc).isoformat())
    if pointer_file.exists():
        terminal = read(pointer_file)
        state.update(native_status=terminal["status"], result_directory=terminal["directory"])
    else:
        state["native_status"] = "CONTROLLER_FAILED_BEFORE_TERMINAL_RECORD"
    write(state_file, state)
    recovery.update(status="ACTUAL_NATIVE_ATTEMPT_TERMINAL_QA_PENDING", terminal_state=str(state_file))
    write(recovery_file, recovery)
    print(json.dumps(state), flush=True)


if __name__ == "__main__":
    main()

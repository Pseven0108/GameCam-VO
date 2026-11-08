"""Single explicit repair of an incomplete native1024-frame capacity failure."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/PHASE5"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            checksum.update(block)
    return checksum.hexdigest()


def main():
    if os.name != "nt":
        raise RuntimeError("Use the existing Windows single-GPU queue host")
    controller_file = REPORTS / "E14_BA_crowd_capacity_followup_controller.json"
    if controller_file.exists():
        raise FileExistsError("An existing controller journal must be inspected, never duplicated")
    repair_file = REPORTS / "E14_BA_crowd_capacity_recovery_plan.json"
    repair = read(repair_file)
    if repair["status"] != "PLANNED_AFTER_ORIGINAL_QUEUE_AND_FIRST_WILDGS_PERSON_NATIVE_TERMINAL":
        raise RuntimeError("Inspect the existing repair rather than automatically retrying")
    prior_file = REPORTS / "BA_crowd_prior_reuse_review.json"
    prior = read(prior_file)
    if prior["status"] != "COMPLETE_NATIVE_LEARNED_PRIORS_BYTE_AND_VALUE_REVIEWED_FOR_CAPACITY_REPAIR":
        raise RuntimeError("Actual full native learned-prior review is required")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = ROOT / "logs/PHASE5" / (stamp+"_BA_crowd_capacity_followup")
    folder.mkdir(parents=True, exist_ok=False)
    source = folder / "run_phase5_ba_crowd_capacity_followup.py.executed_source"
    source.write_bytes(Path(__file__).read_bytes())
    state_file = folder / "state.json"
    state = {"state": "WAITING_FOR_ORIGINAL_QUEUE_AND_FIRST_WILDGS_PERSON_NATIVE_TERMINAL", "PID": os.getpid(),
        "created_at_utc": datetime.now(timezone.utc).isoformat(), "one_GPU_job_at_a_time": True,
        "automatic_model_retry": False, "stage_or_visual_QA_claim": False,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    write(state_file, state)
    with controller_file.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"PID": os.getpid(), "state_file": str(state_file)})+"\n")
    first_person_file = ROOT / "logs/PHASE5/20261101T072721Z_E14_sequential_batch/wildgs_person_first_native_followup/state.json"
    original_plan_file = Path(read(REPORTS / "active_E14_batch.json")["plan"])
    while True:
        try:
            original, person = read(original_plan_file), read(first_person_file)
        except json.JSONDecodeError:
            time.sleep(.2); continue
        if (original["state"] == "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING"
            and person["state"].startswith("FIRST_NATIVE_ATTEMPT_TERMINAL")):
            break
        time.sleep(30)
    state["state"] = "PREPARING_OWNED_D_SWAP_BEFORE_CAPACITY_REPAIR"
    write(state_file, state)
    with (folder / "resource_preparation.log").open("w", encoding="utf-8") as stream:
        code = subprocess.run(["wsl.exe", "-d", "Ubuntu", "-u", "root", "--exec", "/usr/bin/python3",
            "/mnt/d/aaa/GameCam-VO/scripts/activate_phase5_D_sparse_loop_swap.py"], stdout=stream, stderr=subprocess.STDOUT,
            cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW).returncode
    if code:
        state.update(state="RESOURCE_PREPARATION_FAILED_BEFORE_MODEL_LAUNCH", resource_preparation_exit_code=code, native_model_started=False)
        write(state_file, state)
        repair.update(status="RESOURCE_PREPARATION_FAILED_REVIEW_REQUIRED", continuation_state=str(state_file))
        write(repair_file, repair)
        return 1
    command = ["wsl.exe", "-d", "Ubuntu", "--exec", "/home/lsuser/.local/share/gamecam-vo/envs/ba-track/bin/python",
        "/mnt/d/aaa/GameCam-VO/scripts/run_phase5_neural.py", "BA_TRACK", "--experiment", "E14_WILD_DYNAMIC",
        "--input-pointer", "/mnt/d/aaa/GameCam-VO/reports/PHASE5/wild_crowd_input.json",
        "--reuse-prior-review", "/mnt/d/aaa/GameCam-VO/reports/PHASE5/BA_crowd_prior_reuse_review.json"]
    state.update(state="CAPACITY_REPAIR_NATIVE_ATTEMPT_RUNNING", command=command, started_at_utc=datetime.now(timezone.utc).isoformat())
    write(state_file, state)
    repair.update(status="ACTUAL_NATIVE_ATTEMPT_RUNNING", continuation_state=str(state_file), prior_cache_review=str(prior_file))
    write(repair_file, repair)
    with (folder / "native_controller.log").open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        state["native_controller_PID"] = process.pid; write(state_file, state)
        code = process.wait()
    pointer = read(REPORTS / "E14_WILD_DYNAMIC_BA_TRACK_crowd_native.json")
    cache = read(Path(prior["review"]))
    if digest(Path(prior["review"])) != prior["sha256"] or any(digest(Path(r["file"])) != r["sha256"] for r in cache["files"]):
        raise RuntimeError("Repair terminated but an original cached prior identity changed; preserve all evidence for review")
    state["original_cached_prior_files_unchanged_after_model"] = len(cache["files"])
    old = Path(repair["original_failed_directory"]).resolve()
    selected = Path(str(pointer["directory"]).replace("/mnt/d/", "D:/", 1)).resolve()
    state.update(state="CAPACITY_REPAIR_NATIVE_ATTEMPT_TERMINAL_REVIEW_PENDING", controller_exit_code=code,
        completed_at_utc=datetime.now(timezone.utc).isoformat())
    if selected == old:
        state["native_status"] = "CONTROLLER_FAILED_BEFORE_NEW_TERMINAL_RECORD"
    else:
        state.update(native_status=pointer["status"], result_directory=str(selected))
        if pointer["status"] == "BA_TRACK_PIPELINE_COMPLETED":
            with (folder / "external_camera_evaluation.log").open("w", encoding="utf-8") as stream:
                state["external_evaluation_exit_code"] = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/evaluate_phase5_camera.py"),
                    "BA_TRACK", str(selected), "--reference-pointer", str(REPORTS / "wild_crowd_input.json")], cwd=ROOT,
                    stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW).returncode
    write(state_file, state)
    repair.update(status="ACTUAL_NATIVE_ATTEMPT_TERMINAL_QA_PENDING", terminal_state=str(state_file))
    write(repair_file, repair)
    print(json.dumps(state), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

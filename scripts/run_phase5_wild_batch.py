"""One sequential local E14 batch; retain failures and never replay an attempt."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--after-e13", type=Path, required=True)
    parser.add_argument("--wildgs-source-cache", required=True)
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("Run from the existing Windows gamecam-vo environment")
    e13 = args.after_e13.resolve()
    if not e13.is_relative_to(ROOT / "results/E13_WILDGS") or not (e13 / "process.json").exists():
        raise ValueError("A specific already launched E13 run is required")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch = ROOT / "logs/PHASE5" / (stamp+"_E14_sequential_batch")
    batch.mkdir(exist_ok=False)
    jobs = []
    for seq in ("person_tracking", "crowd", "racket"):
        pointer = ROOT / "reports/PHASE5" / ("wild_"+seq+"_input.json")
        if read(pointer)["status"] != "PHASE5_FROZEN_RGB_K_AND_EXTERNAL_CLOCK_ASSOCIATION_READY":
            raise ValueError("Frozen inputs required before batch creation")
        for method, prefix in (("DROID_W", "droid-w"), ("PI3MOS", "pi3mos"), ("BA_TRACK", "ba-track"), ("WILDGS", "wildgs_slam")):
            existing = list((ROOT / "results/E14_WILD_DYNAMIC" / ("WildGS" if method == "WILDGS" else method)).glob("*_"+seq+("_*" if method == "WILDGS" else "")))
            if existing:
                raise RuntimeError("Existing attempt found; review its evidence, do not replay: "+str(existing))
            py = "/home/lsuser/.local/share/gamecam-vo/envs/"+prefix+"/bin/python"
            if method == "WILDGS":
                command = ["wsl.exe", "-d", "Ubuntu", "--exec", py, "/mnt/d/aaa/GameCam-VO/scripts/run_phase5_wildgs.py", "--target", "shared", "--sequence", seq,
                    "--actor-mode", "thread-portability", "--source-cache", args.wildgs_source_cache, "--observe-native-returns"]
                result_pointer = ROOT / "reports/PHASE5" / ("wildgs_shared_"+seq+"_thread-portability.json")
            else:
                command = ["wsl.exe", "-d", "Ubuntu", "--exec", py, "/mnt/d/aaa/GameCam-VO/scripts/run_phase5_neural.py", method,
                    "--experiment", "E14_WILD_DYNAMIC", "--input-pointer", "/mnt/d/aaa/GameCam-VO/reports/PHASE5/"+pointer.name]
                result_pointer = ROOT / "reports/PHASE5" / ("E14_WILD_DYNAMIC_"+method+"_"+seq+"_native.json")
            jobs.append({"method": method, "sequence": seq, "command": command, "result_pointer": str(result_pointer), "input_pointer": str(pointer), "state": "NOT_ATTEMPTED"})
    plan = {"state": "WAITING_FOR_E13", "batch_directory": str(batch), "after_E13": str(e13), "jobs": jobs,
        "one_GPU_job_at_a_time": True, "automatic_retry": False, "old_experiments_replayed": False,
        "same_RGB_K_input_size": [400, 240], "full_support": True, "different_paper_variant_due_to_thread_actor_RNG": "WILDGS",
        "E13_E14_stage_report_before_MOVi_download": True, "no_dataset_download_commands": True}
    write(batch / "plan.json", plan)
    write(ROOT / "reports/PHASE5/active_E14_batch.json", {"plan": str(batch / "plan.json"), "pid": os.getpid()})
    print(json.dumps({"state": plan["state"], "batch": str(batch), "jobs": len(jobs)}), flush=True)
    while not (e13 / "status.json").exists():
        time.sleep(5)
    plan["E13_terminal_state"] = read(e13 / "status.json")
    plan["state"] = "RUNNING"
    write(batch / "plan.json", plan)
    for index, job in enumerate(jobs):
        job.update(state="ATTEMPT_STARTED", started_at_utc=datetime.now(timezone.utc).isoformat())
        write(batch / "plan.json", plan)
        logfile = batch / f"{index:02d}_{job['method']}_{job['sequence']}.log"
        with logfile.open("w", encoding="utf-8") as log:
            child = subprocess.Popen(job["command"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            job["controller_PID"] = child.pid
            write(batch / "plan.json", plan)
            code = child.wait()
        job.update(controller_exit_code=code, state="ATTEMPT_TERMINAL", controller_log=str(logfile), completed_at_utc=datetime.now(timezone.utc).isoformat())
        pointer = Path(job["result_pointer"])
        if pointer.exists():
            native = read(pointer)
            job["native_status"] = native["status"]
            job["result_directory"] = native["directory"].replace("/mnt/d/", "D:/", 1)
            if native["status"].endswith("_COMPLETED"):
                command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/evaluate_phase5_camera.py"), job["method"], job["result_directory"], "--reference-pointer", job["input_pointer"]]
                with (batch / f"{index:02d}_{job['method']}_{job['sequence']}_external_evaluation.log").open("w", encoding="utf-8") as log:
                    evaluated = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                job["external_evaluation_exit_code"] = evaluated.returncode
                job["visual_QA_pending"] = True
        else:
            job["native_status"] = "CONTROLLER_FAILED_BEFORE_TERMINAL_RECORD"
        write(batch / "plan.json", plan)
        print(json.dumps({k: job[k] for k in ("method", "sequence", "native_status")}), flush=True)
    plan["state"] = "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING"
    write(batch / "plan.json", plan)
    print(json.dumps({"state": plan["state"], "batch": str(batch)}), flush=True)


if __name__ == "__main__":
    main()

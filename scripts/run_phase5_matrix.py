"""One local GPU queue for already-audited E15/E16 inputs, no model auto-retry."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
METHODS = (("DROID_W", "droid-w"), ("PI3MOS", "pi3mos"), ("BA_TRACK", "ba-track"), ("WILDGS", "wildgs_slam"))


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, row):
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def wsl(path):
    return "/mnt/d/"+Path(path).resolve().as_posix()[3:]


def local(value):
    return Path(str(value).replace("/mnt/d/", "D:/", 1))


def cpu(script, arguments, logfile):
    with logfile.open("w", encoding="utf-8") as stream:
        return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / script), *map(str, arguments)], cwd=ROOT,
            stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW).returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", choices=("E15_MOVIE", "E16_BONN"))
    parser.add_argument("--input-pointers", nargs="+", type=Path, required=True)
    parser.add_argument("--wildgs-source-cache", required=True)
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("Use the established Windows queue controller")
    reports = ROOT / "reports/PHASE5"
    e14 = read(Path(read(reports / "active_E14_batch.json")["plan"]))
    if e14["state"] != "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING":
        raise RuntimeError("The existing E14 queue must be terminal; never share the GPU between queues")
    from fetch_phase5_bonn import sha
    resource_pointer_file = reports / "active_phase5_runtime_budget.json"
    resource_preparation = None
    if resource_pointer_file.exists():
        resource_pointer = read(resource_pointer_file)
        resource_file = local(resource_pointer["state_file"])
        if sha(resource_file) != resource_pointer["sha256"]:
            raise ValueError("The prepared resumed resource receipt changed")
        resource = read(resource_file)
        if resource["status"] != "OWNED_E15_D_LOOP_16GIB_SWAP_ACTIVE" or resource["original_swap_entries_modified_or_removed"]:
            raise ValueError("Require the actual owned resumed budget, preserving original swap")
        resource_preparation = {"file": str(resource_file), "sha256": sha(resource_file),
            "memory_after": resource["memory_after"], "scope": "Prepared before the new native matrix; actual per-case guest memory/swap is also recorded at launch"}
    gate_file = reports / ("E13_E14_STAGE_DELIVERY.json" if args.experiment == "E15_MOVIE" else "E15_STAGE_DELIVERY.json")
    gate = read(gate_file)
    required_status = "E13_E14_REVIEWED_STAGE_REPORT_WRITTEN" if args.experiment == "E15_MOVIE" else "E15_REVIEWED_STAGE_REPORT_WRITTEN"
    if gate["status"] != required_status or sha(Path(gate["report"])) != gate["report_sha256"]:
        raise ValueError("Actual reviewed prior-stage report identity is required")
    active_pointer = reports / ("active_"+args.experiment+"_batch.json")
    if active_pointer.exists():
        raise FileExistsError("Inspect the existing batch journal; do not recreate or replay it")
    for other in ("E15_MOVIE", "E16_BONN"):
        other_pointer = reports / ("active_"+other+"_batch.json")
        if other_pointer.exists() and read(Path(read(other_pointer)["plan"]))["state"] == "RUNNING":
            raise RuntimeError("Another GPU queue is active")
    pointer_files = [path.resolve() for path in args.input_pointers]
    if not all(path.is_relative_to(reports.resolve()) for path in pointer_files):
        raise ValueError("Only owned frozen phase5 input pointers are accepted")
    inputs = [read(path) for path in pointer_files]
    required_dataset = "MOVi-E" if args.experiment == "E15_MOVIE" else "Bonn RGB-D Dynamic"
    if len(inputs) != (4 if args.experiment == "E15_MOVIE" else 3) or any(x["dataset"] != required_dataset for x in inputs):
        raise ValueError("Require exactly the preregistered test clips or three selected Bonn sequences")
    if len({x["sequence"] for x in inputs}) != len(inputs):
        raise ValueError("Duplicate input sequences")
    audits = [read(local(x["external_validation_directory"]) / "GT_audit.json") for x in inputs]
    repeat_index = None
    if args.experiment == "E15_MOVIE":
        acquisition = read(reports / "movi_test_acquisition.json")
        actual_hashes = [read(local(x["directory"]) / "input_manifest.json")["source_record_sha256"] for x in inputs]
        expected_hashes = [x["sha256"] for x in acquisition["records"]]
        if actual_hashes != expected_hashes or any(not x["pixel_motion_label_geometry_valid"] or x["flow_geometry_review"]["status"] != "PASS" for x in audits):
            raise ValueError("Frozen clip order/independent source geometry must pass before any model scoring")
        repeat_index = max(range(4), key=lambda i: (audits[i]["native_dynamic_pixel_fraction"], -i))
    else:
        if [x["sequence"] for x in inputs] != ["bonn_"+s for s in ("person_tracking", "crowd", "moving_obstructing_box")]:
            raise ValueError("Use the three selected Bonn sequences in requested order")
    for folder in ("DROID_W", "PI3MOS", "BA_TRACK", "WildGS"):
        if any((ROOT / "results" / args.experiment / folder).glob("*/execution_contract.json")):
            raise RuntimeError("A prior model attempt exists; preserve and audit it rather than replaying")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch = ROOT / "logs/PHASE5" / (stamp+"_"+args.experiment+"_matrix")
    batch.mkdir(parents=True, exist_ok=False)
    jobs = []
    selections = [(i, "primary") for i in range(len(inputs))]
    if repeat_index is not None:
        selections.append((repeat_index, "preregistered_independent_repeat"))
    for index, role in selections:
        pointer, sequence = pointer_files[index], inputs[index]["sequence"]
        for method, env in METHODS:
            python = "/home/lsuser/.local/share/gamecam-vo/envs/"+env+"/bin/python"
            command = ["wsl.exe", "-d", "Ubuntu", "--exec", python]
            if method == "WILDGS":
                command += ["/mnt/d/aaa/GameCam-VO/scripts/run_phase5_wildgs.py", "--target", "shared", "--sequence", sequence,
                    "--actor-mode", "thread-portability", "--source-cache", args.wildgs_source_cache, "--observe-native-returns",
                    "--experiment", args.experiment, "--input-pointer", wsl(pointer)]
            else:
                command += ["/mnt/d/aaa/GameCam-VO/scripts/run_phase5_neural.py", method, "--experiment", args.experiment, "--input-pointer", wsl(pointer)]
            result_pointer = reports / (args.experiment+"_"+method+"_"+sequence+"_native.json")
            jobs.append({"method": method, "sequence": sequence, "role": role, "input_pointer": str(pointer), "input_pointer_sha256": sha(pointer),
                "command": command, "result_pointer": str(result_pointer), "state": "NOT_ATTEMPTED"})
    plan = {"state": "RUNNING", "experiment": args.experiment, "jobs": jobs, "GPU_jobs_at_a_time": 1, "model_automatic_retry": False,
        "runtime_resource_preparation": resource_preparation,
        "prior_stage_gate": str(gate_file), "prior_stage_gate_sha256": sha(gate_file), "protected_old_models_replayed": False,
        "repeat_selection_uses_prediction_scores": False, "repeat_clip": inputs[repeat_index]["sequence"] if repeat_index is not None else None,
        "repeat_selection": "Highest mean GT dynamic-pixel fraction; first clip breaks ties; one additional independent launch with unchanged native seeds/defaults" if repeat_index is not None else None,
        "repeat_is_prespecified_not_failure_driven_retry": repeat_index is not None,
        "existing_verified_baseline_environments_reused": True, "GT_and_sensor_depth_are_not_model_inputs": True}
    plan_file = batch / "plan.json"
    write(plan_file, plan)
    write(active_pointer, {"plan": str(plan_file), "pid": os.getpid()})
    for number, job in enumerate(jobs):
        if sha(Path(job["input_pointer"])) != job["input_pointer_sha256"]:
            raise ValueError("Frozen input pointer changed during queue execution")
        job.update(state="ATTEMPT_STARTED", started_at_utc=datetime.now(timezone.utc).isoformat())
        write(plan_file, plan)
        with (batch / f"{number:02d}_{job['method']}_{job['sequence']}_{job['role']}.log").open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(job["command"], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            job["controller_PID"] = process.pid; write(plan_file, plan)
            code = process.wait()
        job.update(controller_exit_code=code, state="ATTEMPT_TERMINAL", completed_at_utc=datetime.now(timezone.utc).isoformat())
        pointer = Path(job["result_pointer"])
        if pointer.exists():
            native = read(pointer)
            directory = local(native["directory"])
            if any(x.get("result_directory") == str(directory) for x in jobs[:number]):
                raise ValueError("Stale terminal pointer refers to an older attempt; never accept it for this launch")
            job.update(native_status=native["status"], result_directory=str(directory))
            write(directory / "planned_experiment_role.json", {"batch_plan": str(plan_file), "job_index": number, "role": job["role"],
                "selection_uses_prediction_accuracy": False, "repeat_clip_selected_by_GT_scene_statistics": args.experiment == "E15_MOVIE",
                "native_hyperparameters_or_seed_changed": False})
            if native["status"].endswith("_COMPLETED"):
                job["camera_evaluation_exit_code"] = cpu("evaluate_phase5_camera.py", [job["method"], directory, "--reference-pointer", job["input_pointer"]], batch / f"{number:02d}_camera_evaluation.log")
                if job["camera_evaluation_exit_code"] == 0:
                    job["camera_error_diagnostic_exit_code"] = cpu("diagnose_phase5_camera.py", [directory, "--reference-pointer", job["input_pointer"]], batch / f"{number:02d}_camera_error_diagnostic.log")
                if args.experiment == "E16_BONN" and job["camera_evaluation_exit_code"] == 0:
                    job["calibration_diagnostic_exit_code"] = cpu("evaluate_phase5_bonn_calibration_diagnostic.py", [directory, "--reference-pointer", job["input_pointer"]], batch / f"{number:02d}_calibration_diagnostic.log")
            if args.experiment == "E15_MOVIE":
                script = "evaluate_phase5_movi_m2.py" if job["method"] == "BA_TRACK" else "evaluate_phase5_movi_m1.py"
                analysis_args = ([directory] if job["method"] == "BA_TRACK" else [job["method"], directory])+["--reference-pointer", job["input_pointer"]]
                job["motion_evaluation_exit_code"] = cpu(script, analysis_args, batch / f"{number:02d}_motion_evaluation.log")
            job["visual_QA_pending"] = True
        else:
            job["native_status"] = "CONTROLLER_FAILED_BEFORE_TERMINAL_RECORD"
        write(plan_file, plan)
        print(json.dumps({k: job[k] for k in ("method", "sequence", "role", "native_status")}), flush=True)
    plan["state"] = "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING"
    write(plan_file, plan)
    print(json.dumps({"state": plan["state"], "jobs": len(jobs), "plan": str(plan_file)}), flush=True)


if __name__ == "__main__":
    main()

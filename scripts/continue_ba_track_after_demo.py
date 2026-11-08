"""One-shot continuation of this active experiment; no retries or scheduling.

Wait for the already-running official Demo, validate it, then wait for the
agent's explicit figure-QA record before the single authorized MVS100 run.
"""
from __future__ import annotations

import _bootstrap
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from gamecam_vo.common import PROJECT, sha256, write_json


def local(value):
    return Path(str(value).replace("/mnt/d/", "D:/", 1)).resolve()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-demo", type=Path, required=True)
    args = parser.parse_args()
    demo = args.official_demo.resolve()
    if not demo.is_relative_to(PROJECT / "results/E9_BA_TRACK"):
        raise ValueError("Expected an owned explicit official Demo run")
    lock = PROJECT / "data/sota_workflows/ba_track_after_demo.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("x", encoding="utf-8") as handle:
        json.dump({"pid": os.getpid(), "demo": str(demo), "policy": "One active continuation only; inspect existing process on uncertain state, never replay automatically"}, handle)
    pointer = PROJECT / "reports/SOTA/ba_track_continuation_state.json"
    state = {"pid": os.getpid(), "official_demo": str(demo), "automatic_model_retries": False,
             "authorized_target": "Same shared100 MVS-Synth0000 RGB+knownK after official Demo validation and figure QA"}

    def phase(name, **extra):
        state.update(stage=name, **extra)
        write_json(pointer, state)
        print(json.dumps({"stage": name, **extra}), flush=True)

    def wait_json(path):
        while True:
            try:
                return json.loads(path.read_text(encoding="utf-8-sig"))
            except FileNotFoundError:
                time.sleep(5)
            except json.JSONDecodeError:
                # A producer writes small JSON files directly; permit its
                # current write to finish rather than interpreting partial IO.
                time.sleep(1)

    try:
        phase("WAITING_EXISTING_OFFICIAL_DEMO_PROCESS")
        status = wait_json(demo / "status.json")
        if status["status"] != "BA_TRACK_PIPELINE_COMPLETED":
            raise RuntimeError("Existing official Demo did not complete; native failure retained, MVS not started")
        phase("EXPORTING_AND_VALIDATING_OFFICIAL_DEMO")
        command = [sys.executable, "-X", "utf8", str(PROJECT / "scripts/export_ba_track_results.py"), str(demo)]
        with (demo / "completed_output_export.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError("Demo output export/sanity check failed; MVS not started")
        phase("WAITING_EXPLICIT_DEMO_FIGURE_QA")
        while True:
            review = wait_json(demo / "output_review.json")
            if review["status"] != "BA_TRACK_COMPLETED_OUTPUTS_SANITY_CHECKED":
                raise RuntimeError("Unexpected numerical review state")
            qa_path = demo / "figure_review.json"
            if review.get("figures_visually_reviewed") and qa_path.exists():
                qa = wait_json(qa_path)
                if qa["status"] == "VISUALLY_REVIEWED_PASS" and all(sha256(demo / item["file"]) == item["sha256"] for item in qa["files"]):
                    break
            time.sleep(3)
        previous = PROJECT / "reports/SOTA/ba_track_mvs.json"
        if previous.exists():
            raise RuntimeError("A MVS attempt already exists; inspect it rather than automatically replaying")
        phase("RUNNING_SINGLE_SHARED_MVS100_PIPELINE")
        command = ["wsl", "-d", "Ubuntu", "--exec", "/home/lsuser/.local/share/gamecam-vo/envs/ba-track/bin/python",
                   "/mnt/d/aaa/GameCam-VO/scripts/run_ba_track_pipeline.py", "--target", "mvs"]
        with (PROJECT / "logs/E9_ba_track_mvs_01.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError("The single MVS pipeline failed; no automatic retry")
        mvs = wait_json(previous)
        if mvs["status"] != "BA_TRACK_PIPELINE_COMPLETED":
            raise RuntimeError("Native MVS terminal state was not completed")
        directory = local(mvs["directory"])
        phase("EXPORTING_AND_VALIDATING_MVS100", MVS_directory=str(directory))
        command = [sys.executable, "-X", "utf8", str(PROJECT / "scripts/export_ba_track_results.py"), str(directory)]
        with (directory / "completed_output_export.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError("MVS output numerical review failed; independent metrics not claimed")
        phase("MVS100_OUTPUTS_READY_FOR_EXTERNAL_GT_EVALUATION", MVS_directory=str(directory))
        return 0
    except Exception as error:
        phase("STOPPED_AT_RECORDED_FAILURE", error=f"{type(error).__name__}: {error}")
        return 1
    finally:
        lock.unlink()


if __name__ == "__main__":
    raise SystemExit(main())

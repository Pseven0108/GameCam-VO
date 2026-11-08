"""Classify actual uninitialized MOVi native attempts without changing model rules."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
import json

import numpy as np
from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import local, read


def main():
    plan_file = local(read(PROJECT / "reports/PHASE5/active_E15_MOVIE_batch.json")["plan"])
    reviewed = []
    for number, job in enumerate(read(plan_file)["jobs"]):
        if job["state"] != "ATTEMPT_TERMINAL" or job["method"] not in ("DROID_W", "WILDGS") or not job.get("result_directory"):
            continue
        folder = local(job["result_directory"])
        if (folder / "evaluation_summary.json").exists() or (folder / "failure_review.json").exists():
            continue
        status = read(folder / "status.json")
        trace_file = folder / "frontend_frames.jsonl"
        trace = [json.loads(line) for line in trace_file.read_text().splitlines()]
        if (status["expected_frames"] != 24 or len(trace) != 24 or
            [row["frame_index"] for row in trace] != list(range(24)) or
            any(row["frontend_initialized"] for row in trace)):
            raise ValueError("This attempt requires a separate case-specific review; never infer uninitialized status")
        videos = list((folder / "upstream_output").rglob("video.npz"))
        if len(videos) != 1:
            raise ValueError("Actual native retained-keyframe evidence is required")
        with np.load(videos[0]) as video:
            indices = video["timestamps"].copy()
        if not 0 < len(indices) < 12:
            raise ValueError("Not the unchanged native 12-keyframe warmup shortfall")
        evidence = [folder / name for name in ("status.json", "execution_contract.json", "frontend_frames.jsonl")]+videos
        if job["method"] == "DROID_W":
            if status["status"] != "DROID_INFERENCE_COMPLETED" or job.get("camera_evaluation_exit_code") != 1:
                raise ValueError("DROID terminal/export evidence differs from this reviewed classification")
            evidence.append(plan_file.parent / f"{number:02d}_camera_evaluation.log")
            classification = "NATIVE_FRONTEND_NOT_INITIALIZED_ON_COMPLETE_24_FRAME_CLIP"
            reason = (f"All 24 actual frontend calls remain uninitialized; {len(indices)} retained keyframes are below the unchanged native 12-keyframe warmup. "
                "The native process completed, but camera tracking is not accepted. Any archived uncertainty is analyzed only as pre-initialization native signal evidence.")
        else:
            log = folder / "inference_log.txt"
            text = log.read_text(encoding="utf-8")
            if status["status"] != "WILDGS_INFERENCE_FAILED" or "AttributeError: 'ObservedMapper' object has no attribute 'cameras'" not in text or "self.mapper.final_refine" not in text:
                raise ValueError("WildGS exception requires its own actual failure review")
            classification = "UNINITIALIZED_NATIVE_FRONTEND_AND_MAPPER_FINAL_REFINE_EXCEPTION"
            reason = (f"All 24 frontend calls remain uninitialized with {len(indices)} retained keyframes. The native mapper reaches final_refine without a cameras member and raises the recorded AttributeError. "
                "No full camera trajectory/map or archived dense uncertainty is available. The wrapper catches the actor exception despite child exit 0; the recorded pipeline FAILED status remains authoritative. "
                "This is a short-clip initialization/finalization limitation, not evidence of camera drift or game-specific dynamic failure.")
            evidence += [log, folder / "runtime_source_cache_manifest.json"]
            archive = folder / "executed_source_archive.json"
            if archive.exists():
                evidence.append(archive)
        write_json(folder / "failure_review.json", {"status": "REVIEWED_FAILURE_OR_UNAVAILABLE_CAMERA_METRICS",
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(), "classification": classification,
            "reason": reason+" No frame looping, warmup/window reduction, or failure-driven model replay.",
            "native_pipeline_terminal_status": status["status"], "camera_tracking_accepted": False,
            "uninitialized_frontend_calls": len(trace), "native_keyframes": len(indices),
            "model_or_frozen_protocol_changed": False,
            "evidence": [{"file": str(path), "sha256": sha256(path)} for path in evidence]})
        reviewed.append({"method": job["method"], "sequence": job["sequence"], "classification": classification})
    print(json.dumps({"new_failure_reviews": reviewed}))


if __name__ == "__main__":
    main()

"""Export only verified complete native camera fields; full BA remains failed."""
from __future__ import annotations

import _bootstrap
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_csv, write_json
from phase5_motion_support import local, read, json_lines
from export_ba_track_results import validate_camera, save_camera


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    if not any(out.is_relative_to(PROJECT / "results" / e / "BA_TRACK") for e in ("E14_WILD_DYNAMIC", "E15_MOVIE", "E16_BONN")):
        raise ValueError("Only the specifically audited new BA camera recovery is accepted")
    candidates = [p for p in (out / "native_camera_prefix_recovery/recovery_review.json", out / "native_terminate_camera_review/recovery_review.json") if p.exists()]
    if len(candidates) != 1:
        raise ValueError("Require exactly one independently reviewed native sparse-camera source")
    review_file = candidates[0]
    review = read(review_file)
    from_return = review["status"] == "COMPLETE_NATIVE_TERMINATE_CAMERA_RETURN_INDEPENDENTLY_CHECKED"
    if review["status"] not in ("COMPLETE_NATIVE_FINAL_SPARSE_CAMERA_PREFIX_RECOVERED_AND_INDEPENDENTLY_CHECKED", "COMPLETE_NATIVE_TERMINATE_CAMERA_RETURN_INDEPENDENTLY_CHECKED") or review["GT_used_in_recovery_or_direction_choice"] or review["native_numeric_values_modified"]:
        raise ValueError("A strict independent native sparse-camera source review is required")
    source_key = "raw_native_return_archive" if from_return else "raw_interrupted_pickle"
    source, archive = local(review[source_key]), local(review["complete_camera_archive"])
    if sha256(source) != review[source_key+"_sha256"] or sha256(archive) != review["complete_camera_archive_sha256"]:
        raise ValueError("Recovered/native artifact identity changed")
    if from_return:
        if sha256(out / "status.json") != review["native_status_sha256"]:
            raise ValueError("Reviewed failed native status changed")
        if review.get("native_return_receipt_sha256"):
            if sha256(source.with_suffix(".json")) != review["native_return_receipt_sha256"]:
                raise ValueError("Reviewed original-return receipt changed")
        else:
            legacy = review.get("legacy_index_IO_exception_evidence")
            if not legacy or legacy["missing_native_field_reconstructed_or_claimed"]:
                raise ValueError("Missing original receipt without an exact independently reviewed recorder exception")
            for key in ("log", "executed_observer", "pretermination_issue_review"):
                if sha256(local(legacy[key])) != legacy[key+"_sha256"]:
                    raise ValueError("Exact legacy recorder-exception evidence changed")
    trace_file = out / "motion_decomposition/frontend_calls.jsonl"
    if sha256(trace_file) != review["independent_native_state_comparison"]["online_trace_sha256"]:
        raise ValueError("Independently archived native state trace changed")
    with np.load(archive) as z:
        times, poses, rigidity = validate_camera(z["tstamps"], z["cams_T_world"], review["expected_frames"])
    scope = "Verified original native terminate return; later full BA pipeline FAILED" if from_return else "Recovered complete native final sparse SLAM T_wc; native process exited -9 during later pickle serialization; full pipeline failed"
    save_camera(out, times, poses, scope)
    calls = json_lines(trace_file)
    rows = [{"frame_index": int(r["input_timestamp"]), "frontend_initialized_after_call": r["initialized"],
        "native_retained_camera_buffer_size": r["retained_buffer_size"], "native_input_calls_seen": r["input_calls_seen"],
        "explicit_tracking_loss_state": None} for r in calls]
    write_csv(out / "tracking_status.csv", rows)
    folder = out / "tracking_visualization"
    folder.mkdir(exist_ok=True)
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none", "axes.spines.top": False, "axes.spines.right": False}):
        fig, axes = plt.subplots(2, 1, figsize=(9, 5), layout="constrained")
        indices = np.arange(len(rows))
        initialized = np.array([r["frontend_initialized_after_call"] for r in rows])
        axes[0].scatter(indices, np.zeros(len(rows)), marker="|", color="#275c8a", s=30, label=f"Recovered finite final cameras {len(rows)}/{len(rows)}")
        axes[0].scatter(indices[initialized], np.ones(initialized.sum()), marker="|", color="#ae563a", s=30, label=f"Initialized after call {initialized.sum()}/{len(rows)}")
        support_title = "a  Complete native sparse cameras and native startup are separate" if from_return else "a  Camera serialization recovery and native startup are separate"
        axes[0].set(yticks=[0, 1], yticklabels=["Final camera", "Initialized"], ylim=(-.6, 1.6), title=support_title)
        axes[0].legend(frameon=False, fontsize=8)
        axes[1].plot(indices, [r["native_retained_camera_buffer_size"] for r in rows], color="#275c8a", lw=1)
        axes[1].set(xlabel="Full input sample key", ylabel="Retained camera states", title="b  Direct frontend observation; no invented tracking-loss rate")
        for ax in axes:
            ax.grid(alpha=.15)
        title = "BA-Track complete native terminate camera return independently checked\nLater full pipeline FAILED; original sparse return preserved; no model rerun" if from_return else "BA-Track final sparse cameras recovered from complete native prefix\nNative full pipeline FAILED: host-memory SIGKILL during later track pickle serialization; no model rerun"
        fig.suptitle(title, fontsize=10)
        for suffix in ("png", "svg"):
            fig.savefig(folder / ("recovered_camera_support."+suffix), dpi=180)
        plt.close(fig)
    checked = {"status": "BA_TRACK_COMPLETE_FINAL_SPARSE_CAMERA_RECOVERED_PIPELINE_FAILED", "expected_frames": len(poses), "finite_filled_pose_frames": len(poses),
        "initialized_frontend_calls": int(initialized.sum()), "frontend_calls": len(rows), "sparse_camera_checks": rigidity,
        "coordinate_check": review["independent_native_state_comparison"], "primary_pose_stage": "Native final sparse SLAM, frozen before GT scoring",
        "native_pipeline_completed": False, "native_output_recovery_without_model_replay": True, "recovery_review_sha256": sha256(review_file),
        "trajectory_sha256": sha256(out / "estimated_trajectory.csv"), "dense_refinement_output": "NOT_ACCEPTED_CHECK_SEPARATE_NATIVE_STAGE_STATUS" if from_return else "NOT_AVAILABLE_NATIVE_STAGE_NOT_STARTED",
        "native_sparse_camera_source": "original_terminate_return" if from_return else "complete_interrupted_pickle_prefix",
        "complete_track_pickle_or_refined_depth_claim": False, "figures_visually_reviewed": False}
    write_json(out / "output_review.json", checked)
    print(json.dumps({"status": checked["status"], "camera_frames": len(poses), "initialized_after_calls": int(initialized.sum())}))


if __name__ == "__main__":
    main()

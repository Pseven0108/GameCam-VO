from __future__ import annotations
import _bootstrap
import json
from pathlib import Path
from gamecam_vo.common import PROJECT, make_run_dir, run_metadata, sha256, write_json
from gamecam_vo.evaluation import load_trajectory
from gamecam_vo.plotting import plot_comparison, plot_trajectory


def main():
    out = make_run_dir(PROJECT / "reports/figures", "real_game_trajectories")
    sources = {}
    for tag, e0_id, e1_id in (("mvs", "E0_MVS", "E1A_MVS"), ("omni", "E0_OMNI", "E1A_OMNI")):
        e0 = Path(json.loads((PROJECT / "results" / e0_id / "latest_run.json").read_text())["directory"])
        root = json.loads((e0 / "validation.json").read_text(encoding="utf-8"))
        for sequence in root["sequences"]:
            sid = sequence["sequence_id"]
            local = e0 / sid
            meta = json.loads((local / "validation.json").read_text(encoding="utf-8"))
            trajectory = local / meta["trajectory_file"]
            times, poses = load_trajectory(trajectory)
            target = out / tag / "reference"
            label = "MVS-Synth ENGINE GROUND TRUTH" if tag == "mvs" else "OmniWorld ESTIMATED REFERENCE"
            plot_trajectory(times, poses, target, meta["length_unit"], label, meta["timestamp_kind"])
            sources[str(target)] = {"trajectory": str(trajectory), "sha256": sha256(trajectory)}
        for summary_path in sorted((PROJECT / "results" / e1_id).rglob("run_summary.json")):
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            folder = summary_path.parent
            if summary.get("fatal_error"):
                continue
            ref = folder / summary["evaluation_reference_file"]
            times, poses = load_trajectory(ref)
            _, predicted = load_trajectory(folder / "estimated_trajectory.csv")
            details = json.loads((folder / "evaluation_details.json").read_text())
            variant = summary.get("experiment_variant", "distance50_default")
            target = out / tag / variant
            target.mkdir(parents=True)
            plot_comparison(times, poses, predicted, details, target, "native_game_unit" if tag == "mvs" else "reference_unit",
                            f"{summary['dataset']} / {summary['sequence_id']} / {variant}", tag == "mvs",
                            "frame_index" if tag == "mvs" else "seconds")
            sources[str(target)] = {"run_summary": str(summary_path), "estimated_trajectory_sha256": sha256(folder / "estimated_trajectory.csv"),
                                     "evaluation_details_sha256": sha256(folder / "evaluation_details.json")}
    write_json(out / "figure_sources.json", {**run_metadata(), "sources": sources, "status": "GENERATED_REQUIRES_VISUAL_REVIEW"})
    write_json(PROJECT / "reports/latest_figures.json", {"directory": str(out)})
    print(str(out))


if __name__ == "__main__":
    main()

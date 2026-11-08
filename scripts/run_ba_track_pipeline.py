"""Execute the reviewed official Demo stages, then the same RGB-only MVS target.

Linux-side orchestration only: pretrained priors, tracker, sparse BA and official
300-iteration/grid12 dense refinement retain their documented parameters.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np


ROOT = Path("/mnt/d/aaa/GameCam-VO")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def linux_path(value):
    return Path(str(value).replace("\\", "/").replace("D:/", "/mnt/d/", 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["official-demo", "mvs"], required=True)
    parser.add_argument("--reuse-priors-from", type=Path, help="Reuse completed, hash-recorded prior outputs in a new retry directory")
    args = parser.parse_args()
    assets = json.loads((ROOT / "reports/SOTA/ba_track_assets.json").read_text())
    if assets["status"] != "BA_TRACK_PRIMARY_ASSETS_VERIFIED":
        raise RuntimeError("Verified complete weights and official Demo RGB are required")
    if args.target == "mvs":
        demo = json.loads((ROOT / "reports/SOTA/ba_track_official_demo.json").read_text())
        demo_review = json.loads((ROOT / "reports/SOTA/ba_track_official_demo_output_review.json").read_text())
        if demo["status"] != "BA_TRACK_PIPELINE_COMPLETED" or demo_review["status"] != "BA_TRACK_COMPLETED_OUTPUTS_SANITY_CHECKED":
            raise RuntimeError("Complete the official Demo before adapting MVS")
        if not demo_review.get("figures_visually_reviewed") or not demo_review["sparse_camera_checks"]["rigid_check_passed"]:
            raise RuntimeError("Review the Demo figures and official sparse pose output first")
        protocol = json.loads((ROOT / "reports/SOTA/ba_track_pose_protocol.json").read_text())
        if protocol["status"] != "OFFICIAL_POSE_PROTOCOL_CONFIRMED_BEFORE_MVS_EXECUTION_OR_GT_SCORING":
            raise RuntimeError("Freeze the official primary pose-evaluation protocol before MVS")
        if (ROOT / "reports/SOTA/ba_track_mvs.json").exists():
            raise RuntimeError("An MVS attempt already exists; inspect it before any explicit retry")
    for row in assets["assets"]:
        if digest(row["path"]) != row["sha256"]:
            raise ValueError("Asset digest changed")
    scene = "tennis" if args.target == "official-demo" else "mvs_0000"
    out = ROOT / "results/E9_BA_TRACK" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_" + args.target.replace("-", "_") + "_" + scene)
    out.mkdir(parents=True, exist_ok=False)
    if args.target == "official-demo":
        rgb = Path(assets["official_demo_rgb_directory"])
        fixed_k = None
    else:
        pointer = json.loads((ROOT / "reports/SOTA/mvs_rgb_input.json").read_text())
        prepared = linux_path(pointer["directory"])
        inputs = json.loads((prepared / "input_manifest.json").read_text())
        if len(inputs["frames"]) != 100 or inputs["inference_inputs"] != ["RGB", "camera_intrinsics"]:
            raise ValueError("The frozen 100-frame RGB+K target is required")
        for frame in inputs["frames"]:
            if digest(linux_path(frame["path"])) != frame["sha256"]:
                raise ValueError("Shared MVS RGB hash changed")
        rgb = prepared / "rgb"
        fixed_k = np.asarray(inputs["fixed_K"], dtype=float)
        shutil.copy2(prepared / "input_manifest.json", out / "input_manifest.json")
    images = sorted(p for p in rgb.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    (out / "RGB_manifest.json").write_text(json.dumps([{"frame_index": i, "name": p.name, "path": str(p), "sha256": digest(p)} for i, p in enumerate(images)], indent=2))
    # Alignment expects data_root/scene. A local symlink only exposes the RGB
    # folder, never MVS poses or engine depth, to the official prior scripts.
    data_root = out / "input"
    data_root.mkdir()
    (data_root / scene).symlink_to(rgb, target_is_directory=True)
    depth = out / "depth_results"
    result = out / "upstream_output"
    launcher = ROOT / "scripts/run_ba_track_reviewed_entrypoint.py"
    def entry(relative, *arguments):
        return [sys.executable, str(launcher), relative, *map(str, arguments)]
    da_args = ["--encoder", "vitl", "--load-from", ROOT / "data/sota_assets/BA_TRACK/weights/depth_anything_v2_vitl.pth", "--img-path", rgb]
    # Preserve the duplicate DA step in the pinned official shell script while
    # retaining both outputs instead of overwriting the first prediction.
    commands = [
        ("depth_anything_v2_first", entry("Depth-Anything/run_videos_v2.py", *da_args, "--outdir", depth / "depthAny_disp_first" / scene)),
        ("depth_anything_v2_second", entry("Depth-Anything/run_videos_v2.py", *da_args, "--outdir", depth / "depthAny_disp" / scene)),
        ("unidepth_v2", entry("UniDepth/scripts/demo_mega-sam.py", "--scene-name", scene, "--img-path", rgb, "--outdir", depth / "unidepthv2")),
        ("align_predicted_depths", entry("main/mono_depth/get_mono_depth.py", "--data_dir", data_root, "--depth_dir", depth, "--save_name", "unidepth_dav2")),
    ]
    calibration = depth / "unidepth_dav2_intrinsics" / scene if fixed_k is None else out / "known_intrinsics"
    if fixed_k is not None:
        calibration.mkdir()
        for image in images:
            np.save(calibration / (image.stem + "_intrinsics.npy"), fixed_k)
    commands += [
        ("sparse_tracker_and_BA", entry("main/run_batrack.py", "--config-path=../configs", "--config-name=davis_demo",
            "data.imagedir=" + str(rgb), "data.savedir=" + str(result), "+data.depthdir=" + str(depth / "unidepth_dav2" / scene),
            "+data.depthdir_gt=" + str(depth / "unidepth_dav2" / scene), "data.calib=" + str(calibration), "data.name=" + scene,
            "model.init_dir=" + str(ROOT / "data/sota_assets/BA_TRACK/weights/md_tracker.pth"),
            "visualizer.save_dir=" + str(out / "visualization"), "hydra.run.dir=" + str(out / "hydra"), "hydra.job.chdir=false",
            "save_trajectory=true", "save_plot=true", "save_results=true")),
        ("dense_global_refinement", entry("main/global_refine/run_global_refine.py", "--result_dir", result, "--grid_size", 12, "--scenes", scene, "--niter", 300)),
    ]
    reused = None
    if args.reuse_priors_from:
        old = args.reuse_priors_from.resolve()
        if not old.is_relative_to(ROOT / "results/E9_BA_TRACK"):
            raise ValueError("Prior reuse must refer to an owned result directory")
        old_contract = json.loads((old / "execution_contract.json").read_text())
        old_stages = json.loads((old / "execution.json").read_text())
        if old_contract["target"] != args.target or old_contract["scene"] != scene or old_contract["expected_frames"] != len(images):
            raise ValueError("Prior reuse target differs")
        if json.loads((old / "RGB_manifest.json").read_text()) != json.loads((out / "RGB_manifest.json").read_text()):
            raise ValueError("Prior input hashes differ")
        if len(old_stages) < 4 or [r["stage"] for r in old_stages[:4]] != [name for name, _ in commands[:4]] or any(r["exit_code"] for r in old_stages[:4]):
            raise ValueError("All four original prior stages must have actually passed")
        manifest = [{"path": p.relative_to(old / "depth_results").as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)}
                    for p in sorted((old / "depth_results").rglob("*")) if p.is_file()]
        shutil.copytree(old / "depth_results", depth, copy_function=os.link)
        reused = {"directory": str(old), "completed_original_stages": old_stages[:4], "files": manifest,
                  "policy": "New retry directory; same RGB hashes; immutable prior outputs hard-linked and only read. Original failed run retained."}
        (out / "reused_prior_manifest.json").write_text(json.dumps(reused, indent=2))
        commands = commands[4:]
    env = os.environ.copy()
    cache = ROOT / "data/sota_assets/BA_TRACK"
    env.update({"HF_HOME": str(cache / "huggingface"), "TORCH_HOME": str(cache / "torch_home"), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "PYTHONPATH": str(ROOT / "baselines/runtime_hooks"), "PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg", "QT_QPA_PLATFORM": "offscreen",
                "GAMECAM_CUDA_MEMORY_DIR": str(out / "cuda_allocator_stats"), "OMP_NUM_THREADS": "4",
                "GAMECAM_BA_MOTION_TRACE_DIR": str(out / "motion_decomposition")})
    env["GAMECAM_BA_REFINE_TRACE_DIR"] = str(out / "depth_results/refine_trace")
    upstream = ROOT / "baselines/ba_track/upstream"
    source_patch = subprocess.check_output(["git", "-C", str(upstream), "diff", "--binary", "456e094ee3ca7fbd9884ba18e68e7c0717d49a67"])
    (out / "source_changes_from_upstream.patch").write_bytes(source_patch)
    contract = {"target": args.target, "scene": scene, "expected_frames": len(images), "commands": commands, "cwd": str(upstream),
                "source_commit": subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip(),
                "source_changes_from_upstream_sha256": hashlib.sha256(source_patch).hexdigest(),
                "source_worktree_status": subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain"], text=True),
                "inference_inputs": ["RGB"] if fixed_k is None else ["RGB", "camera_intrinsics"], "engine_pose_in_inference": False, "engine_depth_in_inference": False,
                "depthdir_gt_is_same_predicted_directory": True, "sparse_calibration": "predicted" if fixed_k is None else "provided_known_K",
                "dense_refines_intrinsics_per_official_cli_default": True, "dense_grid_size": 12, "dense_iterations": 300,
                "primary_pose_evaluation": "Official sparse SLAM pose output, as in official eval_*_pose.sh; frozen before MVS GT scoring",
                "dense_camera_policy": "Retain raw matrices as independent diagnostic; never silently normalize nonrigid outputs",
                "prior_reuse": None if reused is None else {"directory": reused["directory"], "manifest": "reused_prior_manifest.json"},
                "preserve_duplicate_official_DA_step": True, "motion_observation": "Optional hook copies original outputs to CPU and returns None; overhead included in wall time",
                "environment_overrides": {k: env[k] for k in ("HF_HOME", "TORCH_HOME", "HF_HUB_OFFLINE", "PYTHONPATH", "OMP_NUM_THREADS", "GAMECAM_BA_MOTION_TRACE_DIR", "GAMECAM_BA_REFINE_TRACE_DIR")}}
    (out / "execution_contract.json").write_text(json.dumps(contract, indent=2))
    if args.target == "mvs":
        shutil.copy2(ROOT / "reports/SOTA/ba_track_pose_protocol.json", out / "pose_evaluation_protocol.json")
    for path in [Path(__file__), launcher, ROOT / "baselines/runtime_hooks/ba_track_observer.py", ROOT / "baselines/runtime_hooks/ba_track_motion_trace.py",
                 ROOT / "baselines/runtime_hooks/ba_track_refine_trace.py", ROOT / "baselines/runtime_hooks/sitecustomize.py"]:
        shutil.copy2(path, out / (path.name + ".executed_source"))
    stages, peak = [], None
    run_started = time.monotonic()
    with (out / "gpu_memory.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["stage", "run_elapsed_seconds", "stage_elapsed_seconds", "whole_gpu_used_mib", "whole_gpu_total_mib", "whole_gpu_utilization_percent"])
        for name, command in commands:
            started = time.monotonic()
            timed_out = False
            with (out / (name + ".log")).open("w") as log:
                process = subprocess.Popen(command, cwd=upstream, env=env, stdout=log, stderr=subprocess.STDOUT)
                oom_first_seen = None
                while process.poll() is None:
                    try:
                        memory = subprocess.run(["/usr/lib/wsl/lib/nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
                    except subprocess.TimeoutExpired as error:
                        memory = None
                        with (out / "telemetry_errors.jsonl").open("a") as errors:
                            errors.write(json.dumps({"stage": name, "elapsed_seconds": time.monotonic()-started, "error": str(error)})+"\n")
                    if memory is not None and memory.returncode == 0:
                        values = [float(x.strip()) for x in memory.stdout.strip().split(",")]
                        writer.writerow([name, time.monotonic()-run_started, time.monotonic()-started, *values])
                        stream.flush()
                        peak = max(peak or 0, values[0])
                    # After a recorded unhandled CUDA OOM, allow error handling
                    # to exit, then stop this owned child if teardown stalls.
                    # This never changes a successful model computation.
                    with (out / (name + ".log")).open("rb") as observed_log:
                        observed_log.seek(max(0, observed_log.seek(0, 2)-16384))
                        terminal_oom = b"torch.OutOfMemoryError: CUDA out of memory" in observed_log.read()
                    if terminal_oom:
                        oom_first_seen = oom_first_seen or time.monotonic()
                        if time.monotonic()-oom_first_seen > 10 and process.poll() is None:
                            process.kill()
                            break
                    if time.monotonic()-started > 7200:
                        timed_out = True
                        process.terminate()
                        try:
                            process.wait(timeout=20)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        break
                    time.sleep(1)
                code = process.wait()
            stages.append({"stage": name, "exit_code": code, "timed_out": timed_out, "wall_seconds": time.monotonic()-started})
            (out / "execution.json").write_text(json.dumps(stages, indent=2))
            print(json.dumps(stages[-1]), flush=True)
            if code or timed_out:
                break
    passed = len(stages) == len(commands) and all(s["exit_code"] == 0 and not s["timed_out"] for s in stages)
    if passed and not (result / scene / "results_refined.pkl").is_file():
        passed = False
    record = {"status": "BA_TRACK_PIPELINE_COMPLETED" if passed else "BA_TRACK_PIPELINE_FAILED", "directory": str(out),
              "target": args.target, "expected_frames": len(images), "scene": scene, "stages": stages,
              "whole_gpu_peak_used_mib_sampled": peak, "whole_pipeline_wall_seconds": time.monotonic()-run_started,
              "independent_accuracy_evaluation_completed": False,
              "priors_reused_from": None if reused is None else reused["directory"],
              "wall_scope": "This attempt's actual subprocesses and observation; inherited prior compute time is recorded separately, never counted as newly executed",
              "no_algorithm_hyperparameter_changes": True, "engine_pose_in_inference": False, "engine_depth_in_inference": False}
    (out / "status.json").write_text(json.dumps(record, indent=2))
    pointer = "ba_track_official_demo.json" if args.target == "official-demo" else "ba_track_mvs.json"
    (ROOT / "reports/SOTA" / pointer).write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())

"""Run a selected existing neural baseline on one full, frozen RGB/K view."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import yaml

from phase5_runtime import ROOT, digest, environment, execute, freeze_source, local, write, memory_budget


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=("DROID_W", "PI3MOS", "BA_TRACK"))
    parser.add_argument("--input-pointer", type=Path, required=True)
    parser.add_argument("--experiment", choices=("E14_WILD_DYNAMIC", "E15_MOVIE", "E16_BONN"), required=True)
    parser.add_argument("--reuse-prior-review", type=Path, help="Only the byte-reviewed complete learned priors of the failed E14 Crowd capacity attempt")
    args = parser.parse_args()
    if os.name == "nt":
        raise RuntimeError("Use each method's already isolated WSL environment")
    expected_env = {"DROID_W": "droid-w", "PI3MOS": "pi3mos", "BA_TRACK": "ba-track"}[args.method]
    if Path(sys.prefix).resolve() != (Path("/home/lsuser/.local/share/gamecam-vo/envs") / expected_env).resolve():
        raise RuntimeError("Wrong independent baseline environment")
    pointer = json.loads(args.input_pointer.read_text())
    if args.reuse_prior_review and (args.method != "BA_TRACK" or args.experiment != "E14_WILD_DYNAMIC" or pointer.get("sequence") != "crowd"):
        raise ValueError("Prior reuse is restricted to the reviewed incomplete E14 BA Crowd repair")
    inputs = local(pointer["directory"])
    manifest = json.loads((inputs / "input_manifest.json").read_text())
    if manifest["inference_inputs"] != ["RGB", "camera_intrinsics"]:
        raise ValueError("Frozen RGB+K-only view required")
    if len(manifest["frames"]) != pointer["expected_frames"]:
        raise ValueError("Every declared frame must be retained")
    for frame in manifest["frames"]:
        if digest(local(frame["path"])) != frame["sha256"]:
            raise ValueError("Common RGB input changed")
    if any(p.suffix.lower() in (".exr", ".pth", ".pkl", ".csv") for p in inputs.rglob("*") if p.is_file()):
        raise ValueError("Unexpected GT/depth/weights in the model input view")
    method_folder, base = {"DROID_W": ("droid_w", "c3414af6047d06bafc1a6645d09f23247f3b2cdc"),
        "PI3MOS": ("pi3mos", "5e709d27324a935e364e01efc56f3128ac00bf24"),
        "BA_TRACK": ("ba_track", "456e094ee3ca7fbd9884ba18e68e7c0717d49a67")}[args.method]
    upstream = ROOT / "baselines" / method_folder / "upstream"
    if args.method != "PI3MOS":
        asset_file = "droid_assets.json" if args.method == "DROID_W" else "ba_track_assets.json"
        verified = json.loads((ROOT / "reports/SOTA" / asset_file).read_text())
        for asset in verified["assets"]:
            if Path(asset["path"]).suffix in (".pth", ".safetensors") and digest(local(asset["path"])) != asset["sha256"]:
                raise ValueError("A selected official checkpoint changed")
    if args.method == "DROID_W":
        cache_proof = json.loads((ROOT / "reports/SOTA/droid_amp_cache_equivalence.json").read_text())
        if cache_proof["status"] != "AMP_WEIGHT_CACHE_EQUIVALENCE_PASSED":
            raise RuntimeError("Existing AMP cache portability option requires its actual numerical proof")
    sequence = pointer.get("sequence", manifest["sequence_id"])
    reused_prior = None
    if args.reuse_prior_review:
        linked_review = json.loads(args.reuse_prior_review.read_text())
        review_file = local(linked_review["review"])
        if digest(review_file) != linked_review["sha256"]:
            raise ValueError("Reviewed native-prior identity changed")
        reused_prior = json.loads(review_file.read_text())
        if (reused_prior["status"] != "COMPLETE_NATIVE_LEARNED_PRIORS_BYTE_AND_VALUE_REVIEWED_FOR_CAPACITY_REPAIR"
            or reused_prior["sequence"] != sequence or reused_prior["expected_frames"] != len(manifest["frames"])
            or reused_prior["sensor_depth_or_GT_used"] or reused_prior["native_prior_arrays_modified"]
            or reused_prior["input_manifest_sha256"] != digest(inputs / "input_manifest.json")
            or reused_prior["assets_manifest_sha256"] != digest(ROOT / "reports/SOTA/ba_track_assets.json")):
            raise ValueError("The reviewed native-prior source does not match unchanged repair inputs/assets")
        prior_root = local(reused_prior["cached_directory"]).resolve()
        known_root = ROOT / "results/E14_WILD_DYNAMIC/BA_TRACK/20261101T152634Z_crowd/depth_results/unidepth_dav2/crowd"
        if prior_root != known_root.resolve() or len(reused_prior["files"]) != len(manifest["frames"]):
            raise ValueError("Require the exact reviewed complete native prior directory")
        for frame, cached in zip(manifest["frames"], reused_prior["files"], strict=True):
            file = local(cached["file"]).resolve()
            if file.parent != prior_root or file.name != local(frame["path"]).stem+".npy" or digest(file) != cached["sha256"]:
                raise ValueError("A reviewed cached native prior changed")
    video_io_review_file = ROOT / "reports/PHASE5/BA_native_video_visibility_IO_review.json"
    if args.method == "BA_TRACK":
        video_io_review = json.loads(video_io_review_file.read_text())
        if (video_io_review["status"] != "CPU_NATIVE_VIDEO_RGB_BYTE_EQUIVALENCE_PASSED"
            or video_io_review["CUDA_initialized_before_or_after"] or video_io_review["model_forwards"]
            or video_io_review["GT_used"] or len(video_io_review["cases"]) != 12
            or video_io_review["IO_helper_sha256"] != digest(ROOT / "baselines/runtime_hooks/ba_track_video_io.py")
            or video_io_review["native_source_sha256"] != digest(upstream / "main/slam_visualizer.py")):
            raise ValueError("New video IO variant requires its unchanged native-renderer byte comparison")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = ROOT / "results" / args.experiment / args.method / (stamp+"_"+sequence)
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(inputs / "input_manifest.json", out / "input_manifest.json")
    write(out / "RGB_manifest.json", manifest["frames"])
    k = np.asarray(manifest["fixed_K"])
    env = environment(out)
    commands = []
    if args.method == "PI3MOS":
        assets = json.loads((ROOT / "reports/SOTA/pi3mos_assets.json").read_text())
        for row in assets["assets"]:
            if digest(local(row["path"])) != row["sha256"]:
                raise ValueError("Verified Pi3MOS checkpoint changed")
        (out / "input_rgb").symlink_to(inputs / "rgb", target_is_directory=True)
        np.savetxt(out / "input_calibration.txt", [[k[0, 0], k[1, 1], k[0, 2], k[1, 2]]], fmt="%.18g")
        commands = [("native", [sys.executable, str(ROOT / "scripts/run_pi3mos_reviewed_entrypoint.py"), "--imagedir", str(out / "input_rgb"), "--calib", str(out / "input_calibration.txt"), "--config", "config/default.yaml", "--outdir", str(out)])]
    elif args.method == "DROID_W":
        sys.path.insert(0, str(upstream))
        os.chdir(upstream)
        from src import config
        from src.utils.datasets import get_dataset
        cfg = config.load_config("configs/droid_w.yaml")
        cfg.update(dataset="youtube", scene=sequence, save_gt_poses=False)
        cfg["data"].update(input_folder=str(inputs), root_folder=str(inputs), output=str(out / "upstream_output"))
        cfg["tracking"]["pretrained"] = str(ROOT / "data/sota_assets/DROID_W/weights/droid.pth")
        cfg["cam"].update(H=manifest["height"], W=manifest["width"], H_out=manifest["height"], W_out=manifest["width"], fx=float(k[0, 0]), fy=float(k[1, 1]), cx=float(k[0, 2]), cy=float(k[1, 2]))
        cfg["cam"].pop("distortion", None)
        stream = get_dataset(cfg, device="cpu")
        if len(stream) != len(manifest["frames"]) or stream.poses is not None or stream.depth_paths is not None:
            raise ValueError("DROID stream omits inputs or exposes external GT/depth")
        config.save_config(cfg, str(out / "run_config.yaml"))
        (out / "upstream_output" / sequence).mkdir(parents=True)
        cache = ROOT / "data/sota_assets/DROID_W"
        env.update(TORCH_HOME=str(cache / "torch_home"), HF_HOME=str(cache / "huggingface"),
            GAMECAM_FIT3D_REPO=str(ROOT / "baselines/droid_w/prior_sources/FiT3D"), GAMECAM_METRIC3D_REPO=str(ROOT / "baselines/droid_w/prior_sources/Metric3D"),
            GAMECAM_SINGLE_PROCESS_TRACKING="1", GAMECAM_XFORMERS_DISABLE_FA3="1", GAMECAM_FRAME_TELEMETRY=str(out / "frontend_frames.jsonl"), GAMECAM_DISABLE_AMP_WEIGHT_CACHE="1")
        commands = [("native", [sys.executable, "run.py", "--config", str(out / "run_config.yaml")])]
    else:
        scene, rgb = sequence, inputs / "rgb"
        depth, result = out / "depth_results", out / "upstream_output"
        data_root = out / "input"
        data_root.mkdir()
        (data_root / scene).symlink_to(rgb, target_is_directory=True)
        calibration = out / "known_intrinsics"
        calibration.mkdir()
        for frame in manifest["frames"]:
            np.save(calibration / (local(frame["path"]).stem+"_intrinsics.npy"), k)
        launcher = ROOT / "scripts/run_ba_track_reviewed_entrypoint.py"
        def entry(relative, *values):
            return [sys.executable, str(launcher), relative, *map(str, values)]
        da = ["--encoder", "vitl", "--load-from", ROOT / "data/sota_assets/BA_TRACK/weights/depth_anything_v2_vitl.pth", "--img-path", rgb]
        native_capacity = int(yaml.safe_load((upstream / "configs/davis_demo.yaml").read_text())["slam"]["BUFFER_SIZE"])
        ba_capacity = native_capacity
        while ba_capacity < len(manifest["frames"])+1:
            ba_capacity *= 2
        capacity_arguments = ["slam.BUFFER_SIZE="+str(ba_capacity)] if ba_capacity != native_capacity else []
        commands = [
            ("depth_anything_v2_first", entry("Depth-Anything/run_videos_v2.py", *da, "--outdir", depth / "depthAny_disp_first" / scene)),
            ("depth_anything_v2_second", entry("Depth-Anything/run_videos_v2.py", *da, "--outdir", depth / "depthAny_disp" / scene)),
            ("unidepth_v2", entry("UniDepth/scripts/demo_mega-sam.py", "--scene-name", scene, "--img-path", rgb, "--outdir", depth / "unidepthv2")),
            ("align_predicted_depths", entry("main/mono_depth/get_mono_depth.py", "--data_dir", data_root, "--depth_dir", depth, "--save_name", "unidepth_dav2")),
            ("sparse_tracker_and_BA", entry("main/run_batrack.py", "--config-path=../configs", "--config-name=davis_demo", "data.imagedir="+str(rgb), "data.savedir="+str(result),
                "+data.depthdir="+str(depth / "unidepth_dav2" / scene), "+data.depthdir_gt="+str(depth / "unidepth_dav2" / scene), "data.calib="+str(calibration), "data.name="+scene,
                "model.init_dir="+str(ROOT / "data/sota_assets/BA_TRACK/weights/md_tracker.pth"), "visualizer.save_dir="+str(out / "visualization"),
                "hydra.run.dir="+str(out / "hydra"), "hydra.job.chdir=false", "save_trajectory=true", "save_plot=true", "save_results=true", *capacity_arguments)),
            ("dense_global_refinement", entry("main/global_refine/run_global_refine.py", "--result_dir", result, "--grid_size", 12, "--scenes", scene, "--niter", 300))]
        if reused_prior:
            cached_view = depth / "unidepth_dav2" / scene
            cached_view.parent.mkdir(parents=True, exist_ok=False)
            cached_view.symlink_to(prior_root, target_is_directory=True)
            shutil.copy2(review_file, out / "reused_native_prior_review.json")
            write(out / "native_prior_reuse.json", {"source_review": str(review_file), "source_review_sha256": digest(review_file),
                "source_directory": reused_prior["original_directory"], "native_read_input_symlink": str(cached_view),
                "source_prior_values_recomputed_or_modified": False, "sensor_depth_or_external_GT": False,
                "original_completed_prior_stage_seconds": [r["wall_seconds"] for r in reused_prior["completed_native_prior_stages"]],
                "new_wall_excludes_cached_prior_GPU_stages": True})
            commands = commands[4:]
        cache = ROOT / "data/sota_assets/BA_TRACK"
        env.update(TORCH_HOME=str(cache / "torch_home"), HF_HOME=str(cache / "huggingface"),
            GAMECAM_BA_MOTION_TRACE_DIR=str(out / "motion_decomposition"), GAMECAM_BA_REFINE_TRACE_DIR=str(depth / "refine_trace"),
            GAMECAM_BA_RESULT_PICKLE_LOG=str(out / "native_result_serialization.jsonl"), GAMECAM_BA_SAVE_TERMINATED_CAMERA="1",
            GAMECAM_BA_VIDEO_VISIBILITY_CPU_COPY="1")
    contract = {"target": "phase5_shared", "method": args.method, "sequence": sequence, "scene": sequence, "expected_frames": len(manifest["frames"]), "commands": commands,
        "WSL_memory_budget_at_launch": memory_budget(),
        "BA_native_result_pickle_protocol": 5 if args.method == "BA_TRACK" else None,
        "BA_native_terminate_return_archived_before_large_pickle": args.method == "BA_TRACK",
        "BA_result_encoding_scope": "IO-only NumPy dictionary encoding; camera/track values and native computation unchanged" if args.method == "BA_TRACK" else None,
        "BA_native_video_visibility_copy": "One dtype-preserving Tensor-to-CPU-NumPy transfer per native renderer call; full original video renderer retained. Applies only to newly launched cases; timing includes this disclosed IO variant" if args.method == "BA_TRACK" else None,
        "dense_iterations": 300 if args.method == "BA_TRACK" else None, "dense_grid_size": 12 if args.method == "BA_TRACK" else None,
        "cwd": str(upstream), "inference_inputs": ["RGB", "camera_intrinsics"], "GT_in_model": False, "sensor_depth_in_model": False,
        "physical_clock_note": "Input keys identify samples whose external GT is already independently associated by published physical timestamps",
        "model_default_math_windows_points_iterations_preserved": True, "native_GUI_omitted": True,
        "BA_primary_pose_stage": "official sparse SLAM, same stage frozen before phase4 MVS evaluation; dense matrices retained diagnostically",
        **freeze_source(upstream, base, out)}
    if args.method == "BA_TRACK":
        contract.update(BA_native_default_buffer_capacity=native_capacity, BA_actual_buffer_capacity=ba_capacity,
            BA_native_video_visibility_IO_review_sha256=digest(video_io_review_file),
            BA_capacity_policy="Double only the frame-storage capacity until expected_full_RGB_count+1 fits the author's n+1>=N guard; no temporal drop, new RNG draw, window/point/threshold/loss/iteration change",
            BA_native_prior_stages_reused=reused_prior is not None,
            BA_native_prior_reuse_review_sha256=digest(review_file) if reused_prior else None,
            BA_timing_scope="Actually executed sparse+dense repair stages with already-computed byte-verified native learned priors; not a fresh cold full-prior pipeline" if reused_prior else "Cold native prior+sparse+dense stages actually executed until terminal status")
        resource_preparation = ROOT / "reports/PHASE5/D_loop_swap_runtime.json"
        if reused_prior:
            resource_record = json.loads(resource_preparation.read_text())
            if resource_record["status"] != "OWNED_D_LOOP_16_GIB_SWAP_ACTIVE" or memory_budget()["SwapTotal_bytes"] < 17*1024**3:
                raise RuntimeError("Require the explicitly prepared existing swap budget before this capacity repair")
            shutil.copy2(resource_preparation, out / "resource_preparation_before_capacity_repair.json")
            contract["BA_capacity_repair_resource_preparation_sha256"] = digest(resource_preparation)
    write(out / "execution_contract.json", contract)
    for source in (Path(__file__), ROOT / "scripts/phase5_runtime.py"):
        shutil.copy2(source, out / (source.name+".executed_source"))
    observed_sources = [ROOT / "baselines/runtime_hooks/sitecustomize.py"]
    if args.method == "PI3MOS":
        observed_sources.append(ROOT / "scripts/run_pi3mos_reviewed_entrypoint.py")
    if args.method == "BA_TRACK":
        observed_sources += [ROOT / "scripts/run_ba_track_reviewed_entrypoint.py", *[ROOT / "baselines/runtime_hooks" / f for f in ("ba_track_observer.py", "ba_track_motion_trace.py", "ba_track_refine_trace.py", "ba_track_result_pickle.py", "ba_track_video_io.py")]]
    for source in observed_sources:
        shutil.copy2(source, out / (source.name+".executed_source"))
    print(json.dumps({"stage": "PHASE5_NATIVE_RUNNING", "method": args.method, "sequence": sequence, "directory": str(out), "expected_frames": len(manifest["frames"])}), flush=True)
    started, stages = time.monotonic(), []
    with (out / "gpu_memory.csv").open("w", newline="") as gpu:
        writer = csv.writer(gpu)
        writer.writerow(["elapsed_seconds", "whole_gpu_used_mib", "whole_gpu_total_mib", "whole_gpu_utilization_percent"])
        for name, command in commands:
            stage = execute(name, command, upstream, env, out, writer, gpu, started)
            stages.append(stage); write(out / "execution.json", stages)
            print(json.dumps(stage), flush=True)
            if stage["exit_code"] or stage["reason"]:
                break
    completed = len(stages) == len(commands) and all(r["exit_code"] == 0 and r["reason"] is None for r in stages)
    status_name = {"PI3MOS": "PI3MOS_INFERENCE", "DROID_W": "DROID_INFERENCE", "BA_TRACK": "BA_TRACK_PIPELINE"}[args.method]
    record = {"status": status_name+("_COMPLETED" if completed else "_FAILED"), "directory": str(out), "method": args.method, "sequence": sequence,
        "expected_frames": len(manifest["frames"]), "target": "phase5_shared", "wall_seconds": time.monotonic()-started, "stages": stages,
        "whole_gpu_peak_used_mib_sampled": max((r["whole_gpu_peak_used_mib_sampled"] for r in stages), default=None),
        "per_process_cuda_allocator_stats": [json.loads(p.read_text()) for p in (out / "cuda_allocator_stats").glob("*.json")],
        "GT_in_model": False, "all_frames_requested": True, "primary_pose_selection_uses_GT_score": False, "no_automatic_model_retry": True}
    record["native_exit_is_not_output_acceptance"] = True
    if args.method == "BA_TRACK":
        record["native_prior_stages_reused"] = reused_prior is not None
        record["native_buffer_capacity"] = ba_capacity
    write(out / "status.json", record)
    write(ROOT / "reports/PHASE5" / (args.experiment+"_"+args.method+"_"+sequence+"_native.json"), record)
    print(json.dumps({k: record[k] for k in ("status", "directory", "wall_seconds")}), flush=True)
    return int(not completed)


if __name__ == "__main__":
    raise SystemExit(main())

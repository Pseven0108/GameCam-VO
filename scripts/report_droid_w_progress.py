from __future__ import annotations

import _bootstrap
import json
import re
from pathlib import Path

from gamecam_vo.common import PROJECT, write_json


def optional(name):
    path = PROJECT / "reports/SOTA" / name
    return json.loads(path.read_text()) if path.exists() else None


def main():
    root = PROJECT / "baselines/droid_w/repro_outputs"
    status = json.loads((root / "status.json").read_text())
    core, dependencies, native = (optional(name) for name in ("droid_core_runtime.json", "droid_dependencies.json", "droid_native_probe.json"))
    assets, demo, mvs = (optional(name) for name in ("droid_assets.json", "droid_official_demo.json", "droid_mvs.json"))
    evaluation = optional("droid_mvs_evaluation.json")
    if evaluation and (not mvs or evaluation["directory"].replace("\\", "/").split("GameCam-VO/")[-1] != mvs["directory"].replace("\\", "/").split("GameCam-VO/")[-1]):
        evaluation = None
    hub, extra = optional("droid_hub_compatibility.json"), optional("droid_loaded_prior_assets.json")
    attempts = []
    for directory in sorted((PROJECT / "results/E8_DROID_W").glob("*_official_bonn_balloon")):
        path = directory / "status.json"
        if path.exists():
            attempts.append(json.loads(path.read_text()))
        else:
            frames = directory / "frontend_frames.jsonl"
            rows = [json.loads(line) for line in frames.read_text().splitlines()] if frames.exists() else []
            attempts.append({"directory": str(directory), "status": "NO_FINAL_STATUS_YET", "processed_frontend_frames": len(rows),
                             "frontend_initialized_frames": sum(bool(r["frontend_initialized"]) for r in rows)})
    mvs_attempts = []
    for directory in sorted((PROJECT / "results/E8_DROID_W").glob("*_mvs_0000_rgb_only")):
        path = directory / "status.json"
        if path.exists():
            mvs_attempts.append(json.loads(path.read_text()))
        else:
            frames = directory / "frontend_frames.jsonl"
            rows = [json.loads(line) for line in frames.read_text().splitlines()] if frames.exists() else []
            mvs_attempts.append({"directory": str(directory), "status": "NO_FINAL_STATUS_YET", "processed_frontend_frames": len(rows),
                                 "frontend_initialized_frames": sum(bool(r["frontend_initialized"]) for r in rows)})
    builds = {}
    for path in sorted((PROJECT / "logs/SOTA_setup").glob("*_droid_extensions/execution.json")):
        for stage in json.loads(path.read_text()):
            script = Path(stage["script"])
            artifact_only = "pip wheel " in script.read_text()
            builds[stage["stage"]] = {"exit_code": stage["exit_code"], "artifact_only": artifact_only, "evidence": str(path)}
    runtime = {"core": core, "dependencies": dependencies, "hub_compatibility": hub, "native": native, "assets": assets,
               "loaded_extra_assets": extra, "official_demo_last_finished": demo, "official_demo_attempts": attempts,
               "mvs_last_finished": mvs, "mvs_attempts": mvs_attempts, "mvs_external_evaluation": evaluation, "native_builds": builds}
    write_json(PROJECT / "reports/SOTA/droid_runtime_progress.json", runtime)
    status.update(status="partial", highest_patch_risk="low_compatibility_paths_and_observability", patches_applied=True,
                  documented_command_status=("running_or_awaiting_final_record" if attempts and attempts[-1]["status"] == "NO_FINAL_STATUS_YET" else ("completed" if demo and demo["status"] == "OFFICIAL_DEMO_COMPLETED" else ("failed" if demo else "not_run"))),
                  stage_results={"readiness_audit": "completed", "core_cuda": core["status"] if core else "not_run",
                                 "dependencies": dependencies["status"] if dependencies else "not_run",
                                 "native_probe": native["status"] if native else "not_run",
                                 "assets": assets["status"] if assets else "not_acquired",
                                 "official_demo": attempts[-1]["status"] if attempts else "not_run", "mvs_100": mvs_attempts[-1]["status"] if mvs_attempts else "not_run"},
                  protocol_deviations=["Python3.10 / torch2.7.1+cu128 differs from author torch2.1/cu118", "sm_120 compilation, modern scalar-type API and explicit standard headers", "MMCV-lite Python utilities and MMEngine config fallback", "Disable xformers FA3 after actual sm_120 kernel failure; remaining attention dispatcher passed numeric comparison", "Optional frontend JSON telemetry adds recorded file I/O; no model parameter changes"],
                  runtime_evidence=str(PROJECT / "reports/SOTA/droid_runtime_progress.json"),
                  next_safe_action="Follow the first incomplete/failing stage with retained evidence; never manufacture model metrics")
    status["protocol_deviations"] += ["Run the identical tracking function in one process after an independently reproduced local CUDA IPC failure; mapping/gui remain disabled", "huggingface-hub0.25.2 restores timm0.9.10 API compatibility"]
    status["protocol_deviations"] += ["Optional AMP weight-conversion cache disabled only after bitwise-equal checks on actual Metric3D, FiT3D, fnet and cnet; precision/weights unchanged. The full MVS retry records this flag and a 7200-second execution budget."]
    status.update(
        bounded_inference_and_export_completed=bool(evaluation and demo and demo["status"] == "OFFICIAL_DEMO_COMPLETED"),
        observed_metrics={"MVS0000": evaluation["metrics"]} if evaluation else {},
        paper_result_match_status="NOT_EVALUATED: no expected score/tolerance for this hardware and MVS input",
        next_safe_action="DROID-W bounded inference/export is complete; continue the user's explicitly requested BA-Track phase" if evaluation else "Follow the first incomplete/failing stage with retained evidence; never manufacture model metrics",
    )
    status["stage_results"]["mvs_external_evaluation"] = evaluation["status"] if evaluation else "not_run"
    write_json(root / "status.json", status)
    lines = ["# E8 / DROID-W 执行记录", "", "当前是硬件兼容复现；模型结构、权重选择与官方超参数保持原样。软件环境不同于论文环境。", "",
             "| 阶段 | 实际状态 |", "|---|---|"]
    for label, item in (("CUDA 实际运算", core), ("依赖安装", dependencies), ("完整原生内核测试", native), ("完整权重 / Demo 数据", assets), ("官方 Bonn Demo", demo), ("MVS 100 帧最新尝试", mvs_attempts[-1] if mvs_attempts else None)):
        lines.append(f"| {label} | {item['status'] if item else 'NOT_RUN'} |")
    lines += ["", "原生扩展各次尝试：", ""]
    for name, entry in builds.items():
        lines.append(f"- {name}: exit={entry['exit_code']}; artifact_only={entry['artifact_only']}; `{entry['evidence']}`")
    lines += ["", "官方 Demo 各次尝试（未写最终状态不等于成功）：", ""]
    for attempt in attempts:
        lines.append(f"- `{attempt['directory']}`：{attempt['status']}；已完成前端调用 {attempt.get('processed_frontend_frames', 'UNKNOWN')} 帧；初始化后 {attempt.get('frontend_initialized_frames', 'UNKNOWN')} 帧。")
    if demo and demo["status"] == "OFFICIAL_DEMO_COMPLETED":
        lines += ["", f"官方Bonn完整Demo：{demo['pose_output_frames']}/{demo['expected_frames']}个数值有效的补全位姿；墙钟{demo['wall_seconds']:.3f}秒；整卡采样峰值{demo['whole_gpu_peak_used_mib']}MiB。进程的PyTorch allocated/reserved与WDDM整卡采样范围不同，不互相代替。",
                  "Native video.npz内部W2C与最终T_wc关键帧位姿已独立核对；完整轨迹与原生不确定性图保留。Bonn原生评价独立于MVS，不混入MVS指标。"]
    lines += ["", "MVS 100 帧各次尝试：", ""]
    for attempt in mvs_attempts:
        lines.append(f"- `{attempt['directory']}`：{attempt['status']}；已完成前端调用 {attempt.get('processed_frontend_frames', 'UNKNOWN')} /100 帧；超时={attempt.get('timed_out', 'UNKNOWN')}。")
    lines += ["", "首个 MVS 尝试在98帧时被代理设置的40分钟执行预算终止，不是已确认的跟踪丢失。保留其日志与显存采样，重跑使用2小时预算。关闭 AMP 权重转换缓存的单帧验证在四个实际模块上均逐元素相同；这保留FP32权重及FP16自动混合精度，不修改模型/图优化参数。该资源选项及全序列执行结果分别记录。"]
    if evaluation:
        lines += ["", "MVS0000外部评价已完成。100帧统计分母保持完整，单位native_game_unit，时间轴frame_index；输入仅共享RGB+K，Metric3D和FiT3D是学习型先验。", "",
                  "| 对齐 | 有效补全位姿 | ATE RMSE | RPE平移RMSE | RPE旋转RMSE(°) | 全局旋转误差RMSE(°) |", "|---|---:|---:|---:|---:|---:|"]
        for row in evaluation["metrics"]:
            def number(key):
                return f"{row[key]:.6g}" if row[key] is not None else "UNAVAILABLE"
            lines.append(f"| {row['alignment']} | {row['valid_pose_frames']}/100 | {number('ATE_RMSE')} | {number('RPE_translation_RMSE')} | {number('RPE_rotation_RMSE_degrees')} | {number('RotErr_RMSE_degrees')} |")
        sim3 = next(row for row in evaluation["metrics"] if row["alignment"] == "Sim3")
        lines += ["", f"外部Sim3尺度因子为{sim3['alignment_scale']:.8g}。游戏原生单位到米的换算未知，不能将该因子直接解释为学习深度预测失败或米制尺度恢复。",
                  f"本机进程墙钟{sim3['inference_seconds']:.3f}秒，100帧输入吞吐{sim3['input_fps']:.6g}帧/秒；它包含初始化、跟踪、最终BA、补全和原生出图，不是稳态跟踪FPS。原生Timer各嵌套作用域相加的Overall超过墙钟，不用于端到端速度。",
                  f"整卡约1Hz采样峰值{sim3['gpu_peak_used_mib_whole_device_sampled']:.0f}MiB；主进程PyTorch allocated峰值{sim3['gpu_peak_allocated_bytes_main_process']:,} bytes，reserved峰值{sim3['gpu_peak_reserved_bytes_main_process']:,} bytes。WDDM整卡物理占用与分配器范围不同，reserved不作为最低物理显存要求。"]
        lines += ["", f"结果目录：`{evaluation['directory']}`。保留estimated_trajectory.txt、metrics.csv、tracking_status.csv、coordinate_consistency.json、原生关键帧不确定性NPY、显示PNG和可视化。",
                  f"共{evaluation['uncertainty_map_count']}张原生关键帧不确定性图；不生成非关键帧假图，也不将其称为校准动态概率。坐标方向数值核对：{evaluation['coordinate_check']['status']}。",
                  f"本项目导出的不确定性来自最终BA之后的video.npz；上游名为plots_final的原生图实际上在最终全局BA前生成，不能据文件夹名称认定为最终状态。output_support图单独展示{sim3['valid_pose_frames']}个补全位姿、{sim3['initialized_frontend_frames']}个初始化后前端调用和{sim3['keyframe_count']}个关键帧的支持范围。",
                  "filled-pose coverage不是直接tracking success；上游未暴露ORB式逐帧跟踪丢失状态，因此tracking_loss_rate留空。初始化后帧数、关键帧数与补全位姿数分别记录。FPS为含初始化、跟踪、最终BA、补全及原生输出的进程总耗时口径。",
                  "SE3平移误差仅作未校准游戏尺度的诊断；Sim3是外部全局尺度对齐，不能声称恢复游戏米制尺度。单一短序列且无独立物体运动标注，不据此证明动态鲁棒性、长序列漂移或选择创新方向。"]
    if extra:
        lines += ["", f"FiT3D/timm 实际额外加载的基础 DINO 权重：{extra['extra_checkpoint_bytes']:,} bytes，固定修订和全文件 SHA256 已与 HF LFS 核对，详见 droid_loaded_prior_assets.json。"]
    lines += ["", "预编译 torch-scatter 的 GLIBC_2.32 要求、默认 xFormers FA3 的 CUDA invalid argument、标准头文件与 ATen API 编译失败均原样保留。它们是工程兼容证据，不能作为游戏场景算法失效证据。", "",
              "原始 GameCam-VO Windows Conda 环境保持独立；仅操作 DROID-W 的 WSL 环境。未执行训练。MVS 推理只允许 RGB+K，GT 仅用于外部评价。", "",
              "输出轨迹的覆盖率、前端初始化比例和关键帧数量必须分别报告。DROID-W 不提供 ORB 风格的逐帧 tracking-loss 状态，不据非关键帧比例编造失败率。", "",
              "未完成或超时尝试不生成精度指标；已完成评价只报告实测值，不等同论文分数复现或科研结论。", "",
              "详见 `reports/SOTA/droid_runtime_progress.json`、`baselines/droid_w/PATCHES.md` 和每次独立日志目录。", ""]
    text = "\n".join(lines)
    (PROJECT / "reports/SOTA/E8_DROID_W_report.md").write_text(text, encoding="utf-8")
    (root / "SUMMARY.md").write_text(text, encoding="utf-8")
    (root / "PATCHES.md").write_bytes((PROJECT / "baselines/droid_w/PATCHES.md").read_bytes())
    (root / "SCIENTIFIC_CHANGELOG.md").write_text("# Scientific changes\n\nModel architecture, selected checkpoints and inference/optimization hyperparameters remain official. MVS inputs use the declared shared 640x360 RGB view rectified with known per-frame K to fixed K; engine depth/poses are isolated from inference. Compatibility changes are explicit: newer torch/CUDA, source dtype/header/architecture build fixes, fixed local Torch Hub sources, matching Hugging Face client, disabled unsupported FA3 dispatch, identical tracking called in one process after a reproduced CUDA IPC failure, opt-in telemetry, and an optional disabled AMP weight-conversion cache after four-module bitwise-equality checks. Original FP32 weights and FP16 autocast remain; the bounded module check does not prove full-SLAM bitwise equivalence. Scheduling/backend/cache differences affect runtime and may affect numerical roundoff. No training or innovation model is implemented.\n", encoding="utf-8")
    (root / "COMPARABILITY_REPORT.md").write_text("# Comparability\n\nThis is a compatibility reproduction with directly executed inference, not an author-stack or paper-score match. Author torch2.1/cu118 becomes torch2.7.1/cu128 on RTX5060/sm120, Ubuntu20 instead of22; source, backend, scheduling and cache deviations are recorded. No expected paper metric/tolerance applies to the new MVS sequence, so score matching remains not evaluated.\n\nMVS uses ENGINE_GROUND_TRUTH in native_game_unit and frame_index. Bonn native evaluation and Omni ESTIMATED_REFERENCE stay separate. All100 MVS frames remain the denominator. DROID's filled trajectories, frontend initialization and keyframe support are distinct; no unexposed tracking-loss rate is fabricated. Sim3 scale is external evaluation alignment, not recovered game metric scale.\n\nGPU whole-device sampling includes the desktop and is a sampled lower bound; allocated/reserved per-PID values have different scopes, especially under WDDM. Timing includes final BA/fill/output, and this single-process cache variant cannot be ranked by FPS against differently scoped or offline methods.\n\nOne short MVS sequence with no independent object-motion truth does not establish dynamic robustness, long-sequence drift or innovation choice. Historical960px ORB results are retained; a separate shared640px input run is prepared for E11.\n", encoding="utf-8")
    (root / "LOG.md").write_text(text, encoding="utf-8")
    (root / "COMMANDS.md").write_text("# Commands and evidence\n\nExecuted setup commands and frozen environment are recorded under reports/SOTA/conda_setup.json, droid_core_runtime.json, droid_dependencies.json, droid_hub_compatibility.json and droid_native_probe.json; each points to exact commands, scripts and immutable attempt logs. All failed attempts remain intact.\n\nThe README-grounded target is `python run.py --config configs/Dynamic/Bonn/bonn_balloon.yaml`. The wrapper resolves this config and changes paths only; single-process mode is an explicit scheduling compatibility deviation.\n\nActual wrapper command:\n\n```powershell\nwsl -d Ubuntu --exec /home/lsuser/.local/share/gamecam-vo/envs/droid-w/bin/python /mnt/d/aaa/GameCam-VO/scripts/run_droid_w_official_demo.py\n```\n\nEvery attempt has execution_contract.json with executable, cwd, environment overrides, model command, full resolved run_config.yaml, source hook hash, logs and GPU samples. Completed native checks do not imply an inference result. MVS inference remains gated on a completed official Demo.\n", encoding="utf-8")
    source_dir = Path(json.loads((PROJECT / "reports/SOTA/latest_E7.json").read_text())["directory"])
    original = (source_dir / "DROID_W/README.md").read_bytes()
    pieces, start = [], 0
    for match in re.finditer(rb"(?m)^## [^\r\n]+", original):
        pieces.append(original[start:match.start()])
        pieces.append(b'<!-- GAMECAM_REPRO_BEGIN -->\n<div style="color:#8a5500">GameCam reproduction evidence: see status.json and SUMMARY.md. Setup checks are distinct from model inference and paper-result matching.</div>\n<!-- GAMECAM_REPRO_END -->\n')
        start = match.start()
    pieces.append(original[start:])
    annotated = b"".join(pieces)
    stripped = re.sub(rb"<!-- GAMECAM_REPRO_BEGIN -->\n.*?<!-- GAMECAM_REPRO_END -->\n", b"", annotated, flags=re.S)
    assert stripped == original
    (root / "ANNOTATED_README.md").write_bytes(annotated)
    write_json(root / "readme_integrity.json", {"original_source": str(source_dir / "DROID_W/README.md"), "strip_round_trip": "PASS", "annotations": len(pieces)//2})
    print(json.dumps(status["stage_results"]))


if __name__ == "__main__":
    main()

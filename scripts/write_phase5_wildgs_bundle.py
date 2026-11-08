"""Bind the WildGS README evidence bundle to completed inspected E13 artifacts."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from gamecam_vo.common import PROJECT, sha256, write_json


def main():
    out = PROJECT / "results/E13_WILDGS/20261101T070506Z_crowd_thread-portability"
    native = json.loads((out / "status.json").read_text(encoding="utf-8"))
    review = json.loads((out / "map_uncertainty_review.json").read_text(encoding="utf-8"))
    evaluated = json.loads((out / "evaluation_summary.json").read_text(encoding="utf-8"))
    qa = json.loads((out / "figure_review.json").read_text(encoding="utf-8"))
    if not review["native_computation_outputs_complete"] or qa["status"] != "VISUALLY_REVIEWED_PASS":
        raise ValueError("Actual output and curated-figure acceptance required")
    folder = PROJECT / "baselines/wildgs_slam/repro_outputs"
    original = PROJECT / "baselines/wildgs_slam/upstream/README.md"
    annotated = folder / "ANNOTATED_README.md"
    stripped = re.sub(rb"<!-- GAMECAM_REPRO_BEGIN -->\r?\n.*?<!-- GAMECAM_REPRO_END -->\r?\n", b"", annotated.read_bytes(), flags=re.S)
    if stripped != original.read_bytes():
        raise ValueError("Annotated README changed original source bytes")
    metrics = evaluated["metrics"]
    rows = ["| Alignment | ATE (m) | Adjacent RPE translation (m) | RPE rotation (°) | Filled poses |", "|---|---:|---:|---:|---:|"]
    for row in metrics:
        rows.append(f"| {row['alignment']} | {row['ATE_RMSE']:.9f} | {row['RPE_translation_RMSE']:.9f} | {row['RPE_rotation_RMSE_degrees']:.9f} | {row['valid_pose_frames']}/1268 |")
    prefix = "# WildGS-SLAM / E13\n\n实际完成400×240官方Crowd Demo配置的线程兼容变体：1268帧全轨迹、142关键帧、90605个有限高斯参数及142张最终渲染/不确定性图均已核验。\n\n原生双进程因实际CUDA IPC错误失败。完整输出试跑在模型计算和导出完成后，因兼容启动命名空间遗漏active_children而退出1；该失败状态原样保留，独立输出验收不伪称进程成功。后续启动器已补齐原生清理API，并通过实际线程/Pipe及原SLAM全部启动API检查，尚须E14真实执行验证。\n\n"
    summary = prefix+"\n".join(rows)+f"\n\n原生冷启动全流程{native['wall_seconds']:.3f}s；1秒目标采样的全卡显存峰值{native['whole_gpu_peak_used_mib_sampled']:.0f}MiB，包含桌面/其他进程，不是最低需求或保证瞬时峰值。GT为外部OptiTrack/MOCAP_GROUND_TRUTH，参考已在模型评分前按发布物理时钟冻结；全部1268帧及1267相邻对保留。SE3平移依赖未验证的原生尺度，作为尺度诊断；Sim3明确后处理尺度对齐，不声称恢复物理尺度。\n\n完整目录：`{out}`。主文件：status.json、map_uncertainty_review.json、evaluation_summary.json、coordinate_consistency.json、figure_review.json、gpu_memory.csv、inference_log.txt。正式共同RGB/K比较单列E14；本Demo采用原生读入/预处理，不能混入E14共同输入表。\n"
    commands = "# Commands and prerequisites\n\n官方最小目标：\n\n```text\npython run.py ./configs/Dynamic/Wild_SLAM_Mocap/crowd_demo.yaml\n```\n\n已执行：recursive clone与嵌套子模块审计，独立Conda前缀由已有droid-w克隆，WildGS自身后端独立编译，真实CUDA值检查与进程IPC探针。未执行全库下载脚本；只顺序获取所需MoCap包。复用完整已验证官方权重并重新哈希。\n\n实际完整输出试跑（源路径与配置在execution_contract.json逐字绑定）：\n\n```text\nwsl.exe -d Ubuntu --exec /home/lsuser/.local/share/gamecam-vo/envs/wildgs_slam/bin/python /mnt/d/aaa/GameCam-VO/scripts/run_phase5_wildgs.py --target official-demo --actor-mode thread-portability --source-cache /home/lsuser/.local/share/gamecam-vo/source_cache/20261101T070311Z_wildgs\n```\n\n独立CPU输出检查明确允许的仅是已发生且完整输出的末尾清理异常：inspect_phase5_wildgs_outputs.py --allow-terminal-cleanup-failure；evaluate_phase5_camera.py --allow-reviewed-terminal-cleanup-failure。原始status.json从未改为成功。所有命令/默认配置副本与失败试跑均保留。\n"
    log = "# Direct evidence\n\n"+"\n".join(f"- `{p.relative_to(PROJECT)}`" for p in (out / "inference_log.txt", out / "status.json", out / "map_uncertainty_review.json", out / "evaluation_summary.json", out / "figure_review.json", out / "gpu_memory_sampling_summary.json", PROJECT / "reports/PHASE5/wildgs_native_probe.json", PROJECT / "reports/PHASE5/wildgs_actor_API_probe.json"))+"\n\n前序失败/中断：063253原生IPC失败；063542线程试跑在658/1050初始化迭代受控中断，外部只读剖析显示DrvFS的linecache源码访问开销；065857源码缓存遗漏嵌套datasets配置失败。不是OOM、动态跟踪丢失或游戏域失效的证据。修复后递归MMEngine配置预检通过，原anomaly/NaN检查保留。\n"
    changes = "# Scientific scope\n\n未改变模型架构、权重内容、损失、优化器、阈值、窗口、350KF缓冲区或高斯优化迭代数。官方Demo fast_mode=True、初始化1050次、映射450次、最终3000次保持原值；E14非Demo保留fast_mode=False与20000次最终优化及非关键帧位姿优化。原生不确定性MLP/高斯图的在线拟合属于原方法，不是训练自研网络。\n\n按用户和README允许把Demo输出缩为400×240并省略GUI。线程启动保留原tracking/mapping/Pipe同步方法，但进程调度和全局随机数消费可能不同，不能宣称全模型逐位一致或原生多进程成功。源码ext4缓存逐文件原字节核对，只为避免已剖析确认的DrvFS调试栈文件访问开销；未关闭异常检测。\n\n外部GT、坐标方向检查和可视化为另行派生的评价，不反馈给模型。原生uint8 RGB差值显示存在回绕，仅保留原图，不将该显示值当作定量RGB-L1；原图Metric Depth为前端预测深度，不是传感器真值。\n"
    comparison = "# Comparability\n\n本机torch2.7.1+cu128/NVCC12.8/sm120不同于作者torch2.1/cu118栈。顶层Apache-2.0不覆盖全部Gaussian/renderer/prior许可。新环境独立，原Windows环境、三个WSL环境、备份和E7-E12原始结果保留。\n\nDemo没有独立逐像素动态、物体运动或骨骼标签：不计算PR/IoU/AUROC等像素精度。曲线显示人体区域较高不确定性仅为定性观察；不确定性不等于概率。没有论文分数一致性、通用动态鲁棒性、游戏域失效或自研创新的证据结论。正式四方法比较使用E14共同冻结RGB/K，和Demo分开。\n\n视觉验收涵盖7张导出诊断PNG及3张按关键帧索引固定选择的最终原生图（共10 PNG及7对应SVG）；142张原生图全部保留，未声称逐张视觉审阅。\n"
    patches = "# Patches\n\n官方be187eabbe6862cef3cfe87031ee2e64ad8c4cec基础上的sm120编译目标与ATen scalar_type API、固定本地FiT3D/Metric3D hub路径属于平台/路径适配；不兼容sm120的FA3选择在已有实际错误与数值探针后显式禁用。WildGS不同于DROID-W的后端重新编译；相同vendor源码的复用范围见wildgs_native_source_comparison.json，不泛称所有头文件均已逐文件比较。\n\nOwned启动器单独标识线程执行变体、GUI省略、真实返回IO观察器及ext4源码缓存。active_children遗漏发生在070506试跑的末尾清理，失败记录保留；修复只把CPU子进程清理API交还原torch.multiprocessing。新观察器只复制已有返回值，不增加模型前向、随机采样或修改返回张量。\n\n原生全部源码、配置和每次实际执行的启动器副本/缓存SHA见各试验目录。早期完整CRLF差异补丁原文件保留；后续补丁使用与Windows一致的Git clean过滤，精确执行字节另外索引。\n"
    for name, body in (("SUMMARY.md", summary), ("COMMANDS.md", commands), ("LOG.md", log), ("SCIENTIFIC_CHANGELOG.md", changes), ("COMPARABILITY_REPORT.md", comparison), ("PATCHES.md", patches)):
        (folder / name).write_text(body, encoding="utf-8")
    state = {"schema_version": "1.0", "status": "partial", "target_repo": "https://github.com/GradientSpaces/WildGS-SLAM", "upstream_commit": "be187eabbe6862cef3cfe87031ee2e64ad8c4cec",
        "selected_goal": "inference", "documented_command_status": "thread_variant_outputs_accepted_native_process_and_terminal_cleanup_failures_preserved",
        "native_exit_code": native["exit_code"], "native_computation_outputs_complete": True, "result_match": False,
        "observed_metrics": metrics, "evidence_directory": str(out), "patches_applied": True, "patch_branch": "repro/2026-11-01-sm120",
        "human_decisions_required": [], "updated_at_utc": datetime.now(timezone.utc).isoformat(), "whole_phase5_complete": False}
    write_json(folder / "status.json", state)
    required = ("SUMMARY.md", "COMMANDS.md", "LOG.md", "SCIENTIFIC_CHANGELOG.md", "COMPARABILITY_REPORT.md", "status.json", "ANNOTATED_README.md", "PATCHES.md")
    integrity = {"status": "WILDGS_EIGHT_FILE_BUNDLE_AND_README_ROUNDTRIP_PASS", "original_source": str(original), "original_sha256": sha256(original), "annotated_sha256": sha256(annotated),
        "strip_round_trip": "PASS", "annotations": annotated.read_bytes().count(b"<!-- GAMECAM_REPRO_BEGIN -->"),
        "files": [{"file": name, "sha256": sha256(folder / name), "bytes": (folder / name).stat().st_size} for name in required]}
    write_json(folder / "readme_integrity.json", integrity)
    write_json(PROJECT / "reports/PHASE5/wildgs_bundle_integrity.json", integrity)
    for path in (PROJECT / "reports/SOTA/E13_WILDGS_REPRODUCTION.md", PROJECT / "reports/PHASE5/phase5_wildgs_reproduction.md"):
        path.write_text(summary+"\n"+comparison+"\n"+log+"\n"+patches, encoding="utf-8")
    print(json.dumps({"status": integrity["status"], "reproduction_outcome": "partial", "actual_outputs_accepted": True, "paper_score_match": False}))


if __name__ == "__main__":
    main()

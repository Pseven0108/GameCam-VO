"""Report verified weights and actual native Pi3MOS execution; never run models."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

from gamecam_vo.common import PROJECT, write_json


def main():
    reports = PROJECT / "reports/SOTA"

    def read(name):
        path = reports / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    manual = read("pi3mos_manual_checkpoint.json")
    assets, data = read("pi3mos_assets.json"), read("pi3mos_official_demo_data.json")
    demo, mvs, evaluation = [read(name) for name in ("pi3mos_official_demo.json", "pi3mos_mvs.json", "pi3mos_mvs_evaluation.json")]
    demo_state = demo["status"] if demo else ("RUNNING" if read("pi3mos_inference_launch.json") else "NOT_RUN")
    demo_dirs = sorted((PROJECT / "results/E10_PI3MOS").glob("*_official_wild_umbrella"))
    current_demo = demo_dirs[-1] if demo_dirs else None
    forward_observed = bool(current_demo and ((current_demo / "raw_initialization/manifest.jsonl").exists() or (current_demo / "native_prior_outputs/manifest.jsonl").exists()))
    mvs_state = evaluation["status"] if evaluation else (mvs["status"] if mvs else ("RUNNING_NATIVE_INFERENCE" if read("pi3mos_mvs_launch.json") else "NOT_RUN_OFFICIAL_DEMO_GATE"))
    demo_review, mvs_review = [read(name) for name in ("pi3mos_official_demo_output_review.json", "pi3mos_mvs_output_review.json")]
    demo_delivery, mvs_delivery = [read(name) for name in ("pi3mos_official_demo_delivery.json", "pi3mos_mvs_delivery.json")]
    complete = bool(demo_delivery and mvs_delivery and evaluation)
    next_action = ("Bounded baseline execution and delivery complete; choose independent dynamic camera/object truth before selecting M1/M2/M3. No automatic model replay."
                   if complete else "Finish the active native run and its CPU export/evaluation/figure QA; never replay automatically")
    upstream = PROJECT / "baselines/pi3mos/upstream"
    commit = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    root = PROJECT / "baselines/pi3mos/repro_outputs"
    state = json.loads((root / "status.json").read_text(encoding="utf-8"))
    state.update(status="partial", evidence_updated_at_utc=datetime.now(timezone.utc).isoformat(), documented_command_status="official_Demo_"+demo_state,
        full_core_checkpoint_verified=True, model_launch_attempted=bool(demo or read("pi3mos_inference_launch.json")),
        model_inference_executed=forward_observed,
        compatibility_commit=commit, result_match=False, observed_metrics=[] if not evaluation else evaluation["metrics"],
        blocked_upstream_release=False, human_decisions_required=[],
        stage_results={"native_cuda_setup": "passed", "weights": assets["status"],
                       "official_demo_data": data["status"] if data else "NOT_ACQUIRED", "official_demo": demo_state, "MVS100": mvs_state},
        full_core_weight_bytes=manual["bytes"], full_core_weight_sha256=manual["sha256"],
        highest_patch_risk="low_dtype_API_and_optional_GUI_IO_observation",
        bounded_execution_and_delivery_complete=complete,
        outcome_semantics="partial denotes adapted headless/software-stack reproduction and no paper-score match, not a claim that completed native runs are still pending",
        next_safe_action=next_action,
        readme_fidelity="Same author umbrella RGB tracking sequence, checkpoints and native default model settings. Optional GUI omitted; omitted gui_process initialized to None in an owned subclass. IO observations explicit; full-model bitwise/paper equivalence not claimed.")
    state["protocol_deviations"] = list(dict.fromkeys(state.get("protocol_deviations", []) + [
        "Optional GUI omitted; missing gui_process initialized to None in owned subclass; GUI random-display RNG consumption differs",
        "Native output observations copied to CPU without changing returned objects; observation IO included in native wall time"]))
    state["runtime_evidence"] = {"official_demo": demo, "MVS100": mvs,
        "official_demo_review": demo_review, "MVS100_review": mvs_review,
        "official_demo_delivery": str(reports / "pi3mos_official_demo_delivery.json") if demo_delivery else None,
        "MVS100_delivery": str(reports / "pi3mos_mvs_delivery.json") if mvs_delivery else None}
    write_json(root / "status.json", state)
    write_json(PROJECT / "results/E10_PI3MOS/STATUS.json", {"weights": "FULL_CORE_CHECKPOINT_VERIFIED", "official_demo": demo_state,
        "MVS100": mvs_state, "model_inference_executed": forward_observed, "full_core_checkpoint_sha256": manual["sha256"],
        "not_a_paper_score_match": True, "native_history_preserved": True, "bounded_delivery_complete": complete})
    frames = data["expected_frames"] if data else "UNKNOWN"
    observations = []
    for label, native, checked, delivered in (("官方umbrella Demo", demo, demo_review, demo_delivery), ("共享MVS100", mvs, mvs_review, mvs_delivery)):
        if not native:
            continue
        observations.append(f"{label}：原生退出码{native['exit_code']}，墙钟{native['wall_seconds']:.6f}秒，整卡采样峰值{native['whole_gpu_peak_used_mib_sampled']} MiB；CUDA OOM={native['CUDA_OOM_observed']}。目录：`{native['directory']}`。")
        if checked:
            coord = checked["coordinate_check"]
            observations.append(f"有限补全位姿{checked['finite_filled_pose_frames']}/{checked['expected_frames']}；前端调用{checked['frontend_calls']}，调用前/后已初始化计数{checked['initialized_before_calls']}/{checked['initialized_after_calls']}，最终关键帧{checked['native_keyframes']}。保存{checked['native_prior_maps_exported']}帧原生先验，深度有限且为正、动态sigmoid在[0,1]。{coord['keyframes_compared']}个关键帧的内部T_cw取逆与完整T_wc一致：最大平移差{coord['max_translation_difference_map_unit']:.6g} map unit，最大旋转差{coord['max_rotation_difference_degrees']:.6g}°。图表核查={checked['figures_visually_reviewed']}；最终证据清单={'已生成' if delivered else '待完成'}。")
    metric_text = "共享MVS指标尚未生成，不将进程启动或输出文件存在当作评价成功。"
    if evaluation:
        metric_rows = evaluation["metrics"]
        metric_text = "共享MVS外部引擎GT评价（完整100帧、99个原始相邻对；平移单位native_game_unit，米制换算UNKNOWN）：\n\n| 对齐 | ATE RMSE | RPE平移 RMSE | RPE旋转 RMSE/° | 全局旋转 RMSE/° | 有效位姿 | 有效相邻对 |\n|---|---:|---:|---:|---:|---:|---:|\n"
        for row in metric_rows:
            metric_text += f"| {row['alignment']} | {row['ATE_RMSE']:.12g} | {row['RPE_translation_RMSE']:.12g} | {row['RPE_rotation_RMSE_degrees']:.12g} | {row['RotErr_RMSE_degrees']:.12g} | {row['valid_pose_frames']}/100 | {row['valid_rpe_pairs']}/99 |\n"
        sim3 = next(row for row in metric_rows if row["alignment"] == "Sim3")
        metric_text += f"\nSim3尺度{sim3['alignment_scale']:.12g}由外部GT评价拟合，不是模型恢复米制的证据。原生完整输入吞吐{sim3['input_fps']:.6g}帧/秒，含冷启动、权重加载、初始化、跟踪、末尾12次BA、位姿补全及输出观察IO，外部导出/评价不计入；省略可选GUI，不能与论文实时FPS或其他类别算法直接排序。有限补全覆盖率不等于同定义跟踪成功率，tracking_loss_rate仍UNKNOWN。\n"
    observed_text = "\n\n".join(observations)+"\n\n"+metric_text
    summary = f"""# E10 / Pi3MOS-SLAM 当前真实运行

核心权重已由用户从作者链接手动下载并验证，不再受权重缺失阻塞。4,100,235,800 bytes，1276个张量，本地SHA256 `{manual['sha256']}`；与保留的全部1,350,515,846 bytes原始前缀/完整区段逐段SHA一致，safetensors原生CPU结构检查通过。发布者完整文件摘要UNKNOWN，不能把局部比对当成独立发布者全文件签名。DPVO14,167,743 bytes原文件SHA也已重新核对。

官方Demo：{demo_state}；MVS100：{mvs_state}。使用Wild-SLAM Mocap scene1/umbrella的{frames}张跟踪RGB；原包还含nvs/rgb，未混入。单包839,158,138 bytes与官方固定revision158c7407c513fcf7140d14c2ce6271bc5e0450ec的LFS SHA844607c15550090d1773ebb13d0c774257bb9937d3f8e900348e34ab84e857fe匹配，原ZIP及GT文件保留，GT不传给模型。

{observed_text}

原始Pi_SAM.run、DPVO初始化/跟踪/终止和模型默认计算不变。使用config/default.yaml：128点/帧、默认窗口/阈值、PI3_FRAME_RANGE5、原始12帧初始化等均保留。原生图像读取执行标定畸变校正和底部/右侧16整除裁剪，Pi3内部预处理不改。独立WSL Pi3MOS环境继续使用，原Windows及另两个模型环境不作为安装目标。

无GUI流程的原始shutdown_gui缺少gui_process属性，已用原方法的隔离执行复现AttributeError；owned子类只补gui_process=None，原清理方法保持不变。省略可选--viz，不启动交互窗口；GUI随机显示采样的RNG消耗也省略，不能声称与GUI运行逐位等价。观察器仅调用原方法一次，复制原生输出到CPU后返回原对象；包含输出IO的时间不能等同论文实时FPS。

458帧官方Demo完整运行和数值/坐标检查通过后进入共享MVS100。记录原生初始化输出、当前输入的相机局部点、feature-grid深度先验、动态sigmoid及confidence；不同分辨率/尺度分开标注，不伪造尚未提供时刻的图，不称为校准概率或已验证分割精度。相机以原terminate()对内部T_cw取逆的T_wc为准，时间为输入frame_index。MVS引擎GT/真实深度不进入模型，完整100/99分母不改。

过去TLS超时、Google配额HTML和0新增有效字节的分段尝试全部保留；小范围可读没有被当成完整下载成功。数据初次选择检查发现两套RGB而停止，修正为作者明确的umbrella/rgb后复用已校验ZIP，逐图与原包比对，历史失败保留。

源码基线5e709d27324a935e364e01efc56f3128ac00bf24，兼容提交{commit}；上游仅42处dtype分发API修改，数学/模型/默认超参数不改。原生CUDA数值探针已通过，但不是最低显存承诺。顶层LICENSE缺失、MIT badge与第三方Naver/GUI许可分开记录，核心权重许可UNKNOWN。本阶段不进行训练、不替换其他π³模型、不声称论文分数复现。

证据：pi3mos_manual_checkpoint.json、pi3mos_assets.json、pi3mos_official_demo_data.json、pi3mos_headless_cleanup_probe.json、pi3mos_executed_source_verification.json、pi3mos_official_demo_delivery.json、pi3mos_mvs_delivery.json（仅在对应步骤实际完成后存在）；每次实际运行的日志、源文件快照与执行契约位于results/E10_PI3MOS的新目录。repro_outputs的partial记录软件栈/headless偏差和没有论文分数匹配，bounded_execution_and_delivery_complete={complete}单独表明本次限定实验交付状态。
"""
    for path in (reports / "E10_PI3MOS_report.md", root / "LOG.md"):
        path.write_text(summary, encoding="utf-8")
    (root / "SUMMARY.md").write_text(f"# Pi3MOS 限定复现结果\n\n完整权重已核验：{manual['bytes']} bytes、1276张量，SHA256 {manual['sha256']}。全部保留1.35GB原始区段一致、CPU结构检查通过，独立发布者全文件摘要仍UNKNOWN。\n\n官方umbrella{frames}帧：{demo_state}；共享MVS100：{mvs_state}。限定交付完成={complete}。partial指headless/软件栈偏差及无论文分数匹配。\n\n{observed_text}\n\npatches_applied=true；分支repro/2026-10-31-sm120，兼容提交{commit}。默认模型设置保留，dtype API及可选GUI/IO偏差明确。不宣称已验证动态分割精度；完整证据见LOG.md。\n", encoding="utf-8")
    (root / "COMMANDS.md").write_text("# Actual commands\n\nOriginal README target: python demo.py --imagedir datasets/Wild_SLAM_Mocap/scene1/umbrella/rgb --calib calib/wildgs/umbrella.txt --viz. This is provenance; the adapted headless command runs the same native Pi_SAM.run with IO observation.\n\nExecuted user-file verification: Windows gamecam-vo/python.exe -X utf8 scripts/verify_pi3mos_manual_checkpoint.py. Selected Demo ZIP was fetched at a pinned revision and checked against official LFS.\n\nActual native launch:\n```sh\n/home/lsuser/.local/share/gamecam-vo/envs/pi3mos/bin/python /mnt/d/aaa/GameCam-VO/scripts/run_pi3mos_pipeline.py --target official-demo\n```\nThe exact child command, source patch and environment overrides are frozen in that run's execution_contract.json; source snapshots and raw stdout remain alongside it. Do not rerun a model to regenerate reports. MVS is gated on a successful official Demo and saved numerical review.\n", encoding="utf-8")
    if read("pi3mos_mvs_launch.json"):
        with (root / "COMMANDS.md").open("a", encoding="utf-8") as commands:
            commands.write("\nExecuted native MVS launch after accepted Demo:\n```sh\n/home/lsuser/.local/share/gamecam-vo/envs/pi3mos/bin/python /mnt/d/aaa/GameCam-VO/scripts/run_pi3mos_pipeline.py --target mvs\n```\n")
    for label, native, checked, delivered in (("Demo", demo, demo_review, demo_delivery), ("MVS", mvs, mvs_review, mvs_delivery)):
        if checked:
            directory = checked["directory"].replace("\\", "/")
            with (root / "COMMANDS.md").open("a", encoding="utf-8") as commands:
                commands.write(f'\nExecuted Windows CPU export ({label}):\n```powershell\n& "C:/Users/Administrator/.conda/envs/gamecam-vo/python.exe" -X utf8 scripts/export_pi3mos_results.py "{directory}"\n```\n')
                if label == "MVS" and evaluation:
                    commands.write('\nExecuted independent engine-GT evaluation:\n```powershell\n& "C:/Users/Administrator/.conda/envs/gamecam-vo/python.exe" -X utf8 scripts/evaluate_pi3mos_mvs.py\n```\n')
                if delivered:
                    commands.write(f'\nExecuted evidence finalization after explicit figure QA:\n```powershell\n& "C:/Users/Administrator/.conda/envs/gamecam-vo/python.exe" -X utf8 scripts/finalize_pi3mos_evidence.py "{directory}"\n```\n')
    (root / "SCIENTIFIC_CHANGELOG.md").write_text("# Scientific changes\n\nNo architecture, checkpoint, precision, model windows, patch counts, losses or thresholds are changed. Optional GUI omitted, omitted GUI handle initialized to None in an owned subclass; original methods remain. Output copies and IO overhead explicit. GUI random-display RNG consumption differs; no whole-model bitwise equivalence claim. GT remains external.\n", encoding="utf-8")
    (root / "COMPARABILITY_REPORT.md").write_text("# Comparability\n\nNative CUDA proof and complete weights are prerequisites, not a paper result. Full native official umbrella target and its saved outputs must pass before MVS. The single short game geometry sequence does not establish dynamic-object accuracy, long drift, FOV handling or an innovation direction. Native probabilities and confidence weights are not calibrated labels. All original failures and actual memory/timing scopes are retained.\n", encoding="utf-8")
    (root / "PATCHES.md").write_bytes((PROJECT / "baselines/pi3mos/PATCHES.md").read_bytes())
    source = (upstream / "README.md").read_bytes()
    annotation = b'<!-- GAMECAM_REPRO_BEGIN -->\n<div style="color:#8a5500">Core weights and selected umbrella data verified. Native Demo execution and numerical acceptance: SUMMARY.md. Optional GUI/IO deviations are explicit.</div>\n<!-- GAMECAM_REPRO_END -->\n'
    annotated = re.sub(rb"(?m)(^## )", lambda match: annotation+match.group(1), source)
    assert re.sub(rb"<!-- GAMECAM_REPRO_BEGIN -->\n.*?<!-- GAMECAM_REPRO_END -->\n", b"", annotated, flags=re.S) == source
    (root / "ANNOTATED_README.md").write_bytes(annotated)
    print(json.dumps({"weights": "VERIFIED", "official_demo": demo_state, "MVS100": mvs_state}))


if __name__ == "__main__":
    main()

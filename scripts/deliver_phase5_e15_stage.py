"""Deliver actual reviewed MOVi evidence; never generate results from a plan."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import local, read
from deliver_phase5_e13_e14_stage import reviewed_figures, scalar


REPORTS = PROJECT / "reports/PHASE5"


def identified(path, expected=None):
    path = local(path)
    if not path.is_relative_to(PROJECT) or not path.is_file():
        raise ValueError("Expected an existing owned evidence file: "+str(path))
    digest = sha256(path)
    if expected is not None and digest != expected:
        raise ValueError("Evidence identity changed: "+str(path))
    return {"file": str(path), "sha256": digest}


def verify_failure(folder, plan_file, number):
    path = folder / "failure_review.json" if folder else plan_file.parent / "failure_reviews" / f"{number:02d}.json"
    review = read(path)
    if review["status"] != "REVIEWED_FAILURE_OR_UNAVAILABLE_CAMERA_METRICS" or not review.get("reason") or not review.get("classification") or not review.get("evidence"):
        raise ValueError("A failed/unaccepted camera requires an actual classified failure review")
    for row in review["evidence"]:
        identified(row["file"], row["sha256"])
    return {**identified(path), "review": review}


def reviewed_all_derived_figures(folder):
    qa = reviewed_figures(folder)
    ledger = read(folder / "figure_review.json")
    reviewed = {r["file"].replace("\\", "/") for r in ledger["files"]}
    actual = {p.name for p in folder.iterdir() if p.suffix in (".png", ".svg")}
    if not actual or not actual.issubset(reviewed):
        raise ValueError("Every curated derived PNG/SVG requires actual visual review")
    return qa


def reviewed_motion(folder, method):
    pointer_file = folder / ("M2_evaluation_pointer.json" if method == "BA_TRACK" else "M1_evaluation_pointer.json")
    pointer = read(pointer_file)
    identity = identified(pointer["report"], pointer["sha256"])
    report = read(local(pointer["report"]))
    if report["GT_provenance"] != "SYNTHETIC_GROUND_TRUTH" or report["sensor_GT_in_model"]:
        raise ValueError("Motion comparison provenance/model-input scope is invalid")
    if report["status"] == "UNAVAILABLE":
        if not report.get("unavailable_reason"):
            raise ValueError("Unavailable motion output must explain its missing native support")
        return {**identity, "report": report, "visual_QA": None}
    if report["status"] not in ("INDEPENDENT_NATIVE_POINT_MOTION_EVALUATION_COMPLETED", "INDEPENDENT_M1_SCORED_ON_OBSERVED_NATIVE_SUPPORT") or not report["figures_visually_reviewed"]:
        raise ValueError("Actual motion evaluation or visual review is pending")
    analysis_folder = local(report["directory"])
    qa = reviewed_all_derived_figures(analysis_folder)
    key = "point_comparison" if method == "BA_TRACK" else "sample_archive"
    identified(report[key], report[key+"_sha256"])
    return {**identity, "report": report, "visual_QA": qa}


def main():
    gate_file = REPORTS / "E15_STAGE_DELIVERY.json"
    report_file = REPORTS / "E15_stage_report.md"
    if gate_file.exists() or report_file.exists():
        raise FileExistsError("A delivered stage snapshot is immutable")
    prior = read(REPORTS / "E13_E14_STAGE_DELIVERY.json")
    if prior["status"] != "E13_E14_REVIEWED_STAGE_REPORT_WRITTEN":
        raise ValueError("The actual preceding stage must already be delivered")
    identified(prior["report"], prior["report_sha256"])
    plan_file = local(read(REPORTS / "active_E15_MOVIE_batch.json")["plan"])
    plan = read(plan_file)
    jobs = plan["jobs"]
    primary = [j for j in jobs if j["role"] == "primary"]
    repeat = [j for j in jobs if j["role"] == "preregistered_independent_repeat"]
    methods = {"DROID_W", "PI3MOS", "BA_TRACK", "WILDGS"}
    sequences = list(dict.fromkeys(j["sequence"] for j in primary))
    required = {(s, m) for s in sequences for m in methods}
    if (plan["state"] != "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING" or len(jobs) != 20
        or len(sequences) != 4 or len(primary) != 16 or {(j["sequence"], j["method"]) for j in primary} != required
        or len(repeat) != 4 or {j["method"] for j in repeat} != methods or {j["sequence"] for j in repeat} != {plan["repeat_clip"]}
        or plan["repeat_selection_uses_prediction_scores"]):
        raise ValueError("Require the actual terminal preregistered16 primary+4 independent-repeat matrix")
    acquisition_file = REPORTS / "movi_test_acquisition.json"
    acquisition = read(acquisition_file)
    datasets, data_lines = [], []
    for number, sequence in enumerate(sequences):
        pointer_file = Path(next(j["input_pointer"] for j in primary if j["sequence"] == sequence))
        pointer = read(pointer_file)
        validation = local(pointer["external_validation_directory"])
        audit = read(validation / "GT_audit.json")
        identified(validation / "GT_audit.json", pointer["GT_audit_sha256"])
        identified(pointer["reference"], pointer["reference_sha256"])
        inputs = read(local(pointer["directory"]) / "input_manifest.json")
        if (pointer["expected_frames"] != 24 or pointer["GT_provenance"] != "SYNTHETIC_GROUND_TRUTH"
            or not audit["pixel_motion_label_geometry_valid"] or audit["flow_geometry_review"]["status"] != "PASS"
            or inputs["source_record_sha256"] != acquisition["records"][number]["sha256"]):
            raise ValueError("Actual source-record order, complete input support, or independent geometry is invalid")
        identified(audit["original_fields"], audit["original_fields_sha256"])
        identified(audit["motion_ground_truth"], audit["motion_ground_truth_sha256"])
        datasets.append({"sequence": sequence, "input_pointer": identified(pointer_file), "audit": audit,
            "audit_identity": identified(validation / "GT_audit.json"), "visual_QA": reviewed_all_derived_figures(validation / "visualization")})
        data_lines.append("| "+" | ".join(map(scalar, [sequence, audit["condition"], audit["camera_effective_translation_rank"],
            audit["native_dynamic_pixel_fraction"], audit["maximum_rigid_bbox_error_world_unit"], audit["flow_geometry_review"]["status"]]))+" |")
    chosen = max(range(4), key=lambda i: (datasets[i]["audit"]["native_dynamic_pixel_fraction"], -i))
    if datasets[chosen]["sequence"] != plan["repeat_clip"]:
        raise ValueError("The actual repeat clip differs from the prespecified GT-only selection")
    cases, camera_lines, motion_lines, point_lines, resource_lines = [], [], [], [], []
    accepted = 0
    for number, job in enumerate(jobs):
        if job["state"] != "ATTEMPT_TERMINAL" or not job.get("completed_at_utc"):
            raise ValueError("A native attempt remains unstarted or active")
        identified(job["input_pointer"], job["input_pointer_sha256"])
        case = {k: job[k] for k in ("method", "sequence", "role", "native_status", "controller_exit_code")}
        folder = local(job["result_directory"]) if job.get("result_directory") else None
        label = [job["sequence"], job["method"], job["role"]]
        if folder:
            case.update(directory=str(folder), native_status=read(folder / "status.json"),
                contract=identified(folder / "execution_contract.json"), native_status_identity=identified(folder / "status.json"))
            evaluation_file = folder / "evaluation_summary.json"
            if evaluation_file.exists():
                evaluation = read(evaluation_file)
                if evaluation["status"] != "PHASE5_EXTERNAL_CAMERA_EVALUATION_COMPLETED" or not evaluation["figures_visually_reviewed"]:
                    raise ValueError("Actual camera acceptance and visual review are pending")
                case.update(camera=identified(evaluation_file), camera_metrics=evaluation["metrics"], visual_QA=reviewed_figures(folder, camera=True))
                details_file = folder / "evaluation_details.json"
                details = read(details_file)
                case["camera_alignment_details"] = identified(details_file)
                case["orientation_anchored_diagnostic"] = details.get("orientation_anchored_diagnostic")
                accepted += 1
                for metric in evaluation["metrics"]:
                    camera_lines.append("| "+" | ".join(map(scalar, label+[metric["alignment"], metric["status"], metric["ATE_RMSE"],
                        metric["RPE_translation_RMSE"], metric["RPE_rotation_RMSE_degrees"], metric["valid_pose_frames"]]))+" |")
                anchored = details.get("orientation_anchored_diagnostic", {})
                if anchored.get("status") == "UNAVAILABLE":
                    camera_lines.append("| "+" | ".join(map(scalar, label+["orientation_anchored_Sim3_diagnostic",
                        "UNAVAILABLE: "+anchored["reason"], None, None, None, evaluation["expected_frames"]]))+" |")
            else:
                case["failure"] = verify_failure(folder, plan_file, number)
                camera_lines.append("| "+" | ".join(label)+" | N/A | "+case["failure"]["review"]["classification"]+" | N/A | N/A | N/A | N/A |")
            if not case["native_status"]["status"].endswith("_COMPLETED") and "failure" not in case:
                case["failure"] = verify_failure(folder, plan_file, number)
            motion = reviewed_motion(folder, job["method"])
            case["motion"] = motion
            result = motion["report"]
            if job["method"] == "BA_TRACK":
                fields = result.get("point_motion_metrics", {})
                for field in ("camera_only_EPE_network_pixels", "object_residual_EPE_network_pixels", "total_EPE_network_pixels", "zero_object_control_EPE_network_pixels"):
                    summary = fields.get(field, {})
                    point_lines.append("| "+" | ".join(map(scalar, label+[field, summary.get("observations"), summary.get("RMSE"), result["status"]]))+" |")
            else:
                metric = result.get("metrics", {})
                frontend = result.get("native_frontend_observation") or {}
                motion_lines.append("| "+" | ".join(map(scalar, label+[result["signal_semantics"], result.get("observed_signal_frames"),
                    frontend.get("initialized_after_calls"), metric.get("samples"), metric.get("GT_prevalence"), metric.get("AUROC"), metric.get("average_precision"), metric.get("precision"), metric.get("recall"), metric.get("IoU")]))+" |")
            native = case["native_status"]
            seconds = native["wall_seconds"]
            resource_lines.append("| "+" | ".join(map(scalar, label+[native["status"], seconds, 24/seconds if case.get("camera") and seconds else None,
                native["whole_gpu_peak_used_mib_sampled"]]))+" |")
            if job["method"] == "WILDGS" and evaluation_file.exists():
                inspection = read(folder / "map_uncertainty_review.json")
                if not inspection["native_computation_outputs_complete"]:
                    raise ValueError("WildGS actual map/uncertainty output inspection is pending")
                case["map_review"] = identified(folder / "map_uncertainty_review.json")
            if job["method"] == "WILDGS":
                source_archive = folder / "executed_source_archive.json"
                archive = read(source_archive)
                if archive["status"] != "EXECUTED_SOURCE_CACHE_ARCHIVE_BYTE_ROUNDTRIP_PASS":
                    raise ValueError("Exact executed WildGS source archive is required, including failed attempts")
                identified(archive["archive"], archive["archive_sha256"])
                case["executed_source_archive"] = identified(source_archive)
            if job["method"] == "BA_TRACK" and any(s["stage"] == "sparse_tracker_and_BA" and s["exit_code"] == 0 for s in native.get("stages", [])):
                video_qa_file = folder / "native_video_figure_review.json"
                video_qa = read(video_qa_file)
                if video_qa["status"] != "VISUALLY_REVIEWED_PASS":
                    raise ValueError("Actual native BA display examples require their separate visual review")
                for row in video_qa["files"]:
                    identified(folder / row["file"], row["sha256"])
                identified(video_qa["selection_file"], video_qa["selection_sha256"])
                case["native_video_visual_QA"] = identified(video_qa_file)
                case["native_output_review"] = identified(folder / "output_review.json")
        else:
            case["failure"] = verify_failure(None, plan_file, number)
            camera_lines.append("| "+" | ".join(label)+" | N/A | "+case["failure"]["review"]["classification"]+" | N/A | N/A | N/A | N/A |")
        if case.get("directory"):
            sampling_summary = local(case["directory"]) / "gpu_memory_sampling_summary.json"
            if sampling_summary.exists():
                case["GPU_actual_sampling_summary"] = identified(sampling_summary)
        cases.append(case)
    common_pointer = read(REPORTS / "movi_common_signal_analysis.json")
    identified(common_pointer["report"], common_pointer["sha256"])
    common = read(local(common_pointer["report"]))
    if common["status"] != "ACTUAL_COMMON_DENSE_SUPPORT_AND_PLANNED_REPEAT_COMPARISONS_WRITTEN" or common["batch_plan_sha256"] != sha256(plan_file):
        raise ValueError("Actual common-support/repeat comparison must bind the final batch journal")
    common_lines = []
    for group in common["comparisons"]:
        for row in group.get("metrics", []):
            metric = row["metrics"]
            common_lines.append("| "+" | ".join(map(scalar, [group["sequence"], "+".join(group["requested_methods"]), row["method"], len(group["common_frame_ids"]),
                metric["samples"], metric["AUROC"], metric["average_precision"], metric["IoU"]]))+" |")
        if not group.get("metrics"):
            common_lines.append(f"| {group['sequence']} | {'+'.join(group['requested_methods'])} | N/A | 0 | N/A | N/A | N/A | N/A |")
    now = datetime.now(timezone.utc).isoformat()
    present = sorted({d["audit"]["condition"] for d in datasets})
    text = ["# E15：MOVi-E 独立运动真值受控实验", "", f"交付时间：{now}。全部20个预定原生尝试已终止，{accepted}/20个相机输出通过独立评价与图审。失败与不可用指标保留；第五阶段整体尚未完成。", "",
        "仅提取官方MOVi-E/256x256/1.0.0 test分片0–3各第一条完整TFRecord，逐片HTTP Range/对象generation/TFRecord CRC32C/本地SHA审计；不宣称下载完整分片。4段各24帧、12FPS，模型共同输入为完整256x256 RGB与已知K；深度、实例、光流、相机和物体位姿始终在独立评价侧。官方Kubric commit61f2422c84bab75006df33c6989e0b483db3ccfe与预先冻结协议记录在docs/PHASE5_MOVI_protocol.md及source_pin.json。", "",
        "相机源四元数WXYZ、C2W及OpenGL到OpenCV基变换、Euclidean range而非Z深度、物体刚体姿态/实例ID和光流均先于评分检查。运动标签依据每帧位置/速度/姿态变化；初始is_dynamic不代替逐帧标签。所有值使用SYNTHETIC_GROUND_TRUTH，长度单位Kubric_world_unit，不与真实MoCap的meter混合平均。", "",
        "| 片段 | 实际条件 | 相机位置秩 | 可见动态像素比例 | 刚体bbox最大差 | 独立光流几何检查 |", "|---|---|---:|---:|---:|---|", *data_lines, "",
        "实际出现条件："+", ".join(present)+"。未出现的A/B条件记未覆盖，不合成或挑选更有利片段补齐。速度/遮挡以实际独立标签分组；D不是额外伪造数据。线性或静止相机的全局位置对齐不可辨识时，标准SE3/Sim3 ATE为N/A，姿态锚定尺度诊断单列，不称为标准ATE或尺度恢复。", "",
        "| 片段 | 方法 | 运行角色 | 对齐 | 状态 | ATE | 相邻RPE平移 | 相邻RPE旋转° | 有效相机 |", "|---|---|---|---|---|---:|---:|---:|---:|", *camera_lines, "",
        "M1下表使用各方法实际观测到的信号帧，不能直接按不同支持度选择总冠军。初始化观测调用数为0时，存在的信号代表前端未初始化状态下的原生归档值，仍可能经历末尾后端优化，不能据其分数宣称相机跟踪成功或代表完成初始化后的在线表现；不存在的信号记N/A。统一像素格点为u,v=3,11,...,251；DROID-W/WildGS原生不确定性是未校准排序信号，Pi3MOS sigmoid另评价固定0.4阈值与概率校准。所有阈值在GT评分前声明，AP与梯形PR-AUC不混称。", "",
        "| 片段 | 方法 | 角色 | 信号语义 | 实际信号帧 | 已初始化状态的调用数 | 像素样本 | GT动态比例 | AUROC | AP | Precision | Recall | IoU |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|", *motion_lines, "",
        "| 片段 | 实际共同支持方法 | 方法 | 共同帧 | 同一格点样本 | AUROC | AP | IoU |", "|---|---|---|---:|---:|---:|---:|---:|", *common_lines, "",
        "共同支持比较保留三方法交集和成对交集；空交集记N/A。最终关键帧不确定性与在线动态先验仍处于不同原生阶段。稀疏BA点从不与稠密像素混合。单类GT的AUROC/AP不可用，可靠性分箱、Brier/ECE仅在相应概率语义下解释，所有原始曲线及阈值敏感性在各motion_evaluation目录。sigmoid校准仅相对于本实验冻结的逐帧实际运动事件，不断言原发布训练标签与此事件完全相同。", "",
        "M2只使用实际未填充的原生窗口、原始查询及独立验证的前景点。排除同帧/重复/离开视野支持，遮挡保留并单列；相机单独运动和物体残差在原生网络UV像素坐标比较。", "",
        "| 片段 | 方法 | 角色 | 分量/输出对照 | 实际点目标对 | RMSE网络像素 | 状态 |", "|---|---|---|---|---:|---:|---|", *point_lines, "",
        "同向/反向、GT速度中位数分组、遮挡及静态可见比例分组保留在M2报告，空组记N/A。额外3D分量诊断必须通过已观测K/深度和独立源查询尺度检查，属于目标相机坐标、后评价尺度对齐的诊断，不是原生物理尺度或世界3D轨迹恢复。零物体/总运动作为相机的对照只是输出分析，不是模型消融或SLAM改进证明。原生动态点分数在窗口内重复；目标帧运动事件与窗口任一时刻运动事件分别报告，不冒称已知发布训练标签语义。", "",
        f"预定重复片段为{plan['repeat_clip']}：由4段GT动态像素比例最大值选择，平局取第一段，模型分数不参与。四方法各额外独立启动一次，配置/原生种子不变。比较见{common_pointer['report']}。一次额外重复仅提供该片段的重复观测；不把像素/点数当独立片段数，不宣称普遍统计可重复性。", "",
        "| 片段 | 方法 | 角色 | 原生终态 | 全流程秒 | 全输入/wall FPS | 整卡采样峰值MiB |", "|---|---|---|---|---:|---:|---:|", *resource_lines, "",
        "时间包含冷启动、原生先验/跟踪/优化/填充/IO；GUI省略，CPU评价另计。短片初始化不足、CPU内存/序列化失败、兼容性问题与运动估计失效分别记录，不能把启动问题包装为游戏域失效。显存是包含桌面的整卡采样值；线程WildGS调度/RNG差异、BA输出编码差异如实记录，不做无条件公平FPS或论文分数匹配宣称。固定权重与四独立环境沿用E13/E14审计，完整命令、源码/配置/资产身份、资源预算均绑定每个execution_contract.json。", "",
        "原生BA定性视频采用作者wide_list[2:-1]显示裁剪，独立相机评价仍保留全部24帧。已核验的MoviePy浮点duration/采样规则可能在短片末尾多编码一次相同源图；每个原生视频的实际编码帧到输入帧映射单独保存在native_qualitative_examples/selection.json，重复显示不增加相机或统计样本。作者视频10FPS播放与数据物理12FPS时钟分开。", "",
        "原始证据目录：", f"- 数据获取/字段/相机运动真值：{acquisition_file}及四个input-pointer对应的external_validation_directory。", f"- 原生20次调用、配置和日志：{plan_file.parent}。", "- 固定权重与环境：reports/SOTA/*assets.json、E13_WILDGS_READINESS.md及各运行execution_contract.json。", f"- 同支持与重复比较：{common_pointer['report']}。"]
    for case in cases:
        text.append(f"- {case['sequence']} / {case['method']} / {case['role']}：{case.get('directory', 'see failure review in batch logs')}")
        if case.get("failure"):
            text.append("  失败/不可用原因："+case["failure"]["review"]["reason"])
    text += ["", "各方法实际观察/保存的原生信号数量与体积不同，CPU复制、压缩、写盘均计入wall。缺少完整处理证据的失败案例FPS记N/A；失败但已接受完整主相机的运行只计时到故障处，未执行阶段不算作完整成功流程。FPS不等同于统一记录开销下的纯算法速度。M2各方向/速度/遮挡/背景分组另按每个实际绝对帧距分层保留，未平衡预测时距的总体差异只作描述，不当作孤立因果效应。M2速度为源到目标表面位移除以时长，不冒称瞬时速度。"]
    text += ["", "实际GPU采样间隔和最大缺口见各gpu_memory_sampling_summary.json；请求循环休眠1秒不保证连续1秒有效观测。长间隔在资源图中断线，不插补缺失值。已记录的查询异常另存gpu_sampling_errors.jsonl；没有记录原因的旧缺口不归因于特定驱动或GPU行为。"]
    text += ["", "BA-Track固定上游README明确其训练域为Kubric，MOVi-E属于相关合成数据域；当前材料未确认公开权重与这四段TFDS test视频的逐视频重合或去重，故不声明域外测试或训练/测试完全隔离。该来源与解释已在样本获取前记录于[BA原生协议审查](BA_documented_protocol_source_review.json)。原生RGB/查询像素原点约定差也单独披露，不从M2误差中扣除，不作为实测误差界限。", ""]
    text += ["", "本阶段未训练新网络，未用GT调模型或选择位姿方向，未删除困难帧/旧实验。MOVi-E为刚体受控合成数据，不是游戏或人体骨骼真值；常数FOV不能验证M3。M1/M2研究空间仍需结合Bonn真实动态相机结果与最终E17审查，当前不宣称提出的方法有效。", "",
        "[Kubric官方MOVi代码](https://github.com/google-research/kubric/tree/61f2422c84bab75006df33c6989e0b483db3ccfe/challenges/movi)；[MOVi-E官方数据](https://storage.googleapis.com/kubric-public/tfds/movi_e/256x256/1.0.0/dataset_info.json)。", ""]
    body = "\n".join(text)
    evidence_file = REPORTS / "E15_stage_evidence.json"
    write_json(evidence_file, {"created_at_utc": now, "datasets": datasets, "cases": cases,
        "batch_plan": identified(plan_file), "acquisition": identified(acquisition_file), "common_support_and_repeat_comparison": identified(common_pointer["report"], common_pointer["sha256"]),
        "whole_phase5_complete": False})
    report_file.write_text(body, encoding="utf-8")
    snapshot = plan_file.parent / "pre_delivery_report_snapshots"
    snapshot.mkdir(exist_ok=False)
    for destination in (REPORTS / "phase5_movi_results.md", PROJECT / "reports/SOTA/E15_MOVIE_CONTROLLED.md"):
        if destination.exists():
            shutil.copy2(destination, snapshot / destination.name)
        destination.write_text(body, encoding="utf-8")
    gate = {"status": "E15_REVIEWED_STAGE_REPORT_WRITTEN", "report": str(report_file), "report_sha256": sha256(report_file),
        "evidence": str(evidence_file), "evidence_sha256": sha256(evidence_file), "delivered_at_utc": now,
        "native_attempts_terminal": 20, "accepted_camera_cases": accepted, "whole_phase5_complete": False,
        "all_native_exits_successful": all(c.get("native_status", {}).get("status", "FAILED").endswith("_COMPLETED") if isinstance(c.get("native_status"), dict) else False for c in cases)}
    write_json(gate_file, gate)
    print(json.dumps(gate))


if __name__ == "__main__":
    main()

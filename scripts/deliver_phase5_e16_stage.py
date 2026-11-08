"""Deliver only actual reviewed Bonn camera evidence and calibration diagnostics."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
import json
import shutil

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import local, read
from deliver_phase5_e13_e14_stage import reviewed_figures, scalar
from deliver_phase5_e15_stage import identified, reviewed_all_derived_figures, verify_failure


def main():
    reports = PROJECT / "reports/PHASE5"
    report_file, gate_file = reports / "E16_stage_report.md", reports / "E16_STAGE_DELIVERY.json"
    if report_file.exists() or gate_file.exists():
        raise FileExistsError("A delivered stage snapshot is immutable")
    preceding = read(reports / "E15_STAGE_DELIVERY.json")
    if preceding["status"] != "E15_REVIEWED_STAGE_REPORT_WRITTEN":
        raise ValueError("Require the actual delivered MOVi evidence first")
    identified(preceding["report"], preceding["report_sha256"])
    plan_file = local(read(reports / "active_E16_BONN_batch.json")["plan"])
    plan = read(plan_file)
    jobs = plan["jobs"]
    sequences = ["bonn_"+s for s in ("person_tracking", "crowd", "moving_obstructing_box")]
    required = {(s, m) for s in sequences for m in ("DROID_W", "PI3MOS", "BA_TRACK", "WILDGS")}
    if (plan["state"] != "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING" or len(jobs) != 12
        or {(j["sequence"], j["method"]) for j in jobs} != required or any(j["role"] != "primary" for j in jobs)):
        raise ValueError("Require all twelve real selected Bonn attempts, with full input support")
    datasets, data_lines = [], []
    for sequence in sequences:
        pointer_file = local(next(j["input_pointer"] for j in jobs if j["sequence"] == sequence))
        pointer = read(pointer_file)
        folder = local(pointer["external_validation_directory"])
        audit = read(folder / "GT_audit.json")
        identified(folder / "GT_audit.json", pointer["GT_audit_sha256"])
        identified(pointer["reference"], pointer["reference_sha256"])
        identified(pointer["calibration_interpretation_reference"], pointer["calibration_interpretation_reference_sha256"])
        calibration = audit["coordinate_conversion"]
        if (pointer["dataset"] != "Bonn RGB-D Dynamic" or pointer["GT_provenance"] != "MOCAP_GROUND_TRUTH"
            or pointer["unit"] != "Bonn_official_transform_unit" or not audit["depth_and_reference_excluded_from_model_view"]
            or audit["pixel_motion_or_skeleton_GT"] or audit["model_predictions_used_in_GT_preparation"]
            or not calibration["primary_positions_identical_to_exact_native_affine_normalization"]):
            raise ValueError("Actual Bonn calibration or RGB-only provenance does not match the frozen protocol")
        qa = reviewed_all_derived_figures(folder)
        datasets.append({"input_pointer": identified(pointer_file), "audit": audit, "audit_identity": identified(folder / "GT_audit.json"), "visual_QA": qa})
        data_lines.append("| "+" | ".join(map(scalar, [sequence, pointer["expected_frames"], pointer["GT_associated_frames"],
            audit["maximum_accepted_clock_difference_seconds"], calibration["normalized_rotation_max_SO3_Frobenius_defect"], pointer["rotation_metrics_valid"]]))+" |")
    cases, metric_lines, diagnostic_lines, resource_lines = [], [], [], []
    accepted = 0
    for number, job in enumerate(jobs):
        if job["state"] != "ATTEMPT_TERMINAL" or not job.get("completed_at_utc"):
            raise ValueError("An actual Bonn model attempt remains active or unstarted")
        identified(job["input_pointer"], job["input_pointer_sha256"])
        case = {k: job[k] for k in ("method", "sequence", "native_status", "controller_exit_code")}
        out = local(job["result_directory"]) if job.get("result_directory") else None
        if out:
            native = read(out / "status.json")
            case.update(directory=str(out), native_status= native, native_identity=identified(out / "status.json"), contract=identified(out / "execution_contract.json"))
            evaluation_file = out / "evaluation_summary.json"
            if evaluation_file.exists():
                evaluation = read(evaluation_file)
                if evaluation["status"] != "PHASE5_EXTERNAL_CAMERA_EVALUATION_COMPLETED" or not evaluation["figures_visually_reviewed"]:
                    raise ValueError("Bonn camera output or actual figure review is pending")
                case.update(evaluation=identified(evaluation_file), metrics=evaluation["metrics"], visual_QA=reviewed_figures(out, camera=True))
                accepted += 1
                for metric in evaluation["metrics"]:
                    if metric["native_ground_truth_unit"] != "Bonn_official_transform_unit":
                        raise ValueError("Primary and alternative calibration units were mixed")
                    metric_lines.append("| "+" | ".join(map(scalar, [job["sequence"], job["method"], metric["alignment"], metric["status"], metric["ATE_RMSE"],
                        metric["RPE_translation_RMSE"], metric["RPE_rotation_RMSE_degrees"], metric["valid_pose_frames"], metric["GT_associated_frames"], metric["GT_adjacent_pair_support"]]))+" |")
                diagnostic_file = out / "calibration_interpretation_diagnostic/diagnostic_summary.json"
                diagnostic = read(diagnostic_file)
                identified(diagnostic["primary_evaluation_snapshot"], diagnostic["primary_evaluation_sha256"])
                source_primary = read(local(diagnostic["primary_evaluation_snapshot"]))
                if source_primary["metrics"] != evaluation["metrics"] or not diagnostic["not_pooled_with_primary"] or diagnostic["coordinate_convention_selected_by_score"]:
                    raise ValueError("Separate calibration diagnostic does not bind the accepted primary numeric metrics")
                case["calibration_interpretation_diagnostic"] = {**identified(diagnostic_file), "report": diagnostic}
                for metric in diagnostic["metrics"]:
                    diagnostic_lines.append("| "+" | ".join(map(scalar, [job["sequence"], job["method"], metric["alignment"], metric["ATE_RMSE"],
                        metric["RPE_translation_RMSE"], metric["RPE_rotation_RMSE_degrees"], metric["native_ground_truth_unit"]]))+" |")
                if job["method"] == "WILDGS":
                    map_review = read(out / "map_uncertainty_review.json")
                    if not map_review["native_computation_outputs_complete"]:
                        raise ValueError("Actual WildGS map/uncertainty inspection is pending")
                    case["map_review"] = identified(out / "map_uncertainty_review.json")
            else:
                case["failure"] = verify_failure(out, plan_file, number)
                metric_lines.append(f"| {job['sequence']} | {job['method']} | N/A | {case['failure']['review']['classification']} | N/A | N/A | N/A | N/A | N/A | N/A |")
            if not native["status"].endswith("_COMPLETED") and "failure" not in case:
                case["failure"] = verify_failure(out, plan_file, number)
            frames = read(local(job["input_pointer"]))["expected_frames"]
            resource_lines.append("| "+" | ".join(map(scalar, [job["sequence"], job["method"], native["status"], native["wall_seconds"],
                frames/native["wall_seconds"] if case.get("evaluation") and native["wall_seconds"] else None, native["whole_gpu_peak_used_mib_sampled"]]))+" |")
        else:
            case["failure"] = verify_failure(None, plan_file, number)
            metric_lines.append(f"| {job['sequence']} | {job['method']} | N/A | {case['failure']['review']['classification']} | N/A | N/A | N/A | N/A | N/A | N/A |")
        if case.get("directory"):
            sampling_summary = local(case["directory"]) / "gpu_memory_sampling_summary.json"
            if sampling_summary.exists():
                case["GPU_actual_sampling_summary"] = identified(sampling_summary)
        cases.append(case)
    now = datetime.now(timezone.utc).isoformat()
    text = ["# E16：Bonn 真实动态场景交叉验证", "", f"交付时间：{now}。十二个预定RGB-only案例均已实际尝试并终止，{accepted}/12个通过相机评价与图审；失败和不可用指标保留。第五阶段尚待E17证据综合判断。", "",
        "三个官方ZIP按person_tracking、crowd、moving_obstructing_box逐条获取与核验。全体RGB保留，统一一次去畸变/半像素K缩放至320x240、保持4:3画幅；四方法读取完全相同RGB/K。传感器深度仅用于数据完整性审计，GT仅用于独立评价。固定官方权重和原独立环境沿用前序审计；每个execution_contract.json记录实际命令、源码/参数/资源预算，原始日志在对应结果目录与批次目录。", "",
        "本库参考为OptiTrack/MOCAP_GROUND_TRUTH。相机/标记转换采用官方Tros.T @ Traw @ Tros @ Tm及首个已关联GT矩阵的精确逆归一化。Tm线性块并非SO3，约含1.05929缩放，主位置单位明确为Bonn_official_transform_unit。旋转CSV使用正极分解规范化，精确仿射矩阵和未改的平移另存；仅在预定5e-4 SO3偏差门通过时计算旋转相关指标。该约定在新数据和分数出现之前冻结，不按ATE选择坐标。", "",
        "| 序列 | 全RGB分母 | 实际关联GT | 最大关联时差秒 | 归一化旋转最大SO3偏差 | 旋转指标可用 |", "|---|---:|---:|---:|---:|---|", *data_lines, "",
        "RGB/GT使用原始物理时间最近关联、额外偏移0、容差0.02s和平局首项；容差是本实验预先声明的选择。缺失GT不删模型RGB，不算作跟踪失败。RPE只覆盖原输入相邻且都有GT的帧对，不跨缺失GT间隙。完整相机覆盖与前端初始化/显式丢失状态分开；原生未提供丢失状态时N/A，不把填充相机覆盖当作实时跟踪成功率。", "",
        "| 序列 | 方法 | 对齐 | 状态 | 主ATE | 主相邻RPE平移 | RPE旋转° | 完整相机 | GT支持 | 相邻GT帧对 |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|", *metric_lines, "",
        "下表仅为预定的标定解释诊断：Tm线性块取正旋转、保留精确标记平移，且不使用非刚体首矩阵的逆。长度单位raw_MoCap_translation_unit，与主表分开，不选两种约定中更好看的分数。主指标与该诊断均来自同一个已保存模型相机，不重复运行模型。", "",
        "| 序列 | 方法 | 对齐 | 另列ATE | 另列RPE平移 | 另列RPE旋转° | 诊断单位 |", "|---|---|---|---:|---:|---:|---|", *diagnostic_lines, "",
        "| 序列 | 方法 | 原生终态 | 实际执行阶段秒 | 全输入/wall FPS | 整卡采样峰值MiB |", "|---|---|---|---:|---:|---:|", *resource_lines, "",
        "运行时间包含各原生学习先验、跟踪/优化/填充/IO，省略GUI，独立CPU评价另计；GPU为含桌面的整卡采样。线程WildGS与原生多进程的调度/RNG差异、BA输出编码/观察成本和任何资源干预如实记录，不宣称原生多进程位级复现、论文分数匹配或无条件公平FPS排名。", "",
        "Bonn未提供本实验所需的独立逐像素运动、物体刚体轨迹或骨骼标签，因此只报告相机精度、完整支持、资源和可视化行为，不输出虚构的动态分割/M2准确率。真实动态库之间的交叉验证不单独证明游戏到真实的训练域迁移，更不能验证动态FOV或骨骼辅助方法。", "", f"批次命令、原始输出和失败审查：{plan_file.parent}。证据目录："]
    for case in cases:
        text.append(f"- {case['sequence']} / {case['method']}：{case.get('directory', 'see batch failure review')}")
        if case.get("failure"):
            text.append("  失败/不可用原因："+case["failure"]["review"]["reason"])
    text += ["", "不同方法实际保存的逐帧先验/点轨迹/关键帧地图数量不同，观察过程的CPU复制、压缩、写出成本均计入wall。缺少完整处理证据的失败案例FPS记N/A；失败但已接受完整主相机的运行只计时到故障处，未执行阶段不算完整成功流程。FPS不等同于统一记录开销下的纯算法速度。"]
    text += ["", "实际GPU采样间隔和最大缺口见各gpu_memory_sampling_summary.json；请求循环休眠1秒不保证连续1秒有效观测。长间隔在资源图中断线，不插补缺失值。已记录的查询异常另存gpu_sampling_errors.jsonl；没有记录原因的旧缺口不归因于特定驱动或GPU行为。"]
    text += ["", "本阶段未训练新网络，未改基线核心数学、未用GT选位姿方向，未删除困难帧或旧实验。最终M1/M2判断需联合MOVi独立标签和预定重复，分开排除坐标、分辨率、深度、时钟、初始化与内存/兼容性因素；不强行确定创新点。", "", "[Bonn官方数据与相机转换](https://www.ipb.uni-bonn.de/data/rgbd-dynamic-dataset/)。", ""]
    body = "\n".join(text)
    evidence_file = reports / "E16_stage_evidence.json"
    write_json(evidence_file, {"created_at_utc": now, "datasets": datasets, "cases": cases, "batch_plan": identified(plan_file), "whole_phase5_complete": False})
    report_file.write_text(body, encoding="utf-8")
    snapshot = plan_file.parent / "pre_delivery_report_snapshots"
    snapshot.mkdir(exist_ok=False)
    for destination in (reports / "phase5_bonn_results.md", PROJECT / "reports/SOTA/E16_BONN_CROSS_VALIDATION.md"):
        if destination.exists():
            shutil.copy2(destination, snapshot / destination.name)
        destination.write_text(body, encoding="utf-8")
    gate = {"status": "E16_REVIEWED_STAGE_REPORT_WRITTEN", "report": str(report_file), "report_sha256": sha256(report_file),
        "evidence": str(evidence_file), "evidence_sha256": sha256(evidence_file), "delivered_at_utc": now,
        "native_attempts_terminal": 12, "accepted_camera_cases": accepted, "whole_phase5_complete": False}
    write_json(gate_file, gate)
    print(json.dumps(gate))


if __name__ == "__main__":
    main()

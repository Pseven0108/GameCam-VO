"""Explain the actually delivered E13/E14 results after the user-requested stop."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
from pathlib import Path
import shutil

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import local, read


def identity(path):
    return {"file": str(path), "sha256": sha256(path)}


def main():
    reports = PROJECT / "reports/PHASE5"
    summary_file = reports / "phase5_stage_summary_for_beginner_20261102.md"
    closeout_file = reports / "PHASE5_STAGE_CLOSEOUT_20261102.json"
    if summary_file.exists() or closeout_file.exists():
        raise FileExistsError("Preserve the delivered user-requested closeout")
    gate_file = reports / "E13_E14_STAGE_DELIVERY.json"
    gate = read(gate_file)
    if (gate["status"] != "E13_E14_REVIEWED_STAGE_REPORT_WRITTEN"
        or sha256(local(gate["report"])) != gate["report_sha256"]
        or sha256(local(gate["evidence"])) != gate["evidence_sha256"]):
        raise ValueError("Require the actual unchanged stage report and evidence")
    stop_file = reports / "USER_REQUESTED_STOP_20261102.json"
    stop = read(stop_file)
    cleanup_file = reports / "OWNED_RUNTIME_CLEANUP_20261102.json"
    cleanup = read(cleanup_file)
    lease_file = PROJECT / "data/phase5_runtime/20261102T050303179Z_reviewed_resume_runtime_lease/lease.json"
    lease = read(lease_file)
    if (stop["new_model_launches_allowed"] or stop["new_dataset_acquisition_allowed"]
        or stop["handling_current_native_case"] != "USER_CONFIRMED_FINISH_CURRENT_CASE_THEN_STOP"
        or cleanup["status"] != "OWNED_TEMPORARY_SWAPS_DEACTIVATED_DETACHED_AND_REMOVED"
        or cleanup["owned_native_models_after"] or cleanup["user_stop_request_sha256"] != sha256(stop_file)
        or lease["status"] != "OWNED_FOREGROUND_WSL_RUNTIME_LEASE_STOPPED"):
        raise ValueError("Require the actual confirmed stop and completed owned-resource cleanup")
    for path in cleanup["removed_only_exact_temporary_files"]:
        # The ext4 file was verified by the WSL cleanup receipt; inspect the
        # Windows-visible D backing here without inventing a C-side mount.
        if path.startswith("/mnt/d/") and local(path).exists():
            raise ValueError("The task-created D backing file is still present")
    for filename in ("movi_test_acquisition.json", "active_E15_MOVIE_batch.json", "active_E16_BONN_batch.json",
        "bonn_person_tracking_data.json", "bonn_crowd_data.json", "bonn_moving_obstructing_box_data.json"):
        if (reports / filename).exists():
            raise ValueError("Do not describe an acquired later dataset or started queue as unstarted")
    for phase in ("E15_MOVIE", "E16_BONN"):
        if list((PROJECT / "results" / phase).glob("*/*/execution_contract.json")):
            raise ValueError("A later native attempt exists; audit it before summarizing")
    evidence = read(local(gate["evidence"]))
    cases = evidence["E14_cases"]
    methods = (("DROID_W", "DROID-W"), ("PI3MOS", "Pi3MOS"), ("WILDGS", "WildGS"), ("BA_TRACK", "BA-Track"))
    scenes = (("person_tracking", "Person：人物运动"), ("crowd", "Crowd：人群/篮球"), ("racket", "Racket：人物/球拍"))
    if len(cases) != 12 or gate["E14_camera_accepted_cases"] != 12:
        raise ValueError("This completed-stage explanation requires all twelve accepted primary cameras")
    table = ["| 视频 | DROID-W | Pi3MOS | WildGS | BA-Track |", "|---|---:|---:|---:|---:|"]
    poses = 0
    metrics_evidence = []
    for sequence, label in scenes:
        values = []
        for method, _ in methods:
            case = next(c for c in cases if c["sequence"] == sequence and c["method"] == method)
            file = local(case["directory"]) / "evaluation_summary.json"
            if sha256(file) != case["evaluation_sha256"] or not case["camera_accepted"]:
                raise ValueError("A stage-accepted camera identity changed")
            metric = next(m for m in case["metrics"] if m["alignment"] == "Sim3")
            if metric["status"] != "COMPUTED" or metric["native_ground_truth_unit"] != "meter":
                raise ValueError("Do not mix unavailable scores or different units")
            values.append(f"{100*metric['ATE_RMSE']:.2f}")
            poses += metric["valid_pose_frames"]
            metrics_evidence.append({"method": method, "sequence": sequence, "evaluation": identity(file), "Sim3_ATE_meter": metric["ATE_RMSE"]})
        table.append("| "+" | ".join([label, *values])+" |")
    native_failures = [c for c in cases if not c["native_status"].endswith("_COMPLETED")]
    protection = reports / "phase4_protection_validation_at_stage_stop_20261102.json"
    if read(protection)["status"] != "BOUNDED_PHASE4_DELIVERY_ARTIFACT_CHECKS_PASSED":
        raise ValueError("Protected earlier experiment validation must pass")
    now = datetime.now(timezone.utc).isoformat()
    text = ["# GameCam-VO 本次实验成果：新手版", "", "本次已完成E13/E14的实验与评价，并按你的选择停止。最后一项模型于2026-11-02北京时间14:44:38结束；本次临时交换空间已释放，保活进程于14:53:13结束。MOVi-E、Bonn和后续创新点实验均未启动。第五阶段整体仍有后续任务，本次收尾范围为E13/E14。", "",
        "我们在做什么：让四种现成算法观看相同的视频，分别估计摄像机经过的位置和朝向，再用动作捕捉设备测出的真实路线评分。这给以后设计自己的方法建立了可以比较的基准。", "",
        "已经完成的成果：", "", "- 增加WildGS-SLAM，完成官方Crowd演示、地图和不确定性输出检查。Demo结束清理有异常，原始失败状态与已完成输出分开保留。",
        "- 四种方法都完成Person986帧、Crowd1268帧、Racket962帧的主相机轨迹评价，共12项对比。三段共有3216帧（含原数据中保留的重复帧）；四方法合计评价"+str(poses)+"个相机位姿。",
        "- 统一400×240的完整RGB和相机内参输入，保留所有帧。外部真实路线仅用于评分，未作为模型答案输入。",
        "- 保存原始输出、日志、失败记录、参数、轨迹图、资源曲线和文件校验记录。旧E7–E12的已索引结果核验通过，原有独立环境保留。", "",
        "下表为整体轨迹误差（Sim3 ATE，单位：厘米），数值越小，表示对齐后的路线越接近真实路线。", "", *table, "",
        "读表前要知道：评分允许把整条估计路线统一平移、旋转和缩放后对齐。这主要衡量路线形状；例如1厘米不能直接解释为设备已经实现1厘米的真实绝对定位。完整技术报告另列未缩放对齐的SE3指标、相邻运动误差和初始化信息。", "",
        "从这次小样本看到的现象：Person上Pi3MOS的整体轨迹误差较小；Crowd上WildGS较小；Racket上WildGS与DROID-W接近。BA-Track在这三段的整体轨迹误差较大。这些是固定数据与配置下的观察，不能直接推广成所有场景的总排名。", "",
        "为什么有失败记录，仍能完成12项相机评价：BA-Track先输出主相机轨迹，后面还有大文件保存和进一步细化。Person在后续保存时遭遇内存终止，完整相机字段经只读恢复和独立核对；Crowd与Racket保存主轨迹成功，后续细化分别申请17.38GiB和13.19GiB的单次显存，超过约7.96GiB设备容量。三项完整流程仍保留FAILED，主相机结果通过独立检查后用于比较。没有将后续失败改写成完整成功。", "",
        "最后一项Crowd已保留1268/1268帧主相机、5,103,056,724字节原始结果文件和原生结果视频。容量修复使用2048存储槽，1268份原生学习深度在运行前后逐文件核验一致；窗口、点数、迭代和权重保持原设置。此前1024容量失败与一次88帧控制中断也保留，未按GT分数选择更好看的运行。", "",
        "目前证据支持的是：我们已有四方法的真实动态相机对比基准，并定位了轨迹误差与本机内存/显存限制。具体误差是否由动态物体造成，仍需独立运动标签验证。该数据没有逐像素运动或骨骼真值，完整填充位姿也不等于每帧实时跟踪都成功。", "",
        "这批新增视频是真实拍摄的数据。复杂游戏镜头、角色骨骼辅助和动态FOV仍未得到验证；本次没有训练自己的网络，也没有正式选定M1（动态区域置信度）或M2（相机与物体运动解耦）作为已成立的创新点。MOVi-E/Bonn受控与交叉验证、E17创新点决策均停止在未执行状态。", "",
        "几个常用词：Baseline是现成参照算法；GT是真实答案；ATE看整体路线偏差；RPE看相邻两帧运动偏差；显存是显卡可用于计算的空间。原生流程失败、主相机可用和科学结论成立是三件分别检查的事。", "",
        "你可以优先阅读本文件；需要详细参数与证据时，再打开这些入口：", "",
        f"- [E13/E14完整阶段报告]({local(gate['report']).as_posix()})",
        f"- [全部原始结果]({(PROJECT / 'results/E14_WILD_DYNAMIC').as_posix()})",
        f"- [本次停止与资源清理记录]({cleanup_file.as_posix()})", "",
        "所有数据、结果、代码与环境均保留供以后检查。本次仅删除经归属核验、停用并卸载后的两份临时交换文件；原有WSL交换、虚拟磁盘与旧实验未删除。此前用户已删除的旧WSL备份仍按原确认记录处理。没有执行WSL重启或VHDX压缩。", ""]
    summary_file.write_text("\n".join(text), encoding="utf-8")
    folder = PROJECT / "logs/PHASE5" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")+"_user_requested_stage_closeout")
    folder.mkdir(exist_ok=False)
    snapshots = folder / "previous_report_views"
    snapshots.mkdir()
    shutil.copy2(__file__, folder / (Path(__file__).name+".executed_source"))
    previous = []
    views = [reports / "CURRENT_STATE.md", reports / "phase5_status.json", reports / "phase5_wildslam_results.md", PROJECT / "reports/SOTA/E14_WILD_DYNAMIC_EVALUATION.md"]
    for file in views:
        if file.exists():
            saved = snapshots / (file.parent.name+"_"+file.name)
            shutil.copy2(file, saved); previous.append(identity(saved))
    closeout = {"status": "E13_E14_COMPLETED_AND_EXPERIMENTS_STOPPED_BY_USER", "closed_at_utc": now,
        "completed_scope": "E13/E14 actual primary camera experiments, independent evaluation, visual QA and evidence-based failure review",
        "whole_phase5_complete": False, "new_experiments_or_dataset_acquisition_authorized": False,
        "E14_accepted_primary_cameras": 12, "E14_native_full_pipelines_failed": len(native_failures),
        "E14_cases": cases, "E15": "NOT_RUN_USER_REQUESTED_STOP", "E16": "NOT_RUN_USER_REQUESTED_STOP", "E17": "NOT_RUN_NO_INNOVATION_SELECTED",
        "stage_gate": identity(gate_file), "beginner_summary": identity(summary_file), "metric_sources": metrics_evidence,
        "stop_request": identity(stop_file), "owned_resource_cleanup": identity(cleanup_file), "stopped_runtime_lease": identity(lease_file),
        "protected_phase4_validation": identity(protection), "previous_report_views_preserved": previous,
        "report_writer_source_sha256": sha256(Path(__file__))}
    write_json(closeout_file, closeout)
    write_json(reports / "phase5_status.json", closeout)
    current = "# 当前实验状态\n\nE13/E14已完成收尾，后续实验按用户要求停止。12/12项完整主相机轨迹已评价；BA-Track三项完整流程的后续异常仍记FAILED。第五阶段整体未完成，E15/E16/E17未执行，不自动继续。\n\n"+f"优先阅读[新手版成果总结]({summary_file.as_posix()})；详细数据见[E13/E14阶段报告]({local(gate['report']).as_posix()})。\n\n"+"本次临时交换与保活进程已释放；原数据、结果和独立环境保留。旧报告视图另存快照，E7–E12已索引结果保护核验通过。\n"
    (reports / "CURRENT_STATE.md").write_text(current, encoding="utf-8")
    professional = "用户已要求完成当前项后停止；E15/E16/E17未启动。此处为已交付E13/E14报告的阅读副本，末尾后续步骤只表示原计划，不构成继续执行。\n\n"+local(gate["report"]).read_text(encoding="utf-8")
    for file in (reports / "phase5_wildslam_results.md", PROJECT / "reports/SOTA/E14_WILD_DYNAMIC_EVALUATION.md"):
        file.write_text(professional, encoding="utf-8")
    print({"status": closeout["status"], "summary": str(summary_file), "accepted": 12, "native_full_pipeline_failures": len(native_failures)})


if __name__ == "__main__":
    main()

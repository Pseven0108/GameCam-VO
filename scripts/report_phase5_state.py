"""Refresh phase5 evidence views from actual files, never start or replay jobs."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
import json
from pathlib import Path

from gamecam_vo.common import PROJECT, write_json


def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def local(value):
    return Path(str(value).replace("/mnt/d/", "D:/", 1))


def main():
    reports = PROJECT / "reports/PHASE5"
    if (reports / "active_phase5_resume_20261102.json").exists():
        from report_phase5_resumed_state import main as resumed_view
        resumed_view()
        return
    closeout = read(reports / "PHASE5_STAGE_CLOSEOUT_20261102.json")
    if closeout and closeout["status"] == "E13_E14_COMPLETED_AND_EXPERIMENTS_STOPPED_BY_USER":
        print(json.dumps({"status": closeout["status"], "whole_phase5_complete": False,
            "scope": "Preserve the delivered user-requested stage stop; no active-state view rewrite"}))
        return
    trials = []
    for folder in sorted((PROJECT / "results/E13_WILDGS").glob("*")):
        if not folder.is_dir() or not (folder / "execution_contract.json").exists():
            continue
        record = read(folder / "status.json")
        contract = read(folder / "execution_contract.json")
        trials.append({"directory": str(folder), "status": record["status"] if record else "RUNNING",
            "actor_mode": contract["actor_mode"], "source_cache": contract.get("source_execution_cache"),
            "reason": record.get("reason") if record else None, "exit_code": record.get("exit_code") if record else None,
            "wall_seconds": record.get("wall_seconds") if record else None, "agent_stop": read(folder / "agent_stop_reason.json"),
            "output_acceptance": (read(folder / "map_uncertainty_review.json") or {}).get("status")})
    table = ["| Demo trial | Native state | Actor mode | Reason | Independent output review |", "|---|---|---|---|---|"]
    for trial in trials:
        reason = trial['agent_stop']['reason'] if trial['agent_stop'] else trial['reason'] or ("POST_COMPUTATION_CLEANUP_EXCEPTION" if trial['output_acceptance'] == "WILDGS_OUTPUTS_COMPLETE_TERMINAL_CLEANUP_FAILED" else "—")
        table.append(f"| {Path(trial['directory']).name} | {trial['status']} | {trial['actor_mode']} | {reason} | {trial['output_acceptance'] or 'N/A'} |")
    state = {"updated_at_utc": datetime.now(timezone.utc).isoformat(), "status": "ACTIVE_NOT_COMPLETE", "whole_phase5_complete": False,
        "E13_official_Demo_trials": trials, "E14_datasets": {}, "E14_model_runs": [],
        "E15": "SOURCE_AUDITED_SAMPLES_NOT_ACQUIRED", "E16": "SOURCE_AUDITED_SAMPLES_NOT_ACQUIRED", "E17": "NOT_SELECTED_PENDING_INDEPENDENT_EVIDENCE"}
    state["original_WSL_backup_current_state"] = read(reports / "user_backup_state_20261101.json")
    state["E14_case_recovery_plan"] = read(reports / "E14_case_recovery_plan.json")
    state["E14_BA_crowd_capacity_recovery_plan"] = read(reports / "E14_BA_crowd_capacity_recovery_plan.json")
    observer_issue = read(reports / "BA_crowd_observer_IO_pretermination_review.json")
    if observer_issue:
        issue_native = read(local(observer_issue["directory"]) / "status.json")
        state["E14_Crowd_recorder_issue_review"] = {"review": str(reports / "BA_crowd_observer_IO_pretermination_review.json"),
            "issue_recorded_before_BA_Crowd_GT_score": True, "executed_observer_sha256": observer_issue["executed_observer_sha256"],
            "actual_native_terminal_status": issue_native["status"] if issue_native else "RUNNING",
            "active_model_state_modified_or_replayed": False}
    for experiment, phase in (("E15_MOVIE", "E15"), ("E16_BONN", "E16")):
        active = read(reports / ("active_"+experiment+"_batch.json"))
        if active:
            phase_plan = read(Path(active["plan"]))
            state[phase] = phase_plan["state"]
            state[phase+"_batch"] = {"plan": active["plan"], "jobs": [{k: row.get(k) for k in ("method", "sequence", "role", "state", "native_status", "result_directory")} for row in phase_plan["jobs"]]}
    if read(reports / "movi_test_acquisition.json") and "E15_batch" not in state:
        state["E15"] = "OFFICIAL_SAMPLES_ACQUIRED_GT_PREPARATION_OR_MODEL_QUEUE_PENDING"
    bonn_data = [read(reports / ("bonn_"+s+"_data.json")) for s in ("person_tracking", "crowd", "moving_obstructing_box")]
    if any(bonn_data) and "E16_batch" not in state:
        state["E16"] = "SELECTED_SEQUENCES_BEING_ACQUIRED_OR_PREPARED"
    batch_pointer = read(reports / "active_E14_batch.json")
    batch = read(Path(batch_pointer["plan"])) if batch_pointer else None
    state["E14_sequential_batch"] = {"plan": batch_pointer["plan"], "state": batch["state"]} if batch else None
    rows = ["| Sequence | Frames | Clock/source status |", "|---|---:|---|"]
    for seq in ("person_tracking", "crowd", "racket"):
        data = read(reports / ("wild_"+seq+"_data.json"))
        prepared = read(reports / ("wild_"+seq+"_input.json"))
        state["E14_datasets"][seq] = {"acquisition": data["status"] if data else "NOT_ACQUIRED", "input": prepared["status"] if prepared else "NOT_PREPARED", "frames": data["frames"] if data else None}
        rows.append(f"| {seq} | {data['frames'] if data else 'N/A'} | {data['status'] if data else 'NOT_ACQUIRED'} |")
    model_rows = ["| Sequence | Method | Actual native state |", "|---|---|---|"]
    metric_rows = ["| Sequence | Method | Alignment | ATE | RPE translation | RPE rotation (°) | Filled poses | Unit |", "|---|---|---|---:|---:|---:|---:|---|"]
    for seq in ("person_tracking", "crowd", "racket"):
        for method in ("DROID_W", "PI3MOS", "BA_TRACK", "WILDGS"):
            terminal_pointer = reports / ("wildgs_shared_"+seq+"_thread-portability.json" if method == "WILDGS" else "E14_WILD_DYNAMIC_"+method+"_"+seq+"_native.json")
            record = read(terminal_pointer)
            job = next((j for j in batch["jobs"] if j["method"] == method and j["sequence"] == seq), None) if batch else None
            status = record["status"] if record else ("RUNNING" if job and job["state"] == "ATTEMPT_STARTED" else "QUEUED_NOT_RUN" if job else "NOT_RUN")
            case = {"sequence": seq, "method": method, "status": status, "native_pointer": str(terminal_pointer) if record else None}
            if not record and job and job["state"] == "ATTEMPT_STARTED":
                method_folder = "WildGS" if method == "WILDGS" else method
                candidates = list((PROJECT / "results/E14_WILD_DYNAMIC" / method_folder).glob("*_"+seq+("_*" if method == "WILDGS" else "")))
                if len(candidates) == 1:
                    case["directory"] = str(candidates[0])
            if record:
                directory = local(record["directory"])
                evaluation = read(directory / "evaluation_summary.json")
                case.update(directory=str(directory), wall_seconds=record["wall_seconds"], evaluation=evaluation["status"] if evaluation else "NOT_ACCEPTED_OR_PENDING")
                if evaluation:
                    case["camera_recovered_after_native_serialization_failure"] = evaluation.get("native_final_sparse_camera_recovered_after_serialization_failure", False)
                    case["metrics"] = [{k: row.get(k) for k in ("alignment", "status", "ATE_RMSE", "RPE_translation_RMSE", "RPE_rotation_RMSE_degrees", "valid_pose_frames")} | {"unit": row["native_ground_truth_unit"]} for row in evaluation["metrics"]]
                    for row in case["metrics"]:
                        metric_rows.append(f"| {seq} | {method} | {row['alignment']} | {row['ATE_RMSE']} | {row['RPE_translation_RMSE']} | {row['RPE_rotation_RMSE_degrees']} | {row['valid_pose_frames']} | {row['unit']} |")
            if "directory" in case:
                failure = read(Path(case["directory"]) / "failure_review.json")
                if failure:
                    case["failure_review"] = {k: failure.get(k) for k in ("classification", "reason", "final_camera_output_accepted")}
                resource = read(Path(case["directory"]) / "memory_budget_intervention.json")
                if resource:
                    case["runtime_resource_intervention"] = {k: resource.get(k) for k in ("status", "swap_file", "added_swap_bytes", "started_at_utc", "native_wall_time_contains_memory_pressure_and_resource_intervention")}
            state["E14_model_runs"].append(case)
            model_rows.append(f"| {seq} | {method} | {status} |")
    later = f"E15 MOVi-E：{state['E15']}。E16 Bonn：{state['E16']}。按E13/E14阶段报告、MOVi-E、Bonn的顺序执行。E17未提前选定M1/M2/M3；不能将CUDA IPC、文件访问耗时、内存耗尽或数据时钟重复包装成游戏域方法失效。"
    intervention = "\n\nBA-Track Person在约570帧后出现WSL内存/原2GiB交换空间耗尽。保留只读进程栈与资源证据，原运行中新增独立8GiB交换文件后继续，无重启、无重跑或模型参数变化。该次完整耗时包含内存阻塞和资源干预，不作无条件公平FPS排名；后续启动记录实际WSL内存预算。详见docs/PHASE5_RESOURCE_INTERVENTIONS.md。" if any("runtime_resource_intervention" in c for c in state["E14_model_runs"]) else ""
    protection = "原E7–E12结果、三个原环境保留；原WSL备份ext4.vhdx已由用户删除并确认，备份清单保留，当前不再声明该大文件存在。" if state["original_WSL_backup_current_state"] else "原E7–E12结果、三个原环境和WSL备份保留。"
    recovery_note = "\n\nBA-Track Person已完整处理986帧，随后在原生大轨迹pickle写出期间被内核OOM/SIGKILL终止，完整管线仍为FAILED，dense未启动。从未写完文件的完整开头字段只读恢复全部986帧最终稀疏相机；与独立保存的最后12帧原生W2C状态反变换一致，未重跑、未改数值、未用GT选方向。仅该完整主相机输出接受独立评价，未恢复大轨迹/深度文件。WildGS Person首次控制器错误发生在模型启动前：使用了DROID专用读取器别名；已改用WildGS原有RGB_NoPose别名并通过三序列CPU输入核对，首个实际模型运行排在当前队列终止后。" if any(c.get("camera_recovered_after_native_serialization_failure") for c in state["E14_model_runs"]) else ""
    observer_note = "\n\nBA-Track首个Crowd运行的可选相机归档器漏写CUDA索引的CPU复制，潜在问题在GT评分前已记录。该次实际先处理1023帧后触发原生BUFFER_SIZE=1024容量上限，未执行到terminate归档；完整相机及其GT指标不可用，不能归因为OOM或运动失效。归档器后续已修正CPU复制和可选写出故障传播。容量修复按作者提示取2048，只复用通过逐文件SHA/数值核验的1268份原生学习先验，输入/权重/窗口/点数/迭代/阈值不变；未完成案例补跑排在当前队列和WildGS Person首个实际模型终止后，原失败保留且不按GT选择结果。" if observer_issue else ""
    body = "# 第五阶段当前状态\n\n限定任务尚未完成。"+protection+"没有重跑已完成的旧实验来追分。\n\n"+"\n".join(table)+"\n\n"+"\n".join(rows)+"\n\n"+"\n".join(model_rows)+"\n\n"+later+intervention+recovery_note+observer_note+"\n\nPerson390/391的重复图像/时间戳与不同GT姿态均保留，官方物理时间最近关联的首项规则在任何新模型评分前冻结；Racket422/423重复时钟的GT相同。共同输入400×240，深度和外部GT不进入正式RGB-only模型。数据无独立逐像素动态/骨骼标签。\n\n原生双进程WildGS的CUDA IPC失败、线程兼容试跑的受控性能诊断中断、源码缓存遗漏配置的失败均保留在各自目录。线程兼容版保留原模型计算/同步方法，但进程调度和全局RNG可能不同，不能宣称原生多进程或论文分数复现。本地源码缓存逐文件字节核对，保留原anomaly/NaN检查，不改迭代数。\n"
    (reports / "CURRENT_STATE.md").write_text(body, encoding="utf-8")
    (reports / "phase5_wildslam_results.md").write_text(body, encoding="utf-8")
    (PROJECT / "reports/SOTA/E14_WILD_DYNAMIC_EVALUATION.md").write_text(body, encoding="utf-8")
    experiment_notes = "\n\n共同正式输入：400×240全帧RGB+已知K；额外深度为各自原生学习先验，未输入传感器深度或外部MoCap姿态。DROID-W/Pi3MOS/BA-Track使用第四阶段固定权重和原独立环境；WildGS使用新wildgs_slam环境。完整命令、模型参数和源码补丁绑定在各目录execution_contract.json。冷启动原生全流程时间包含先验、优化、填充与IO；另保存1秒采样的全卡GPU占用，不冒称单进程显存。全部MOCAP_GROUND_TRUTH逐序列分别报告；学习深度的物理尺度尚未经独立验证，SE3平移作为尺度诊断，Sim3评价明确包含尺度对齐。\n\n填充完整相机轨迹不等于逐帧跟踪成功：初始化调用数来自实际前端观测，原生方法没有显式丢失状态时不伪造Tracking Failure率。原始日志及失败原因保存在各试验目录；线程WildGS的调度/RNG差异和GUI省略明示，尚无论文分数一致性结论。\n\n"+"\n".join(metric_rows)+"\n"
    for path in (reports / "phase5_wildslam_results.md", PROJECT / "reports/SOTA/E14_WILD_DYNAMIC_EVALUATION.md"):
        path.write_text(body+experiment_notes, encoding="utf-8")
    audit = (PROJECT / "reports/SOTA/E13_WILDGS_READINESS.md").read_text(encoding="utf-8")
    history = audit+"\n\n"+"\n".join(table)+"\n\nLatest state is actual execution status, not a score-match claim. Completed output inspection is recorded separately from native exit status.\n"
    (reports / "E13_trial_history.md").write_text(history, encoding="utf-8")
    if not (reports / "wildgs_bundle_integrity.json").exists():
        (reports / "phase5_wildgs_reproduction.md").write_text(history, encoding="utf-8")
        (PROJECT / "reports/SOTA/E13_WILDGS_REPRODUCTION.md").write_text(history, encoding="utf-8")
    for filename, label in (("phase5_movi_results.md", "E15 / MOVi-E"), ("phase5_bonn_results.md", "E16 / Bonn")):
        path = reports / filename
        if not path.exists():
            path.write_text(f"# {label}\n\n实际状态：NOT_RUN_E13_E14_STAGE_GATE。数据/GT字段尚待官方源审计，当前没有新增数据下载或模型结果。配置、权重和环境将在实际执行时绑定；指标、日志、可视化均为N/A，不填0分。GT类型将分别使用SYNTHETIC_GROUND_TRUTH或MOCAP_GROUND_TRUTH，不与引擎/估计参考混合。\n", encoding="utf-8")
    write_json(reports / "phase5_status.json", state)
    print(json.dumps({"status": state["status"], "E13_latest": trials[-1]["status"] if trials else "NOT_RUN", "datasets": state["E14_datasets"]}))


if __name__ == "__main__":
    main()

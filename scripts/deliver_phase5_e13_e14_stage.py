"""Write the requested stage report only after real attempts and visual QA."""
from __future__ import annotations

import _bootstrap
from datetime import datetime, timezone
import csv
import json
from pathlib import Path

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import local, read
from plot_phase5_gpu_memory import load_sampling


def reviewed_figures(folder, camera=False):
    ledger_file = folder / "figure_review.json"
    ledger = read(ledger_file)
    if ledger["status"] != "VISUALLY_REVIEWED_PASS" or not ledger["files"]:
        raise ValueError("Actual visual review is pending: "+str(folder))
    indexed = set()
    for row in ledger["files"]:
        path = (folder / row["file"]).resolve()
        if not path.is_relative_to(folder.resolve()) or sha256(path) != row["sha256"]:
            raise ValueError("A reviewed figure changed or escaped its owned folder")
        indexed.add(row["file"].replace("\\", "/"))
    if camera:
        mandatory = {str(p.relative_to(folder)).replace("\\", "/") for p in (folder / "tracking_visualization").glob("*") if p.suffix in (".png", ".svg")}
        mandatory |= {"gpu_memory_timeline.png", "gpu_memory_timeline.svg"}
        if not mandatory.issubset(indexed):
            raise ValueError("A curated derived camera/GPU figure has not been reviewed")
    return {"ledger": str(ledger_file), "sha256": sha256(ledger_file), "files": len(indexed)}


def scalar(value):
    return "N/A" if value is None else f"{value:.6g}" if isinstance(value, float) else str(value)


def main():
    reports = PROJECT / "reports/PHASE5"
    gate_file = reports / "E13_E14_STAGE_DELIVERY.json"
    report_file = reports / "E13_E14_stage_report.md"
    if gate_file.exists() or report_file.exists():
        raise FileExistsError("A delivered stage snapshot is immutable; inspect it instead of overwriting")
    plan_file = Path(read(reports / "active_E14_batch.json")["plan"])
    plan = read(plan_file)
    recovery_plan_file = reports / "E14_case_recovery_plan.json"
    if recovery_plan_file.exists() and read(recovery_plan_file)["status"] != "ACTUAL_NATIVE_ATTEMPT_TERMINAL_REVIEWED":
        raise RuntimeError("The required first real WildGS Person launch after the prelaunch IO fix is still pending")
    capacity_plan_file = reports / "E14_BA_crowd_capacity_recovery_plan.json"
    if capacity_plan_file.exists() and read(capacity_plan_file)["status"] != "ACTUAL_NATIVE_ATTEMPT_TERMINAL_REVIEWED":
        raise RuntimeError("The required failed-incomplete BA Crowd capacity repair is still pending")
    resolutions_file = reports / "E14_case_resolutions.json"
    resolutions = read(resolutions_file)["resolutions"] if resolutions_file.exists() else []
    interruption_file = reports / "E14_interrupted_controller_attempts.json"
    interruptions = read(interruption_file)["attempts"] if interruption_file.exists() else []
    for item in interruptions:
        review_file = local(item["review_file"])
        review = read(review_file)
        if (sha256(review_file) != item["review_sha256"]
            or review["status"] != "REVIEWED_EXTERNAL_CONTROL_INTERRUPTION_NO_NATIVE_TERMINAL_RECORD"
            or review["GT_scores_computed_for_interrupted_partial_output"]
            or (local(review["directory"]) / "status.json").exists()):
            raise ValueError("An additional interruption requires exact preserved evidence, not a fabricated native exit")
        for artifact in review["artifacts"]:
            if sha256(local(artifact["file"])) != artifact["sha256"]:
                raise ValueError("Interrupted-attempt evidence changed")
    required = {(s, m) for s in ("person_tracking", "crowd", "racket") for m in ("DROID_W", "PI3MOS", "BA_TRACK", "WILDGS")}
    if any((r["sequence"], r["method"]) not in required for r in resolutions):
        raise ValueError("A reviewed resolution must belong to an actual requested E14 case")
    if plan["state"] != "ALL_ATTEMPTS_TERMINAL_VISUAL_QA_AND_STAGE_REPORT_PENDING" or {(x["sequence"], x["method"]) for x in plan["jobs"]} != required or len(plan["jobs"]) != 12:
        raise RuntimeError("All twelve real E14 attempts must first be terminal")
    bundle = read(reports / "wildgs_bundle_integrity.json")
    if bundle["status"] != "WILDGS_EIGHT_FILE_BUNDLE_AND_README_ROUNDTRIP_PASS" or bundle["strip_round_trip"] != "PASS":
        raise ValueError("Actual WildGS reproduction bundle integrity must pass")
    bundle_folder = PROJECT / "baselines/wildgs_slam/repro_outputs"
    for row in bundle["files"]:
        if sha256(bundle_folder / row["file"]) != row["sha256"]:
            raise ValueError("WildGS bundle changed since its integrity check")
    e13 = Path(plan["after_E13"])
    e13_review = read(e13 / "map_uncertainty_review.json")
    if not e13_review["native_computation_outputs_complete"]:
        raise ValueError("E13 actual camera/map/uncertainty outputs not accepted")
    e13_evaluation = read(e13 / "evaluation_summary.json")
    e13_qa = reviewed_figures(e13, camera=True)
    datasets = []
    for sequence in ("person_tracking", "crowd", "racket"):
        pointer = reports / ("wild_"+sequence+"_input.json")
        reference = read(pointer)
        if sha256(local(reference["reference"])) != reference["reference_sha256"]:
            raise ValueError("Frozen independent reference changed")
        acquired_file = reports / ("wild_"+sequence+"_data.json")
        acquired = read(acquired_file)
        datasets.append({"sequence": sequence, "frames": reference["expected_frames"], "input_pointer": str(pointer), "input_pointer_sha256": sha256(pointer),
            "acquisition_record_sha256": sha256(acquired_file), "source": acquired["source"],
            "archive_bytes": acquired["archive_bytes"], "archive_sha256": acquired["archive_sha256"],
            "reference_sha256": reference["reference_sha256"], "visual_QA": reviewed_figures(local(reference["external_validation_directory"]))})
    environment_file = reports / "runtime_environment_metadata_snapshot.json"
    environment = read(environment_file)
    if environment["status"] != "READ_ONLY_EXISTING_FOUR_CONDA_PREFIX_PACKAGE_METADATA_RECORDED" or environment["environment_created_or_modified"] or environment["any_extra_GPU_model_launched"]:
        raise ValueError("Require the actual read-only environment metadata snapshot")
    for row in environment["environments"]:
        if sha256(local(row["raw_probe_file"])) != row["raw_probe_sha256"]:
            raise ValueError("Environment metadata source record changed")
    cpu_environment_file = reports / "CPU_evaluation_environment_metadata_snapshot.json"
    cpu_environment = read(cpu_environment_file)
    if cpu_environment["status"] != "READ_ONLY_EXISTING_WINDOWS_CPU_EVALUATION_METADATA_RECORDED" or cpu_environment["environment_created_or_modified"] or cpu_environment["GPU_model_started"]:
        raise ValueError("Require the actual separate CPU evaluation environment metadata")
    weight_manifests = []
    for name in ("droid_assets", "droid_loaded_prior_assets", "pi3mos_assets", "ba_track_assets", "ba_track_dino_assets", "ba_track_hf_prior_assets"):
        path = PROJECT / "reports/SOTA" / (name+".json")
        weight_manifests.append({"file": str(path), "sha256": sha256(path)})
    cases, metric_lines, resource_lines = [], [], []
    accepted = 0
    for original_job in plan["jobs"]:
        selected = [r for r in resolutions if r["method"] == original_job["method"] and r["sequence"] == original_job["sequence"]]
        if len(selected) > 1:
            raise ValueError("Ambiguous independently reviewed case resolution")
        job = {**original_job, **selected[0]} if selected else original_job
        if job["state"] != "ATTEMPT_TERMINAL" or "completed_at_utc" not in job:
            raise RuntimeError("An actual native launch is still active or unattempted")
        case = {"sequence": job["sequence"], "method": job["method"], "native_status": job["native_status"], "controller_exit_code": job["controller_exit_code"]}
        if selected:
            case["original_attempt_preserved"] = original_job
            case["reviewed_resolution"] = selected[0]
        directory = local(job["result_directory"]) if job.get("result_directory") else None
        if directory:
            native = read(directory / "status.json")
            native_contract = read(directory / "execution_contract.json")
            case.update(directory=str(directory), native_status_sha256=sha256(directory / "status.json"),
                execution_contract_sha256=sha256(directory / "execution_contract.json"), wall_seconds=native["wall_seconds"],
                whole_gpu_peak_MiB=native["whole_gpu_peak_used_mib_sampled"])
            case["BA_native_buffer_capacity"] = native_contract.get("BA_actual_buffer_capacity")
            case["native_priors_reused"] = native_contract.get("BA_native_prior_stages_reused", False)
            if case["native_priors_reused"]:
                post_file = directory / "reused_prior_integrity_after_native.json"
                post = read(post_file)
                if (post["status"] != "REUSED_NATIVE_LEARNED_PRIORS_BYTE_IDENTICAL_AFTER_TERMINAL_REPAIR"
                    or post["native_status_sha256"] != case["native_status_sha256"]
                    or post["execution_contract_sha256"] != case["execution_contract_sha256"]
                    or post["source_review_sha256"] != native_contract["BA_native_prior_reuse_review_sha256"]
                    or post["files_checked"] != native_contract["expected_frames"]
                    or len(post["checked_files"]) != post["files_checked"]
                    or post["source_prior_values_modified"] or post["new_model_forwards"]
                    or post["external_GT_or_sensor_depth_read"]
                    or sha256(directory / "review_phase5_ba_reused_prior_integrity.py.executed_source") != post["reviewer_source_sha256"]):
                    raise ValueError("Post-terminal native learned-prior identity review is missing or inconsistent")
                case["post_native_reused_prior_integrity"] = {"file": str(post_file), "sha256": sha256(post_file), "files_checked": post["files_checked"]}
            case["actual_timing_scope"] = native_contract.get("BA_timing_scope")
            case["native_video_visibility_IO_variant"] = native_contract.get("BA_native_video_visibility_copy", "Original native renderer and visibility input retained")
            case["native_video_visibility_IO_review_sha256"] = native_contract.get("BA_native_video_visibility_IO_review_sha256")
            case["WSL_memory_budget_at_launch"] = native_contract.get("WSL_memory_budget_at_launch")
            case["native_fast_mode"] = native_contract.get("native_fast_mode")
            case["native_launch_working_directory"] = native_contract["cwd"]
            case["native_source_commit"] = native_contract.get("source_commit")
            if "command" in native_contract:
                case["actually_started_native_commands"] = [["native", native_contract["command"]]]
            else:
                started_stages = {row["stage"] for row in native.get("stages", []) if row.get("native_subprocess_started", True)}
                case["actually_started_native_commands"] = [row for row in native_contract["commands"] if row[0] in started_stages]
            case["actual_native_stage_terminal_records"] = native.get("stages")
            sampling_file = directory / "gpu_memory.csv"
            if sampling_file.exists():
                with sampling_file.open(newline="") as handle:
                    sample_count = sum(1 for _ in csv.DictReader(handle))
                if sample_count >= 2:
                    _, case["GPU_sampling_review_from_raw_CSV"] = load_sampling(directory)
                else:
                    case["GPU_sampling_review_from_raw_CSV"] = {"status": "INSUFFICIENT_ACTUAL_SAMPLES", "samples": sample_count,
                        "source_sha256": sha256(sampling_file), "maximum_sampling_interval_seconds": None}
            native_video_review = directory / "native_video_figure_review.json"
            if native_video_review.exists():
                video_qa = read(native_video_review)
                if video_qa["status"] != "VISUALLY_REVIEWED_PASS" or any(sha256(directory / row["file"]) != row["sha256"] for row in video_qa["files"]):
                    raise ValueError("Native video examples or their actual visual review changed")
                if sha256(directory / video_qa["selection_file"]) != video_qa["selection_sha256"]:
                    raise ValueError("Native video example selection changed")
                case["native_video_qualitative_review_sha256"] = sha256(native_video_review)
            preparation_file = directory / "resource_preparation_before_capacity_repair.json"
            if preparation_file.exists():
                if sha256(preparation_file) != native_contract.get("BA_capacity_repair_resource_preparation_sha256"):
                    raise ValueError("Capacity-repair resource preparation changed after native launch")
                case["resource_preparation_before_native_launch"] = read(preparation_file)
                case["resource_preparation_sha256"] = sha256(preparation_file)
        evaluation_file = directory / "evaluation_summary.json" if directory else None
        evaluation = read(evaluation_file) if evaluation_file and evaluation_file.exists() else None
        recovered_camera = bool(evaluation and (evaluation.get("native_final_sparse_camera_recovered_after_serialization_failure") or evaluation.get("native_primary_sparse_camera_accepted_with_failed_pipeline")))
        if evaluation and (job.get("external_evaluation_exit_code") == 0 or recovered_camera):
            if evaluation["status"] != "PHASE5_EXTERNAL_CAMERA_EVALUATION_COMPLETED" or not evaluation["figures_visually_reviewed"]:
                raise ValueError("Camera output acceptance/actual image QA is pending")
            case.update(camera_accepted=True, evaluation_sha256=sha256(evaluation_file), metrics=evaluation["metrics"], visual_QA=reviewed_figures(directory, camera=True))
            if recovered_camera:
                recovery_review_file = local(evaluation["sparse_camera_recovery_review"]) if evaluation.get("sparse_camera_recovery_review") else directory / "native_camera_prefix_recovery/recovery_review.json"
                recovery_review = read(recovery_review_file)
                if recovery_review["status"] not in ("COMPLETE_NATIVE_FINAL_SPARSE_CAMERA_PREFIX_RECOVERED_AND_INDEPENDENTLY_CHECKED", "COMPLETE_NATIVE_TERMINATE_CAMERA_RETURN_INDEPENDENTLY_CHECKED"):
                    raise ValueError("Recovered sparse camera source acceptance is missing")
                case["complete_sparse_camera_only_full_pipeline_failed"] = True
                case["failure_review"] = read(directory / "failure_review.json")
                case["camera_recovery_review_sha256"] = sha256(recovery_review_file)
            accepted += 1
            for row in evaluation["metrics"]:
                metric_lines.append("| "+" | ".join(map(scalar, [job["sequence"], job["method"], row["alignment"], row["status"]+(" / recovered sparse camera; pipeline FAILED" if recovered_camera else ""), row["ATE_RMSE"],
                    row["RPE_translation_RMSE"], row["RPE_rotation_RMSE_degrees"], row["valid_pose_frames"], row["native_ground_truth_unit"]]))+" |")
            if job["method"] == "WILDGS":
                inspection = read(directory / "map_uncertainty_review.json")
                if not inspection["native_computation_outputs_complete"]:
                    raise ValueError("Formal WildGS map/uncertainty acceptance missing")
                case["map_review_sha256"] = sha256(directory / "map_uncertainty_review.json")
        else:
            failure_file = directory / "failure_review.json" if directory else plan_file.parent / "failure_reviews" / (job["method"]+"_"+job["sequence"]+".json")
            failure = read(failure_file)
            if failure.get("status") != "REVIEWED_FAILURE_OR_UNAVAILABLE_CAMERA_METRICS" or not failure.get("reason") or not failure.get("evidence"):
                raise ValueError("A failed/unaccepted attempt requires an evidence-based failure review")
            for row in failure["evidence"]:
                if sha256(local(row["file"])) != row["sha256"]:
                    raise ValueError("Failure evidence identity changed")
            case.update(camera_accepted=False, failure_review=failure, failure_review_sha256=sha256(failure_file))
            metric_lines.append(f"| {job['sequence']} | {job['method']} | N/A | {failure.get('classification', 'UNCLASSIFIED')} | N/A | N/A | N/A | N/A | meter |")
        resource = read(directory / "memory_budget_intervention.json") if directory and (directory / "memory_budget_intervention.json").exists() else None
        case["runtime_resource_intervention"] = resource
        if directory:
            initialized = next((r.get("initialized_frontend_calls") for r in case.get("metrics", []) if r.get("initialized_frontend_calls") is not None), None)
            frames = next(x["frames"] for x in datasets if x["sequence"] == job["sequence"])
            resource_label = ("YES: pressure/profiling/extra swap" if resource else
                "D-backed swap prepared before launch; cached priors" if case.get("resource_preparation_before_native_launch") else
                "No mid-run resource change recorded")
            resource_lines.append("| "+" | ".join(map(scalar, [job["sequence"], job["method"], case.get("wall_seconds"), frames/case["wall_seconds"] if case.get("camera_accepted") and case.get("wall_seconds") else None,
                case.get("whole_gpu_peak_MiB"), case.get("GPU_sampling_review_from_raw_CSV", {}).get("maximum_sampling_interval_seconds"), initialized, frames, resource_label]))+" |")
        cases.append(case)
    now = datetime.now(timezone.utc).isoformat()
    text = ["# E13/E14 阶段交付：真实动态相机实验", "", f"交付时间：{now}。12个E14正式案例均已实际尝试并终止，其中{accepted}/12个通过相机输出/独立GT评价与图审。失败和N/A保留在表内；第五阶段整体尚未完成。", "",
        "E13官方Crowd Demo已输出1268帧完整轨迹、142个关键帧、90605个有限Gaussian及142张原生渲染/不确定性图。原生进程仍记exit1：全部计算完成后的active_children清理接口遗漏；独立审查接受已完成输出，不将其改写成干净原生成功。其余CUDA IPC、受控文件访问性能诊断中断和首次缓存配置遗漏的历史记录完整保留。", "",
        "Demo遵循作者fast_mode及400x240 OOM建议，作者原始loader/K与正式共同视图有差异；Demo结果仅用于复现诊断，不混入E14正式同输入比较。线程兼容调用保留原方法计算/同步接口，但调度/全局RNG可能不同，不宣称原生多进程、位级一致或论文分数复现。", "",
        "数据来自固定Wild-SLAM MoCap revision158c7407c513fcf7140d14c2ce6271bc5e0450ec。Person986、Crowd1268、Racket962全部RGB保留；每个数据包均通过完整ZIP/RGB哈希、相机内参、深度可读性和已发布物理时钟审计。公开GT已在RGB时钟上；未附原120Hz原始流及逐次偏移，不能凭空再插值。Person390/391的重复RGB/时钟和略不同GT保留，官方首项最近关联在模型评分前冻结；Racket422/423为相同GT。相邻样本RPE不当作零dt速度。", "",
        "全部正式方法读取相同400x240全帧RGB/K，统一一次去畸变和半像素K缩放。OptiTrack外部参考为MOCAP_GROUND_TRUTH，单位meter；传感器深度和参考位姿不进入RGB-only模型。额外深度均为各自原生学习先验。三个原环境不变，WildGS使用新增独立wildgs_slam环境。模型固定权重、原生内部尺寸/默认窗口/迭代与完整命令详见各execution_contract.json及权重清单。", "",
        "| 序列 | 方法 | 对齐 | 实际指标状态 | ATE | 相邻RPE平移 | 相邻RPE旋转(°) | 有限填充位姿 | GT单位 |", "|---|---|---|---|---:|---:|---:|---:|---|", *metric_lines, "",
        "学习先验的物理尺度未经独立验证；SE3平移列保留尺度诊断，Sim3明确包含后处理尺度对齐。跨序列不把不同真值类型/单位混合平均，也不从ATE单项选总冠军。填充位姿覆盖率、初始化调用比例与显式跟踪丢失率不同：原生未暴露丢失状态时Tracking Failure记N/A。", "",
        "| 序列 | 方法 | 实际执行阶段wall秒 | 请求输入/wall FPS | 定期采样全卡峰值MiB | 最大采样间隔秒 | 初始化后调用数 | 全输入分母 | 资源说明 |", "|---|---|---:|---:|---:|---:|---:|---:|---|", *resource_lines, "",
        "时间包含原生先验、优化、填充与IO；图形界面省略，独立CPU评价不计入。显存为整张GPU采样值，包含桌面且不保证捕捉瞬时峰值。BA-Track Person约570帧时原7.7GiB WSL RAM与2GiB交换耗尽，在同一运行中新增独立8GiB交换文件后继续；完整压力/只读进程栈/命令保留，耗时包含该干预，不用于无条件公平FPS排名。后续预算在启动时记录。", "",
        "采样循环的请求间隔为1秒，查询/调度等待和未成功记录的查询可造成更长的实际间隔；逐案例最大间隔由原始CSV重新核算，不把请求周期表述为无缺口连续监测。WildGS Racket和Person的最大间隔分别为651.17及1823.43秒；新资源图按max(5秒,5×中位间隔)断线，缺失值不插补，Racket修订前图另存快照。此前已验收图件保持原SHA，间隔限制另在本表披露。新启动案例对实际查询错误另存日志，既有未记录原因的缺口不事后推测成特定驱动故障。", "",
        "正式WildGS保留原生fast_mode=False：完整后处理含20,000次地图精修、全轨迹补全及逐帧非关键帧相机位姿精修，均计入wall。官方Demo采用不同fast_mode，不能用Demo耗时代替正式同输入案例的耗时，也不能把后处理后的相机误差表述为纯实时前端误差。", "",
        "BA稠密阶段配置沿用README链接的作者Demo脚本：grid_size=12、niter=300；它与Python CLI自身的默认值不同，未从本次GT分数选择。主相机始终按此前冻结的原生稀疏SLAM阶段评价，稠密结果单列诊断；未执行的稠密阶段保留为未执行。脚本和训练域来源详见[BA原生协议审查](BA_documented_protocol_source_review.json)。", "",
        "所有交付图均逐张查看，PNG及SVG哈希绑定figure_review.json。WildGS原生大图保留，仅固定首/中/末关键帧作为图审子集；前端Metric Depth不是传感器GT，原生uint8 RGB差值显示不用于定量L1。该MoCap库没有独立像素运动或骨骼标签，因此不计算M1/M2分割/骨骼准确率，也不能据相机误差直接宣称游戏专属失效。", "",
        "以下证据入口包含实际状态、配置、原始日志、失败说明与图审：", "", f"- E13：{e13}", f"- WildGS标准复现包：{bundle_folder}", f"- E14原生批次计划/日志：{plan_file.parent}", "- 数据/权重审计：reports/PHASE5/phase5_dataset_audit.md、reports/SOTA/E13_WILDGS_READINESS.md及三个原模型assets清单。"]
    for case in cases:
        text.append(f"- {case['sequence']} / {case['method']} / {case['native_status']}：{case.get('directory', 'see batch controller log and failure review')}")
        if case.get("failure_review"):
            text.append("  原因："+case["failure_review"]["reason"])
    if capacity_plan_file.exists():
        text += ["", "BA-Track原Crowd尝试处理1023帧后触发原生1024缓存上限，未产生完整相机；这属于长序列容量配置问题，不是已证实的动态/游戏域失效，亦非OOM。未完成案例按作者提示将存储容量扩到2048，原窗口、400点、迭代/阈值、权重、种子和完整1268 RGB/K保持不变。其已完成的1268份原生学习深度经逐文件SHA/数值核验后输入复用；修复尝试的wall只计实际新执行的稀疏/稠密阶段，不冒称重新执行全部先验的冷启动耗时，原先验阶段实测时间单独保留。原失败与复用审核完整保存；未按GT分数挑选更好的运行。"]
    if interruptions:
        text += ["", f"另有{len(interruptions)}次已受检的控制中断记录：第一次2048容量Crowd修复在88次前端返回后，Windows控制器与Linux原生进程均消失，未写原生终态或完整相机，退出码未知，不伪造OOM或运动失效结论。Windows未观察到重启，具体中断原因未确认。原始日志/部分输出保留；用户继续指令后，恢复同一已有资源预算，按相同完整输入与原生设置从第0帧继续这条未完成案例。没有成功模型或GT分数用于选择继续。实际控制器记录共{len(plan['jobs'])+len(resolutions)+len(interruptions)}条，与12个正式方法/序列组合区分；详见[E14中断记录](E14_interrupted_controller_attempts.json)。"]
    text += ["", "各方法的审计输出量不同：逐帧先验、点轨迹/概率、关键帧不确定性和地图观察的CPU复制/压缩/写盘成本均包含在wall内。没有完整输入处理证据的失败案例FPS记N/A，不能拿请求总帧数除以部分运行时间制造吞吐。失败但已接受完整主相机的wall/FPS只覆盖实际执行到故障处的阶段，未启动的dense等阶段不计时；不可称为完整成功流程耗时。所列FPS不等同于相同记录开销下的纯算法速度。",
        "后续新启动的BA案例保留作者完整视频绘制，仅将每次绘图的可见性张量一次性复制到CPU，避免逐点GPU同步；既有运行不改动、不重放。12项CPU原生绘图RGB字节比较通过，属于绘图IO核验，不是GPU全模型逐位等价证明。实际采用情况及审查SHA按案例执行契约记录；不同IO变体的wall不能直接解释为模型加速。"]
    diagnostic_reports = []
    for name in ("person_camera_error_audit", "crowd_camera_error_audit", "pi3mos_crowd_pose_completion_audit", "racket_camera_error_audit", "racket_shared_peak_RGB_review"):
        diagnostic_file = reports / (name+".json")
        if diagnostic_file.exists():
            diagnostic_reports.append({"file": str(diagnostic_file), "sha256": sha256(diagnostic_file)})
    if diagnostic_reports:
        text += ["", "已完成相机结果的事后误差定位另存独立快照，保留原完整主分母及对齐，不按诊断子集重新拟合成绩。Pi3MOS Crowd原生最终缓冲间隔9—120覆盖早期平移异常；其余位姿由保存的相对SE3递归补全，并非线性插值。单次重叠不能证明物体运动、Mask或游戏域导致误差。详见[Person误差核验](person_camera_error_audit.md)、[Crowd误差核验](crowd_camera_error_audit.md)、[Pi3MOS位姿补全核验](pi3mos_crowd_pose_completion_audit.md)、[Racket误差核验](racket_camera_error_audit.md)及[共同峰值原始RGB审查](racket_shared_peak_RGB_review.md)。"]
    text += ["", "实际环境的CPU只读版本快照时间："+environment["created_at_utc"]+"；未修改任何环境、导入Torch或另开GPU任务。完整原生命令、实际启动阶段、工作目录、原始日志和权重清单SHA见[E13/E14阶段证据](E13_E14_stage_evidence.json)及各案例execution_contract.json；未执行的dense等计划阶段不会计入已启动命令列表。", "",
        "| Conda前缀 | Python | Torch发行包 | NumPy |", "|---|---|---|---|"]
    for row in environment["environments"]:
        text.append(f"| {row['prefix']} | {row['Python'].split()[0]} | {row['packages']['torch']} | {row['packages']['numpy']} |")
    text += ["", f"独立CPU评价/绘图环境：{cpu_environment['prefix']}；Python {cpu_environment['Python'].split()[0]}、NumPy {cpu_environment['packages']['numpy']}、SciPy {cpu_environment['packages']['scipy']}、Matplotlib {cpu_environment['packages']['matplotlib']}。GPU模型环境与CPU评价环境分别记录，未假设其依赖版本相同。"]
    text += ["", "固定数据包（压缩字节数及原SHA，Crowd包同时供Demo和正式案例使用，不重复下载）："]
    for row in datasets:
        text.append(f"- {row['sequence']}：{row['archive_bytes']} bytes；SHA256 {row['archive_sha256']}")
    backup_state = reports / "user_backup_state_20261101.json"
    if backup_state.exists():
        text += ["", "原WSL备份ext4.vhdx在阶段执行期间由用户删除并明确确认；备份清单仍保留，当前不声明该大文件存在。现有WSL、原独立环境和旧实验未被本阶段删除或重跑。"]
    text += ["", "下一步按已冻结协议获取MOVi-E test分片0–3各第一条TFRecord，先验CRC、实际字段、相机C2W、距离深度、物体姿态/光流，再进行M1/M2评价与预定重复。之后逐条接入Bonn，最后根据独立标签和真实重复结果做E17判断。当前不训练自有网络，不提前选M1/M2，不宣布M3、骨骼或复杂游戏镜头得到验证。", "",
        "[WildGS官方代码](https://github.com/GradientSpaces/WildGS-SLAM)；[Wild-SLAM固定数据源](https://huggingface.co/datasets/gradient-spaces/Wild-SLAM/tree/158c7407c513fcf7140d14c2ce6271bc5e0450ec/Mocap/scene1)。", ""]
    report_file.write_text("\n".join(text), encoding="utf-8")
    evidence_file = reports / "E13_E14_stage_evidence.json"
    write_json(evidence_file, {"created_at_utc": now, "E13": {"directory": str(e13), "native_status": read(e13 / "status.json"),
        "output_review": e13_review, "evaluation_sha256": sha256(e13 / "evaluation_summary.json"), "visual_QA": e13_qa,
        "actual_GPU_sampling_review": load_sampling(e13)[1]},
        "E14_datasets": datasets, "E14_cases": cases, "additional_reviewed_interrupted_controller_attempts": interruptions,
        "post_hoc_camera_diagnostic_snapshots": diagnostic_reports,
        "environment_metadata_snapshot": {"file": str(environment_file), "sha256": sha256(environment_file)},
        "CPU_evaluation_environment_metadata_snapshot": {"file": str(cpu_environment_file), "sha256": sha256(cpu_environment_file)},
        "pinned_model_weight_manifests": weight_manifests,
        "BA_documented_protocol_source_review": {"file": str(reports / "BA_documented_protocol_source_review.json"), "sha256": sha256(reports / "BA_documented_protocol_source_review.json")},
        "batch_plan_sha256": sha256(plan_file), "E13_bundle_integrity_sha256": sha256(reports / "wildgs_bundle_integrity.json")})
    gate = {"status": "E13_E14_REVIEWED_STAGE_REPORT_WRITTEN", "report": str(report_file), "report_sha256": sha256(report_file),
        "evidence": str(evidence_file), "evidence_sha256": sha256(evidence_file), "delivered_at_utc": now,
        "E14_terminal_cases": 12, "E14_original_controller_attempt_records": len(plan["jobs"]),
        "E14_additional_reviewed_resolution_attempts": len(resolutions),
        "E14_additional_reviewed_external_interruptions": len(interruptions),
        "E14_total_controller_attempt_records": len(plan["jobs"])+len(resolutions)+len(interruptions),
        "E14_camera_accepted_cases": accepted, "all_native_exits_successful": False,
        "failures_and_output_acceptance_distinguished": True, "whole_phase5_complete": False}
    write_json(gate_file, gate)
    print(json.dumps(gate))


if __name__ == "__main__":
    main()

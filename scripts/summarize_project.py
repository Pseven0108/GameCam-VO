from __future__ import annotations
import _bootstrap
import csv
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from gamecam_vo.common import PROJECT, write_csv, write_json


def load_json(path: Path, fallback=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else fallback


def main():
    reports = PROJECT / "reports"
    reports.mkdir(exist_ok=True)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    latest = load_json(PROJECT / "results/E0/latest_run.json", {})
    e0_run = Path(latest["directory"]) if latest.get("directory") else None
    validation = load_json(e0_run / "validation.json", {}) if e0_run else {}
    tests = load_json(PROJECT / "logs/latest_tests.json", {})
    access = load_json(PROJECT / "docs/sources/WildWorld_access_check.json", {})
    request = load_json(PROJECT / "reports/dataset_access_status.json", {})
    pending_review = request.get("request_status") == "pending_author_review"
    plan = load_json(PROJECT / "docs/sources/WildWorld_small_sample_plan.json", [])
    environment = load_json(PROJECT / "reports/E0_environment_report.json", {})
    items = {}
    for record in plan:
        sequence = record["path"].split("/")[1]
        items[sequence] = items.get(sequence, 0) + int(record["size_bytes"])
    first = next(iter(items), None)
    first_bytes = items[first] + 62854 if first else None
    total_bytes = sum(items.values()) + 62854 if items else None
    measurements = []
    orb_runs = []
    for summary_path in sorted((PROJECT / "results/E1/orb_essential").glob("*/*/run_summary.json")):
        summary = load_json(summary_path, {})
        orb_runs.append(summary)
        metrics_path = summary_path.parent / "metrics.csv"
        if metrics_path.exists():
            with metrics_path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    measurements.append(row | {"result_directory": str(summary_path.parent)})
    compare_columns = ["baseline", "sequence_id", "alignment", "status", "expected_frames", "valid_pose_frames",
                       "failed_frames", "pose_coverage", "failure_rate", "ATE_RMSE", "RPE_translation_RMSE",
                       "RPE_rotation_RMSE_degrees", "RotErr_RMSE_degrees", "TransErr_RMSE", "tracking_pair_success",
                       "input_fps", "prediction_scale_status", "native_ground_truth_unit", "result_directory"]
    write_csv(PROJECT / "results/comparison/all_baselines_metrics.csv", measurements, compare_columns)
    statuses = [{"experiment": "E0", "baseline": "data_validation", "status": validation.get("status", "NOT RUN"),
                 "reason": "No trusted real-data camera trajectory" if not validation.get("e0_passed") else "See E0 validation artifact"}]
    definitions = [("E1-A", "orb_essential", "02_orb_essential.md", "ORB + Essential Matrix"),
                   ("E1-B", "orb_slam3", "03_orb_slam3.md", "ORB-SLAM3"),
                   ("E2", "droid_slam", "04_droid_slam.md", "DROID-SLAM"),
                   ("E3", "monst3r", "05_monst3r.md", "MonST3R"),
                   ("E4-A", "vggt", "06_vggt.md", "VGGT"),
                   ("E4-B", "megasam", "07_megasam.md", "MegaSaM"),
                   ("E5", "dynamic_mask", "09_dynamic_mask_ablation.md", "动态区域过滤消融")]
    for experiment, baseline, filename, title in definitions:
        ran = baseline == "orb_essential" and bool(orb_runs)
        status = "RUN (see individual run summaries)" if ran else "NOT RUN"
        reason = "See saved per-run failures and coverage" if ran else "E0 real-data validation prerequisite is unmet"
        statuses.append({"experiment": experiment, "baseline": baseline, "status": status, "reason": reason})
        text = [f"# {experiment} {title}", "", f"状态：{status}", "", f"原因：{reason}。", ""]
        if baseline == "orb_essential":
            text += ["已实现 ORB、Hamming BFMatcher、KNN/Lowe ratio、Essential RANSAC、recoverPose 和 T_wc 积分。",
                     "配置保存在 configs/experiment.yaml。采用统一片段读取与逐帧真实 K；缩放图像时同步缩放 K。",
                     "平移每条边只有方向，单位步长仅为任意规范；SE(3) 结果属于尺度不匹配诊断，Sim(3) 也不构成米制精度证明。",
                     "低视差、纯旋转退化和匹配不足被记为失败；继续尝试与上次成功定位帧关联，保留全部期望帧作为覆盖率分母。",
                     "", f"真实数据运行数量：{len(orb_runs)}。测试输入均为已知构造，不是 WildWorld 实验结果。",
                     "未运行时没有 estimated_trajectory、ATE 或 FPS 实测结果。"]
        elif baseline == "orb_slam3":
            text += ["官方来源：https://github.com/UZ-SLAMLab/ORB_SLAM3",
                     "读取到的上游 HEAD：4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4。",
                     "官方 README 列出 C++ 编译器、CMake、Pangolin、OpenCV、Eigen3 等依赖；许可证 GPLv3。",
                     "Windows 的 Python OpenCV wheel 不能替代 C++ 开发依赖。",
                     "已检测到 WSL2 Ubuntu 和 g++；无配置文件启动的探测未发现 cmake 或 pkg-config。",
                     "WSL 登录配置曾因含空格的 PATH 导致 shell 错误；用 bash --noprofile --norc 完成只读探测。",
                     "E0 尚未通过，本轮没有克隆、编译或执行 ORB-SLAM3，不能将其记为编译失败。"]
        elif baseline == "dynamic_mask":
            text += ["真实 Mask 的存在与语义未验证；未制造 Oracle Mask。",
                     "没有运行 SAM2 或其他掩码模型；A/B/C 三组结果全部缺失。",
                     "只有基础基线获得稳定真实结果后才进行这一阶段。"]
        else:
            text += ["没有安装本模型、下载权重或执行推理；没有真实轨迹、GPU 显存或性能测量。",
                     "尚未实现本模型适配器。取得 E0/E1 真实结果后，再读取官方 README、核对许可及硬件需求。",
                     "VGGT 的短片段几何预测与在线 SLAM 跟踪须分开解释。"]
        (reports / filename).write_text("\n".join(text) + "\n", encoding="utf-8")
    write_csv(PROJECT / "results/comparison/experiment_status.csv", statuses)
    project_status = {"generated_china_time": now, "milestone_achieved": bool(validation.get("e0_passed") and orb_runs),
                      "e0_status": validation.get("status", "NOT RUN"), "real_sequence_count": len(validation.get("sequences", [])),
                      "real_orb_runs": len(orb_runs), "unit_test_status": tests.get("status", "UNKNOWN"),
                      "dataset_access_gated": access.get("gated"), "anonymous_access_status": access.get("status_code"),
                      "user_access_request_status": request.get("request_status", "UNKNOWN"),
                      "dataset_bytes_downloaded": access.get("dataset_bytes_downloaded", 0), "model_weights_downloaded_bytes": 0,
                      "first_sample_proposed_bytes_including_edges": first_bytes,
                      "six_sample_proposed_bytes_including_edges": total_bytes}
    write_json(reports / "project_status.json", project_status)
    lines = ["# GameCam-VO 项目状态", "", f"更新时间（Asia/Shanghai）：{now}", "",
             "首个里程碑「E0 数据验证通过 + E1-A 真实基线」尚未达到。", "",
             f"项目目录：{PROJECT}", "Conda 环境：gamecam-vo；Python " + environment.get("python", "unknown").splitlines()[0],
             "", "已完成：独立环境、依赖锁定、数据发现与有界读取、源依据明确的 GL→CV 位姿转换、",
             "同步/坐标/长度单位准入、轨迹图与异常保留、ORB 几何基线、双对齐评价、代码级测试。",
             "", f"E0 实际入口运行：{validation.get('status', 'NOT RUN')}；发现真实样本 {len(validation.get('sequences', []))} 条。",
             "E1-A 入口返回 NOT RUN；其余阶段均未运行。未产生真实轨迹、精度、速度或比较结论。",
             "", "证据：",
             f"- E0 归档：{e0_run}",
             "- reports/E0_environment_report.md",
             "- logs/E0_first_local_run.log",
             "- logs/E1_A_gate_check.log",
             f"- 最终单元测试：{tests.get('status', 'UNKNOWN')}；{tests.get('log', '')}",
             "- 初次测试因系统临时目录权限产生 6 个 setup errors，日志保留在 logs/unit_tests.log；",
             "  已通过项目内唯一临时目录解决，未删除失败记录。",
             "", "当前阻塞：用户确认本机尚未下载数据；WildWorld 为 manual-gated 数据集，匿名文件 HEAD 返回 HTTP 401。",
             ("用户已提交访问申请；提供的截图显示正在等待仓库作者审核，尚未获批。" if pending_review else
              "官方申请需要本人提供姓名、国家、机构并确认许可。"),
             "", ("当前步骤：等待作者批准；申请已提交。" if pending_review else
                  "需要用户完成：[申请 WildWorld 数据访问](https://huggingface.co/datasets/AlayaLab/WildWorld)。"),
             "获批后在本机进行 Hugging Face 登录，或直接提供已合法取得的样本目录。",
             "随后按 reports/data_acquisition_plan.md 的有界清单推进。", "", "各阶段状态：", "",
             "| 阶段 | Baseline | 状态 |", "|---|---|---|"]
    lines += [f"| {row['experiment']} | {row['baseline']} | {row['status']} |" for row in statuses]
    (reports / "00_project_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    e0_text = ["# E0 数据验证与证据", "", f"状态：{validation.get('status', 'NOT RUN')}", "",
               "没有真实样本，故没有执行真实相机位姿解算、同步验证、骨骼投影审查或轨迹误差评价。",
               "已保存空样本 manifest、仅含表头的 inspection CSV、明确阻塞的 validation JSON 与入口日志。",
               "未生成 normalized_ground_truth.csv、pose_statistics.csv 或轨迹 PNG，避免用空文件/自造轨迹充当实测交付物。",
               "", "官方依据已核对：camera.pos 为世界中的相机中心；camera.rot 为 XYZW、OpenGL camera-to-world。",
               "官方渲染代码将世界点乘 R 的逆，再翻转相机 Y/Z；本项目保存 T_wc_cv = [R_wc_gl diag(1,-1,-1), p_w]。",
               "原生世界坐标保留。物理世界轴方向、长度单位与畸变证据仍未确认。",
               "官方渲染例程按行配帧只支持候选索引关联；本工程还检查计数、PTS、唯一关联与独立审查证据。",
               "", "来源：[官方 README](https://github.com/AlayaLab/WildWorld)；",
               "[官方投影代码](https://github.com/AlayaLab/WildWorld/blob/main/scripts/render_skeleton_video.py)。",
               "本地源文件与修订证据在 docs/sources/，只用于本地科研核对。",
               "", "数据到位后的 E0 必须同时满足：坐标依据、单调/唯一时间或独立确认的帧映射、",
               "可追溯长度单位与畸变说明、投影/RGB 审查、有效相机与内参。",
               "每个样本最多解码默认 15 秒；异常区间完整保留；候选 GT 明确标记不可信。",
               "", f"完整运行归档：{e0_run}"]
    (reports / "01_dataset_validation.md").write_text("\n".join(e0_text) + "\n", encoding="utf-8")
    comparison = ["# Baseline 比较", "", f"实际指标行数：{len(measurements)}。",
                  "没有真实运行时比较 CSV 仅包含列定义；NOT RUN 状态另存 experiment_status.csv。",
                  "不得使用单元测试数据作为任何模型在 WildWorld 上的准确率或性能结果。",
                  "", "评价协议：同一 E0 片段、同一采样与真值，按显式时间戳唯一关联，不插值补全失败帧。",
                  "分别输出 SE(3) / Sim(3) ATE、RPE 平移与旋转 RMSE、全局 RotErr、",
                  "TransErr（定义为对应 RPE 平移 RMSE）、有效帧/失败率、有效 RPE 对数和输入吞吐。",
                  "RPE 使用期望采样序列的固定 lag，不跨缺失帧重排相邻关系；位置对齐退化时指标为空并说明原因。",
                  "跟踪成功率的分母包含全部期望运动对；初始化原点另外计入 pose coverage。",
                  "单目 SE(3) 在无可靠尺度时仅作诊断；全局 Sim(3) 不能证明米制精度，亦不能修复每条边的尺度歧义。",
                  "", "结果表：results/comparison/all_baselines_metrics.csv。"]
    for name in ("08_baseline_comparison.md", "baseline_comparison.md"):
        (reports / name).write_text("\n".join(comparison) + "\n", encoding="utf-8")
    (reports / "E5_dynamic_mask_ablation.md").write_text((reports / "09_dynamic_mask_ablation.md").read_text(encoding="utf-8"), encoding="utf-8")
    decision = ["# 下一阶段研究决策", "", "状态：DEFERRED — 缺少 E0–E5 真实证据。",
                "", "本轮不选择 M1、M2 或 M3，不宣称某类场景最难，也不报告模型优劣。",
                "优先事项是获得合法小样本，审查相机投影与同步，再获得 ORB/E1-B 的真实失效记录。",
                "M1 需要掩码消融与几何残差支持；M2 需要骨骼坐标、时间与可用性验证；M3 需要逐帧 K/FOV 变化及对应误差证据。",
                "目前三类证据均不足。8GB GPU/16GB RAM 是后续模型可行性检查的约束，不构成预先排除或性能结论。"]
    (reports / "10_research_direction_decision.md").write_text("\n".join(decision) + "\n", encoding="utf-8")
    plan_lines = ["# WildWorld 小样本取得方案", "", "状态：PROPOSED / NOT DOWNLOADED", "",
                  "数据源：[官方 Hugging Face 数据集](https://huggingface.co/datasets/AlayaLab/WildWorld)。",
                  "数据修订：54e98414dc58579528a6e1933a56d0d640e442df。",
                  "官方元数据 gated=manual；文件内容匿名 HEAD HTTP 401，下载字节为 0。",
                  "许可为非商业研究用途且禁止再分发。",
                  ("用户已提交访问申请，截图显示等待作者审核；尚无获批证据。" if pending_review else
                   "需本人在网页填写信息并确认，代理未代填或提交。"),
                  "", "先取 1 条完整原始序列，解码其中 15 秒进行 E0；链路通过后再处理 6 条各 15 秒。",
                  "远端按完整序列提供文件，清单大小不等于仅 15 秒的视频下载大小。",
                  "文件限 rgb.mp4、state.csv、skeleton.npz 与一个共享 skeleton_edges.json。",
                  "第一轮不取 depth.mkv 或模型权重。所选 ID 仅按目录顺序提案，场景类别未审查；",
                  "不宣称覆盖普通移动、战斗或遮挡类别，需先抽帧核对后再决定正式样本。", ""]
    if first:
        plan_lines += [f"首条：{first}，加骨骼连线共 {first_bytes:,} bytes（{first_bytes/1024**2:.2f} MiB）。",
                       f"六条加共享连线共 {total_bytes:,} bytes（{total_bytes/1024**3:.3f} GiB）。", "",
                       "| 候选序列 | RGB+state+skeleton bytes |", "|---|---:|"]
        plan_lines += [f"| {name} | {size:,} |" for name, size in items.items()]
    plan_lines += ["", "逐文件大小与对象标识见 docs/sources/WildWorld_small_sample_plan.json。",
                   "访问申请获批并完成本地认证后再执行此清单，不执行全库 snapshot_download。",
                   "已下载数据的本地预期结构：data/WildWorld/data_part1/<id>/{rgb.mp4,state.csv,skeleton.npz}。",
                   "共享 skeleton_edges.json 放在 data/WildWorld/；配置 roots 指向 data/WildWorld/data_part1。",
                   "若提供其他路径，直接在 configs/dataset.yaml 设置，无需移动原始文件。"]
    (reports / "data_acquisition_plan.md").write_text("\n".join(plan_lines) + "\n", encoding="utf-8")
    print(json.dumps(project_status, ensure_ascii=False))


if __name__ == "__main__":
    if (PROJECT / "configs/data_strategy.yaml").is_file():
        from summarize_public_experiments import main as summarize_public
        summarize_public()
    else:
        main()

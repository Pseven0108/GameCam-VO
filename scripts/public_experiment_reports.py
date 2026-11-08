"""Evidence-grounded reports for the first complete public game samples."""
from __future__ import annotations
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from gamecam_vo.common import PROJECT, write_csv, write_json
from datasets.mvs_synth.parser import read_camera


def load(path, default=None):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8-sig")) if p.is_file() else default


def rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def e0(identifier):
    pointer = load(PROJECT / "results" / identifier / "latest_run.json", {})
    root = load(Path(pointer["directory"]) / "validation.json", {}) if pointer else {}
    if not root.get("e0_passed"):
        raise ValueError(f"Real-data report requires completed {identifier}")
    folder = Path(root["result_directory"]) / root["sequences"][0]["sequence_id"]
    return root, load(folder / "validation.json"), folder


def runs(identifier):
    return [load(p) for p in sorted((PROJECT / "results" / identifier).rglob("run_summary.json"))]


def metrics(records):
    data = []
    for r in records:
        folder = Path(r["result_directory"])
        data.extend(row | {"run_id": folder.name, "result_directory": str(folder), "execution_status": r["status"],
                           "fatal_error": r.get("fatal_error"), "experiment_id": r["experiment_id"],
                           "experiment_variant": r.get("experiment_variant", "distance50_default")}
                    for row in rows(folder / "metrics.csv"))
    return data


def fmt(value):
    if value is None or value == "":
        return "N/A"
    try:
        return f"{float(value):.6g}"
    except (ValueError, TypeError):
        return str(value).replace("|", "/")


def table(data, columns):
    if not data:
        return "NOT RUN — 没有实测指标。"
    return "\n".join(["| " + " | ".join(v for _, v in columns) + " |", "|" + "---|" * len(columns)] +
                     ["| " + " | ".join(fmt(row.get(k)) for k, _ in columns) + " |" for row in data])


def metric_table(data):
    return table(data, [("run_id", "运行"), ("experiment_variant", "配置"), ("alignment", "对齐"),
                        ("valid_pose_frames", "有效帧"), ("expected_frames", "总帧"), ("ATE_RMSE", "ATE"),
                        ("RPE_translation_RMSE", "RPE平移"), ("RPE_rotation_RMSE_degrees", "RPE旋转°"),
                        ("valid_rpe_pairs", "有效RPE对"), ("tracking_pair_success", "运动对成功率"), ("input_fps", "程序FPS")])


def run_links(records):
    out = []
    for r in records:
        folder = Path(r["result_directory"])
        log = folder / ("native_stdout.log" if r["baseline"] == "ORB-SLAM3" else "tracking_log.txt")
        out.append(f"- [{folder.name}]({(folder/'run_summary.json').as_posix()})；[逐帧日志]({log.as_posix()})；状态 {r['status']}，fatal_error={r.get('fatal_error')}。")
    return "\n".join(out)


def failures(records):
    result = []
    for r in records:
        if r.get("fatal_error") or r.get("baseline") != "ORB+Essential":
            continue
        counts = Counter(row["reason"].split(":", 1)[0] for row in rows(Path(r["result_directory"]) / "tracking_status.csv") if row["status"] == "failed")
        for reason, count in sorted(counts.items()):
            result.append({"run_id": Path(r["result_directory"]).name, "experiment_variant": r.get("experiment_variant", "distance50_default"),
                           "dynamic_mask_source": r["dynamic_mask_source"], "reason": reason, "failed_frames": count})
    return result


def report(name, *paragraphs):
    (PROJECT / "reports" / name).write_text("\n\n".join(map(str, paragraphs)) + "\n", encoding="utf-8")


def main():
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    m, ml, md = e0("E0_MVS")
    o, ol, od = e0("E0_OMNI")
    mr, ar, br, sr = [runs(tag) for tag in ("E1A_MVS", "E1A_OMNI", "E5_OMNI", "E1B_OMNI")]
    mm, am, bm, sm = [metrics(r) for r in (mr, ar, br, sr)]
    tests = load(PROJECT / "logs/latest_tests.json", {})
    fp = Path(load(PROJECT / "reports/latest_figures.json")["directory"])
    ap = Path(load(PROJECT / "results/E5_OMNI/latest_analysis.json")["directory"])
    ab = rows(ap / "paired_ablation.csv")
    model = load(PROJECT / "reports/monst3r_preflight.json", {})
    slam_status = sr[-1]["status"] if sr else "NOT RUN — see build logs"
    slam_measured = next((r for r in sm if r["alignment"] == "Sim3" and r["status"] == "COMPUTED"), {})
    primary = next((r for r in mm if r["alignment"] == "Sim3" and r["status"] == "COMPUTED" and r["experiment_variant"] == "distance50_default"), {})
    raw_root = PROJECT / "data/mvs_synth/GTAV_540/0000"
    counts = {kind: len(list((raw_root/kind).glob("*."+ext))) for kind, ext in (("images","png"),("depths","exr"),("poses","json"))}
    diagnostics = [{"frame": p.stem, **read_camera(p)["diagnostics"]} for p in sorted((raw_root/"poses").glob("*.json"))]
    write_json(PROJECT / "reports/mvs_actual_camera_diagnostics.json", {"source": "Actual local camera JSON files, not unit fixtures", "partial_or_complete": "complete", "frames": diagnostics})
    ma = [load(p) for p in (PROJECT / "logs/acquisition_mvs").glob("*/download_manifest.json")]
    ma = [a for a in ma if a.get("mirror")]
    status = {"updated_china_time": now, "primary_milestone_achieved": bool(m.get("e0_passed") and primary),
              "milestone_scope": "Complete real game sequence E0 + RGB-only execution + actual metrics; not stable full-sequence tracking",
              "active_dataset_order": ["MVS-Synth", "OmniWorld-Game", "WildWorld"], "mvs_e0_status": m["status"],
              "mvs_local_raw_file_counts": counts, "mvs_orb_attempts_including_software_failure": len(mr),
              "mvs_primary_valid_pose_frames": primary.get("valid_pose_frames"), "mvs_mirror_authorized": True,
              "mvs_mirror_complete": any(a.get("status") == "COMPLETE_SELECTED_SAMPLE" for a in ma),
              "omni_e0_status": o["status"], "omni_pose_provenance": "ESTIMATED_REFERENCE", "omni_orb_runs": len(ar),
              "omni_dataset_mask_runs": len(br), "omni_orbslam3_status": slam_status,
              "omni_orbslam3_valid_pose_frames": slam_measured.get("valid_pose_frames"),
              "monst3r_status": model.get("status", "NOT RUN"), "predicted_mask_C": "NOT RUN",
              "wildworld_access": "pending_author_review", "unit_tests": tests.get("status", "UNKNOWN"),
              "paired_ablation_directory": str(ap), "figure_directory": str(fp)}
    for name in ("public_experiment_status.json", "project_status.json"):
        write_json(PROJECT / "reports" / name, status)
    combined = mm + am + bm + sm
    failure_rows = failures(mr + ar + br)
    write_csv(PROJECT / "results/comparison/tracking_failure_reasons.csv", failure_rows)
    columns = list(dict.fromkeys(k for r in combined for k in r))
    for tag, data in (("mvs_synth", mm), ("omniworld_game", am+bm+sm)):
        write_csv(PROJECT / "results/comparison" / tag / "metrics.csv", data, columns)
    write_csv(PROJECT / "results/comparison/all_baselines_metrics.csv", combined, columns)
    report("00_project_status.md", "# GameCam-VO 当前状态", f"更新时间（Asia/Shanghai）：{now}",
           f"首要里程碑完成：{status['primary_milestone_achieved']}。完整 MVS 0000 真实游戏渲染序列 E0={m['status']}，已运行 RGB-only ORB+Essential，取得实测指标；算法覆盖率较低，不代表精度已通过。",
           f"OmniWorld 完整场景 c5e5ed9a4462 / split_0 共 132 帧，E0={o['status']}，A/B 各 2 种配置已完成。POSE_PROVENANCE = ESTIMATED_REFERENCE。",
           f"E1B_OMNI / ORB-SLAM3：{slam_status}。E3_OMNI / MonST3R：{model.get('status', 'NOT RUN')}。C predicted mask：NOT RUN。",
           f"工程测试：{tests.get('status')}；[日志]({Path(tests.get('log','')).as_posix()})。合成单元测试不进入真实实验指标。",
           "项目继续使用 D:/aaa/GameCam-VO 与 Conda gamecam-vo，旧代码、结果和失败日志保留；报告见下列各数据集、消融与决策文件。")
    report("dataset_comparison.md", "# 数据集策略与实际结果", "分数据集独立评价，不汇总跨集 ATE；native_game_unit 与 reference_unit 不可直接比较。",
           "| 数据集 | 本轮完整样本 | 位姿来源 | 本轮状态 |\n|---|---|---|---|\n"
           f"| MVS-Synth / GTA V | 0000，100 帧 / 300 文件 | ENGINE_GROUND_TRUTH | E0 {m['status']}；RGB-only 完成 |\n"
           f"| OmniWorld-Game | c5e5ed9a4462 / split_0，132 帧 | ESTIMATED_REFERENCE | E0 {o['status']}；A/B 完成；ORB-SLAM3 见专报 |\n"
           "| WildWorld | 未下载 | 原计划保留，尚未本地验证 | 等待作者审核 |",
           "MVS：PNG + EXR + W2C JSON，旋转块 det=-1，经固定世界 Z 反射与有界精度修正后输出 T_wc。保留原矩阵和相机中心。未提供采集 FPS，不猜秒数或米制单位。限研究/教育用途。",
           "Omni：split_info 明确编号映射，WXYZ W2C 优化参考、编码深度与 GDINO 模型掩码。Metric Scale 不会使估计参考变成独立引擎 GT；本轮未采用 metric scale。许可 CC-BY-NC-SA 4.0，并受原游戏内容条款约束。",
           "本次默认 MVS 位姿覆盖 23/100，Omni A 为 7/132、B 为 4/132。只能描述单序列观测，不能把差异归因于动态程度；更不能据两套 ATE 数值大小判断精度优劣。",
           "首组真实实验工程里程碑已达成。动态掩码硬过滤尚未证明有效，下一步应先稳定基线与扩展独立 GT。",
           "来源：[MVS 官方页](https://phuang17.github.io/DeepMVS/mvs-synth.html)、[MVS 官方投影代码](https://github.com/phuang17/DeepMVS/blob/4276bf17f965d08c31faf814fc54c80883e3373f/python/generate_volume_train.py)、[Omni 官方数据卡](https://huggingface.co/datasets/InternRobotics/OmniWorld/tree/4e34897a2fcf8e1cc44b1ae8d2bbd0188c8f2841)。")
    projection = ml["depth_reprojection"]
    errors = [r["median_relative_depth_error"] for r in projection]
    mfx = np.load(md / "intrinsics.npy")[:, 0, 0]
    report("mvs_synth_validation.md", "# E0_MVS — 完整真实序列验证", f"状态：{m['status']}。POSE_PROVENANCE = ENGINE_GROUND_TRUTH。0000 共 100 帧，960×540；RGB / Depth / Camera 各 100 文件。阻塞项：{ml['blockers']}。",
           "已获用户明确镜像许可。全部 300 文件匹配镜像发布对象哈希，13 文件额外独立匹配已取得的官方原包；不声称全部 300 文件都与官方完整原包独立比对。官方修订 73e4b0abff2806a67c0f9bc038c3a1ac5df9ef0b，镜像修订 c886d86505054f18f79d0a1c838150d9e98935b2。",
           "输入 E_raw 是 W2C，旋转块 det≈-1。固定 F=diag(1,1,-1,1)，E_new=E_raw F，T_wc=inv(E_new)。这是统一世界基变换，投影和相对相机运动保持。原始 JSON 不改写。",
           "原始浮点矩阵有约 1e-5 非正交误差；只在反射移除后对近 SO(3) 矩阵做严格有界极分解修正，容差 1e-4，保持从原始外参得到的相机中心。不逐帧猜反射轴，不修复任意错误矩阵。逐帧诊断见 mvs_actual_camera_diagnostics.json。",
           f"全部文件按官方同编号配对并实际解码。EXR 中 +inf 是天空零视差。抽查 {len(projection)} 个相邻帧对，跨帧深度重投影中位相对误差范围 {min(errors):.6g}–{max(errors):.6g}（最高约 {100*max(errors):.4f}%）；逐对重叠范围和异常检查保留在归档。这是几何一致性证据，不是人工投影准确率。",
           f"fx 范围 {mfx.min():.9g}–{mfx.max():.9g} px。长度是 native_game_unit，采集时间未知，timestamp=frame_index，不报告米制尺度、物理速度或采集 FPS。",
           f"[E0 运行与检查]({(md.parent/'validation.json').as_posix()})；[完整输入 SHA256 清单]({(md.parent/'data_manifest.json').as_posix()})；[E0 日志]({(PROJECT/'logs/E0_MVS_complete_sequence_0000.log').as_posix()})。",
           f"![MVS 完整引擎真值轨迹]({(fp/'mvs/reference/trajectory_3d.png').as_posix()})",
           "图源为实际 normalized_ground_truth.csv；颜色是帧索引，箭头是相机前向，位置采用固定反射后的原生世界坐标。无合成测试轨迹。")
    report("mvs_synth_baseline.md", "# E1A_MVS — 首组真实 RGB-only 基线", "完整 100 帧已执行。默认有效位姿 23/100（含初始化），22/99 个运动估计成功；Sim(3) ATE=16.4806 native_game_unit。追踪不稳定，完成的是实际数据链路与评价里程碑。", metric_table(mm),
           "平移误差单位是 native_game_unit，旋转为度。RPE 基于全部 99 个原始相邻采样对；默认仅 3 对可算、对照仅 10 对，不能概括为完整序列的相对精度。SE(3) 仅为无尺度条件下的诊断。",
           "复用 ORB 3000 / Hamming BF-KNN / Lowe .75 / Essential RANSAC / recoverPose / 逆相对变换积分。逐帧 K 按实际 resize 半像素约定缩放并分别归一化。RGB-only 推理不读取深度或 GT 位姿；失败行保留 NaN，之后尝试上次成功参考帧，保持旧姿态不算成功。",
           "每条 essential 平移只有单位方向，逐边尺度都不确定；一个全局 Sim(3) 不能修复逐边尺度歧义。全局位置拟合方向也不保证相机朝向对齐，默认绝对 RotErr≈86.93°、对照≈118.11°；不能只展示较小局部 RPE。",
           "首次真实运行在处理前遇到旧内参接口（4 元素与 3×3 K 不兼容）并失败。已修复并加入回归测试，失败归档保留，指标留空；这不是算法追踪失败率观测。",
           "固定 4 个帧对的几何诊断发现默认 recoverPose distanceThresh=50 会过滤远点。新增独立 distance1000_diagnostic，其他参数不变，.3° 视差门限不变。12→13 cheirality 内点 1→1294，但平移方向相对 GT 仍有错误。覆盖率提高至 31/100，尚未解决追踪。没有按最低 ATE 搜索参数或覆盖默认结果。",
           "按实际逐帧拒绝原因计数：默认 77 次失败中 73 次 cheirality 内点不足、2 次匹配不足、2 次低视差；distance1000 的 69 次失败中 68 次低视差、1 次 cheirality 不足。视差门限仍为预设 .3°，没有通过继续放松门限强行增加成功数。原因标签是算法拒绝条件，不是对动态物体的因果标注。",
           "[OpenCV 官方文档](https://docs.opencv.org/4.13.0/d9/d0c/group__calib3d.html)明确远点过滤和单位平移方向；数值诊断归档见 reports/diagnostics/。",
           "CPU 程序 FPS 包括解码、特征、匹配、几何与少量匹配图输出，排除评价/绘图；不是采集 FPS。本轮未追加 RGB-D PnP，后续若执行将独立报告。",
           run_links(mr), f"[默认配置控制台日志]({(PROJECT/'logs/E1A_MVS_sequence_0000_intrinsics_fix.log').as_posix()})；[远点阈值对照日志]({(PROJECT/'logs/E1A_MVS_distance1000.log').as_posix()})。",
           f"![真实 ORB 预测、引擎轨迹与全部失败帧]({(fp/'mvs/distance50_default/trajectory_comparison.png').as_posix()})")
    rd = ol["reference_diagnostics"]
    ofx = np.load(od / "intrinsics.npy")[:, 0, 0]
    report("omniworld_validation.md", "# E0_OMNI — 结构与参考自洽验证", "POSE_PROVENANCE = ESTIMATED_REFERENCE。E0 通过表示文件、映射和几何自洽检查通过，不证明独立 GT 准确率。",
           f"状态 {o['status']}。完整 c5e5ed9a4462 / split_0，{ol['pose_count']} 帧，1280×720，fps.txt 明示 30.0 FPS，时间=原始编号/FPS，不是独立传感器时钟。仅取一个小的完整单 split 场景，不按结果挑选。",
           "官方修订 4e34897a2fcf8e1cc44b1ae8d2bbd0188c8f2841。RGB / depth / others 总计 158,937,728 bytes，3 包完整 SHA256 与官方 LFS 对象一致，解包 403 成员，原压缩包保留。",
           "split_info 明确映射 RGB、depth、gdino_mask 和相机数组；只解析 FPS 标签，不误用处理耗时。相机优化参数为 WXYZ W2C，按官方 SciPy 读取方式归一化有限非零四元数再转换 T_wc。",
           f"原始四元数范数 min/median/max={rd['raw_quaternion_norm_min']:.6g}/{rd['raw_quaternion_norm_median']:.6g}/{rd['raw_quaternion_norm_max']:.6g}；invalid_frame={rd['source_invalid_frames']}。fx={ofx.min():.9g}–{ofx.max():.9g} px；input_size=0.5 原字段保留，不猜成标定宽高。",
           "深度按官方 uint16 公式 d=raw/65535，z=d/(1000−999d)/.004，另有无效掩码。GDINO 白色为动态，是模型标注而非 Oracle。样本没有对应 optical-flow 包，未进行 flow 实验。输出文件名使用 normalized_reference_trajectory.csv；未采用 metric scale。",
           f"源报告重投影误差（前/后/过滤后）={rd['source_reported_reprojection_error_before_refine']:.6g}/{rd['source_reported_reprojection_error_after_refine']:.6g}/{rd['source_reported_reprojection_error_refine_filtered']:.6g}；这是源元数据，不是本工程独立复现。估计深度/位姿互相一致也不构成引擎精度证据。",
           f"[E0 完整归档]({(od.parent/'validation.json').as_posix()})；[输入清单]({(od.parent/'data_manifest.json').as_posix()})；[获取日志]({(PROJECT/'logs/download_omni_c5e5ed9a4462.log').as_posix()})。",
           f"![OmniWorld 估计参考轨迹]({(fp/'omni/reference/trajectory_3d.png').as_posix()})")
    report("omniworld_baseline.md", "# OmniWorld-Game 独立基线报告", "POSE_PROVENANCE = ESTIMATED_REFERENCE。以下误差是相对优化参考的偏差，不是独立引擎真值的绝对误差；reference_unit 不是米。",
           "E1A_OMNI A 组：默认 7/132 有效位姿，distance1000 对照 21/132，覆盖率很低。", metric_table(am),
           "两组相邻原始帧有效 RPE 对数都是 0，RPE 留空，不能写作零误差。初始化原点计入 pose coverage，成功运动对另列。", run_links(ar),
           f"E1B_OMNI / 官方 ORB-SLAM3：{slam_status}。", metric_table(sm), run_links(sr),
           "官方基线完整处理 132 帧，最终 98 帧有效（74.24%），34 帧初始化阶段缺失全部计入失败；最大地图 9 个关键帧，导出与在线 OK 均为 98 帧。97/131 个原始相邻帧对可计算 RPE。Sim(3) ATE=9.04459e-5 reference_unit，RPE 平移=5.53028e-5 reference_unit，RPE 旋转=.332396°，绝对 RotErr=16.0759°。这些是本次估计参考一致性结果，不能宣称引擎真实精度。",
           "同步 TrackMonocular 调用总计 1.77405 秒（74.406 次/秒）；包括词典加载、输入解码、播放间隔、退出和导出的墙钟 15.1270 秒（约 8.73 输入帧/秒），外层含 WSL 启动为 16.0614 秒。不把同步调用速率误称为端到端实时 FPS。首次启动因 FPS YAML 类型要求整数而失败，已修正 30.0→30，失败归档保留，不作为算法跟踪失败观测。",
           f"![官方 ORB-SLAM3 与估计参考]({(Path(sr[-1]['result_directory'])/'trajectory_comparison.png').as_posix()})" if sr and not sr[-1].get("fatal_error") else "原生基线尚无可画轨迹。",
           "使用现有 Ubuntu WSL 原生 CPU 构建官方 v1.0-release；OpenCV 最低版本查找 4.4→4.2 的构建兼容补丁、C++14 与 I/O 适配明示记录，跟踪和优化源码未改。详见 baselines/orb_slam3/PATCHES.md 和构建日志。每帧已提供 K 先重映射到首帧固定 K，输入只有 RGB。",
           "官方最终导出仅取最大地图，再与在线 state=OK 的帧取交集；未初始化、丢失及其他地图帧保持 NaN，不拼图、不插值。ORB-SLAM3 的 1000 特征、多线程建图、C++/WSL、TrackMonocular 调用计时与 Python ORB+Essential 不同，FPS 不作公平速度排名。",
           f"E3_OMNI / MonST3R：{model.get('status','NOT RUN')}。主权重约 2.28GB 未下载；只完成官方代码/许可/资源前置检查，未运行推理、不报告模型性能。详见 monst3r_preflight.md。",
           f"![Omni 默认无掩码预测与估计参考]({(fp/'omni/distance50_default/trajectory_comparison.png').as_posix()})")
    report("dynamic_mask_analysis.md", "# E5_OMNI — 真实动态区域过滤消融", "POSE_PROVENANCE = ESTIMATED_REFERENCE。结论：硬掩码没有显示可靠的改善证据，且本样本的位姿覆盖率下降。",
           table(ab, [("variant","配置"),("group","组"),("valid_pose_frames","有效帧/132"),("feature_count_mean","平均特征数"),
                      ("dynamic_mask_fraction_mean","动态面积"),("tracking_pair_success","运动对成功率"),
                      ("ATE_Sim3_own_valid_subset","各自子集ATE"),("common_valid_frames","共同帧"),("conditional_common_frames_Sim3_ATE","共同帧条件ATE")]),
           "A 无掩码；B 数据集 GDINO 掩码；C 独立自动分割 NOT RUN。B 既不是 C，也不是 Oracle。两种距离阈值分别比较 A/B，不把跨配置差异当成掩码效果。",
           "已程序核对：配置仅 experiment_id 不同；全帧编号、时间戳、参考 SHA256 一致；过滤前 ORB 数量逐帧一致。B 过滤同一组特征且不补点，所以研究的是硬过滤，不是保持特征数的对照。",
           "过滤前平均 2994 点，B 保留 1592.77，约减少 46.80%；动态掩码平均面积 32.62%。默认定位 7→4，distance1000 对照 21→15。B 更快也受候选点与匹配量减少影响，不能解释为方法性能全面提高。",
           "32.62% 是原图全部像素上的给定掩码比例；预览可见该样本上下黑边也被掩码覆盖，不能将此比例解释为独立 GT 确认的运动物体面积。未裁剪黑边或改写原掩码，A/B 输入保持一致。",
           "默认共同有效帧仅 1（初始化），无法对齐；对照共同帧仅 3（含初始化），条件 Sim(3) 极不稳健。共同帧指标在相同交集分别拟合对齐，全 132 帧分母保留；不能把不同成功子集上的较小 ATE 当作全序列改进。全部 A/B RPE 均无原始相邻有效帧对，留空。",
           "distance1000 的 essential RANSAC 内点率均值 A=.9452、B=.9351，cheirality 均值 A=.5608、B=.5646，各覆盖 131 次尝试。但失败后的参考帧不同，不能视作相同匹配集合。相同参考帧的 12 对 cheirality 均值 A=.5342、B=.5075。默认旧日志仅成功对有内点诊断（A 6/B 3），不补零、不与全尝试均值混比。",
           f"[公平性核对 JSON]({(ap/'ablation_analysis.json').as_posix()})；[数据 CSV]({(ap/'paired_ablation.csv').as_posix()})。",
           f"![完整帧轴上的特征与有效位姿]({(ap/'paired_ablation.png').as_posix()})",
           "一段约 4.37 秒的估计参考场景不足以归因动态干扰，需更多独立 GT 序列、特征空间分布/视差与同数量特征对照。")
    report("research_direction_decision.md", "# 下一阶段科研决策", "已取得首组真实游戏相机运动实验；论文创新点仍待验证，优先建立稳定基线与更多独立 GT，不立即启动训练。",
           "1. GTA V 传统 ORB：默认覆盖 23/100、远点阈值对照 31/100。远点过滤、低视差和逐边尺度歧义有诊断支持，但不可泛化为全部动态游戏场景。\n2. 动态视频：Omni 本样本的低覆盖率明显，但不能据此区分动态、遮挡、低视差或参考误差的因果影响。\n3. 掩码过滤：丢掉约 47% 特征，位姿更少，共同帧不足，尚未证明改善。\n4. 数据差异：本次 MVS 覆盖率较高；参考来源与单位不同，不比较跨集 ATE。\n5. 论文方向：M1 是值得检验的假设，尚无正结论；M2 缺少同步骨骼证据；M3 需要独立引擎焦距与失效实例。",
           "下一轮先单列 RGB-D PnP，用 MVS 引擎深度检验平移可观测性/尺度，再扩展 3–5 条不同运动序列。下载前给出逐条大小与预算，预设协议后运行，始终保留完整帧分母与失败。",
           "若检验 M1，加入硬过滤后补足静态特征与几何一致性软权重对照，记录空间覆盖/视差，在独立 GT 上同时评价精度与覆盖率，避免成功子集选择偏差。",
           "M2 角色/骨骼辅助等 WildWorld 获批后验证真实骨骼同步和投影；当前不虚构。M3 中 Omni 焦距本身是估计参考，不当作引擎 FOV 真值。",
           "官方 ORB-SLAM3 在同一 Omni 完整场景得到 98/132 有效位姿，显著高于简化的逐边单位平移积分。说明不能仅据简化基线失效就认定存在论文级新问题。先以多视图地图/优化基线作为后续参照，再检查独立 GT 下的动态场景失效；此处不同方法有效帧集合、参数和计时口径不同，不作未经控制的精度或速度排名。",
           f"ORB-SLAM3 当前实际状态 {slam_status}；MonST3R 在大权重批准前只做前置检查，不把未执行记为推理失败。")
    report("data_acquisition_plan.md", "# 本轮数据取得记录", "两个最小完整样本已取得，没有下载全库。",
           "MVS 官方 540p 原包 10,492,893,238 bytes。首次有界流式读取 283,250,507 bytes 后 EOF，保留 13 官方原文件和失败日志；旧官方站连接超时也保留记录。",
           f"经用户允许，使用 fantasticoven/mvs-synth 修订 c886d86505054f18f79d0a1c838150d9e98935b2 的单序列。300 文件 85,641,391 bytes，复用 13 份官方文件后，镜像实际网络读取 {sum(a.get('network_bytes_read',0) for a in ma):,} bytes。全文件匹配镜像对象哈希，只有 13 文件独立匹配官方原包。",
           "授权记录 reports/mvs_mirror_authorization.json；逐文件记录 logs/acquisition_mvs/；原始目录 data/mvs_synth/GTAV_540/0000。",
           "Omni 官方修订 4e34897a2fcf8e1cc44b1ae8d2bbd0188c8f2841，c5e5ed9a4462：RGB 94,336,794、depth 64,353,022、others 247,912 bytes，总计 158,937,728。3 包官方 LFS SHA256 已核验，原包与原成员保留；没有该场景 flow 包。",
           "MVS 限研究/教育用途，Omni 非商业共享许可并受原游戏条款约束；不公开重分发原游戏素材。MonST3R 2.28GB 主权重、其他模型资产与 CUDA PyTorch 尚未下载，见前置报告。",
           "WildWorld 作者访问审核仍待完成；不绕过访问限制，不阻塞 MVS / Omni。先前报告与失败归档保留。")
    print(json.dumps(status, ensure_ascii=True))

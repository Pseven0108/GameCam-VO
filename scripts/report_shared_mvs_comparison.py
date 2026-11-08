"""Write the bounded comparison without conflating missing methods or supports."""
from __future__ import annotations

import _bootstrap
import csv
import json
from pathlib import Path

from gamecam_vo.common import PROJECT, write_json


def rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(value, digits=6):
    return f"{float(value):.{digits}g}" if value not in (None, "") else "N/A"


def main():
    report = PROJECT / "reports/SOTA"
    pi3_availability_path = report / "pi3mos_download_availability.json"
    pi3_availability = json.loads(pi3_availability_path.read_text(encoding="utf-8")) if pi3_availability_path.exists() else {}
    pi3_blocker = "实际续传被Google Drive公共文件配额拒绝，用户准备手动下载同一官方文件" if pi3_availability.get("public_quota_observed") else "历史请求遭遇Google Drive配额限制，最新检查连接超时"
    pi3_assets_path = report / "pi3mos_assets.json"
    pi3_assets = json.loads(pi3_assets_path.read_text(encoding="utf-8")) if pi3_assets_path.exists() else {}
    pi3_summary = f"Pi3MOS官方核心权重下载未完成：{pi3_blocker}，未运行Demo/MVS。"
    pi3_scientific = "Pi3MOS尚受核心权重下载阻塞，没有推理失败或质量结论。"
    pi3_delivery = "native_setup_passed; official_core_weight_incomplete_public_file_quota_manual_download_pending"
    if pi3_assets.get("status") == "PI3MOS_CORE_WEIGHTS_ACQUIRED":
        demo_path = report / "pi3mos_official_demo.json"
        demo_state = json.loads(demo_path.read_text(encoding="utf-8"))["status"] if demo_path.exists() else "RUNNING"
        pi3_summary = f"Pi3MOS完整核心权重及458帧官方umbrella数据已校验，真实官方Demo状态{demo_state}；MVS评价尚未取得。"
        pi3_scientific = "Pi3MOS完整权重与官方umbrella数据已校验，正在执行/核验原生Demo；MVS质量结论以实际结果为准。"
        pi3_delivery = "core_checkpoint_and_official_data_verified; native_Demo_"+demo_state
    folder = report / "E11_shared_input_audit"
    audit = json.loads((folder / "audit.json").read_text(encoding="utf-8"))
    primary = [r for r in rows(folder / "primary_metrics.csv") if r["alignment"] == "Sim3"]
    common = [r for r in rows(folder / "common_support_diagnostic_metrics.csv") if r["alignment"] == "Sim3"]
    primary_table = []
    categories = {"DROID-W": "在线SLAM", "ORB-SLAM3": "在线SLAM", "Pi3MOS-SLAM": "在线SLAM", "BA-Track": "离线/窗口式重建", "ORB+Essential": "逐边几何"}
    for row in primary:
        primary_table.append(f"| {row['method']} | {categories[row['method']]} | {row['valid_pose_frames']}/100 | {number(row['ATE_RMSE'])} | {number(row['RPE_translation_RMSE'])} | {number(row['RPE_rotation_RMSE_degrees'])} | {row['valid_rpe_pairs']}/99 |")
    common_table = [f"| {r['method']} | {number(r['ATE_RMSE'])} | {number(r['RPE_translation_RMSE'])} | {number(r['RPE_rotation_RMSE_degrees'])} | {r['valid_rpe_pairs']}/99 |" for r in common]
    droid = next(r for r in primary if r["method"] == "DROID-W")
    orb = next(r for r in primary if r["method"] == "ORB-SLAM3")
    essential = next(r for r in primary if r["method"] == "ORB+Essential")
    ba = next((r for r in primary if r["method"] == "BA-Track"), None)
    pi3 = next((r for r in primary if r["method"] == "Pi3MOS-SLAM"), None)
    pi3_missing_row = "| Pi3MOS-SLAM | 在线SLAM | N/A | N/A | N/A | N/A | N/A |\n"
    pi3_runtime_note = ""
    pi3_observation = ""
    if pi3:
        pi3_review = json.loads((report / "pi3mos_mvs_output_review.json").read_text(encoding="utf-8"))
        pi3_missing_row = ""
        pi3_summary = "Pi3MOS已完成官方458帧umbrella原生Demo及共享MVS100的真实推理、先验导出和独立引擎GT评价。"
        pi3_scientific = "Pi3MOS已取得同MVS100的实际结果；原生动态sigmoid与深度提供了方法输出证据，但没有独立物体运动GT，不能计算分解/分割准确性或推出动态游戏鲁棒性。"
        pi3_delivery = "official_Demo_and_shared_MVS100_inference_external_evaluation_completed"
        pi3_runtime_note = f"\n\nPi3MOS原生进程墙钟{number(pi3['inference_seconds'])}秒，输入吞吐{number(pi3['input_fps'])}帧/秒，整卡采样峰值{number(pi3['gpu_peak_used_mib_whole_device_sampled'])}MiB；包含权重加载、原生12帧初始化、跟踪、末尾12次BA、补全及输出观察IO，省略可选GUI。100帧输出与初始化前/后调用数分别保存，不作为同定义丢失率；原始初始化模型网格和后续feature-grid先验分开标注。"
        pi3_runtime_note += f" 实际100次前端调用，调用前/后已初始化计数{pi3_review['initialized_before_calls']}/{pi3_review['initialized_after_calls']}，最终{pi3_review['native_keyframes']}个关键帧，导出{pi3_review['native_prior_maps_exported']}帧先验。"
        pi3_observation = f"Pi3MOS在本段100/100有限位姿、99/99相邻对上的Sim3 ATE为{number(pi3['ATE_RMSE'])}、平移RPE为{number(pi3['RPE_translation_RMSE'])} native_game_unit，旋转RPE为{number(pi3['RPE_rotation_RMSE_degrees'])}°。这仅描述该固定短片段的相机几何误差，不能把完整补全覆盖率或可见动态先验当作动态鲁棒性、运动分割准确性的证明。"
    ba_summary = "BA-Track官方70帧Demo已完成稀疏BA和全局细化，MVS100已启动，尚无完整外部评价。"
    ba_row = "| BA-Track | 离线/窗口式重建 | N/A | N/A | N/A | N/A | N/A |\n"
    ba_timing = "BA本次MVS完整流程尚未取得最终计时与显存；原历史OOM不是完整方法显存门槛。"
    ba_figures = "BA官方70帧Demo的深度和运动分解图已查看；MVS结果待完整检查。"
    if ba:
        ba_summary = "BA-Track官方70帧Demo及共享MVS100的稀疏BA和300次全局细化均已执行，主轨迹按作者pose evaluation口径完成外部评价。"
        ba_row = ""
        ba_timing = f"BA全六阶段墙钟{number(ba['inference_seconds'])}秒、{number(ba['input_fps'])}输入帧/秒，包含两次官方DA预测、UniDepth、预测深度对齐、稀疏BA和dense300/grid12及观察IO；整卡采样峰值{number(ba['gpu_peak_used_mib_whole_device_sampled'])}MiB。它是离线完整管线吞吐，不等于在线跟踪调用速度。"
        ba_figures = "BA官方Demo和共享MVS的原生运动/深度、主相机轨迹、支持范围和资源图均有独立检查记录；细化相机原矩阵另存诊断。"
    method_count = audit["compared_method_count"]
    common_count = audit["common_output_support_frames"]
    common_pairs = common[0]["valid_rpe_pairs"]
    ba_native_note = "BA主轨迹为官方稀疏SLAM姿态，MVS执行与GT评分前已经依据README和eval_*_pose.sh冻结，不按分数选阶段。其native dense camera旋转在官方Demo中未通过1e-4刚体检查，原矩阵不归一化、不投影；联合细化几何解释因此受限。有限正的原生细化深度照实导出。隔离Adam/PyPose诊断与上游issue377机制一致，但未完全隔离整模型原因，未修改官方优化器。"
    ba_next = "优先完成本次BA共享MVS结果核验、取得Pi3MOS同一官方权重"
    if ba:
        ba_details = json.loads((report / "ba_track_mvs_evaluation.json").read_text(encoding="utf-8"))
        check = ba_details["output_review"]["refined_camera_checks"]
        ba_native_note += f" MVS细化矩阵最大RtR偏差{check['max_rotation_orthogonality_error']:.6g}、行列式最大偏差{check['max_determinant_error']:.6g}，均明显超限；不是仅有显示误差。主稀疏姿态最大RtR偏差约2.26e-7，检查通过。"
        endpoint = json.loads((report / "ba_track_endpoint_diagnostic.json").read_text(encoding="utf-8"))
        ba_native_note += f"\n\nBA尾帧99的ATE={endpoint['last_frame_ATE_native_game_unit']:.6g} native_game_unit；98→99旋转RPE={endpoint['last_adjacent_pair']['RPE_rotation_degrees']:.6g}°，贡献完整99对旋转平方误差的{endpoint['last_pair_fraction_of_total_squared_RPE_rotation']:.3%}。50次原生Tracker前向未提供输入99的新点预测，但100个相机位姿完整；此处只定位同期现象，不建立因果。主指标不删除尾帧、不重拟合对齐，完整逐对诊断另存。"
        ba_next = "BA共享MVS完整评价与图表核验已完成；下一步先取得Pi3MOS同一官方权重"
        if pi3_assets.get("status") == "PI3MOS_CORE_WEIGHTS_ACQUIRED":
            ba_next = "BA共享MVS完整评价与图表核验已完成；下一步完成Pi3MOS官方Demo与同MVS结果核验"
        if pi3:
            ba_next = "三个核心方法及传统对照的同MVS100实际结果已取得；下一步选择独立动态相机真值片段"
    support_observation = ""
    if pi3:
        support_observation = f"同为完整100帧支持时，Pi3MOS的ATE={number(pi3['ATE_RMSE'])}小于DROID的{number(droid['ATE_RMSE'])}，而DROID的相邻平移/旋转RPE={number(droid['RPE_translation_RMSE'])}/{number(droid['RPE_rotation_RMSE_degrees'])}°小于Pi3MOS的{number(pi3['RPE_translation_RMSE'])}/{number(pi3['RPE_rotation_RMSE_degrees'])}°；全局轨迹一致性和局部运动误差没有给出同一排序，不能据单个指标指定总赢家。"
    missing_note = "缺失方法记N/A，不生成排名或0分。" if not (ba and pi3) else "五种方法均有本次实际结果，按任务类别及有效支持分别解释。"
    text = f"""# E11 / 共享MVS100帧横向评价

已经完成DROID-W、ORB-SLAM3、ORB+Essential的同输入实际运行与外部评价。{ba_summary}{pi3_summary}{missing_note}

所有已完成方法使用相同100张640×360整流RGB与已知K，逐文件SHA验证相同。MVS0000的引擎GT仅用于外部评价，单位为native_game_unit，米制换算UNKNOWN。保留100帧和99个相邻RPE对作为分母；不跨失效帧补RPE。官方模型内部resize/crop/pad另行记录。历史960px ORB与Omni结果保留，不冒充本表主对照。

| 方法 | 类别 | 有效输出位姿 | Sim3 ATE | Sim3 RPE平移 | RPE旋转/° | 有效相邻对 |
|---|---|---:|---:|---:|---:|---:|
""" + "\n".join(primary_table) + "\n" + ba_row + pi3_missing_row + """

本表分别在各方法有效输出集合拟合全局Sim3，各行支持集合不同，不能把单一ATE作为总排名。完整SE3/Sim3、全局旋转、缺失比例、尺度和时间范围见E11_shared_input_audit/primary_metrics.csv。Sim3是评价后处理，不证明单目方法恢复米制尺度；RPE平移也受该全局尺度影响。

DROID的100/100是补全后的有限位姿，不等于100次前端初始化后跟踪：实际86次初始化后调用、71个关键帧；相邻RPE99对。ORB-SLAM3的96/100是最终最大地图位姿与online OK交集；原生状态2帧NOT_INITIALIZED、96帧OK、2帧RECENTLY_LOST，地图含29个KF。ORB+Essential的20/100包含初始原点，直接运动成功19/99，只有3个相邻有效RPE对。三者的缺失比例不能直接当成同定义跟踪丢失率。

BA的100/100同样表示有限输出；初始化后前端调用88次，不能把0缺失位姿当成0跟踪丢失率。其原生点预测支持、深度与相机输出分别保存，不将未提供的末帧运动图插值成模型观测。

""" + f"作为支持范围敏感性诊断，{method_count}种已完成方法共同有效输入只有{common_count}/100帧，仅{common_pairs}/99个相邻对。下面重新在相同{common_count}帧拟合，不用它替换主结果，也不把其他帧人为排除解释为模型失败。\n\n" + f"""

| 共同{common_count}帧诊断 | Sim3 ATE | RPE平移 | RPE旋转/° | 有效相邻对 |
|---|---:|---:|---:|---:|
""" + "\n".join(common_table) + f"""

坐标审核通过：ORB-SLAM3的28个可比较原生关键帧与规范T_wc导出，最大平移差{audit['ORB_SLAM3_max_keyframe_translation_difference_map_unit']:.6g} map_unit、最大旋转差{audit['ORB_SLAM3_max_keyframe_rotation_difference_degrees']:.6g}°；原生System.cc单目分支明确对T_cw取逆，XYZW和纳秒时钟已核实。DROID另有71个KF逆变换一致性检查。没有通过选择GT坐标约定降低误差。

ORB-SLAM3本次能连续给出较多位姿，但轨迹形状与引擎参考有明显偏差；坐标审核排除了本项目导出方向错误。单序列不能定位唯一成因。其全局RotErr约178.804°与位置对齐所拟合旋转耦合，应结合相邻RPE旋转{number(orb['RPE_rotation_RMSE_degrees'])}°读取，不能把它孤立解释为每帧反向相机。ORB+Essential覆盖有限，ATE低于另一低质量轨迹不能作为优势结论。

时间分别列出，不排序：DROID完整进程墙钟3001.016秒，输入吞吐{number(droid['input_fps'])}帧/秒，包含初始化、最终BA、补全和原生出图；ORB-SLAM3 TrackMonocular调用合计0.969302269秒，调用吞吐{number(orb['input_fps'])}，原生总墙钟13.331224秒包含加载、假定30Hz节奏、停止及导出；ORB+Essential循环4.2445325秒、{number(essential['input_fps'])}输入帧/秒，包含CPU解码、特征、几何和JSON观察记录。真实采集FPS UNKNOWN，不能据此声称实时性或跨类别速度胜负。

类别分别保留：ORB-SLAM3/DROID/Pi3MOS为在线SLAM，BA-Track为离线或窗口式动态重建，ORB+Essential为逐边几何。DROID本轮使用RTX5060，整卡采样峰值7855MiB；PyTorch分配/保留的虚拟内存范围另记，不能与该数字相加或推最低显存。两个ORB基线仅使用CPU。{ba_timing}
{pi3_runtime_note}

{ba_native_note}

目前能够支持的观察：覆盖率与位姿准确性是不同指标；不同有效帧集合会影响ATE解释。{pi3_observation}{support_observation}尚不能回答动态游戏角色鲁棒性、长序列漂移、运动解耦准确性或动态FOV处理：仅100帧几何序列、无独立物体运动真值。其他4条MVS序列只有12张定性预览，交通/行人可见不证明跨帧独立运动。Omni的ESTIMATED_REFERENCE只作参考一致性，绝不与MVS引擎GT混合ATE。

图表：本次两个传统基线的10张PNG及同源SVG已逐张查看，单位/图例/缺帧断线检查通过；每个运行目录保存figure_review.json。DROID的8组图另有已核验记录。{ba_figures}Pi3MOS图表检查以其独立结果目录的figure_review.json为准。

原始结果目录与数据摘要见E11_shared_input_audit/audit.json；比较协议见docs/SOTA_comparison_protocol.md。所有模型参数与失败记录均保留，不以调参追分。
"""
    (report / "E11_comparison_report.md").write_text(text, encoding="utf-8")
    (report / "E11_comparison_status.md").write_text(text, encoding="utf-8")
    decision = f"""# E12 / 创新方向暂不定，先补齐可验证的问题

现有真实证据还不足以选择M1/M2/M3。DROID已完成游戏几何序列且对齐误差较小；ORB-SLAM3出现高覆盖与较差轨迹形状并存，ORB+Essential输出支持稀疏。它们说明评价需要同时报告覆盖与准确性，不能证明近期动态SLAM共同不能处理游戏角色。

BA-Track已在官方真实tennis数据完成70帧先验、稀疏BA、运动解耦和全局细化。原历史显存复制失败已用局部逐位一致的内存索引兼容补丁解决；资源问题不是游戏域泛化失败。细化姿态的刚体约束异常按上游行为保留，不把它包装为游戏角色特有失败。{pi3_scientific}软件API、显存索引修复及下载工具均属于工程复现，不当作科研创新。

| 方向 | 当前缺少的关键证据 | 可审核的下一步 |
|---|---|---|
| M1 动态置信度 | DROID不确定性不是校准动态概率；缺少独立像素/物体运动标签 | 在有独立相机与动态标签的同片段验证置信度与位姿残差/区域运动的关系，保留静态对照 |
| M2 角色辅助 | 当前没有同步独立角色骨骼/三维物体运动GT | 先取得相机与角色独立真值、遮挡和动画时间对应；再验证分解误差，不能用估计相机标签循环证明 |
| M3 动态FOV | 当前MVS0000内参变化极小；共享K整流最大改动约0.00448像素 | 需要明确逐帧K/FOV变化和同动作固定FOV对照，记录裁剪/缩放，先排除纯预处理误差 |

{ba_next}，再选择有独立相机真值和真实动态运动的短片段。BA尾帧误差集中与全局细化刚体约束异常应优先作为输出收尾/数值诊断问题核对，不能直接转化为游戏特有创新结论。可以先明确“静态固定FOV、动态物体固定FOV、静态变FOV”的成对验证需求；此处仅定义证据缺口，没有启动新数据下载、训练或自己的网络。

只有在近期方法出现可重复失败，并排除坐标、标定、输出补全、动态标签来源和资源问题后，才评估哪个方向能解释并改善该失败。100帧不能检验长序列漂移；Omni估计参考不能替代独立绝对相机真值。本阶段不提前选M1/M2/M3，也不提出跨数据集或论文级鲁棒性结论。
"""
    (report / "E12_research_direction_status.md").write_text(decision, encoding="utf-8")
    bounded_complete = bool(ba and pi3 and (report / "pi3mos_official_demo_delivery.json").exists() and (report / "pi3mos_mvs_delivery.json").exists())
    write_json(report / "phase4_comparison_delivery.json", {"status": "BOUNDED_PHASE4_BASELINE_DELIVERY_COMPLETED_WITH_EXPLICIT_LIMITS" if bounded_complete else "PARTIAL_REAL_COMPARISON_WITH_EXPLICIT_BLOCKERS",
        "bounded_E7_to_E12_delivery_complete": bounded_complete,
        "completion_scope": "Audits, official Demos, shared MVS100 runs, external evaluation, output diagnostics and evidence-based direction assessment; no paper-score/robustness/innovation claim",
        "completed_shared_MVS_methods": [r["method"] for r in primary], "expected_input_frames": 100,
        "common_valid_frames_for_diagnostic": audit["common_output_support_frames"],
        "BA_Track": "official_demo_and_MVS_native_completed_external_evaluation_with_dense_camera_diagnostic_limit" if ba else "official_demo_completed_primary_pose_checked_MVS100_running",
        "Pi3MOS": pi3_delivery,
        "E12_direction_selected": None, "comparison_report": str(report / "E11_comparison_report.md"),
        "innovation_status": str(report / "E12_research_direction_status.md")})
    print(json.dumps({"completed_methods": len(primary), "common_diagnostic_frames": common_count, "direction_selected": None}))


if __name__ == "__main__":
    main()

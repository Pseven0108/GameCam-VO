"""Report observed BA results after the recovered official Demo; no execution."""
from __future__ import annotations

import _bootstrap
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone

from gamecam_vo.common import PROJECT, write_json


def main():
    reports = PROJECT / "reports/SOTA"

    def read(name):
        path = reports / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    demo, review = read("ba_track_official_demo.json"), read("ba_track_official_demo_output_review.json")
    if not demo or not review or review["status"] != "BA_TRACK_COMPLETED_OUTPUTS_SANITY_CHECKED":
        raise RuntimeError("A numerically reviewed primary official Demo output is required")
    mvs, evaluation = read("ba_track_mvs.json"), read("ba_track_mvs_evaluation.json")
    endpoint = read("ba_track_endpoint_diagnostic.json")
    mvs_dir = None
    if mvs:
        mvs_dir = str(mvs["directory"])
    else:
        dirs = sorted((PROJECT / "results/E9_BA_TRACK").glob("*_mvs_mvs_0000"))
        mvs_dir = str(dirs[-1]) if dirs else None
    mvs_state = "not_run" if mvs_dir is None else "running"
    if mvs:
        mvs_state = mvs["status"]
    if evaluation:
        mvs_state = evaluation["status"]
    upstream = PROJECT / "baselines/ba_track/upstream"
    original = "456e094ee3ca7fbd9884ba18e68e7c0717d49a67"
    commit = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain"], text=True)
    patch = subprocess.check_output(["git", "-C", str(upstream), "diff", "--binary", original])
    patch_hash = hashlib.sha256(patch).hexdigest()
    folder = PROJECT / "baselines/ba_track/patches"
    snapshot = folder / (("working-tree-"+patch_hash[:16]) if dirty else commit)
    snapshot = snapshot.with_suffix(".patch")
    if snapshot.exists() and snapshot.read_bytes() != patch:
        raise ValueError("Immutable patch snapshot differs")
    snapshot.write_bytes(patch)
    write_json(folder / "current_manifest.json", {"upstream": original, "verified_setup_commit": commit,
        "source_worktree_dirty": bool(dirty), "source_worktree_status": dirty,
        "patch_sha256": patch_hash, "patch": str(snapshot), "full_demo_completed": True,
        "full_demo_primary_camera_reviewed": True, "global_refined_camera_rigid_check_passed": review["global_alignment_camera_usable_as_rigid_poses"],
        "sampler_equivalence": str(reports / "ba_track_sampler_equivalence.json"),
        "query_feature_equivalence": str(reports / "ba_track_query_feature_equivalence.json")})
    root = PROJECT / "baselines/ba_track/repro_outputs"
    state = json.loads((root / "status.json").read_text(encoding="utf-8"))
    state.update(generated_at=datetime.now(timezone.utc).isoformat(), status="partial",
        documented_command_status="official_demo_all_native_stages_exit0_primary_sparse_pose_sanity_checked_dense_pose_diagnostic_limit",
        compatibility_commit=commit, source_worktree_dirty=bool(dirty), patches_applied=True,
        highest_patch_risk="medium_inference_memory_access_implementation_with_exact_local_equivalence_proof",
        result_match=False, result_match_status="not_evaluated_no_expected_paper_score", observed_metrics={} if not evaluation else evaluation["metrics"],
        prior_component_inference_executed=True, BA_tracker_inference_executed=True, full_official_demo_completed=True,
        stage_results={"core_and_native_setup": "passed", "full_official_assets": "verified",
            "official_tennis_depth_priors": "70_of_70_verified_two_DA_runs_bitwise_identical",
            "complete_sparse_camera_BA": "70_of_70_rigid_camera_poses_agree_with_native_TUM",
            "dense_global_refine": "native300_grid12_exit0_depth_finite_positive_camera_rigid_diagnostic_failed",
            "MVS100": mvs_state},
        scientific_limits=["No paper-score reproduction claim", "Primary pose stage follows official pose evaluation, frozen before MVS GT scoring",
            "Dense refined rotations are not silently normalized; geometric interpretation of the joint dense reconstruction is limited",
            "Point motion/probabilities are not dense calibrated segmentation or independently measured object-motion accuracy",
            "One100-frame mostly static game sequence cannot establish dynamic gameplay robustness or long-sequence drift"],
        next_safe_action="Evaluate and visually inspect the single already-running MVS100 pipeline" if not evaluation else "Inspect saved bounded results; Pi3MOS remains blocked by incomplete official core weight",
        human_decisions_required=[], runtime_recovery_evidence=str(reports / "wsl_recovery.json"),
        official_demo_evidence=str(reports / "ba_track_official_demo_output_review.json"),
        source_integrity={"upstream": original, "compatibility_commit": commit, "current_patch_sha256": patch_hash, "snapshot": str(snapshot)},
        readme_fidelity="Official tennis and original checkpoint/default model settings; explicit runtime/API/exact-local memory deviations; pose-evaluation output matches official eval_*_pose.sh",
        error=None)
    write_json(root / "status.json", state)
    mvs_text = f"MVS100状态：{mvs_state}。结果目录：{mvs_dir or '尚无'}。"
    if evaluation:
        sim3 = next(r for r in evaluation["metrics"] if r["alignment"] == "Sim3")
        mvs_text += f"\n\n外部引擎GT：Sim3 ATE={sim3['ATE_RMSE']:.9g} native_game_unit；RPE平移={sim3['RPE_translation_RMSE']:.9g}，旋转={sim3['RPE_rotation_RMSE_degrees']:.9g}°；有限位姿{sim3['valid_pose_frames']}/100，相邻有效对{sim3['valid_rpe_pairs']}/99。完整SE3/Sim3及统计范围见metrics.csv。"
        mvs_review = evaluation["output_review"]
        mvs_text += f"\n\n六个原生阶段墙钟{mvs['whole_pipeline_wall_seconds']:.6f}秒，输入吞吐{sim3['input_fps']:.9g}帧/秒，包含双DA、UniDepth、对齐、稀疏BA与dense300/grid12及原生IO/观察，不包含外部导出/评价。整卡采样峰值{mvs['whole_gpu_peak_used_mib_sampled']:.0f}MiB；各阶段单进程PyTorch分配峰值的最大值{sim3['gpu_peak_allocated_bytes_max_one_process']:,} bytes，属于WDDM/分配器的不同范围，不是专用物理显存或最低门槛。"
        mvs_text += f"\n\nMVS稀疏旋转最大正交偏差{mvs_review['sparse_camera_checks']['max_rotation_orthogonality_error']:.9g}，通过1e-4检查；dense原生矩阵最大正交偏差{mvs_review['refined_camera_checks']['max_rotation_orthogonality_error']:.9g}、行列式最大偏差{mvs_review['refined_camera_checks']['max_determinant_error']:.9g}，未通过。此异常明显大于官方tennis，联合细化三维几何不能作为可信刚体重建。原矩阵和有限正深度分别完整保留，没有做姿态修正或dense姿态评分。"
        mvs_text += f"\n\nMVS前端调用100次，其中初始化后{mvs_review['initialized_frontend_calls']}次；原生Tracker前向{mvs_review['motion']['native_forward_calls']}次。原生点预测未覆盖的输入索引为{mvs_review['motion']['raw_maps_missing_for_input_indices']}，不伪造该帧运动图；这与100个输出相机位姿是不同支持范围。八组PNG/SVG均经实际查看，资源图阶段标签拥挤已修复，数据/指标不变。"
    if endpoint:
        mvs_text += f"\n\n尾帧诊断（不改主结果）：索引99的ATE={endpoint['last_frame_ATE_native_game_unit']:.9g} native_game_unit，为本段最大值；98→99的RPE平移{endpoint['last_adjacent_pair']['RPE_translation_native_game_unit']:.9g}、旋转{endpoint['last_adjacent_pair']['RPE_rotation_degrees']:.9g}°，分别贡献全99对平方误差之和的{endpoint['last_pair_fraction_of_total_squared_RPE_translation']:.3%}与{endpoint['last_pair_fraction_of_total_squared_RPE_rotation']:.3%}。缺少99的新Tracker预测只作为同期现象，不声称因果或游戏特有失败；全部100帧与99对仍进入主指标。"
    text = f"""# E9 / BA-Track 实际运行记录

官方DAVIS tennis的70帧稀疏Tracker/BA与300次/grid12全局深度细化均已真实执行，两个阶段正常退出。70个主相机位姿通过刚体检查并与原生TUM一致，70张细化深度均有限且为正；运动分解和深度图已逐张查看。过程完成不等于论文分数复现，也不保证联合重建几何正确。

{mvs_text}

官方Demo：{demo['directory']}。本次复用了逐文件校验的原始70帧预测先验，稀疏阶段{demo['stages'][0]['wall_seconds']:.3f}秒，全局细化{demo['stages'][1]['wall_seconds']:.3f}秒；本次墙钟{demo['whole_pipeline_wall_seconds']:.3f}秒不包含继承的先验计算，不能当成完整冷启动Demo吞吐。整卡采样峰值{demo['whole_gpu_peak_used_mib_sampled']:.0f}MiB，包含桌面等其他进程；PyTorch虚拟分配不与该数字相加。

相机评价口径在MVS执行和GT评分前冻结：官方README的pose evaluation调用main/run_batrack.py，使用slam.terminate()保存的batrack_traj.txt与results.pkl稀疏SLAM姿态。项目原先把后续dense refinement姿态当作主结果的导出假设已纠正，未依据GT分数选择阶段。证据ba_track_pose_protocol.json含官方源文件SHA。

细化姿态异常保留：官方Demo原生旋转最大RtR偏差0.00202459097、行列式最大偏差约0.002025，超出本项目1e-4刚体检查；未放宽阈值、归一化四元数、投影矩阵或修改优化器。原矩阵单独导出为global_alignment_camera_diagnostic/native_cams_T_world.npy，不冒充合法相机姿态。隔离CPU/CUDA测试显示Adam绕过PyPose的LieTensor.add_，与上游PyPose issue377所述机制一致，但没有完全隔离整模型异常原因。全局细化深度仅按原生有限正数组导出，联合重建的几何解释受该问题限制。

原生运动输出包含total UV、camera-induced UV/depth、动态sigmoid、visibility与queries；由原值派生总运动、相机分量和物体残差。实际初始化后调用{review['initialized_frontend_calls']}/70，与70个输出位姿分开统计。网络内部补齐的12帧时隙不计真实输入；没有未提供时刻的伪造概率图。稀疏SLAM静态标签与可见/查询有效范围分别保存，显示用概率阈值并不冒充最终SLAM动态掩码。

上游{original}，当前兼容提交{commit}，工作树有未提交修改={bool(dirty)}，完整补丁{snapshot.name}。最高风险medium：默认模型、精度、400点/帧、12帧窗口、4次Tracker迭代、阈值及损失未改。5D采样改为直接同点对角索引，并在no-grad下按查询帧采样避免每点复制整张特征图；两组各24个CPU/CUDA多dtype、边界/重复/非连续用例逐位一致。默认2400查询的局部新增临时分配2,082,816 bytes，原复制项计算为15,099,494,400 bytes；不是完整方法最低显存，未声称完整Tracker逐位一致。

历史失败均保留：Qt绘图、Torch weights_only元数据兼容、原5D采样OOM、相关性临时量OOM及14.06GiB查询特征复制OOM。经用户授权恢复WSL后，Ubuntu与三个Conda环境可运行，未删除/重装Ubuntu。50.3GiB离线VHD备份校验通过；微软组件修复尝试因缺少安装源1706/1603回滚，不能称为成功安装。C盘清理是否导致最初卡死尚无结论。

输入约束：MVS使用同一组100张640×360哈希RGB和已知K，稀疏内部裁至640×352，模型内部512×384，按官方处理。深度仅来自DA-V2/UniDepth的预测和官方尺度对齐；引擎相机与深度不进入模型。dense默认同时细化K，未强制固定K。外部GT单位native_game_unit，米制UNKNOWN，SE3/Sim3都保留，失效帧/相邻对分母100/99。

许可分别适用顶层Apache-2.0、DA-V2-Large CC-BY-NC4.0和UniDepth相关声明，HF权重单独许可UNKNOWN。Ubuntu20/Torch2.7.1/cu128与作者Ubuntu22/Torch2.1.1/cu118的差异、Legacy Nyström与FA3后端处理均见PATCHES.md。原Windows gamecam-vo环境保持独立。
"""
    (reports / "E9_BA_TRACK_report.md").write_text(text, encoding="utf-8")
    (root / "LOG.md").write_text(text, encoding="utf-8")
    (root / "SUMMARY.md").write_text("# BA-Track bounded reproduction\n\nOfficial70-frame tennis sparse SLAM and dense300/grid12 completed. Primary camera poses follow the official pose-evaluation scripts and pass native TUM/rigid checks. Native dense camera matrices fail the independent rigid check and are retained without normalization; joint dense reconstruction interpretation is limited.\n\n"+mvs_text+f"\n\npatches_applied=true; branch repro/2026-10-31-sm120; highest patch risk medium; upstream {original}, compatibility {commit}. Explicit local exact-value memory-indexing/runtime deviations retain default model settings. No expected paper metric/tolerance is supplied, so result-match remains not evaluated and overall evidence status partial.\n", encoding="utf-8")
    (root / "PATCHES.md").write_bytes((PROJECT / "baselines/ba_track/PATCHES.md").read_bytes())
    (root / "SCIENTIFIC_CHANGELOG.md").write_text("# Scientific changes\n\nNo architecture, checkpoint, precision, points, window, iterations, losses, thresholds or metric equations were changed. Software/API and locally bitwise-proved memory-indexing differences are explicit. Sparse camera output is primary according to the official pose evaluation scripts, frozen before MVS execution/GT scoring. Dense nonrigid matrices are a diagnostic limitation, never normalized to pass. Observation IO and duplicate official depth prediction time are included in fresh full-pipeline timings.\n", encoding="utf-8")
    (root / "COMPARABILITY_REPORT.md").write_text("# Comparability\n\nOfficial human tennis70 Demo ran all native stages with unchanged default parameters and verified selected assets. Sparse poses agree with native TUM. Dense cameras have a recorded rigid-constraint failure; native depth is exported without promising correct joint geometry. MVS uses the same100 shared RGB+knownK frames and predicted depths only. Sparse-SLAM pose metrics follow the author's pose-evaluation entrypoints and are not a best-of-stages score. One short geometry sequence does not establish dynamic-object robustness, long drift, FOV behavior, calibrated probabilities, object motion accuracy or paper result match.\n", encoding="utf-8")
    (root / "COMMANDS.md").write_text("# Commands and actual execution\n\nDocumented source: README Demo scripts/demo/run_mono_depth.sh, run_sparse.sh, run_dense.sh; pose evaluation scripts/eval_sintel/eval_sintel_pose.sh and scripts/eval_shibuya/eval_shibuya_pose.sh. These documented suggestions are provenance, while the adapted per-stage exact commands executed are frozen in each results/E9_BA_TRACK/*/execution_contract.json.\n\nActual recovered Demo command (Linux independent BA environment):\n```sh\n/home/lsuser/.local/share/gamecam-vo/envs/ba-track/bin/python /mnt/d/aaa/GameCam-VO/scripts/run_ba_track_pipeline.py --target official-demo --reuse-priors-from /mnt/d/aaa/GameCam-VO/results/E9_BA_TRACK/20261031T094723Z_official_demo_tennis\n```\nBoth prior DA steps, UniDepth and depth alignment were previously executed and hash-verified, then reused read-only in a new result folder; reuse time is not counted as fresh inference.\n\nActual single fresh MVS pipeline:\n```sh\n/home/lsuser/.local/share/gamecam-vo/envs/ba-track/bin/python /mnt/d/aaa/GameCam-VO/scripts/run_ba_track_pipeline.py --target mvs\n```\nCurrent outcome is in SUMMARY.md; no automatic model retry. Local equivalence: verify_and_patch_ba_track_sampler.py and verify_and_patch_ba_feature_queries.py. External Windows CPU export: export_ba_track_results.py <recorded-result-directory>. Independent MVS GT evaluation, only after completed output checks: evaluate_ba_track_mvs.py. Do not rerun models merely to regenerate reports. Raw failures and each executed source snapshot are retained.\n", encoding="utf-8")
    source = (upstream / "README.md").read_bytes()
    annotation = b'<!-- GAMECAM_REPRO_BEGIN -->\n<div style="color:#8a5500">Official tennis70 sparse and dense stages completed. Official sparse pose output passes sanity checks; dense camera rigidity limitation retained. MVS state and exact evidence: SUMMARY.md.</div>\n<!-- GAMECAM_REPRO_END -->\n'
    annotated = re.sub(rb"(?m)(^## )", lambda m: annotation+m.group(1), source)
    assert re.sub(rb"<!-- GAMECAM_REPRO_BEGIN -->\n.*?<!-- GAMECAM_REPRO_END -->\n", b"", annotated, flags=re.S) == source
    (root / "ANNOTATED_README.md").write_bytes(annotated)
    print(json.dumps({"status": "partial", "full_native_Demo": True, "primary_pose_reviewed": True, "dense_pose_limit": True, "MVS100": mvs_state}))


if __name__ == "__main__":
    main()

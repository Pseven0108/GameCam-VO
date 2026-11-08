"""Report actual official-demo partial inference and the terminal resource state."""
from __future__ import annotations

import _bootstrap
import json
import re
import subprocess

from gamecam_vo.common import PROJECT, sha256, write_json


def main():
    reports = PROJECT / "reports/SOTA"
    if (reports / "ba_track_official_demo_output_review.json").exists():
        from report_ba_track_completed_state import main as report_completed
        return report_completed()
    def read(name):
        return json.loads((reports / name).read_text(encoding="utf-8"))
    assets = read("ba_track_assets.json")
    partial = read("ba_track_partial_tracker_output_review.json")
    observation = read("ba_track_external_failure_observation.json")
    equivalence = read("ba_track_sampler_equivalence.json")
    upstream = PROJECT / "baselines/ba_track/upstream"
    base = "456e094ee3ca7fbd9884ba18e68e7c0717d49a67"
    commit = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain"], text=True)
    patch = subprocess.check_output(["git", "-C", str(upstream), "diff", "--binary", base])
    import hashlib
    patch_hash = hashlib.sha256(patch).hexdigest()
    folder = PROJECT / "baselines/ba_track/patches"
    target = folder / (("working-tree-" + patch_hash[:16]) if dirty else commit)
    target = target.with_suffix(".patch")
    if target.exists() and target.read_bytes() != patch:
        raise ValueError("An immutable patch snapshot differs")
    target.write_bytes(patch)
    write_json(folder / "current_manifest.json", {"upstream": base, "verified_setup_commit": commit,
        "source_worktree_dirty": bool(dirty), "source_worktree_status": dirty, "patch_sha256": patch_hash, "patch": str(target),
        "sampler_equivalence": str(reports / "ba_track_sampler_equivalence.json"), "full_demo_completed": False})
    root = PROJECT / "baselines/ba_track/repro_outputs"
    state = json.loads((root / "status.json").read_text(encoding="utf-8"))
    state.update(status="partial", documented_command_status="official_demo_attempted_priors_complete_tracker_forward_then_CUDA_OOM",
                 compatibility_commit=commit, source_worktree_dirty=bool(dirty),
                 highest_patch_risk="medium_inference_memory_access_implementation_with_exact_local_equivalence_proof",
                 patches_applied=True, patch_branch="repro/2026-10-31-sm120", result_match=False, observed_metrics={},
                 prior_component_inference_executed=True, BA_tracker_inference_executed=True, full_official_demo_completed=False,
                 stage_results={"core_and_native_setup": "passed", "full_official_assets": assets["status"],
                     "official_tennis_depth_priors": "70_of_70_verified", "duplicate_DA_steps": "both_executed_70_frames_bitwise_identical",
                     "Tracker": "five_saved_native_forward_outputs_ten_returned_frontend_calls_then_OOM",
                     "complete_sparse_camera_BA": "not_reached", "dense_global_refine": "not_run_sparse_gate_failed",
                     "MVS100": "not_run_official_demo_gate_closed"},
                 scientific_limits=["No completed BA-Track camera trajectory, ATE, RPE or whole-method FPS",
                     "Observed sparse native point probabilities are not calibrated dense segmentation or object-motion ground truth",
                     "Resource failure on the official human tennis Demo is not a demonstrated gameplay generalization failure"],
                 next_safe_action="After explicit Ubuntu restart approval and recovery, verify bounded feature-memory indexing equivalence before another default-parameter Demo attempt; only then MVS100",
                 human_decisions_required=["User approval to restart the unresponsive Ubuntu WSL distribution is pending; it could interrupt other Linux work"],
                 partial_tracker_output_evidence=str(reports / "ba_track_partial_tracker_output_review.json"),
                 terminal_resource_observation=str(reports / "ba_track_external_failure_observation.json"))
    native = read("ba_track_native_probe.json")
    state["runtime"] = {"environment": native["environment"], "platform": "WSL2 Ubuntu20.04", "torch": native["numerical_probe"]["torch"],
                        "cuda": native["numerical_probe"]["cuda"], "device": native["numerical_probe"]["device"], "original_Windows_environment_modified": False}
    state["readme_fidelity"] = "Same official tennis target/checkpoints/default model settings; private paths, observation, plotting/API and documented local memory implementation deviations; full Demo remains incomplete"
    write_json(root / "status.json", state)
    text = f"""# E9 / BA-Track 实际运行记录

官方tennis Demo已真实执行：70/70帧DA-V2、UniDepth及预测深度对齐完成，两个官方重复DA步骤均执行且全部逐位一致。Tracker权重加载成功，已保存5次原生前向输出；10次前端调用返回成功，随后在默认参数下发生CUDA OOM。完整相机轨迹、BA初始化完成、dense refine与MVS100均未取得，不能称为完整复现成功。

原先Google Drive连接阻塞已恢复：官方Tracker 423,781,410 bytes，SHA256 28dec511769e1d60a9d54b298f26bcd7ac810cc028ce75f0cc01ee8274b8a104；DAVIS包19,046,400 bytes，SHA256 2b92873ec0bed4f1bc064771b3b4dabce50e940ffe148727d126890fffa46a0f。DA-V2、UniDepth及DINO完整文件已核验。没有把权重发布TODO当成未发布。

上游{base}；已验证安装提交{commit}；repro/2026-10-31-sm120。当前另有显式未提交工作树兼容/内存修改，完整补丁{target.name}与SHA记录在current_manifest.json；不把工作树当成已验证完整Demo的提交。最高风险medium，推理内存索引实现有变化，但模型、400点/帧、12帧窗口、4次Tracker迭代、阈值与损失均保持官方配置。

失败及修复依次保留：Qt绘图导入失败，仅对当前进程使用Agg；Torch新weights_only默认值拒绝官方checkpoint元数据，单一可信作者权重加载显式恢复旧语义；原5D采样构造N×N中间值后取对角线，引发OOM，改为直接选取同一对角线。24组CPU/CUDA、FP16/FP32/FP64、4D/5D、非连续输入、边界与梯度对照逐位一致。小型CUDA分配检查为134,475,776→520,192 bytes临时峰值，不是完整模型显存门槛。完整Tracker逐位一致未验证。

下一次OOM在相关性构造处，释放不再读取的fmaps_sample局部引用后再次运行；最后实际OOM发生在fmaps_sample本身申请14.06 GiB。该临时量按每个查询重复特征图，当前本机无法容纳。没有通过降低模型/窗口/采样点数使其通过。其后Ubuntu命令通道无响应；Windows侧正常，仍等待用户批准仅重启该WSL发行版，尚未执行全局重启或驱动修改。

最新原始运行：{partial['directory']}。已完成前端输入0–9；最后保存的Tracker输出对应真实输入0–8，网络内部补齐到12的时隙不计为12张真实输入。原始total UV、static UV/depth、sigmoid dynamic probability、visibility与queries均保存，有限性通过。派生2D总运动、相机分量、物体残差与原生阈值稀疏点mask也已导出，图已查看。它们不是世界XYZ、独立动态真值或完整稠密掩码，不报告运动分解精度。

未执行阶段：完整稀疏相机BA、grid12/niter300全局细化、MVS100。保留门禁，官方Demo成功后才适配MVS。没有相机输出的阶段不填0误差、0覆盖率或100%跟踪丢失。Ubuntu20/Torch2.7.1/cu128与作者Ubuntu22/Torch2.1.1/cu118差异显式记录；原Windows与DROID环境未作为BA安装目标。

证据：ba_track_assets.json、ba_track_partial_tracker_output_review.json、ba_track_sampler_equivalence.json、ba_track_external_failure_observation.json；五次Demo尝试均位于results/E9_BA_TRACK，不覆盖历史失败。许可分别适用顶层Apache-2.0、DA-V2-Large CC-BY-NC4.0与UniDepth相关声明，HF权重单独许可UNKNOWN。
"""
    for name in ("SUMMARY.md", "LOG.md"):
        (root / name).write_text(text, encoding="utf-8")
    (reports / "E9_BA_TRACK_report.md").write_text(text, encoding="utf-8")
    (root / "PATCHES.md").write_bytes((PROJECT / "baselines/ba_track/PATCHES.md").read_bytes())
    (root / "SCIENTIFIC_CHANGELOG.md").write_text("# Scientific changes\n\nNo architecture, checkpoint, model precision, points, window, iterations, losses or metric changes. Software/API compatibility and exact-local-value memory indexing differ explicitly. Intermediate outputs are observed without mutating predictions; timing includes observation. Full Tracker equivalence and completed camera inference remain unverified.\n", encoding="utf-8")
    (root / "COMPARABILITY_REPORT.md").write_text("# Comparability\n\nThe official70-frame human tennis Demo has complete predicted priors and partial real Tracker outputs, then resource OOM. No complete camera trajectory or BA-Track MVS score exists. A failed resource allocation is not evidence of gameplay motion failure. Sparse UV point probabilities do not establish dense segmentation accuracy. Setup success, partial inference, full bounded success and paper-score match remain distinct.\n", encoding="utf-8")
    (root / "COMMANDS.md").write_text("# Actual commands\n\nAdapted setup and exact commands remain in their setup execution JSON.\n\nExecuted Linux BA environment: `python scripts/fetch_ba_track_assets.py --hf-transport-base https://hf-mirror.com`; `python scripts/run_ba_track_pipeline.py --target official-demo`. Original README mono-depth/sparse/dense scripts are the reviewed source; private paths and output hooks are adapted. Two DA steps were actually preserved.\n\nRetries used `--reuse-priors-from /mnt/d/aaa/GameCam-VO/results/E9_BA_TRACK/20261031T094723Z_official_demo_tennis`; original priors were verified and hard-linked read-only in new result directories. Inherited prior time is not counted as newly executed. Each attempt stores source/command snapshots and the raw failure.\n\nExecuted: `python scripts/verify_and_patch_ba_track_sampler.py`; its explicit-strided review compares the same candidate to captured original code. Windows-only external review: `python scripts/audit_ba_track_partial_outputs.py <recorded-failed-demo-directory>`.\n\nNOT RUN: `run_ba_track_pipeline.py --target mvs`; complete dense refinement300/grid12; no parameter-reduced alternative. A Ubuntu restart was requested but has not been approved or executed.\n", encoding="utf-8")
    readme = (upstream / "README.md").read_bytes()
    annotation = b'<!-- GAMECAM_REPRO_BEGIN -->\n<div style="color:#8a5500">Official tennis predicted priors completed; native Tracker outputs were saved before CUDA OOM. Full camera/Demo/MVS target remains incomplete. See SUMMARY.md.</div>\n<!-- GAMECAM_REPRO_END -->\n'
    annotated = re.sub(rb"(?m)(^## )", lambda m: annotation+m.group(1), readme)
    assert re.sub(rb"<!-- GAMECAM_REPRO_BEGIN -->\n.*?<!-- GAMECAM_REPRO_END -->\n", b"", annotated, flags=re.S) == readme
    (root / "ANNOTATED_README.md").write_bytes(annotated)
    print(json.dumps({"status": state["status"], "actual_Tracker_inference": True, "full_Demo": False, "patch_snapshot": str(target)}))


if __name__ == "__main__":
    main()

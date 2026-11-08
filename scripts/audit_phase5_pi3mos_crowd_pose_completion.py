"""Post hoc native pose-completion audit; preserves full-run camera metrics."""
from __future__ import annotations

import _bootstrap
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import numpy as np

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import read, local


def main():
    folder = PROJECT / "results/E14_WILD_DYNAMIC/PI3MOS/20261101T123456Z_crowd"
    target = PROJECT / "reports/PHASE5/pi3mos_crowd_pose_completion_audit.json"
    note = target.with_suffix(".md")
    if target.exists() or note.exists():
        raise FileExistsError("Keep this dated diagnostic snapshot immutable")
    contract = read(folder / "execution_contract.json")
    evaluation = read(folder / "evaluation_summary.json")
    diagnostic = read(folder / "camera_error_diagnostic/diagnostic.json")
    snapshot = local(diagnostic["source_evaluation_snapshot"])
    if (sha256(snapshot) != diagnostic["source_evaluation_sha256"]
            or read(snapshot)["metrics"] != evaluation["metrics"]
            or not evaluation["figures_visually_reviewed"]):
        raise ValueError("Require the accepted unchanged full native evaluation")
    upstream = PROJECT / "baselines/pi3mos/upstream"
    core = upstream / "dpvo/dpvo.py"
    committed = subprocess.check_output(["git", "-C", str(upstream), "show", contract["source_commit"]+":dpvo/dpvo.py"])
    if core.read_bytes().replace(b"\r\n", b"\n") != committed.replace(b"\r\n", b"\n"):
        raise ValueError("The inspected native core differs from the recorded source commit")
    patch_file = folder / "source_changes_from_upstream.patch"
    if sha256(patch_file) != contract["source_patch_sha256"]:
        raise ValueError("Recorded execution source patch changed")
    with np.load(folder / "native_final_keyframes.npz", allow_pickle=False) as data:
        retained = data["input_frame_indices"].astype(np.int64)
    align = next(r for r in diagnostic["alignments"] if r["alignment"] == "Sim3")
    per_frame = local(align["per_frame_file"])
    if sha256(per_frame) != align["per_frame_sha256"]:
        raise ValueError("Full-frame diagnostic changed")
    with per_frame.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    keys = np.array([int(row["sample_key"]) for row in rows])
    errors = np.array([float(row["aligned_position_residual"]) for row in rows])
    metric = next(r for r in evaluation["metrics"] if r["alignment"] == "Sim3")
    if (not np.array_equal(keys, np.arange(1268)) or len(retained) != 25
            or not np.all(np.isfinite(errors))
            or abs(np.sqrt(np.mean(errors**2))-metric["ATE_RMSE"]) > 1e-10):
        raise ValueError("Keep all 1268 poses under the original full-run Sim3")
    is_retained = np.isin(keys, retained)
    gap = (keys >= 9) & (keys <= 120)
    groups = {}
    for name, mask in [("all", np.ones(len(keys), dtype=bool)),
                       ("final_native_buffer", is_retained),
                       ("other_relative_pose_completed", ~is_retained),
                       ("post_hoc_interval_9_120", gap), ("outside_interval", ~gap)]:
        groups[name] = {"frames": int(mask.sum()),
            "fixed_full_Sim3_position_residual_RMSE_meter": float(np.sqrt(np.mean(errors[mask]**2))),
            "fraction_of_full_position_squared_error": float(np.sum(errors[mask]**2)/np.sum(errors**2))}
    source_lines = core.read_text(encoding="utf-8").splitlines()
    report = {"status": "POST_HOC_NATIVE_POSE_COMPLETION_AUDIT", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_result_directory": str(folder), "native_source_commit": contract["source_commit"],
        "native_core_file": str(core), "native_core_sha256": sha256(core),
        "native_core_matches_recorded_commit": True, "source_patch_sha256": sha256(patch_file),
        "native_core_inspected_lines": {"get_pose_and_terminate_217_250": source_lines[216:250],
            "keyframe_relative_pose_retention_316_351": source_lines[315:351]},
        "final_native_keyframes_sha256": sha256(folder / "native_final_keyframes.npz"),
        "final_native_buffer_input_keys": retained.tolist(), "full_frame_diagnostic_sha256": sha256(per_frame),
        "accepted_evaluation_sha256": sha256(folder / "evaluation_summary.json"),
        "initial_crowd_audit_sha256": sha256(PROJECT / "reports/PHASE5/crowd_camera_error_audit.json"),
        "groups_under_unchanged_full_run_alignment": groups,
        "native_mechanism": "A removed frame stores its relative SE3 transform to an earlier frame. terminate() recursively composes those retained relative transforms, then inverts T_cw to T_wc. Despite the source comment saying interpolate, this is not linear interpolation between the neighboring final retained frames.",
        "observation": "The largest ATE residual at frame46 and the largest adjacent translation RPE at92->93 occur within the final-buffer gap9..120. Initialization had already completed. A count of12 in the live buffer does not mean those12 frame identities stay fixed.",
        "selection": "The interval is selected after inspecting camera errors and the native final buffer. All groups reuse the original full-1268-pose Sim3; no subgroup refit or improved subset main score.",
        "limits": "Correlation in one native run only. No saved relative-transform chain exists for independent per-edge error attribution. These diagnostics do not establish dynamic-object causality, incorrect GT, initialization failure, tracking-loss rate, or a game-domain failure.",
        "model_reexecuted": False, "main_camera_metrics_or_input_support_changed": False}
    write_json(target, report)
    lines = ["# Pi3MOS Crowd 原生位姿补全核验", "", "快照时间："+report["created_at_utc"], "",
        "完整1268帧主评价不变：Sim3 ATE 0.01634362m。原生最终缓冲中有25帧，其余1243帧由作者代码保存的相对SE3递归补全。该过程并非相邻两个最终关键帧间的线性插值。", "",
        "最终保留8帧之后是121帧；9—120共112帧覆盖最大位置残差帧46和最大平移RPE帧对92→93。在原来完整轨迹的同一个Sim3下，该区间贡献约83.30%的位置平方误差。前端当时已初始化；动态缓冲里的12个状态不能解释为固定的前12帧。", "",
        "| 事后分组 | 帧数 | 固定完整Sim3的位置残差RMSE m | 完整位置平方误差占比 |",
        "|---|---:|---:|---:|"]
    labels = {"all": "全部主评价帧", "final_native_buffer": "最终原生缓冲帧", "other_relative_pose_completed": "相对位姿补全帧", "post_hoc_interval_9_120": "事后区间9—120", "outside_interval": "其余帧"}
    for key, values in groups.items():
        lines.append(f"| {labels[key]} | {values['frames']} | {values['fixed_full_Sim3_position_residual_RMSE_meter']:.8f} | {100*values['fraction_of_full_position_squared_error']:.4f}% |")
    lines += ["", "这些分组只定位已有误差，不作为删除前缀后重新评分的依据。没有重跑模型、改动阈值、改变输入或重新拟合子集。原生代码与执行记录中的提交一致，原始源补丁、最终相机缓冲和全帧诊断均由SHA绑定。", "",
        "当前证据说明误差与原生补全区间重叠。没有逐边相对变换的独立存档，无法进一步证明哪一步产生误差；也不能据此归因于运动物体、Mask、GT错误或游戏域。仍需后续运动真值实验与预先约定的重复实验。", "",
        "原始快照[crowd_camera_error_audit.md](crowd_camera_error_audit.md)保持不变；本次详细证据见[pi3mos_crowd_pose_completion_audit.json](pi3mos_crowd_pose_completion_audit.json)。", ""]
    note.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(target), "full_frame_count": len(rows), "native_final_buffer_count": len(retained)}))


if __name__ == "__main__":
    main()

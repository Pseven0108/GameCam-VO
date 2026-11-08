"""Post hoc camera-error audit of accepted Crowd outputs; no model replay."""
from __future__ import annotations

import _bootstrap
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

from gamecam_vo.common import PROJECT, sha256, write_json
from phase5_motion_support import read, local, json_lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-viewed-selected-images", action="store_true", help="Only after actually viewing the four exact hashed RGB files")
    args = parser.parse_args()
    folders = {"DROID_W": PROJECT / "results/E14_WILD_DYNAMIC/DROID_W/20261101T122607Z_crowd",
        "PI3MOS": PROJECT / "results/E14_WILD_DYNAMIC/PI3MOS/20261101T123456Z_crowd"}
    pointer = read(PROJECT / "reports/PHASE5/wild_crowd_input.json")
    if sha256(local(pointer["reference"])) != pointer["reference_sha256"]:
        raise ValueError("Independently frozen MoCap reference changed")
    report = {"status": "POST_HOC_ACCEPTED_CROWD_CAMERA_ERROR_AUDIT", "created_at_utc": datetime.now(timezone.utc).isoformat(), "GT_provenance": "MOCAP_GROUND_TRUTH", "unit": "meter",
        "reference_sha256": pointer["reference_sha256"], "new_model_execution": False,
        "sample_or_clock_changes": False, "independent_motion_pixel_or_skeleton_GT": False,
        "selected_RGB_images_visually_reviewed": args.record_viewed_selected_images, "cases": {}, "images": []}
    for method, folder in folders.items():
        evaluation = read(folder / "evaluation_summary.json")
        if evaluation["status"] != "PHASE5_EXTERNAL_CAMERA_EVALUATION_COMPLETED" or not evaluation["figures_visually_reviewed"]:
            raise ValueError("Accept actual full native output/evaluation/figures before this diagnostic")
        diagnostic_file = folder / "camera_error_diagnostic/diagnostic.json"
        diagnostic = read(diagnostic_file)
        snapshot = local(diagnostic["source_evaluation_snapshot"])
        if sha256(snapshot) != diagnostic["source_evaluation_sha256"] or read(snapshot)["metrics"] != evaluation["metrics"]:
            raise ValueError("Diagnostic source snapshot and accepted primary numeric metrics differ")
        sim3 = next(r for r in diagnostic["alignments"] if r["alignment"] == "Sim3")
        pairs_file = local(sim3["per_pair_file"])
        if sha256(pairs_file) != sim3["per_pair_sha256"]:
            raise ValueError("Accepted all-pair diagnostic changed")
        with pairs_file.open(encoding="utf-8", newline="") as stream:
            pairs = list(csv.DictReader(stream))
        selected = [r for r in pairs if int(r["first_input_key"]) in (91, 92, 93, 604, 605, 606)]
        metric = next(r for r in evaluation["metrics"] if r["alignment"] == "Sim3")
        if metric["valid_pose_frames"] != 1268 or metric["valid_rpe_pairs"] != 1267 or len(selected) != 6:
            raise ValueError("Keep full accepted input/pair denominators")
        report["cases"][method] = {"directory": str(folder), "evaluation_sha256": sha256(folder / "evaluation_summary.json"),
            "diagnostic_sha256": sha256(diagnostic_file), "Sim3_metrics": metric, "Sim3_error_concentration": sim3,
            "selected_original_adjacent_pair_rows": selected}
    rows = json_lines(folders["PI3MOS"] / "frontend_frames.jsonl")
    report["Pi3MOS_direct_frontend_context_92_93"] = [{key: r[key] for key in ("input_frame_index", "initialized_before", "initialized_after", "retained_keyframes", "native_counter", "current_prior_provided")} for r in rows if r["input_frame_index"] in (92, 93)]
    report["Pi3MOS_frontend_trace_sha256"] = sha256(folders["PI3MOS"] / "frontend_frames.jsonl")
    manifest = read(folders["PI3MOS"] / "input_manifest.json")
    for index in (92, 93, 605, 606):
        frame = manifest["frames"][index]
        file = local(frame["path"])
        if sha256(file) != frame["sha256"]:
            raise ValueError("Post hoc inspected RGB changed from the common model input")
        report["images"].append({"input_key": index, "file": str(file), "sha256": frame["sha256"],
            "selection": "92/93 are the maximum Pi3MOS Sim3 translation pair;605/606 are both methods' maximum rotation pair. Selected after scoring for inspection only."})
    report["inference_boundary"] = "A same-frame cross-method camera difference in one unchanged run, not a causal mask/object-motion failure, proven GT error, tracking-loss rate, or confirmed repeatable/game-specific failure"
    target = PROJECT / "reports/PHASE5/crowd_camera_error_audit.json"
    write_json(target, report)
    text = ["# Crowd 相机误差的事后核验", "", "快照时间："+report["created_at_utc"]+"。本快照仅包括已接受的DROID-W和Pi3MOS完整1268帧结果；BA-Track/WildGS正式Crowd案例尚未完成，不能视为四方法最终比较。没有重跑模型、删除样本、修改时钟、改变位姿方向或从GT选择阈值。", "",
        "| 方法 | Sim3 ATE m | Sim3相邻RPE平移 m | RPE旋转° | 最大平移误差帧对 | 该帧对误差m | 占平移平方误差 |", "|---|---:|---:|---:|---|---:|---:|"]
    for method, case in report["cases"].items():
        metric, concentration = case["Sim3_metrics"], case["Sim3_error_concentration"]["translation"]
        pair = "→".join(map(str, concentration["largest_pair"]))
        text.append(f"| {method} | {metric['ATE_RMSE']:.8f} | {metric['RPE_translation_RMSE']:.8f} | {metric['RPE_rotation_RMSE_degrees']:.6f} | {pair} | {concentration['largest_pair_error']:.8f} | {100*concentration['largest_pair_squared_error_fraction']:.4f}% |")
    text += ["", "Pi3MOS的最大局部平移误差在92→93，为0.11352965m，占全1267帧对平移平方误差17.5516%；DROID-W同帧对为0.00178255m。该时差为33.348ms，关联GT平移速度0.38047m/s，与相邻两对0.38153/0.37434m/s接近。Pi3MOS在92、93帧前后均已初始化，保留12个关键帧且有当前先验；不能把这一观测误写成尚未初始化。其全局位置最大残差在46帧，为0.131143m，不把不同指标的峰值混为一个事件。", "",
        "两方法最大旋转误差均在605→606：DROID-W0.884968°、Pi3MOS0.885263°，分别占各自旋转平方误差约1.1568%/1.1572%。末尾1266→1267旋转误差仅占0.0080%/0.0123%，未出现保护的BA-Track MVS100单个末帧对支配旋转误差的模式。", "",
        "图像检查状态："+("已逐张查看对应SHA绑定的RGB92、93、605、606。92/93有两人及篮球，605/606仍有持球人物、另一人物和房间背景。" if args.record_viewed_selected_images else "尚未记录对四张原始RGB的人工/助手实际查看。")+"这些视觉观察不提供独立像素运动真值。相同旋转峰值不证明MoCap GT有误，Pi3MOS单次平移异常也不证明由动态Mask、物体速度或游戏域造成；需后续独立运动标签及预定重复。", "",
        "全部1268相机、1267相邻帧对仍在主评价中。此处只为事后定位而选择峰值附近RGB，不以这些图重新计算更好看的子集成绩。详细CSV、原生前端上下文、评价/GT/图像SHA及原始目录见[crowd_camera_error_audit.json](crowd_camera_error_audit.json)。后续方法结果出现后应另加有日期的更新，保留本快照。", ""]
    (PROJECT / "reports/PHASE5/crowd_camera_error_audit.md").write_text("\n".join(text), encoding="utf-8")
    print(json.dumps({"status": report["status"], "methods": len(folders), "images_actually_viewed": args.record_viewed_selected_images,
        "RGB_files_verified": len(report["images"]), "output": str(target)}))


if __name__ == "__main__":
    main()

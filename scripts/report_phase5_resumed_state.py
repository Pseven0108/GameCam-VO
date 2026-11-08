"""Refresh resumed Phase5 views from real journals without launching work."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports/PHASE5"


def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def local(path):
    return Path(str(path).replace("/mnt/d/", "D:/", 1))


def main():
    pointer = read(REPORTS / "active_phase5_resume_20261102.json")
    resume = read(local(pointer["resume_file"])) if pointer else None
    if not resume or not resume["supersedes_previous_stop_for_future_E15_E16_E17_work"]:
        raise ValueError("An actual explicit user-requested resume record is required")
    for key in ("previous_stage_closeout", "E13_E14_stage_gate"):
        file = local(resume[key])
        if hashlib.sha256(file.read_bytes()).hexdigest() != resume[key+"_sha256"]:
            raise ValueError("A preserved prior-stage record changed")
    state = {"status": "RESUMED_ACTIVE_NOT_COMPLETE", "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "whole_phase5_complete": False, "explicit_user_resume": pointer,
        "prior_stage_closeout_is_historical_snapshot": True, "E13_E14_accepted_primary_cameras": 12,
        "E13_E14_BA_full_pipeline_failures_preserved": 3, "completed_old_models_replayed": False,
        "new_network_training": False, "research_innovation_selected": False}
    acquisition = read(REPORTS / "movi_test_acquisition.json")
    state["E15_acquisition"] = {"status": acquisition["status"], "records": len(acquisition["records"]),
        "sample_bytes": acquisition["total_sample_bytes"]} if acquisition else {"status": "NO_TERMINAL_ACQUISITION_RECORD_YET"}
    inputs = sorted(REPORTS.glob("movi_e_test_s*_input.json"))
    state["E15_prepared_inputs"] = [{"file": str(p), "sequence": read(p)["sequence"], "frames": read(p)["expected_frames"]} for p in inputs]
    lines = ["# 第五阶段当前状态：已恢复实验", "", "用户明确要求继续实验。当前从E15 MOVi-E受控实验继续，随后按原任务顺序进行E16/Bonn与E17证据判断；不训练自有网络，不提前确定创新点。", "",
        "E13/E14的12项主相机评价、三项BA完整流程失败和全部历史记录保留。此前停止记录及已给GPT的资料包属于当时快照，未回写为新的实验结果。", "",
        "MOVi-E获取记录："+state["E15_acquisition"]["status"]+"；已冻结RGB/K输入数量："+str(len(inputs))+"/4。", ""]
    for experiment, phase in (("E15_MOVIE", "E15"), ("E16_BONN", "E16")):
        batch = read(REPORTS / ("active_"+experiment+"_batch.json"))
        plan = read(local(batch["plan"])) if batch else None
        state[phase+"_batch_journal"] = {"plan": batch["plan"], "state": plan["state"],
            "terminal_jobs": sum(j["state"] == "ATTEMPT_TERMINAL" for j in plan["jobs"]), "total_jobs": len(plan["jobs"])} if plan else {"state": "NOT_STARTED"}
        delivery = read(REPORTS / (phase+"_STAGE_DELIVERY.json"))
        state[phase+"_delivery"] = delivery["status"] if delivery else "NOT_DELIVERED"
        lines += [phase+"原生批次日志状态："+state[phase+"_batch_journal"]["state"]+"；阶段报告："+state[phase+"_delivery"]+"。", ""]
    state["E17"] = "PENDING_ACTUAL_E15_E16_INDEPENDENT_EVIDENCE"
    lines += ["日志中的ATTEMPT_STARTED是控制器记录，不单凭旧PID或目录存在宣称模型当前存活；原生终态、完整输出与独立图审分别核验。", "",
        "恢复授权与原阶段身份："+pointer["resume_file"], "", "当前没有把准备好的协议或脚本当成已完成指标。", ""]
    (REPORTS / "phase5_status.json").write_text(json.dumps(state, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (REPORTS / "CURRENT_STATE.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": state["status"], "E15_acquisition": state["E15_acquisition"], "E15_prepared_inputs": len(inputs),
        "E15_batch": state["E15_batch_journal"]}))


if __name__ == "__main__":
    main()

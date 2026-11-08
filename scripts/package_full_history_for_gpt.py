"""Package existing experiment evidence for reading; never launch experiments."""
from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CN = timezone(timedelta(hours=8))
TEXT = {".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".log", ".py", ".sh", ".ps1",
    ".patch", ".toml", ".cfg", ".ini", ".xml", ".html", ".cc", ".cpp", ".c", ".h", ".hpp", ".cu", ".cuh",
    ".cmake", ".bat", ".executed_source", ".reviewed_source", ".source_for_native_pose_direction"}
ADMIN = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
BUILD = {"build", "dist", "node_modules", "site-packages", "envs", "wheelhouse", "Vocabulary", "weights", "checkpoints", "pretrained_models"}
SMALL_CAMERAS = {"native_terminated_camera.npz", "canonical_camera_fields.npz", "camera_fields.npz", "camera_matrices.npz"}
ATTACHMENTS = [
    ("01_initial_experiment_task.txt", Path("C:/Users/Administrator/.codex/attachments/b0a50040-dc89-4781-b633-a612930891da/已粘贴的文本.txt")),
    ("02_public_dataset_strategy.txt", Path("C:/Users/Administrator/.codex/attachments/526f7740-0d28-4cf6-8dde-895aee819704/已粘贴的文本.txt")),
    ("03_phase4_SOTA_task.txt", Path("C:/Users/Administrator/.codex/attachments/8a1d3ac9-34b4-4dd3-82b5-1177e83c45ec/已粘贴的文本.txt")),
    ("04_phase5_task.txt", Path("C:/Users/Administrator/.codex/attachments/347498b5-8fdd-4dc2-ae0c-6128a92ee42c/已粘贴的文本.txt")),
    ("05_WildWorld_access_request_screenshot.png", Path("C:/Users/Administrator/AppData/Local/Temp/codex-clipboard-59fc9e85-80a6-455a-b82f-12d7ae8f7537.png")),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def local(value):
    return Path(str(value).replace("/mnt/d/", "D:/", 1))


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")


def inventory():
    rows, errors = [], []
    for directory, dirs, files in os.walk(ROOT, followlinks=False, onerror=lambda e: errors.append({"path": str(e.filename), "error": str(e)})):
        here = Path(directory)
        for name in list(dirs):
            p = here / name
            if name in ADMIN or (here == ROOT and name == "deliverables"):
                dirs.remove(name)
                continue
            try:
                s = p.lstat()
                if p.is_symlink() or getattr(s, "st_file_attributes", 0) & 0x400:
                    dirs.remove(name)
                    rows.append({"path": p.relative_to(ROOT).as_posix(), "bytes": s.st_size,
                        "mtime_utc": datetime.fromtimestamp(s.st_mtime, timezone.utc).isoformat(), "kind": "DIRECTORY_LINK_NOT_FOLLOWED"})
            except OSError as e:
                dirs.remove(name); errors.append({"path": p.relative_to(ROOT).as_posix(), "error": str(e)})
        for name in files:
            if name in ADMIN:
                continue
            p = here / name
            try:
                s = p.lstat()
                linked = p.is_symlink() or bool(getattr(s, "st_file_attributes", 0) & 0x400)
                rows.append({"path": p.relative_to(ROOT).as_posix(), "bytes": s.st_size,
                    "mtime_utc": datetime.fromtimestamp(s.st_mtime, timezone.utc).isoformat(),
                    "kind": "FILE_LINK_NOT_FOLLOWED" if linked else "FILE" if stat.S_ISREG(s.st_mode) else "SPECIAL_FILE"})
            except OSError as e:
                errors.append({"path": p.relative_to(ROOT).as_posix(), "error": str(e)})
    return sorted(rows, key=lambda r: r["path"]), errors


def base_selection(row):
    p = Path(row["path"])
    parts = p.parts
    top, ext = parts[0], p.suffix.lower()
    if row["kind"] != "FILE":
        return False, "LINK_OR_SPECIAL_FILE_INVENTORIED_WITHOUT_FOLLOWING"
    if any(x in BUILD or x.endswith(".egg-info") for x in parts):
        return False, "COMPILED_DEPENDENCY_OR_MODEL_ASSET_RETAINED_LOCALLY"
    if p.name.lower() in {"token", ".env", ".netrc", "credentials", "credentials.json", "cookies.txt"}:
        return False, "AUTHENTICATION_FILE_NOT_INCLUDED"
    text = ext in TEXT or p.name in {"LICENSE", "LICENSE.md", "CMakeLists.txt", "Makefile", ".gitignore"}
    if top in {"reports", "docs", "scripts", "configs", "gamecam_vo", "datasets"}:
        return (True, "REPORT_DOCUMENTATION_OR_PROJECT_SOURCE") if text or (top == "reports" and ext in {".png", ".svg"}) else (False, "BINARY_OR_NONREVIEW_INPUT_RETAINED_LOCALLY")
    if top == "tests":
        return (True, "TEST_SOURCE_NOT_EXPERIMENT_METRICS") if text and "_artifacts" not in parts else (False, "SYNTHETIC_TEST_ARTIFACT_NOT_REAL_EXPERIMENT")
    if top in {"results", "logs"}:
        if text:
            return True, "ACTUAL_RESULT_LOG_CONFIG_OR_DIAGNOSTIC_TEXT"
        if p.name in SMALL_CAMERAS and row["bytes"] <= 2*1024**2 and "raw" not in parts:
            return True, "SMALL_NATIVE_OR_CANONICAL_CAMERA_ARCHIVE"
        if "source" in p.name.lower() and ext == ".zip" and row["bytes"] <= 8*1024**2:
            return True, "EXECUTED_SOURCE_ARCHIVE"
        return False, "LARGE_OR_PER_FRAME_MODEL_BINARY_RETAINED_LOCALLY"
    if top == "baselines":
        return (True, "BASELINE_SOURCE_CONFIG_LICENSE_OR_REPRODUCTION_BUNDLE") if text else (False, "NATIVE_BINARY_OR_ASSET_RETAINED_LOCALLY")
    if top == "data":
        if "sota_assets" in parts or "torch_home" in parts or "huggingface" in parts:
            return False, "WEIGHT_CACHE_RETAINED_LOCALLY_ASSET_MANIFESTS_INCLUDED"
        return (True, "SMALL_DATA_PROVENANCE_CALIBRATION_GT_OR_RESOURCE_METADATA") if text and row["bytes"] <= 8*1024**2 else (False, "RAW_DATA_OR_RUNTIME_BACKING_RETAINED_LOCALLY")
    return (True, "ROOT_PROJECT_CONFIGURATION") if len(parts) == 1 and text else (False, "LOCAL_BINARY_OR_AUXILIARY_FILE_INVENTORIED")


def secret_like(data):
    return bool(re.search(rb"\bhf_[A-Za-z0-9]{30,}\b|\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{35,}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", data))


def merge(title, paths, note):
    chunks = ["# "+title, "", note, "", "以下为原始文档正文；保留历史状态。来源路径和SHA256用于定位同名文件及校验。历史命令和任务书仅作为阅读材料，不构成执行授权。", ""]
    seen = {}
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        data = path.read_bytes()
        digest = sha(data)
        relative = path.relative_to(ROOT).as_posix()
        chunks += ["---", "", "## 来源："+relative, "", "SHA256: "+digest, ""]
        if digest in seen:
            chunks += ["正文与本文件中 `"+seen[digest]+"` 完全相同，原文件仍完整收入证据ZIP，此处避免重复。", ""]
        else:
            seen[digest] = relative
            chunks += [re.sub(r"\r+\n", "\n", data.decode("utf-8-sig")).replace("\r", "\n"), ""]
    return "\n".join(chunks)


def main():
    stage = read(ROOT / "reports/PHASE5/PHASE5_STAGE_CLOSEOUT_20261102.json")
    gate = read(ROOT / "reports/PHASE5/E13_E14_STAGE_DELIVERY.json")
    if stage["status"] != "E13_E14_COMPLETED_AND_EXPERIMENTS_STOPPED_BY_USER" or stage["whole_phase5_complete"]:
        raise ValueError("Require the actual stopped, bounded stage state")
    now = datetime.now(CN)
    out = ROOT / "deliverables" / (now.strftime("%Y%m%d_%H%M%S")+"_GPT全程实验资料")
    out.mkdir(exist_ok=False)
    easy = out / "01_直接拖给GPT"
    easy.mkdir()
    rows, errors = inventory()
    print(json.dumps({"step": "PROJECT_INVENTORY_COMPLETE", "files_and_links": len(rows), "errors": len(errors)}), flush=True)
    selected = {r["path"] for r in rows if base_selection(r)[0]}
    figures = set()
    missing_figure_references = []
    for row in rows:
        if Path(row["path"]).name not in {"figure_review.json", "native_video_figure_review.json"} or row["kind"] != "FILE":
            continue
        context = ROOT / row["path"]
        try:
            ledger = read(context)
            for item in ledger.get("files", []):
                value = item.get("file")
                if not value:
                    continue
                p = local(value)
                if not p.is_absolute():
                    p = context.parent / p
                p = p.resolve()
                if p.is_relative_to(ROOT) and p.suffix.lower() in {".png", ".svg"}:
                    if p.is_file():
                        figures.add(p.relative_to(ROOT).as_posix())
                    else:
                        missing_figure_references.append({"ledger": row["path"], "reference": value})
        except (OSError, ValueError, TypeError) as e:
            errors.append({"path": row["path"], "figure_index_error": str(e)})
    selected |= figures
    early = sorted((ROOT / "reports").glob("*.md")) + sorted((ROOT / "docs/history/wildworld_phase1_reports").glob("*.md"))
    phase4 = [ROOT / ("reports/SOTA/"+name) for name in ("CURRENT_STATE.md", "SOTA_environment_audit.md", "DROID_W_readiness.md", "E8_DROID_W_report.md",
        "BA_TRACK_readiness.md", "E9_BA_TRACK_report.md", "PI3MOS_readiness.md", "E10_PI3MOS_report.md", "E11_comparison_report.md", "E12_research_direction_status.md", "MVS_dynamic_content_audit.md", "E11_comparison_status.md")]
    phase5_names = ["CURRENT_STATE.md", "phase5_stage_summary_for_beginner_20261102.md", "E13_E14_stage_report.md", "phase5_dataset_audit.md", "phase5_wildgs_reproduction.md",
        "E13_trial_history.md", "wildgs_crowd_formal_review.md", "wildgs_racket_formal_review.md", "wildgs_person_formal_review.md", "person_camera_error_audit.md", "crowd_camera_error_audit.md", "pi3mos_crowd_pose_completion_audit.md", "racket_camera_error_audit.md", "racket_shared_peak_RGB_review.md"]
    phase5 = [ROOT / "reports/PHASE5" / name for name in phase5_names] + [ROOT / "reports/SOTA/E13_WILDGS_READINESS.md"]
    plans = sorted((ROOT / "docs").glob("PHASE5*.md")) + [ROOT / "docs/SOTA_comparison_protocol.md", ROOT / "docs/SOTA_figure_contract.md", ROOT / "docs/figure_contract.md",
        ROOT / "reports/PHASE5/phase5_movi_results.md", ROOT / "reports/PHASE5/phase5_bonn_results.md", ROOT / "reports/SOTA/E15_MOVIE_CONTROLLED.md", ROOT / "reports/SOTA/E16_BONN_CROSS_VALIDATION.md"]
    mvs = list(csv.DictReader(io.StringIO((ROOT / "reports/SOTA/E11_shared_input_audit/primary_metrics.csv").read_text(encoding="utf-8"))))
    mvs_table = ["| 方法 | 有效位姿/100 | Sim3 ATE | 相邻平移RPE | 相邻旋转RPE° |", "|---|---:|---:|---:|---:|"]
    for m in mvs:
        if m["alignment"] == "Sim3":
            mvs_table.append("| "+" | ".join([m["method"],m["valid_pose_frames"],*[f"{float(m[k]):.6g}" for k in ("ATE_RMSE", "RPE_translation_RMSE", "RPE_rotation_RMSE_degrees")]])+" |")
    evidence = read(local(gate["evidence"]))
    wild_table = ["| 序列 | 方法 | 有效位姿 | Sim3 ATE（米） | 相邻平移RPE（米） | 相邻旋转RPE° | 原生完整流程 |", "|---|---|---:|---:|---:|---:|---|"]
    for case in evidence["E14_cases"]:
        m = next(m for m in case["metrics"] if m["alignment"] == "Sim3")
        wild_table.append("| "+" | ".join([case["sequence"],case["method"],str(m["valid_pose_frames"]),*[f"{m[k]:.9g}" for k in ("ATE_RMSE", "RPE_translation_RMSE", "RPE_rotation_RMSE_degrees")],case["native_status"]])+" |")
    overview = "\n".join(["# GameCam-VO 从立项到现在：完整阅读总览", "", "整理时间（北京时间）："+now.isoformat(), "", "最新状态：E13/E14完成收尾，后续实验按用户要求停止。E15 MOVi-E、E16 Bonn和E17最终创新点决策未执行；第五阶段整体尚未完成。", "",
        "这是把现有本地文件整理成阅读材料的操作，没有新下载、模型运行或训练。", "",
        "## 全程经过", "", "| 顺序 | 实际工作 | 已有证据/边界 |", "|---|---|---|",
        "| 立项 | GameCam-VO：动态游戏视频中的相机运动估计 | 最初拟用WildWorld；访问申请已提交，但本项目未取得样本，最初空数据/受阻记录保留 |",
        "| 公开数据启动 | MVS-Synth/GTA V 0000共100帧；OmniWorld-Game split_0共132帧 | MVS为独立引擎GT；Omni位姿为估计参考；两种不能混成一个准确率 |",
        "| 传统方法与过滤消融 | ORB+Essential、ORB-SLAM3；Omni无掩码/给定GDINO掩码A/B | 硬掩码过滤未显示可靠改善，成功位姿减少；给定掩码也非独立运动GT |",
        "| E7–E12 | DROID-W、BA-Track、Pi3MOS官方Demo和共享MVS100；五方法横评；创新证据审查 | 全部限定交付完成；稀疏相机与dense矩阵异常分开，M1/M2/M3暂未选定 |",
        "| 复现期间穿插进行 | WSL/CUDA恢复、独立Conda环境和内存兼容处理 | 工程问题不当作游戏域失效；用户后来删除了旧ext4.vhdx备份，未删除模型环境或结果 |",
        "| E13 | 加入WildGS-SLAM，官方Crowd Demo | 输出完整；结束清理exit1保留，线程兼容方式及调度/RNG差异披露 |",
        "| E14 | Person986、Crowd1268、Racket962，四方法相同400×240完整RGB/K | 12项主相机轨迹全部接受独立MoCap评价和图审；三项BA完整流程仍FAILED |",
        "| 当前停止 | 当前最后一项于北京时间2026-11-02 14:44:38结束；保活进程14:53:13结束 | 临时交换已释放；停止后未开始MOVi/Bonn；原结果和环境保留 |", "",
        "## 不同阶段的真值与单位", "", "MVS-Synth是ENGINE_GROUND_TRUTH，单位native_game_unit，米制换算未知；OmniWorld是ESTIMATED_REFERENCE，单位reference_unit；Wild-SLAM MoCap是MOCAP_GROUND_TRUTH，单位米。合成单元测试、未来MOVi-E协议均不能混进真实已运行指标。", "",
        "## 第四阶段共享MVS100的主要实际结果", "", "平移单位native_game_unit，非厘米或米；各方法支持集合不同，五方法共同支持只有18帧/2个相邻对，不能据单列ATE选总冠军。", "", *mvs_table, "",
        "来源：reports/SOTA/E11_shared_input_audit/primary_metrics.csv；三种神经方法均为100/100，Pi3MOS的ATE较低，DROID-W的相邻RPE更低。", "",
        "## 第五阶段已完成E14的全部主要实际结果", "", "每条序列独立做全局Sim3评价，尺度属于评分对齐，不证明恢复了真实物理尺度。完整SE3/Sim3、初始化、资源和失败见04及证据ZIP。", "", *wild_table, "",
        "## 失败与结果可用性", "", "原始流程状态、完整主相机可用性和科学结论分开判断。BA Person在后续大pickle保存时OOM/SIGKILL，完整主相机字段只读恢复并独立核验；BA Racket、最终Crowd稀疏步骤正常保存后，dense分别申请13.19/17.38GiB而超出约7.96GiB设备容量。三个完整流程仍为FAILED。", "",
        "Crowd另保留原1024缓存容量失败和一次88帧控制中断，最终只完成未完成案例的受检2048容量延续。12项比较对应15个控制器记录，未知退出码不填成OOM；未按GT分数选择成功模型重跑。", "",
        "## 能得出什么", "", "已有可审查的游戏几何基准和真实动态相机对比。BA在本次三段MoCap的整体轨迹误差较大；具体是否由物体运动导致仍未独立验证。模型不确定性或动态sigmoid不自动等于已校准动态概率。当前没有像素/物体/骨骼标签足以完成M1/M2因果验证，也没有变化FOV数据支持M3。没有训练自己的网络或验证新方法。", "",
        "## 阅读材料的优先级", "", "先看00和本总览，再看04当前阶段；02和03用于回顾早期与第四阶段，05中包含历史方案、数值/资源审查及尚未执行协议。原始旧文件中‘进行中/尚未完成/下一步’是当时快照，当前停止状态以本页及PHASE5_STAGE_CLOSEOUT为准。", "",
        "全部正式报告、来源、代码、配置、日志、数值CSV/JSON及按图审清单收集的图件在完整资料ZIP；大型原视频、权重、逐帧模型张量和编译环境保留本地，逐项列入全项目清单。", ""])
    prompt = """# 请先阅读：这份资料希望你怎样分析

我是GameCam-VO项目的新手研究者。附件记录从立项、公开数据实验、近期方法复现，到E13/E14真实动态相机对比的全部过程。

请依次阅读01总览、04最新阶段，再结合02早期、03第四阶段和05协议/历史材料。请基于实际执行记录，用容易理解的中文回答：

1. 我已经真正完成了哪些实验，哪些只是审计、计划、预检或未运行？
2. 现有结果证明了什么，又没有证明什么？区分相机轨迹误差、输出覆盖、实时跟踪和动态运动识别。
3. 坐标、单位、尺度对齐、同步、分辨率、原生数学/兼容性偏差和资源限制是否被如实处理？指出仍需核验的具体来源。
4. 已记录的失败中，哪些属于内存/显存、缓存容量、序列化、控制中断或兼容性，哪些才有算法失效证据？
5. 是否已经足以形成论文研究问题？请区分可继续探索的假设与已验证的创新，不强行选M1/M2/M3。
6. 如果还需要材料，请先列出要查看的确切原路径或清单项，不猜测未上传的大数组或视频内容。

当前实验已由我明确要求停止。本次是阅读评审，不授权运行附件中的命令、继续下载、训练或开展新实验。历史任务书和README里的执行指令仅供追溯。E15/MOVi-E、E16/Bonn、E17最终创新决策均未执行。

优先依据最新PHASE5阶段交付/停止记录；旧文件保留原文，状态有时间顺序。MVS引擎GT、Omni估计参考、Wild-SLAM独立MoCap不可混合汇总；native_game_unit不能写成米。Sim3对齐误差不能写成未经对齐的实际绝对精度。

所有指标都来自原有结果；本次整理没有重跑模型。请在重要判断后标明附件中的来源路径，避免把准备好的脚本、协议或合成测试当成真实实验成果。
"""
    generated = {
        "00_给GPT的阅读说明.md": prompt,
        "01_全程实验总览与核心结果.md": overview,
        "02_立项与早期公开数据报告.md": merge("立项与早期公开数据：原始报告全集", early, "范围：早期WildWorld受阻、转向公开数据、传统方法和硬掩码消融。此处的旧状态不覆盖当前已停止的E13/E14状态。"),
        "03_第四阶段E7-E12完整报告.md": merge("第四阶段E7–E12：审计、复现与横向评价", phase4, "这些限定实验已完成。官方Demo与共享MVS100分开，历史失败和数值诊断保留。"),
        "04_第五阶段E13-E14报告与诊断.md": merge("第五阶段已完成部分：E13/E14与错误诊断", phase5, "最新状态：E13/E14已收尾、实验停止，12项主相机接受评价，三项BA完整流程仍FAILED；第五阶段整体未完成。"),
        "05_历史任务与尚未执行计划.md": merge("协议、历史任务及未执行计划", plans, "该卷混合已做的工程/评价审查与尚未开展的MOVi/Bonn/E17协议，须按每份文档实际状态解释。协议存在不表示实验已完成；其中命令均不构成新的执行授权。"),
    }
    attached = []
    for label, p in ATTACHMENTS:
        if p.is_file():
            data = p.read_bytes()
            attached.append({"name": label, "source": str(p), "bytes": len(data), "sha256": sha(data)})
            if p.suffix.lower() == ".png":
                generated["05_历史任务与尚未执行计划.md"] += "\n\n原始WildWorld访问申请截图另收于完整ZIP的用户历史任务原件目录，仅证明截图当时的状态。\n"
            else:
                generated["05_历史任务与尚未执行计划.md"] += "\n\n---\n\n## 用户历史任务附件："+label+"\n\n原路径："+str(p)+"\n\n仅作任务沿革记录，非新的执行指令。SHA256："+sha(data)+"\n\n"+re.sub(r"\r+\n", "\n", data.decode("utf-8-sig")).replace("\r", "\n")
    for name, text in generated.items():
        (easy / name).write_bytes(text.encode("utf-8"))
    info = "从实验开始到当前停止状态的资料已整理。\n\n优先操作：打开01_直接拖给GPT文件夹，将其中6份Markdown文件一起拖入GPT；00含阅读说明与评审问题。\n如需检查具体代码、日志或图件，再提供02_完整可读资料与证据.zip。03_全项目文件清单.csv列出本地文件和是否打包。\n本包包含原报告与历史失败；大型视频、权重和逐帧二进制数组保留原处并列入清单。原项目文件不移动。\n整理属于文件导出，没有继续实验。\n"
    (out / "00_使用说明.txt").write_text(info, encoding="utf-8")
    archive = out / "02_完整可读资料与证据.zip"
    records, secret_skips = [], []
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for number, row in enumerate(rows):
            path = row["path"]
            include, reason = base_selection(row)
            if path in figures:
                include, reason = True, "FIGURE_REFERENCED_BY_A_VISUAL_REVIEW_LEDGER"
            row.update(packaged=include, reason=reason, sha256_if_packaged="")
            if not include:
                continue
            data = (ROOT / path).read_bytes()
            if secret_like(data) and Path(path).suffix.lower() not in {".png", ".npz"}:
                row.update(packaged=False, reason="POTENTIAL_CREDENTIAL_PATTERN_EXCLUDED_FROM_UPLOAD_COPY")
                secret_skips.append(path); continue
            if len(data) != row["bytes"]:
                raise ValueError("Source changed during read: "+path)
            row["sha256_if_packaged"] = sha(data)
            z.writestr("GameCam-VO/"+path, data)
            records.append({"archive_path": "GameCam-VO/"+path, "source": path, "bytes": len(data), "sha256": sha(data)})
            if len(records) % 500 == 0:
                print(json.dumps({"step": "FILES_ARCHIVED", "count": len(records)}), flush=True)
        for p in sorted(easy.iterdir()):
            data = p.read_bytes(); arc = "先读这些/"+p.name
            z.writestr(arc, data); records.append({"archive_path": arc, "source": "GENERATED_READING_DOCUMENT", "bytes": len(data), "sha256": sha(data)})
        for item in attached:
            data = Path(item["source"]).read_bytes(); arc = "用户历史任务原件/"+item["name"]
            z.writestr(arc, data); records.append({"archive_path": arc, "source": item["source"], "bytes": len(data), "sha256": sha(data)})
        inv = io.StringIO(newline="")
        fields = ["path", "bytes", "mtime_utc", "kind", "packaged", "reason", "sha256_if_packaged"]
        writer = csv.DictWriter(inv, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
        inv_data = ("\ufeff"+inv.getvalue()).encode("utf-8")
        (out / "03_全项目文件清单.csv").write_bytes(inv_data)
        z.writestr("全项目文件清单.csv", inv_data)
        manifest = {"created_at_Asia_Shanghai": now.isoformat(), "project_root": str(ROOT),
            "scope": "All available project reports/docs and selected source/config/log/metric/calibration/GT text, reviewed figure references and small camera archives; full metadata inventory records omitted large raw data/weights/arrays/native dependencies. This is a review bundle, not a complete executable binary/environment backup.",
            "current_stage_state": stage["status"], "whole_phase5_complete": False, "new_experiment_or_download_started": False,
            "excluded_inventory_roots": [".git at any depth", "deliverables at project root", *sorted(ADMIN-{".git"})],
            "logical_bytes_not_allocated_disk_bytes": True, "project_inventory_rows": len(rows), "project_packaged_files": sum(r["packaged"] for r in rows),
            "project_logical_bytes_in_regular_files": sum(r["bytes"] for r in rows if r["kind"] == "FILE"),
            "original_user_task_attachments": attached, "unreadable_entries": errors, "missing_figure_references": missing_figure_references,
            "potential_credential_files_omitted_without_modifying_originals": secret_skips,
            "files": records, "inventory_sha256": sha(inv_data),
            "git_head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
            "package_script_sha256": sha(Path(__file__).read_bytes())}
        z.writestr("BUNDLE_MANIFEST.json", json.dumps(manifest, indent=2, ensure_ascii=False)+"\n")
        z.writestr("先读这些/使用说明.txt", info)
    print(json.dumps({"step": "ZIP_WRITTEN_VERIFYING_CONTENT", "bytes": archive.stat().st_size}), flush=True)
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError("Duplicate archive names")
        if z.testzip() is not None:
            raise ValueError("ZIP CRC verification failed")
        for row in records:
            data = z.read(row["archive_path"])
            if len(data) != row["bytes"] or sha(data) != row["sha256"]:
                raise ValueError("Archive/source SHA mismatch: "+row["archive_path"])
        if sha(z.read("全项目文件清单.csv")) != manifest["inventory_sha256"]:
            raise ValueError("Inventory roundtrip failed")
    with archive.open("rb") as stream:
        h = hashlib.file_digest(stream, "sha256").hexdigest()
    delivery = {k: v for k, v in manifest.items() if k != "files"}
    delivery.update(status="FULL_HISTORY_READING_BUNDLE_CREATED_AND_VERIFIED", directory=str(out), archive=str(archive), archive_bytes=archive.stat().st_size,
        archive_sha256=h, archive_files=len(records)+3, CRC_and_every_packaged_file_SHA_roundtrip="PASS",
        reading_files=[{"file": str(p), "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())} for p in sorted(easy.iterdir())])
    write(out / "04_打包范围与校验.json", delivery)
    print(json.dumps(delivery, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

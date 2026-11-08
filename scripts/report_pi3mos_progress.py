"""Write Pi3MOS native proof and the actual public-file quota blocker."""
from __future__ import annotations

import _bootstrap
import json
from pathlib import Path
import re
import subprocess

from gamecam_vo.common import PROJECT, sha256, write_json


def main():
    reports = PROJECT / "reports/SOTA"
    current_assets = json.loads((reports / "pi3mos_assets.json").read_text(encoding="utf-8"))
    if current_assets["status"] == "PI3MOS_CORE_WEIGHTS_ACQUIRED" and (reports / "pi3mos_manual_checkpoint.json").exists():
        from report_pi3mos_runtime_state import main as report_runtime
        return report_runtime()
    records = {key: json.loads((reports / filename).read_text(encoding="utf-8")) for key, filename in
               (("core", "pi3mos_core_runtime.json"), ("dependencies", "pi3mos_dependencies.json"), ("native", "pi3mos_native_probe.json"),
                ("assets", "pi3mos_assets.json"), ("transport", "pi3mos_weight_transport.json"))}
    availability_path = reports / "pi3mos_download_availability.json"
    availability = json.loads(availability_path.read_text(encoding="utf-8")) if availability_path.exists() else None
    availability_note = "完整权重可用性尚未确认。"
    if availability and availability.get("public_quota_observed"):
        availability_note = "本轮64KiB旧区段抽查与原值一致，但两个实际缺失分段均返回2040-byte配额HTML，新增有效覆盖0 bytes；其余重复请求已停止。用户准备手动下载同一官方文件，完整目标4,100,235,800 bytes。"
    elif availability:
        availability_note = f"最新小范围检查为{availability['status']}；连接超时不当作配额恢复或完整权重已取得的证明。"
    upstream = PROJECT / "baselines/pi3mos/upstream"
    base = "5e709d27324a935e364e01efc56f3128ac00bf24"
    commit = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    patch = subprocess.check_output(["git", "-C", str(upstream), "diff", "--binary", base])
    folder = PROJECT / "baselines/pi3mos/patches"
    folder.mkdir(exist_ok=True)
    patch_path = folder / (commit + ".patch")
    if patch_path.exists() and patch_path.read_bytes() != patch:
        raise ValueError("Immutable Pi3MOS compatibility patch differs")
    patch_path.write_bytes(patch)
    write_json(folder / "manifest.json", {"upstream": base, "compatibility_commit": commit, "patch": str(patch_path), "patch_sha256": sha256(patch_path)})
    transport = records["transport"]
    original = json.loads((Path(transport["directory"].replace("/mnt/d/", "D:/", 1)) / "transport_plan.json").read_text(encoding="utf-8"))
    accepted_bytes = original["seed_bytes"] + sum(r["actual_bytes"] for r in transport["segments"] if r["complete"])
    quota_files = []
    transport_folder = Path(transport["directory"].replace("/mnt/d/", "D:/", 1))
    # Request records point to small rejected bodies retained beside the chunks.
    for segment in transport["segments"]:
        for request in segment["requests"]:
            values = request["command"]
            body = Path(values[values.index("--output")+1].replace("/mnt/d/", "D:/", 1))
            if body.is_file() and body.stat().st_size < 8192 and b"Quota exceeded" in body.read_bytes():
                quota_files.append({"path": str(body), "sha256": sha256(body), "HTTP_success_does_not_mean_weight": True})
    if not quota_files:
        raise RuntimeError("Actual retained Google Drive quota evidence is required")
    state_path = PROJECT / "baselines/pi3mos/repro_outputs/status.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(status="blocked", documented_command_status="not_run_core_checkpoint_incomplete_Google_Drive_quota",
                 patches_applied=True, patch_branch="repro/2026-10-31-sm120", compatibility_commit=commit,
                 highest_patch_risk="low_dtype_API_compatibility", result_match=False,
                 model_inference_executed=False, observed_metrics={}, blocked_upstream_release=False,
                 stage_results={"core": records["core"]["status"], "dependencies": records["dependencies"]["status"],
                                "native": records["native"]["status"], "core_weights": "INCOMPLETE_GOOGLE_DRIVE_QUOTA",
                                "official_demo": "not_run_missing_complete_core_weight", "MVS100": "not_run_official_demo_gate_closed"},
                 valid_core_weight_prefix_and_segments_bytes=accepted_bytes, required_core_weight_bytes=4100235800,
                 quota_evidence=quota_files, human_decisions_required=[],
                 latest_bounded_download_availability_check=availability,
                 protocol_deviations=["Ubuntu20/torch2.7.1+cu128/GCC13 replaces author Ubuntu22/torch2.3.1+cu121 for sm120",
                                      "Eigen3.4.0 headers transported through Conda; scatter2.1.2 source wheel reused in independent prefix",
                                      "Only legacy dtype dispatch API arguments changed after actual compilation error"],
                 next_safe_action="User offered manual download of the same official model.safetensors. Verify exact size, full SHA256, safetensors structure and retained known bytes before inference. No substitute Pi3 weights.")
    native = records["native"]
    state["runtime"] = {"environment": native["environment"], "platform": "WSL2 Ubuntu20.04", "torch": native["numerical_probe"]["torch"],
                        "cuda": native["numerical_probe"]["cuda"], "device": native["numerical_probe"]["device"], "original_Windows_environment_modified": False}
    state["readme_fidelity"] = "Same reviewed official umbrella Demo target; no checkpoint substitution or model changes; dtype API compatibility only; target not run because complete core checkpoint is unavailable"
    write_json(state_path, state)
    patch_text = f"""# Pi3MOS compatibility patches

Upstream {base}; branch repro/2026-10-31-sm120; verified commit {commit}.
Highest risk: low dtype API compatibility. Three source files change only 42
dispatch arguments from tensor.type() to tensor.scalar_type(). Actual compiler
failure is retained. No CUDA math, model, window, points, threshold or iterations
change. Native rebuild, SE3, correlation FP32/FP16, patchify values/gradients,
identity reprojection, zero-residual BA/covariance and RoPE checks passed. The
official model and Demo modules import. These are setup checks, not checkpoint
inference, a minimum-VRAM claim or paper-score reproduction.

Conda supplies the same Eigen3.4.0 headers after the README archive transport
failed. Torch/CUDA are modern sm120-compatible versions in a separate prefix;
the author explicitly allows matching Torch to CUDA. Python3.10, NumPy1.26.4,
Open3D0.19 and scatter2.1.2 declarations remain respected. No xFormers dependency
was added; the official native Torch/RoPE fallbacks are used.
"""
    (PROJECT / "baselines/pi3mos/PATCHES.md").write_text(patch_text, encoding="utf-8")
    root = state_path.parent
    text = f"""# E10 / Pi3MOS-SLAM 当前复现记录

独立Conda环境、原生编译与GPU数值检查已通过。官方DPVO权重完整取得；π³mos的4,100,235,800 byte核心权重尚未齐全。{availability_note}官方umbrella Demo与MVS均未执行，不标为BLOCKED_UPSTREAM_RELEASE，也不填造轨迹指标。

上游{base}，兼容提交{commit}，分支repro/2026-10-31-sm120；patches_applied=true，最高风险低级dtype API兼容差异。42处类型分发参数修改后实际构建通过；数学和默认超参数均保留。环境Python3.10、Torch2.7.1/cu128、NumPy1.26.4、Eigen3.4.0、Open3D0.19，原Windows和另两个模型环境均未作为此安装目标。

实际CUDA验证：SE3非零exp/log及逆、patchify双线性值/梯度、FP32/FP16相关性、scatter、相同位姿重投影、零残差BA保持位姿/深度、协方差分支有限、RoPE零位置不变量，以及模型与Demo导入。未执行预训练π³mos，不据此宣称8GB可运行完整方法。

DPVO权重14,167,743 bytes已完整取得，摘要见pi3mos_assets.json。核心权重已保留{accepted_bytes:,} bytes的原始前缀与完整有效分段，每段检查Content-Range和全文件目标长度；没有把HTTP200的2KB配额HTML当作权重。有效分段、本地SHA、失败TLS及配额响应全部保留。并发请求未获得的段没有记作成功；当前停止重复请求。

官方README的umbrella ZIP单包大小839,158,138 bytes已做元数据核实，但未下载；没有运行全场景下载器。待核心权重完整验证后，先官方Demo，后同一MVS100帧，输入仅RGB+K。模型默认5帧先验、阈值与BA语义保持不变。

许可分别记录：顶层LICENSE缺失，MIT badge不覆盖Naver CC-BY-NC-SA4.0代码和GUI许可；核心权重单独许可UNKNOWN。用户已授权本地科研复现，无新增许可审批步骤。权重传输未完成是当前外部阻塞，不是核心实现或权重未发布。检查的作者官方仓库/关联资料与检索结果中，尚未核实同一权重的作者备用源；这不证明全网没有其他来源，未用普通π³或非作者同名模型替代。

证据：pi3mos_core_runtime.json、pi3mos_dependencies.json、pi3mos_native_probe.json、pi3mos_assets.json、pi3mos_weight_transport.json；补丁及摘要在baselines/pi3mos/patches/。

手动下载官方地址：https://drive.google.com/file/d/145bC76pMHikhdTGkqDK0t9Ta0R7tw51v/view 。建议保存到D:/aaa/GameCam-VO/data/sota_assets/PI3MOS/weights/model.safetensors；完整大小4,100,235,800 bytes。已有前缀/分段保留，不将它们当成完整文件。
"""
    for filename in ("SUMMARY.md", "LOG.md"):
        (root / filename).write_text(text, encoding="utf-8")
    (reports / "E10_PI3MOS_report.md").write_text(text, encoding="utf-8")
    (root / "PATCHES.md").write_text(patch_text, encoding="utf-8")
    (root / "SCIENTIFIC_CHANGELOG.md").write_text("# Scientific changes\n\nNo model, training, loss, metric, data-label or hyperparameter changes. Software stack and dtype API compatibility differ from the author environment and remain explicit. No checkpoint inference has executed.\n", encoding="utf-8")
    (root / "COMPARABILITY_REPORT.md").write_text("# Comparability\n\nNative setup checks cannot establish tracking coverage, ATE, dynamics or minimum VRAM. Missing core bytes due to public-service quota are acquisition failures, not algorithm failures. No paper-score match or MVS/Omni pooled accuracy is claimed.\n", encoding="utf-8")
    (root / "COMMANDS.md").write_text("# Commands\n\nExecuted adapted setup: `python scripts/setup_pi3mos_runtime.py --stage core` and `--stage dependencies`; `python scripts/build_pi3mos_extensions.py`; actual source/API failure and successful numerical probes are recorded in their execution JSON.\n\nExecuted Linux selected-asset acquisition: `python scripts/fetch_pi3mos_assets.py`; `python scripts/fetch_pi3mos_weight_ranges.py`; `--resume-record reports/SOTA/pi3mos_weight_transport.json --workers 2`. Exact byte ranges, sources and rejected HTML remain in transport logs. No new request should run while the known quota blocker is unchanged.\n\nReviewed official target, NOT RUN: `python demo.py --imagedir datasets/Wild_SLAM_Mocap/scene1/umbrella/rgb --calib calib/wildgs/umbrella.txt --viz`. Headless output/export compatibility must be recorded if the GUI flag is omitted later. Neither the all-scene downloader nor MVS inference was executed.\n", encoding="utf-8")
    readme = (upstream / "README.md").read_bytes()
    annotation = b'<!-- GAMECAM_REPRO_BEGIN -->\n<div style="color:#8a5500">Native CUDA setup passed; core checkpoint remains incomplete due to Google Drive quota. See SUMMARY.md for evidence and unexecuted Demo status.</div>\n<!-- GAMECAM_REPRO_END -->\n'
    annotated = re.sub(rb"(?m)(^## )", lambda m: annotation + m.group(1), readme)
    assert re.sub(rb"<!-- GAMECAM_REPRO_BEGIN -->\n.*?<!-- GAMECAM_REPRO_END -->\n", b"", annotated, flags=re.S) == readme
    (root / "ANNOTATED_README.md").write_bytes(annotated)
    print(json.dumps({"status": state["status"], "valid_partial_bytes": accepted_bytes, "quota_evidence_files": len(quota_files)}))


if __name__ == "__main__":
    main()

"""Write current BA-Track evidence without promoting component checks to a Demo."""
from __future__ import annotations

import _bootstrap
import json
import re
import subprocess

from gamecam_vo.common import PROJECT, sha256, write_json


def read(name):
    path = PROJECT / "reports/SOTA" / name
    return json.loads(path.read_text()) if path.exists() else None


def main():
    if read("ba_track_assets.json") and read("ba_track_partial_tracker_output_review.json"):
        from report_ba_track_runtime_state import main as report_runtime
        return report_runtime()
    core, dependencies, native, priors, smoke, dino = [read(name) for name in ("ba_track_core_runtime.json", "ba_track_dependencies.json", "ba_track_native_probe.json", "ba_track_hf_prior_assets.json", "ba_track_depth_prior_smoke.json", "ba_track_dino_assets.json")]
    upstream = PROJECT / "baselines/ba_track/upstream"
    commit = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    root = PROJECT / "baselines/ba_track/repro_outputs"
    state = json.loads((root / "status.json").read_text())
    state.update(status="partial", documented_command_status="not_run_required_Google_Drive_assets_network_blocked",
                 patches_applied=True, patch_branch="repro/2026-10-31-sm120", compatibility_commit=commit,
                 highest_patch_risk="low_API_import_and_computational_backend_compatibility",
                 stage_results={"readiness_audit": "completed", "core_cuda": core["status"], "dependencies": dependencies["status"], "native_probe": native["status"],
                                "HF_priors": priors["status"], "DINO_initialization_asset": dino["status"], "prior_component_inference": smoke["status"], "official_DAVIS_demo": "not_run_network_assets_unavailable", "MVS100": "not_run_official_demo_gate_closed"},
                 observed_metrics={}, result_match=False, prior_component_inference_executed=True, BA_tracker_inference_executed=False,
                 protocol_deviations=["Ubuntu20/torch2.7.1+cu128 replaces author Ubuntu22/torch2.1.1+cu118 for RTX5060; NumPy1.24.3 and root package pins retained",
                     "Conda Eigen3.4.0 header source after README archive timeout; same declared version and no setup.py include edits",
                     "Dispatch arguments use scalar_type; unchanged official0.0.23 Python NystromAttention restored with an import fallback alongside modern CUDA kernels",
                     "xFormers FA3 disabled after actual same-host failure; remaining attention and legacy Nyström branches numerically checked",
                     "HF assets transported through mirror and verified against primary pinned LFS hashes; DA LFS pointer authenticated by exact official Git commit ID"],
                 next_safe_action="Obtain the public official Tracker/DAVIS assets after network access recovers, then run the documented Demo before MVS",
                 human_decisions_required=["Current configured proxy cannot complete TLS to Google Drive; user was asked to restore a reachable node while local work continues"])
    write_json(root / "status.json", state)
    patch_folder = PROJECT / "baselines/ba_track/patches"
    patch_folder.mkdir(exist_ok=True)
    patch = subprocess.check_output(["git", "-C", str(upstream), "diff", "--binary", "456e094ee3ca7fbd9884ba18e68e7c0717d49a67"])
    target = patch_folder / (commit + ".patch")
    if target.exists() and target.read_bytes() != patch:
        raise ValueError("Recorded compatibility patch changed")
    target.write_bytes(patch)
    write_json(patch_folder / "manifest.json", {"upstream": "456e094ee3ca7fbd9884ba18e68e7c0717d49a67", "compatibility_commit": commit,
               "patch": str(target), "patch_sha256": sha256(target), "legacy_python_source_evidence": str(PROJECT / "reports/SOTA/ba_track_legacy_nystrom.json")})
    text = f"""# E9 / BA-Track 当前复现记录

已完成独立Conda环境、CUDA原生编译与数值检查，以及两种学习深度先验的真实推理。官方DAVIS tennis Demo、Tracker、运动解耦、BA/全局细化和MVS100帧均尚未运行；缺少当前网络无法取得的Google Drive Tracker与样本包，不能把组件成功称为BA-Track复现完成。

| 阶段 | 直接证据状态 |
|---|---|
| CUDA核心 | {core['status']} |
| 原始根依赖及pip check | {dependencies['status']} |
| 相关性/LieTorch等原生数值检查 | {native['status']} |
| DA-V2和UniDepth完整权重 | {priors['status']} |
| DINO基础初始化完整权重与固定Hub源码 | {dino['status']} |
| 官方UniDepth示例RGB的深度组件推理 | {smoke['status']} |
| 官方BA-Track DAVIS Demo | NOT_RUN_NETWORK_ASSETS_UNAVAILABLE |
| MVS100帧 | NOT_RUN_OFFICIAL_DEMO_GATE_CLOSED |

上游456e094ee3ca7fbd9884ba18e68e7c0717d49a67；兼容提交{commit}；分支repro/2026-10-31-sm120。patches_applied=true，最高风险为低级API/导入/计算后端兼容差异；模型、权重选择、窗口、landmarks、迭代及损失未更改。精确补丁在baselines/ba_track/patches/。

实际检查包括SE3非零exp/log及逆变换、patchify双线性数值和梯度、FP32/FP16相关性、scatter、注意力对SDPA，以及原版Nyström短序列精确分支和长序列均值不变量。首次ATen编译失败、缺失Nyström导入失败均保留；恢复的是作者版本原始Python组件，不替换算法。

HF先验已完整取得：DA-V2-Large 1,341,395,338 bytes，SHA256 a7ea19fa0ed99244e67b624c72b8580b7e9553043245905be58796a608eb9345；UniDepthV2 safetensors 1,452,916,608 bytes，SHA256 13952af59d28d21d4de5873f8b8bf6d679c5dd031dbf7f9e5818cbeca579f6af。镜像仅作为传输，DA元数据Git对象匹配原先官方API固定的commit，LFS全文件摘要匹配；UniDepth摘要来自E7官方固定树。DINO基础初始化已通过官方Meta直连取得86,728,949 bytes，完整本地SHA256为55c8b267f479b614ec20858947ce361ba804846c193e20be74263a096bb6d75e；作者未提供独立摘要，不将本地摘要当作发布者摘要。DINO Hub源码固定在7c446df5b9f45747937fb0d72314eb9f7b66930a。当前仅缺Google Drive的Tracker与DAVIS样本。

深度组件在vendored UniDepth/assets/demo/rgb.png单张官方示例上执行原脚本，未输入配套真实深度/内参，未使用MVS。两个进程分别exit0，输出480×640；DA-V2允许ReLU后的零值，首次本项目后检查过严已修正，旧日志和执行源码保留。修正只复核已保存数组，没有重新执行模型。此检查不计算相机轨迹/运动解耦或精度指标。图已实际查看，属于输出行为验证。

初次Conda代理TLS失败、NVIDIA下载空文件引发摘要拦截均保留。仅安装命令采用直连；系统代理没有修改。已验证本地torch/vision完整wheel及官方PyPI摘要的CUDA运行库用于独立安装，原DROID与Windows环境未改。

网络证据：Google Drive原请求、TLS1.2和SOCKS5尝试均连接超时。它不是上游未发布、不是模型跟踪失败，也不计为100%丢帧。许可仍分别适用：BA顶层Apache-2.0；DA-V2-Large CC-BY-NC4.0；UniDepth源码声明非商业，HF权重卡许可UNKNOWN。

原始执行证据分别见reports/SOTA/ba_track_core_runtime.json、ba_track_dependencies.json、ba_track_native_probe.json、ba_track_hf_prior_assets.json、ba_track_depth_prior_smoke.json。已通过设置不等同论文分数匹配，result_match=false。
"""
    (PROJECT / "reports/SOTA/E9_BA_TRACK_report.md").write_text(text, encoding="utf-8")
    (root / "SUMMARY.md").write_text(text, encoding="utf-8")
    (root / "LOG.md").write_text(text, encoding="utf-8")
    (root / "PATCHES.md").write_bytes((PROJECT / "baselines/ba_track/PATCHES.md").read_bytes())
    (root / "SCIENTIFIC_CHANGELOG.md").write_text("# Scientific changes\n\nNo training or algorithm changes. Model windows, grids, losses, thresholds, checkpoints and iterations remain official. New Torch/CUDA, Eigen header transport, dtype dispatch API, exact legacy Python attention import, and disabled unsupported FA3 backend are explicit compatibility deviations. Only a one-RGB prior component inference has executed; the BA-Track Tracker/DAVIS/MVS target has not. The corrected DA zero-value validation changes the owned audit, not model output.\n", encoding="utf-8")
    (root / "COMPARABILITY_REPORT.md").write_text("# Comparability\n\nNative/prior component successes do not establish a BA-Track camera result. No BA-Track ATE, coverage, tracking failure, FPS ranking or motion-decomposition accuracy is available. Google Drive transport failure is not upstream release absence or algorithm failure. Author software/hardware differs; no paper expected metric/tolerance has been matched. MVS engine truth remains isolated from inference, and Omni estimated reference remains separate.\n", encoding="utf-8")
    (root / "COMMANDS.md").write_text("# Actual commands and provenance\n\nREADME target: `bash scripts/demo/run_mono_depth.sh`, `run_sparse.sh`, `run_dense.sh` (not yet executed as a complete Demo).\n\nExecuted owned setup: `python scripts/setup_ba_track_runtime.py --stage core --direct-network --cached-core-wheels`; `--stage dependencies --direct-network`; `python scripts/build_ba_track_extensions.py` and `--probe-only`; actual commands and immutable failures are in the JSON execution records and logs linked by the reports.\n\nExecuted assets: `fetch_ba_track_assets.py --hf-transport-base https://hf-mirror.com --hf-only`, gated on native CUDA proof, with source Git authentication and full LFS digest verification.\n\nExecuted prior smoke: WSL BA environment `probe_ba_track_depth_priors.py`; both original depth entry points are listed in execution_contract.json under its result directory. `audit_ba_track_prior_smoke.py` then reviews the same saved arrays. These are prior component commands, not the official BA-Track Demo or MVS experiment.\n", encoding="utf-8")
    original = (upstream / "README.md").read_bytes()
    annotation = b'<!-- GAMECAM_REPRO_BEGIN -->\n<div style="color:#8a5500">GameCam: verified setup and prior-component evidence are in SUMMARY.md. The complete DAVIS/Tracker/MVS target remains pending required Google Drive assets.</div>\n<!-- GAMECAM_REPRO_END -->\n'
    annotated = re.sub(rb"(?m)(^## )", lambda match: annotation + match.group(1), original)
    assert re.sub(rb"<!-- GAMECAM_REPRO_BEGIN -->\n.*?<!-- GAMECAM_REPRO_END -->\n", b"", annotated, flags=re.S) == original
    (root / "ANNOTATED_README.md").write_bytes(annotated)
    print(json.dumps(state["stage_results"]))


if __name__ == "__main__":
    main()

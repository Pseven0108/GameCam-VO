from __future__ import annotations
import _bootstrap
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from gamecam_vo.common import PROJECT, make_run_dir, write_json, write_csv


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def write(name, *parts):
    p = PROJECT / "reports/SOTA" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


def main():
    source = Path(load(PROJECT / "reports/SOTA/latest_E7.json")["directory"])
    repositories = load(source / "repositories.json")
    probes = load(source / "asset_probes.json") + load(source / "prior_assets/probes.json")
    probe = {p["label"]: p for p in probes}
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    reviewed = make_run_dir(PROJECT / "results/E7_SOTA_AUDIT", "readiness_review")
    prior = source / "prior_assets"
    hf = {name: load(prior / (name + "_model.json")) for name in ("metric3d", "fit3d", "unidepth", "dav2")}
    hf_meta = {k: {"id": v["id"], "revision": v["sha"], "gated": v.get("gated"), "card_license": v.get("cardData", {}).get("license", "UNKNOWN")} for k, v in hf.items()}
    write_json(reviewed / "pinned_priors.json", hf_meta)
    states = {"DROID_W": "READY_FOR_ISOLATED_COMPATIBILITY_PROBE", "BA_TRACK": "WAIT_DROID_W_THEN_COMPATIBILITY_PROBE", "PI3MOS": "RELEASE_PRESENT_LICENSE_SCOPE_AND_COMPATIBILITY_UNRESOLVED"}
    profiles = {}
    for label, repo in repositories.items():
        profiles[label] = {"repository": repo["repository"], "commit": repo["revision"], "status": states[label],
                           "minimum_vram_official": "UNKNOWN", "demo_executed": False, "gamecam_inference_executed": False,
                           "source_snapshot": str(source / label), "prerequisite_assets": [], "source_code_modified": False}
    for label, names in {"DROID_W": ["DROID_W_droid_download_probe", "DROID_W_Metric3D_ViT_Large", "DROID_W_FiT3D_DINOv2_reg_small"],
                         "BA_TRACK": ["BA_TRACK_tracker_download_probe", "BA_TRACK_DepthAnythingV2"],
                         "PI3MOS": ["PI3MOS_dpvo_download_probe", "PI3MOS_core_download_probe"]}.items():
        profiles[label]["prerequisite_assets"] = [probe[n] for n in names]
    write_json(reviewed / "readiness.json", {"client_time": now, "source_evidence": str(source), "methods": profiles,
               "original_environment_unchanged": True, "official_stack_matches_local_gpu": False,
               "first_action": "Create one isolated WSL Conda environment; test sm_120-compatible torch/CUDA and required native extensions before full model asset acquisition",
               "primary_dataset": "MVS-Synth/0000 ENGINE_GROUND_TRUTH, all 100 frames", "secondary_dataset": "OmniWorld ESTIMATED_REFERENCE, separate reporting"})
    common = "MVS-Synth sequence 0000 仅作为几何相机估计基准：当前没有独立动态物体运动标注，不用它证明动态鲁棒性。其他 119 序列的官方结构也无动态标签，本轮未下载更多序列，动态充足程度 UNKNOWN。OmniWorld 单独标记 POSE_PROVENANCE = ESTIMATED_REFERENCE；不会合并两套 ATE。"
    wsl = "本机 Windows 11，WSL2 Ubuntu 20.04.3、Linux 6.18.33.2。GPU RTX 5060 8151MiB，compute capability 12.0，驱动 596.21；审计时空闲约 5.2GiB，不能把标称显存当作可用显存。主机 RAM 15.89GiB，WSL 7.7GiB RAM + 2GiB swap。C: 约 54.8GiB、D: 约 167.5GiB 空闲；WSL 虚拟磁盘容量不是 C: 实际剩余容量。"
    compatibility = "官方旧依赖与本机不是相同环境。Windows nvcc 13.2 支持列表已实测没有 compute_60/61/70，但包含 compute_120。WSL 尚无 Conda/CUDA 编译工具链。RTX 5060 需先验证支持 Blackwell 的 PyTorch/CUDA；计划单独验证 PyTorch 2.7.1 + CUDA 12.8，而非把旧 PyTorch 2.1/cu118 安装成功等同 GPU 可运行。此为明确环境偏差，不能声称严格复现作者软件栈。"
    write("SOTA_environment_audit.md", "# E7 本机与复现环境审计", f"审计时间（Asia/Shanghai）：{now}", wsl,
          "原 Conda gamecam-vo：Python 3.11.18，无 PyTorch，继续保留。Windows CUDA toolkit 13.2、驱动支持的 CUDA 版本、WSL CUDA toolkit、PyTorch 编译使用的 CUDA 是不同对象。现有 Conda 环境清单及原始命令证据见 environment.json。",
          compatibility, "只按 DROID-W → BA-Track → Pi3MOS 的顺序安装，一个环境完成或明确失败后再进入下一个。不会修改系统 NVIDIA 驱动、原 GameCam 环境或升级整套 WSL 系统；Ubuntu 20.04 与作者 22.04 的差异保留。",
          "显存：三份官方 README 没有最低需求数值，均为 UNKNOWN；BA-Track 作者测试使用 A40 不等于其最低需求。不会依据 checkpoint 大小或网上估计声称能在 8GB 上完成。DROID 默认缓冲张量已有数 GiB 的静态负载，且还未包含先验模型、激活、优化图与 CUDA workspace，必须实测。",
          common, f"[原始主机证据]({(source/'environment.json').as_posix()})；[固定版本/源代码哈希]({(source/'repositories.json').as_posix()})；[权重限量访问校验]({(source/'asset_probes.json').as_posix()})。",
          "兼容性来源：[NVIDIA GPU 架构表](https://developer.nvidia.com/cuda/gpus)、[NVIDIA Blackwell 兼容指南](https://docs.nvidia.com/cuda/archive/12.8.0/blackwell-compatibility-guide/index.html)、[PyTorch 2.7 Blackwell 支持](https://pytorch.org/blog/pytorch-2-7/)。NVIDIA 允许合适 PTX 的前向兼容，不能笼统断言所有 CUDA 11.8 二进制必然失败；这里 DROID root setup 的固定 flags 没有 PTX，需解决其具体编译目标。")
    dr = repositories["DROID_W"]
    write("DROID_W_readiness.md", "# E7 / DROID-W 可行性审计", f"状态：{states['DROID_W']}。这不是已通过 Demo 或已得到 SOTA 结果。",
          f"1. 官方仓库：{dr['repository']}\n2. 固定 commit：`{dr['revision']}`\n3. 论文：CVPR 2026，arXiv 2603.19076（官方 README / 项目页）。\n4. 顶层 LICENSE：Apache-2.0；第三方 GUI/深度与特征模型许可仍分别适用。",
          "5–7. 主权重 droid.pth 公开链接返回 HTTP 206，有效 ZIP/PyTorch 二进制前缀，总长 **16,061,701 bytes**。默认 mono_prior 还会隐式获取 Metric3D ViT-Large **1,647,972,663 bytes** 和 FiT3D DINOv2-reg-small **88,283,296 bytes**；三者合计 **1,752,317,660 bytes**。FiT3D 的 timm.create_model(pretrained=True) 还会先获取基础 DINO 权重，总量另需增加，不能只报 16MB。链接探测只读取 8 bytes，未完成全权重下载或哈希验证。",
          f"模型仓库修订/许可元数据：{json.dumps(hf_meta, ensure_ascii=False)}。主要先验代码将固定 Metric3D `eb5b6fac0dc155e4e52f576e304fbf11655ff339`、FiT3D `18200c21f047b5add8b7e796d6aab97fba25e790`；GitHub API 限流 403 已保留，用 git ls-remote 取得 HEAD，不伪装成 API 成功。",
          "8–9. README：Python 3.10、CUDA 11.8、torch2.1.0/vision0.16.0/audio2.1.0、torch-scatter、xformers0.0.22.post7、MMCV；自编译 lietorch、diff-gaussian-rasterization-w-pose、simple-knn、droid_backends。虽 GS mapping 默认关闭，src/slam.py 顶层仍导入 Mapper / GUI / GaussianModel，不能假定其编译依赖自动消失。requirements.txt 也未固定全部依赖。",
          "10. 官方最低显存 UNKNOWN。default tracking.buffer=350，Bonn H_out×W_out=384×512，DINO 384 通道按帧驻留 GPU；CPU 图像和 DINO 共享内存也占 RAM。不给出未经实测的峰值。",
          "11–12. 两个数据集均可走已有 RGB_NoPose / dataset='youtube'，只喂 RGB 和内参，depth_paths=None、poses=None；原接口中的零深度仅为占位，Tracker 忽略该字段。GT 不进入模型进程。MVS 原始 K 每帧微变，静态 K 接口需对每帧 RGB 以已知 K 重映射为固定 K，并明示这一预处理；Omni 相同方式，参考轨迹只在推理结束后独立评价。",
          "13. 预计修改：独立运行配置/路径与输出目录；输入命名 rgb/frame*.png；必要的 CUDA 编译目标或旧 ATen API 兼容修复需建 repro 分支并记录 PATCHES.md。不得改不确定性、深度先验、buffer/分辨率等参数来隐藏 OOM。已有输出取 T_wc（internal poses 为 W2C，traj filler 显式取逆），仍需数值方向检查和全 100 帧对应表。",
          "官方首个最小样本选 Bonn balloon：仅该序列 zip HEAD=243,818,512 bytes，先获取官方 Demo。不会运行会下载 8 条数据的整套 shell 脚本。README Bonn 命令遗漏 --config，run.py 实际只接受 --config；按接口补该参数为命令修正，非模型改动。",
          "技能自动规划器误把 README 的一句说明识别成命令，已拒绝执行该候选；正式命令必须依据 run.py 的 argparse 与明确配置手工绑定，保留原 README，不执行伪命令。",
          common, f"[固定 README]({(source/'DROID_W/README.md').as_posix()})；[官方权重入口](https://drive.google.com/file/d/1PpqVt1H4maBa_GbPJp4NwxRsd9jk-elh/view)。")
    ba = repositories["BA_TRACK"]
    write("BA_TRACK_readiness.md", "# E7 / BA-Track 可行性审计", f"状态：{states['BA_TRACK']}。未安装第二个环境，未执行 Demo。",
          f"1–4. 官方 {ba['repository']}；commit `{ba['revision']}`；ICCV 2025 Oral，arXiv 2504.14516；顶层 Apache-2.0。当前 README 的 pretrained checkpoints 与 evaluation scripts 已打勾，旧任务书的待发布判断已过时。",
          "5–7. Tracker md_tracker.pth 的公开下载返回 HTTP 206，**423,781,410 bytes**；DAVIS demo davis.tar **19,046,400 bytes**，有效二进制前缀已验证。DepthAnythingV2-Large **1,341,395,338 bytes**；UniDepthV2 源码固定 revision 1d0d3c52f60b5164629d279bb9a7546458e6dcc4，HF model.safetensors **1,452,916,608 bytes**（pytorch_model.bin 是同模型的另一格式，不重复计入）。三主资产合计至少 **3,218,093,356 bytes**，另有基础 DINO / 依赖，完整总量 UNKNOWN。限量探测不是完整下载验证。",
          "8–10. Ubuntu22.04 / Python3.10 / torch2.1.1 / CUDA11.8 / 作者 A40；xformers、torch-scatter、pypose、Eigen3.4 与 cuda_corr/lietorch 扩展。最低显存 UNKNOWN，A40 是测试硬件，不是最低门槛。当前原生 Windows 不视作可直接支持；后续独立 WSL 环境需像 DROID 一样验证 sm_120。",
          "11–12. 可适配 MVS / Omni 的 RGB、连续编号与 K，深度先验由 UniDepthV2 + DA-V2 推断，不能用引擎 EXR 代替。scripts/demo/run_sparse.sh 的 depthdir_gt 指向的是预测深度目录，不能因此称它为引擎 GT。",
          "13. 先照官方 tennis Demo 的 mono-depth → sparse → dense 顺序；之后仅改数据路径、配置、输入标定和输出桥接。相机轨迹方向需核对 main/run_batrack.py 与 export；Total/Camera/Object motion 从内部解耦结果导出，README 的 motion-decoupling visualization TODO 仍未完成，不能把未有可视化接口称为缺失全部解耦代码，也不能虚构图。",
          "scripts/demo/run_mono_depth.sh 当前把 DA-V2 步骤重复两次；保留这个源码事实，正式执行时记录是否完全遵循或只做一次等价深度缓存生成。深度先验模型许可证独立适用：DA-V2-Large / UniDepth 的模型卡须分别记录非商业约束。",
          common, f"[固定 README]({(source/'BA_TRACK/README.md').as_posix()})；[Tracker 公开链接](https://drive.google.com/file/d/1wWK_ur0Pr4jivqDUdyRUFzHPaF-f1clC/view)。")
    pi = repositories["PI3MOS"]
    write("PI3MOS_readiness.md", "# E7 / Pi3MOS-SLAM 可行性审计", f"状态：{states['PI3MOS']}。不标成 BLOCKED_UPSTREAM_RELEASE，因为代码和核心权重当前已公开。",
          f"1–3. 官方 {pi['repository']}；commit `{pi['revision']}`；CVPR2026，预印本 arXiv2512.06868（2025）。SLAM/weights/camera-tracking evaluation 的 TODO 当前已打勾；待完成的是深度评价和训练代码。dpvo、pi3 与 evaluation 实际存在。",
          "4. README 的 MIT badge 是许可证意向，但仓库顶层没有 LICENSE 文件；pi3/models/layers/pos_embed.py 带 Naver CC-BY-NC-SA4.0 头，GUI 另有自身 LICENSE。因此不能统一写成全部 MIT；核心权重单独许可范围 UNKNOWN，执行大权重前需明确这个范围。",
          "5–7. DPVO 公开链接 HTTP206、有效二进制前缀，**14,167,743 bytes**；π³mos model.safetensors 同样通过限量校验，**4,100,235,800 bytes**；二者合计 **4,114,403,543 bytes**。没有完整下载。旧 Dropbox models.zip 的 HEAD 可达但长度 UNKNOWN，不执行有删除压缩包动作的原下载脚本。",
          "8–10. README Ubuntu22.04 / CUDA12.1；environment.yml Python3.10 / torch2.3.1 / vision0.18 / scatter2.1.2；Eigen3.4，cuda_corr/cuda_ba/lietorch 扩展；π³有 PyTorch RoPE fallback，不能仅因没有 cuRoPE 编译产物就断言核心缺失。官方最低显存 UNKNOWN；默认 PI3_FRAME_RANGE=5、MIXED_PRECISION=True；8GB 是否能运行需实测，4.1GB checkpoint 不等于完整显存消耗。",
          "11–13. Demo 可接受图像目录与 calib；将 MVS/Omni RGB 与 K 接入，GT 只给独立 evaluator。保留 DPVO/π³ 的默认模型、5 帧先验、动态阈值与BA语义。相机轨迹、dynamic probability、depth prior 需从实际返回值与内部缓存导出并保存原尺寸/帧索引。headless 时 demo.shutdown_gui 访问 gui_process 的潜在空属性需验证后做最小修复；不能自行实现另一算法替代。",
          common, f"[固定 README]({(source/'PI3MOS/README.md').as_posix()})；[核心权重公开页](https://drive.google.com/file/d/145bC76pMHikhdTGkqDK0t9Ta0R7tw51v/view)。")
    comparison = [{"method": label, "method_type": kind, "dataset": "MVS-Synth", "POSE_PROVENANCE": "ENGINE_GROUND_TRUTH",
                   "expected_frames": 100, "execution_status": states[label], "ATE": None, "RPE": None, "coverage": None,
                   "failure_rate": None, "FPS": None, "GPU_memory": None, "reason": "Audit only; no inference output"}
                  for label, kind in (("DROID_W", "online_SLAM"), ("BA_TRACK", "offline_window_reconstruction"), ("PI3MOS", "online_SLAM"))]
    write_csv(reviewed / "E11_status_only.csv", comparison)
    write("E11_comparison_status.md", "# E11 横向对比当前状态", "本轮尚无 DL 推理指标，不生成方法总排名；空值不是 0 误差或 0% 覆盖率。DROID/π³在线SLAM、BA-Track离线或窗口重建、ORB+Essential逐边几何，分别陈述时间范围与输入先验。",
          "已有 ORB-SLAM3 98/132 是 OmniWorld 的估计参考实验，不能与 MVS0000 的 ORB 或未来 SOTA ATE 做跨集总排名。若要同一 MVS片段对比 ORB-SLAM3，可复用已有实现运行，不新增传统方法。当前暂不补跑，优先完成 DROID-W。",
          "100 帧不能检验长序列漂移，单场景没有鲁棒性统计；运动分解若没有独立运动真值，只能做行为与一致性分析。", common)
    write("E12_research_direction_status.md", "# E12 创新方向：暂不确定", "E7 的发布状态修正和 CUDA 兼容修复属于工程工作，不是创新。尚未得到近期模型在游戏数据上的实际失败证据，不能提前选择 M1/M2/M3。",
          "M1 等真实不确定性/掩码与独立GT残差共同分析；M2 需要可验证的角色/物体运动与同步骨骼，当前数据不具备；M3 需要真实焦距变化和对照，MVS0000 的焦距几乎固定。任何后续协议改动都需留记录。", common)
    write_json(PROJECT / "reports/SOTA/latest_readiness.json", {"directory": str(reviewed), "source_evidence": str(source), "methods": states})
    print(json.dumps({"readiness_directory": str(reviewed), "states": states}))


if __name__ == "__main__":
    main()

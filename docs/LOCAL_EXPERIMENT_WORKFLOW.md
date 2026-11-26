# GameCam-VO 本地与远端实验规范

2026-11-26，Asia/Shanghai。按用户要求采用三级执行体系。

| 执行位置 | 默认任务 | 当前验收范围 |
| --- | --- | --- |
| 本地 RTX 5060，8 GB | 小批量 GPU 原型、Confidence/TTA 探索、轻量训练候选、算子数值验证 | CUDA、FP32/FP16/BF16、卷积、自求导、深度图双线性恢复、float64 求解、torchvision NMS 和独立 spawn GPU 子进程已通过 |
| 本地 CPU | 数据/GT 审计、指标、统计、绘图、单元测试和数学推导 | 原有科学计算依赖保留，`pip check` 通过 |
| 远端 RTX 3090，24 GB | 正式 DROID-W、长序列 BA、全量数据及论文实验 | 保留原有独立冻结环境；启动与运行仍按阶段授权 |

## 使用现有环境

真实 Conda 环境名为 `gamecam-vo`，不是新建环境。位置保持为：

`C:\Users\Administrator\.conda\envs\gamecam-vo`

在 PowerShell 中使用：

```powershell
conda activate gamecam-vo
Set-Location D:\aaa\GameCam-VO
python -c "import torch; print(torch.__version__, torch.version.cuda); print(torch.cuda.get_device_name(0)); print(torch.cuda.get_arch_list())"
```

2026-11-26 实测版本：Python 3.11.18；PyTorch `2.15.0+cu132`；torchvision `0.29.2+cu132`。
GPU 为 NVIDIA GeForce RTX 5060，Compute Capability `(12, 0)`；PyTorch 架构列表包含 `sm_120`。
驱动 596.21，现有 Toolkit 13.2。驱动、Toolkit 和其他 Conda 环境本轮未修改。
实际执行成功是兼容性依据，不仅依据版本号或 `cuda.is_available()`。

原环境尚未安装 torch；本轮仅新增官方 PyTorch/torchvision 及必要依赖，原有包版本均保持。
安装前后清单、来源哈希、安装日志保存在：

`maintenance/LOCAL_RTX5060_ENVIRONMENT_20261126/`

可重跑的有界检查（使用不同的输出文件名以保留历史记录）：

```powershell
python scripts/check_local_gamecam_gpu.py --output maintenance/local_gpu_check_YYYYMMDD_HHMMSS.json
python -m pip check
```

检查仅使用合成张量，不加载研究模型、不读真实视频、不反序列化 checkpoint。
本机 Windows/PyTorch 构建的实测发现：空字符串遮蔽时 `is_available=True`、`device_count=0`，两者不一致。
因此本机 CPU-only 启动器使用经实测的 `CUDA_VISIBLE_DEVICES='-1'`：available=False、count=0、未初始化CUDA。
这项本地兼容处理不改写历史服务器任务的环境合同。GPU 子进程显式使用设备0，不改变系统级永久设置。

也可通过项目启动器显式选择 CPU/GPU；启动器使用固定的现有环境，并将模型缓存设置到 D:，只影响本次子进程：

```powershell
python scripts/run_gamecam_local.py --device gpu -- -c "import torch; print(torch.cuda.is_available())"
python scripts/run_gamecam_local.py --device cpu -- -c "import torch; print(torch.cuda.is_available())"
```

启动器不会自行加载模型或启动实验。运行具体脚本时，将 `-c ...` 替换为该任务的脚本与参数。

## 推进规则

1. 新的本地推理先从 batch size 1、单帧开始，记录显存、耗时、精度和输出有效率。Flip TTA 先顺序执行两次，避免同时保留两份模型。
2. FP16/autocast 只作为经过数值检查的探索候选。不要为了 8 GB 显存修改已冻结实验的精度、分辨率、K、权重或算法开关。
3. 本轮的峰值张量显存仅约 33 MiB，属于合成检查；它不能预测 Metric3D、DINO 或 DROID-W 的实际显存。
4. Metric3D 完整模型、真实单帧、Confidence/TTA 一致性、训练及 DROID-W 尚未在本机验证。需要对应任务授权和单独 smoke test，不能根据本报告宣布通过。
5. 本机 Windows 的独立 spawn GPU 子进程已通过；跨进程共享 CUDA Tensor 未测试。不能用它推断 Linux DROID-W 多进程运行可用。
6. `nvcc --list-gpu-code` 支持 sm_120，但本轮未编译任何自定义扩展；MSVC/cl、CMake、Ninja 未在当前 PATH 找到。需要编译的任务另行核验，不替换原生 BA 扩展。
7. 保持本地探索和远端正式结果分开。PyTorch 2.15/CUDA 13.2 与历史服务器 PyTorch/CUDA 11.8 不构成数值等价性证明。
8. 所有阶段仍遵守当次研究授权。采用本地优先不等于允许自动进入下一阶段、训练新模型或扩大数据集。

## 存储与交付

现有 Conda 环境仍在 C:；本轮下载、临时文件、日志和成果放在 D:。
安装后 C: 实测约 5.02 GiB 可用，后续安装或下载需重新检查，不将模型缓存默认写入 C:。
后续任务应显式将 Hugging Face/Torch 模型缓存及输出设置到 D: 的独立目录，避免改写已封存资产。

评审沿用 Public `Pseven0108/GameCam-VO` 的完整 ZIP 加展开文件发布方式，交付固定 commit 链接。
发布不包括 wheel、环境二进制、权重、原始数据或凭据。核验远端 ZIP 后仅删除本轮本地评审 ZIP，保留展开成果。

原始科学配置与历史报告保持不变。本规范是后续任务的工程执行约定，不重新定义已有实验成绩。

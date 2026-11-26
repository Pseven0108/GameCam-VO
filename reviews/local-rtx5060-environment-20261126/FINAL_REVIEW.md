# GameCam-VO 本地 RTX 5060 环境调试评审

2026-11-26，Asia/Shanghai。

**状态：LOCAL_GPU_ENVIRONMENT_READY_FOR_BOUNDED_EXPLORATION。**

复用现有 `gamecam-vo` Conda 环境，补齐官方 PyTorch GPU 构建。12/12 有界合成 GPU 检查通过；
CPU/GPU 两种项目启动器均通过真实子进程检查。三级实验策略已登记，不自动启动新的科研阶段。

## 环境结果

| 项目 | 实测 |
| --- | --- |
| 项目 | `D:\aaa\GameCam-VO` |
| 复用环境 | `C:\Users\Administrator\.conda\envs\gamecam-vo` |
| Python | 3.11.18 |
| GPU | NVIDIA GeForce RTX 5060，8151 MiB，capability 12.0 |
| NVIDIA 驱动 | 596.21，未修改 |
| 已有 CUDA Toolkit | 13.2，nvcc V13.2.78，支持 sm_120，未修改 |
| 新增 PyTorch | 2.15.0+cu132，构建包含 sm_120 |
| 新增 torchvision | 0.29.2+cu132，原生 CUDA NMS 已运行 |
| 依赖一致性 | `pip check` PASS，所有原有包版本保持 |
| GPU 检查 | 12/12 PASS |
| 远程模型/GPU实验 | 0 |

原环境无 PyTorch。本次新增 torch、torchvision 和8个必要依赖；完整前后清单及差异在 `before/`、`after/`。
官方 wheel 及依赖总下载量 2,124,344,754 bytes；全部 SHA256 核验通过。两份镜像依赖缺少 index hash，
额外向 PyPI publisher metadata 查询同名同版本 wheel 的 SHA256 后才接受。
安装采用离线 `--require-hashes`，没有从未锁定源安装额外包。

## 验证范围

1. 科学计算依赖与 torchvision 导入。
2. RTX 5060、capability 12.0、编译架构 sm_120 检查。
3. FP32 矩阵乘法，最大绝对误差 2.56e-7。
4. FP16 矩阵乘法。
5. BF16 矩阵乘法。
6. cuDNN 卷积及 FP16 autocast，对照 CPU。
7. 640×360 双线性深度恢复，CPU/GPU 最大绝对差 1.79e-7。
8. float64 SPD 线性求解，最大绝对差 2.55e-15。
9. 合成 autograd 梯度对照，没有模型训练或 optimizer step。
10. torchvision 原生 CUDA NMS。
11. pinned CPU/GPU 数据传输。
12. Windows spawn 独立子进程 GPU 运算；未测试跨进程 CUDA Tensor IPC。

详细预设容差、逐项结果和失败跟踪逻辑见 `scripts/gpu_probe.py` 及 `after/GPU_SMOKE_REPORT.json`。
父进程 PyTorch 峰值 allocated 34,340,864 bytes，仅是合成检查，不是模型显存预算。
没有改变 cudnn deterministic/benchmark：本次记录均为 false。

## 实际解决的问题

- 目标环境没有 torch：加入官方 CUDA 13.2 wheel，确认不仅能导入，而且原生 GPU 算子可执行。
- Windows 空字符串 CUDA mask 检查不一致：`available=True`、`count=0`、`initialized=False`。
  失败证据保留在 `logs/CPU_MASK_INITIAL_EMPTY_VALUE_DIAGNOSTIC.log`。
  项目 CPU 启动器改用经实测的 `CUDA_VISIBLE_DEVICES=-1`，得到 false/0/false；GPU 使用0。
  只设置子进程环境，不修改系统或历史服务器合同。
- C: 空间有限：下载和临时文件放 D:，安装前按 wheel 展开体积检查余量。
  现有 Conda 环境按用户要求保留原位置；安装后约5.02 GiB可用。未来模型缓存由启动器指向 D:。
- 一个下载脚本最初假设每个 pip plan 依赖都带 hash，遇 Jinja2 停止；修正为独立 publisher hash 验证。
  未重复下载已验证的大 wheel，没有跳过哈希检查。初次失败日志保留。

## 长期执行约定

| 位置 | 用途 |
| --- | --- |
| 本地 RTX 5060 | 小批量 GPU 原型，逐帧 Metric3D/TTA 的候选运行，轻量模型/算子探索 |
| 本地 CPU | GT审计、数据处理、指标、统计、可视化、测试及数学验证 |
| 远端 RTX 3090 | 按阶段授权的完整 SLAM、长程 BA、全量数据与正式论文实验 |

`project_files/AGENTS.md` 和 `project_files/LOCAL_EXPERIMENT_WORKFLOW.md` 为项目中的同内容副本。
`project_files/run_gamecam_local.py` 提供固定环境、CPU/GPU选择和D盘缓存入口。
这些副本与实际项目文件逐字节核验。不把本轮环境调试当成R2.3/训练/新SLAM授权。

## 局限与下一步

- 尚未加载 Metric3D、DINO 或 DROID-W，未执行真实RGB、权重反序列化、SLAM或训练。
- 8GB不保证任何指定模型可容纳；下一次已授权本地模型任务从batch=1、单帧开始，记录实际显存。
- 不默认把FP16用于冻结协议；必须隔离精度变化并验证输出。
- 本地 Windows/PyTorch 2.15/CUDA13.2 不与远端冻结环境自动等价。
- 自定义CUDA编译尚未验收；当前PATH未找到cl/CMake/Ninja，不声称DROID原生扩展可在本机直接运行。
- 未连接或改变远端GPU资源；GitHub发布仅使用已授权凭据执行报告交付。

本轮完成后停止。下一阶段仍按用户的具体实验授权执行。

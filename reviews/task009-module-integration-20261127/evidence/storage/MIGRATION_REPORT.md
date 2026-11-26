# 项目存储迁移

2026-11-27。用户要求“全部移动到D盘”。

现有 GameCam-VO 环境实际目录为 `D:\aaa\envs\gamecam-vo`，不是重新安装或替换包版本。
原 C: 环境路径保留为 Junction；旧路径的 Python 已实际执行成功。

| 内容 | D: 实际目录 | SHA-256 核验文件数 | 字节数 |
|---|---|---:|---:|
| gamecam-vo 环境 | `D:\aaa\envs\gamecam-vo` | 36,414 | 3,984,580,414 |
| Hugging Face 缓存 | `D:\aaa\caches\huggingface` | 76 | 2,923,288,049 |
| Torch 缓存 | `D:\aaa\caches\torch` | 261 | 451,724,589 |
| Conda 包缓存 | `D:\aaa\caches\conda_pkgs` | 70,550 | 2,610,512,494 |
| pip 缓存 | `D:\aaa\caches\pip` | 115 | 4,666,674 |

操作顺序：复制 → 两端逐文件流式 SHA-256 → D: CUDA 验证 → 原目录改名 → 建立兼容 Junction → 删除已验证的旧副本。
所有目标均使用固定绝对路径校验。复制和删除失败时停止；不删除其他项目或系统文件。

实测 C: 从 230,195,200 可用字节增加到 10,198,106,112 字节，约从 220 MiB 增加到 9.50 GiB。
剩余空间是此时采样，不是固定保证。各目录的文件清单与切换收据保存在本目录。

验证：原版 Python 3.11.18、torch 2.15.0+cu132、torchvision 0.29.2+cu132 保留；
RTX 5060 (sm_120) 的实际 CUDA 矩阵运算和 torchvision CUDA NMS 通过；`pip check` 通过。

新增 Conda 激活/退出钩子仅影响 gamecam-vo 会话，将临时文件和缓存写入 D:，退出时恢复原变量。
本项目启动器改为直接使用 D: 环境，临时目录为 `D:\aaa\tmp\gamecam-vo`。
代码、数据、权重、WSL 专用实验运行库与新实验结果原本就在 D:，继续保留。

Windows、驱动、系统分页文件及其他 Conda 环境保持原状。

迁移后的 TASK009 实际进度：MDTracker 16 帧降低尺寸重试成功，32 帧低分辨率推理成功；
GPU 动态观测权重适配器的 124 项坐标/参数测量完成。
这些属于独立模块验证，尚不构成 DROID-W E0/E1 轨迹精度结果。

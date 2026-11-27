# TASK011C：A7 空间效用对照——数据审计与 CPU 准入评审

日期：2026-11-28（Asia/Shanghai）。前置提交：`78ca580c636bb232eba6d46ccf704b193988b5ab`。

**结论：CPU 实现通过，数据准入阻断；研究决策为 `INCONCLUSIVE`。本轮 GPU 运行 0 次。**

按任务书最后一段，本轮只完成数据审计、A7 实现和 CPU 测试，停在正式 GPU 准入前。
这不是 300 次实验结果，也不是 A5、A7 优劣的验证。

## 1. 数据阻断有直接历史记录

VIPER Validation 共 47 条源序列。历史 3090 双 Baseline 全序列运行终态清单已覆盖
全部 47 条：94 条模型终态，92 次 COMPLETE、1 次 GPU_OOM、1 次 BUFFER_CAPACITY。
本轮逐条对照 94 份独立 `attempt.json`，身份与状态均匹配。失败且已处理输入的源序列
同样参与过对照，不能包装为未使用数据。历史 stride=4 不是当前协议，但仍构成源序列暴露。

扫描了 1450 份历史 Manifest/执行索引候选文件。
扫描中的普通文本引用只记为引用，不单独当作运行证据；排除依据是完整终态和独立运行收据。
全部规则下可用新源序列为 **0**，没有冻结正式窗口，没有创建可执行 GPU 顺序表。

| 天气 | Validation 总数 | TASK011B 用过 | 只排除 TASK011B 后剩余 | 排除全部历史对照后 | 要求 |
|---|---:|---:|---:|---:|---:|
| Day |12|4|8|0|4|
| Sunset |10|4|6|0|4|
| Rain |7|4|3|0|4|
| Snow |8|4|4|0|4|
| Night |10|4|6|0|4|

即使忽略更早的实验，Rain 也只有 3 条，不能满足每天气 4 条。本轮没有自行改成 Train、
缩减天气配额、复用旧窗口或下载新数据。47 个中点的 K/相机映射/GT path 和 ZIP 目录存在性
只是候选普查，不是算法表现筛选；没有解压或解码新 RGB。

证据：[数据准入表](01_DATA_ADMISSION/VALIDATION_SEQUENCE_ADMISSION.csv)、
[历史逐次执行证据](01_DATA_ADMISSION/HISTORICAL_EXECUTION_EVIDENCE.csv)、
[最终数据决策](01_DATA_ADMISSION/DATA_ADMISSION_DECISION.json)。

## 2. A7 实现了什么

A0/A1/A4/A5 原样调用父提交锁定实现。A7 缓存保留完全相同的 A5 像素可靠性，直到
实际 BA 调用才在原生 disparity 网格、真实 `kx=unique(arange(t0,t1)∪ii)` 和
`M=(mono_disparity>0)∩Native-valid` 内逐源帧求均值；M 外为零。没有使用整张 640×360 均值。

每次调用验证有效/正支持集、逐帧均值、整次调用有效域与稠密域均值、A7 常数性。
alpha 保持 0.01；原始 30 个 BA 实参、U/UBA、Schur、retraction、迭代次数未改。
非局部 BA、初始化、Final BA、Filler 与 motion-only 均保持原安装路径。

**匹配边界：** 这里保证 A7 对“同一个当前状态的反事实 A5”均值相同。
两条独立运行的关键帧和调用历史可能分叉，不能声称两条轨迹第 k 次 BA 的均值也必然相同。
若评审要求后一种严格固定状态匹配，需要另行批准实验设计，本轮未擅自固定关键帧。

**支持集边界：** 若非有限 Confidence 导致 A5 在 M 内为零，均匀化可能重新启用该像素。
实现会 STOP，而不修改 M 或悄悄恢复先验。Pair-invalid 的 Native-only fallback
先由原 A5 计算，然后参与均值；A7 不保留像素间不同的 fallback 系数。

见 [数学定义](02_A7_IMPLEMENTATION/A7_MATHEMATICAL_DEFINITION.md) 和
[源码](reproducibility/experiments/TASK011C/uniform_control.py)。

## 3. 真实执行的 CPU 验证

- 新增 A7 合同与 CPU Tensor 接入测试：56/56。
- 原 TASK011B 回归：66/66；合计 **122/122**，无跳过。
- 独立数值探针：12 次合成 BA 调用、119 个源帧记录，网格 45×80，CPU 种子 43/44/45。
- 逐源帧最大 FP32 均值误差 **7.95852723723e-08**，低于原定 1e-6；没有放宽容差。
- 输入数组保护通过；PyTorch CPU 测试没有初始化 CUDA，没有导入或加载研究模型。

这些是合成数学和接入合同证据，不是原生 CUDA 等价性或 VIPER 轨迹实验。
首次回归因父提交顶层没有物化一份历史 JSON 夹具而报错；随后从同一固定提交展开评审中
恢复逐字节相同夹具，通过完整回归。保留第一次日志，没有删除失败测试或修改其断言。
首次目录检查将跨分卷公共目录误当作重复文件，已改为只比较 JPEG 文件成员，保留开发记录。

见 [完整测试结果](03_CPU_VERIFICATION/results_002/CPU_TEST_SUMMARY.json) 和
[合成均值审计](03_CPU_VERIFICATION/cpu_probe_001/SYNTHETIC_PER_SOURCE_MEAN_AUDIT.csv)。

## 4. 保护与局限

父提交实验代码/配置等 79 份与本地原始 DROID-W 源码 110 份，
执行前后 SHA-256 全部一致。没有编译 CUDA、替换生产扩展、读取权重、运行模型或接触远端实验。
远端 GitHub 发布（如已完成）仅用于交付，不属于研究计算。权重及远端扩展没有在本轮重新
做现场 SHA 核验，不能将“未访问/未修改”写成新的远端运行证书。

没有 A5/A7 真实轨迹、GPU 时间/显存、三 seed 稳定性、天气效果、bootstrap CI 或空间效用结果。
不以 TASK011B 的已有 ATE 填充本轮表格；不将合成 Probe 种子当成正式三 seed 重复。
没有动态/深度概率校准结论，也没有证明均匀衰减足够。

## 5. 下一步审查点

首先决定是否以及如何修订数据排除规则和天气配额；任何修订必须在看新算法结果前冻结。
同时明确同状态均值匹配的估计对象，以及 RPE、raw-scale 和成本的数值退化边界。
当前任务书没有给这些次指标“不可接受退化”的数值界限，不能事后按结果选择。

在这些问题解决并获得后续 GPU 准入之前，**不启动 Pilot、不运行 300 组、不开发新 Geometry Need**。

[完整协议](00_PROTOCOL/PROTOCOL.md) · [下一阶段边界](06_DECISION/NEXT_STAGE_BOUNDARY.md) ·
[机器可读决策](TASK011C_DECISION.json)

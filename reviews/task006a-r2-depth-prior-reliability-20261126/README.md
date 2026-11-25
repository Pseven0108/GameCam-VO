# TASK006A-R2｜Metric3D 深度先验可信度研究：阶段证据包

日期：2026-11-26（Asia/Shanghai）。状态：**PARTIAL / WAITING_GPU_AND_GT_ADMISSION**。
进入联合可信度控制器的决策：**NO-GO — INSUFFICIENT_INDEPENDENT_EVIDENCE**。

请先读 [最终研究报告](TASK006A_R2_FINAL_RESEARCH_REPORT.md) 和
[阻断与恢复入口](TASK006A_R2_CODEX_HANDOFF.md)。本包不是完整的 GPU 可信度验证结果。
61/61 是 CPU 评价器、源代码监督 mask 和数据合同测试，不能当作 Metric3D 准确率。

已完成：实际模型/权重身份核验、Confidence 生成与监督源码审计、四篇核心论文阅读、
100 帧真实 RGB/EXR/相机数据审计、300 个 MVS 文件身份复核、投影诊断、独立 CPU 评价器。
未执行：模型加载、Confidence 数值推理、TTA 推理、真实 bin 分布提取、梯度实验、GT 准确性评价。

实测远端 nvidia-smi 返回 Exec format error，未确认可用 GPU；没有重启、申请 GPU 或修驱动。
审计的本地 VIPER 输入没有配套 Dense Depth GT；MVS-Synth 0000 的物理单位尚未建立，
且只有一条完整序列，不具备序列独立的校准与测试划分。

所有未测数值 CSV 保留空值和 NOT_EXECUTED 状态；空值不是零误差。
03_dataset_audit 中的图是真实 GT 审计图，不是预测深度或 Confidence 热力图。

可复算代码在 experiments/scripts。源代码快照及许可证在 evidence/sources；
SHA256_MANIFEST.csv 覆盖发布负载，ZIP 内文件原样对应展开目录。
为避免递归，清单不包含其自身、外部 ZIP 及验证收据；详见 PACKAGE_CONTENTS.md。
无模型权重、原始数据集或论文全文随包发布。R1 和 Baseline 资产保持封存。

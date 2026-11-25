# TASK006A-R2 最终阶段评审入口

**PARTIAL_WAITING_GPU_AND_GT_ADMISSION / NO-GO_INSUFFICIENT_INDEPENDENT_EVIDENCE。**

完整报告：[TASK006A_R2_FINAL_RESEARCH_REPORT.md](TASK006A_R2_FINAL_RESEARCH_REPORT.md)。
已完成源码/权重核验、四篇论文相关全文阅读、100 帧真实数据审计、61/61 CPU 测试；没有模型推理结果。
Confidence 监督 mask 排除 relative error>=1 的位置；需要真实误差验证，不能据此宣布模型无效。
当前 GPU 不可用，VIPER 本地无配套 dense-depth GT，MVS 单位及独立序列划分不足。
不能使用 R1 几何输出作伪 GT，不能把 raw score 称为概率，不能接入 CADP/BA。
评审包保留完整本轮相关脚本、原始读写收据、结构化结果、源码和可视化；
论文全文、工具依赖、权重和原始数据集仅列来源或 SHA，不再分发。

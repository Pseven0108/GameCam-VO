# Task005A真实执行记录

- 2026-11-25，接收“封存Task004C-B、集中解释D×S反向效果”指令。
- 首次探索脚本对B4路径使用D盘位置导致FileNotFound；实际B4/B3在C盘receiver。仅修正新Task005A读取路径，未搬动或修改原始数据，失败检查日志保留。
- 一个探索输出错误地按数值event ID统计，造成冗长诊断；后续改用type。该输出没有被用于科学指标或结论。保留初稿脚本，正式分析使用task005a_analysis.py。
- ANALYSIS_01：共同支持评分、4756次BA三联记录、各阶段/端点/图/深度诊断完成，exit0。
- SECONDARY_01：同调度离散字段相等性、203候选前缀、强制/自然决策、先验尺度归一化、源码Git Blob复核完成，exit0。
- CPU_QA_01：22/22真实执行通过，生成4张Matplotlib图，exit0；四图逐张查看。
- METRIC_SENSITIVITY_01：四组全487位置Sim(3)ATE与封存结果差值均小于1e-10；审计表明确保留尺度/旋转指标不具有同样反转的事实。
- REPORTS_01/02：生成正式证据报告与输入完整SHA清单；02补充评价口径敏感性，不改写Task004C-B。回执/输出保存于07_evidence。
- 全部Python进程显式设置CUDA_VISIBLE_DEVICES为空，未导入PyTorch，未加载模型或C0，无GPU/SSH操作。
- 本机读原有stage/observer/native-trace/选定npz数组；所有新文件只写入Task005A及后续独立发布checkout。
- 原实验ZIP整体SHA、1772文件元数据和85项内容SHA复核保持一致。包装/发布阶段的CRC、SHA和GitHub读取验收由独立回执记录。

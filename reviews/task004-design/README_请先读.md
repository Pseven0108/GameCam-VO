# Task 004 静态轻量评审包

入口：[TASK004_FINAL_REVIEW.md](TASK004_FINAL_REVIEW.md)。本包是 DROID-W 消融设计与 CPU 模拟证据。没有运行 GPU、DROID-W 或 VIPER；不包含新轨迹、新 ATE 或因果结论。

| 想复核什么 | 阅读入口 |
| --- | --- |
| 三个因素能否独立且只在局部 BA 生效 | [底层开关](TASK004_LOW_LEVEL_SWITCH_AUDIT.md)、[阶段范围](TASK004_PHASE_SCOPE_AUDIT.md)、[实参补丁](candidates/TASK004_ON_TASK003.diff) |
| 8 组如何比较、为何要复跑 E0 | [矩阵](TASK004_FACTORIAL_MATRIX.csv)、[交互计划](TASK004_FACTOR_INTERACTION_PLAN.md)、[评分](TASK004_METRIC_AND_STATISTICS_PLAN.md) |
| 历史观测凭据 | [Task003 成绩与证据摘要](evidence/task003_selected/TASK003_FINAL_REVIEW.md)、[证据指纹](evidence/HISTORICAL_INPUTS.json)、[Task003 关键事件](evidence/task003_selected/TASK003_312_328_LOCAL_BA_TIMELINE.csv) |
| 这次真正执行了什么 | [执行记录](EXECUTION_LOG.md)、[最终 CPU Mock 原始输出](logs/cpu_mock_release.stderr.txt)、[退出码](logs/cpu_mock_release.exit.txt) |
| E5-F 与后续 GPU | [Final BA 阶段设计](TASK004_E5_FINAL_BA_PLAN.md)、[预算与停止门槛](TASK004_RESOURCE_AND_RUN_BUDGET.md) |

包内候选代码、策略和冻结 YAML 仅供审阅。历史选段证据是原字节副本；历史报告中指向未收录的大文件的链接需在原 Task003 目录查看。包内不附 RGB、权重、原始 GT、CUDA 库、全仓库或大体积运行日志。

可直接把此 ZIP 交给 GPT 聊天版评审。若聊天版不能解压，优先单独提供 TASK004_FINAL_REVIEW.md、TASK004_LOW_LEVEL_SWITCH_AUDIT.md、TASK004_PHASE_SCOPE_AUDIT.md、TASK004_FACTORIAL_MATRIX.csv 与 logs/cpu_mock_release.stderr.txt。所有载荷的 SHA-256 与大小见 FILE_SHA256_MANIFEST.json；清单不自列，整个 ZIP 的哈希由外部回执记录。

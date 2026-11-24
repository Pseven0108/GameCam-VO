# Task004-A：筛选实验评审材料

先读 `TASK004A_FINAL_REVIEW.md`。本地准备测试已完成，**正式 GPU 消融未获批（0/8）**。可单独把最终报告和端点合同给 ChatGPT 审阅；ZIP 同时带可检查的实现、证据和校验清单。

- `TASK004A_RELEASE_READINESS.md`：锁定实验、当前通过项和上线前缺口。
- `TASK004_ENDPOINT_RETENTION_PLAN.md`、`TASK004_*ENDPOINT*.csv`：固定 RGB 最终导出和保留关键帧采用两套口径，另报保留情况；无正式数值。
- `TASK004_E5_F0_FINAL_RECHECK.md`：为什么 F0 的原生准入继续阻断。
- `TASK004A_*_AUDIT.md`、`TASK004A_*_PLAN.md`、`TASK004A_LOG_PARSER_TEST.md`：串行、日志、可视化与归档。
- `evidence/`、`evaluation/`、`logs/`：冻结资料复核、Task003 旧数据回放、替身可复核收据、执行日志。`HISTORICAL_TASK003` 和 `SYNTHETIC_ONLY` 均不可用于正式比较。
- `_local_probe/probe_05/`：本机浏览器截图、传输计数、版本与执行记录。

包内 `FILE_SHA256_MANIFEST.json` 校验所有其余成员。没有权重、VIPER 图像、GT 文件、原始全量历史 trace、完整仓库、SDK、浏览器配置或远端连接凭证；需重跑依赖历史原件的验证时，使用其原有位置。`--native` 与候选 runner 的原生启动保护继续生效。

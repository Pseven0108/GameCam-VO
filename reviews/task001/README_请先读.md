# GameCam-VO Task 001 评审入口

**主线：VIPER `stride=1` 正式配对评估。状态：源码审计完成，`val_007` 的运行时根因未确定。** 历史 `stride=4` 结果只作归档，停止沿该分支推进；原始源码和实验记录均保留。

1. [FINAL_REVIEW.md](FINAL_REVIEW.md)：正式结果、来源与版本、候选机制和研究决策。单独上传此文件也可阅读核心结论。
2. [ARCHITECTURE_AND_BA.md](ARCHITECTURE_AND_BA.md)：对照两版前端、匹配、深度、不确定性、在线 BA、最终 BA 和轨迹补位，附具体源码行号。
3. [INSTRUMENTATION_PROPOSAL.md](INSTRUMENTATION_PROPOSAL.md)：以后如何用同一段 `stride=1` 输入定位变化。本轮只交付设计，未实施埋点或启动后续实验。
4. `evidence/`：版本与来源、完整文件与符号差异表、正式 R2 输入和配对依据、`val_007` 区间位移、已读取历史文件的 SHA-256。
5. `logs/` 与 [EXECUTION_LOG.md](EXECUTION_LOG.md)：静态核验两次尝试的真实输出与退出码；ZIP 内 `FILE_SHA256_MANIFEST.csv` 覆盖除清单自身外的所有成员。

压缩包未收录完整仓库、24.4 MB 文本差异、RGB、权重或轨迹大文件。完整原始证据的磁盘位置和哈希见最终报告与 `evidence/AUDIT_INPUT_FINGERPRINTS.csv`。

# Task004C-B 发布修复 CPU评审包

请先读 `FINAL_REVIEW.md`，再读五份 `TASK004C_B_*.md`。

本包包含：Local BA安全边界修复、文件映射共享存储实现、完整C0预算机制、原118项记录与152项最新回归、失败记录、原尺寸2.2464GB双CPU进程proof、小型快照预算实测、源代码preimage与patch。

**没有真实GPU实验、没有C0、没有RGB前缀、没有B1/B2/B3/B4结果。** 完整C0大小未知；CPU共享机制通过不等于真实Tracker/Rerun已验证。

文件导航：

- `candidate/`：从完整远端093分支导出的相关改后源码子集。
- `baseline_export/`与`source_before/`：远端093基线相关源码与Git preimage。
- `tests/`与`configs/`：CPU套件及既有合同副本，未授权正式执行。
- `evidence/FINAL_RELEASE_AUDIT.json`：完整版本、原资产保护、提交及空间收尾证据。
- `evidence/CPU_final/.../CPU_TEST_REPORT.json`：152项逐项结果。
- `evidence/ORIGINAL_118_CPU_TEST_REPORT.json`：原始118记录，原样保留。
- `evidence/FULL_BUFFER/`：完整尺寸CPU proof。
- `evidence/FINAL_ARTIFACTS/`：patch、版本绑定证书、小型CPU预算fixture。
- `tools/`：合成试验及CPU传输辅助源；传输助手依赖本项目已有受信SSH bootstrap，不包含凭据。

SHA清单覆盖除两份清单自身外的全部包内文件；外置验证记录提供ZIP CRC、清单匹配和ZIP SHA。包不含模型、RGB、完整官方仓库或两块2.09GiB大合成backing文件。不得将合成snapshot误标为真实C0。

# GameCam-VO · Task004A 补充复核评审包

**建议先读 `TASK004A_FINAL_RELEASE_RECOMMENDATION.md`。** 本轮交付的是源码范围、历史证据复算和磁盘模拟；正式筛选为 0/8，仍阻断。选择效应、真实机容量和远端 Rerun 应各自审批和验证。

| 要复核什么 | 看哪份文件 |
| --- | --- |
| 为什么这八组只能解释前端总效应 | `TASK004A_SCOPE_RECHECK.md`、`TASK004A_PHASE_EFFECT_INTERPRETATION.md` |
| 怎么单独测 BA 的直接作用 | `TASK004_DIRECT_EFFECT_FOLLOWUP_DESIGN.md`（仅设计） |
| 已知产物大小、完整输出缺口、同盘与异机容量 | `TASK004A_REAL_STORAGE_CAPACITY_REVIEW.md`、`TASK004A_EIGHT_ARM_STORAGE_SIMULATION.csv` |
| 哪些地方还需要授权再查 | `TASK004A_REMOTE_PREFLIGHT_CHECKLIST.md` |
| 复算证据 | `TASK004A_LOCAL_EVIDENCE.json`、`TASK004A_ARM_PHASE_STATISTICS.csv`、`LOCAL_ANALYSIS.*.txt`、`measure_local_evidence.py` |

无模型权重、RGB、原生大文件或完整源码仓库。CSV 采用 UTF-8，空白值与 `NOT_RUN` 表示没有正式观察。内部 `FILE_SHA256_MANIFEST.json` 覆盖全部载荷成员，不自哈希。

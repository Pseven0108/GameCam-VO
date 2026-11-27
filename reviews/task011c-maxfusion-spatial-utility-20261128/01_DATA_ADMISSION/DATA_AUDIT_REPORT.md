# Validation 源序列资格审计

准入规则未降低。全部 47 条 Validation 源序列已经有历史双 Baseline 执行记录，
严格排除后为 0；只排除 TASK011B 后，Rain 也仅有 3 条。

所有 94 个 aggregate 记录与各自独立 attempt.json 的 case/model/status 一致。
val_043 的两次失败已经分别处理了真实输入，仍属于参与过对照的源序列。
退役的 stride4 研究分支并未恢复；其历史暴露记录不能因此消失。

GT path >0.0001 native camera units 与 K <0.001 px 在任务开始前写入 STAGE_CONTRACT。
审计只读取已有 offline_gt 缓存，不向算法提供 GT。原始 ZIP 只读取中央目录；
成员存在不代表本轮 CRC 或 JPEG 解码通过，未作这类虚假声明。

REPOSITORY_MANIFEST_CENSUS 是有界的名称/文本引用普查，并非所有本地资料的穷尽证明。
它既不把计划表当执行证据，也不把 Train 001 和 Validation 001 合并。
证明本轮无可用源序列只需已独立核验的完整 Validation 终态证据。

GPU_EXECUTION_MANIFEST.csv 只有列名、0 行，明确表示没有正式运行计划。
VALIDATION_SEQUENCE_ADMISSION 的 47 个中点是普查记录，不是被冻结的 20 个正式窗口。

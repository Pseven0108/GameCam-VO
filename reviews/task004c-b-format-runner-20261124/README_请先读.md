# 请先读

本轮结论：**Format 修复和真实 C0 跨进程状态恢复通过；RGB019 续跑因输出目录冲突失败。**

先读 `FINAL_REVIEW.md`，再读 `TASK004C_B_RESTORE_FINAL_REPORT.md` 和 `TASK004C_B_FORMAT_CLOSURE_REPORT.md`。

实际 GPU 阶段：1 次初始化 C0 采集成功，1 次新进程恢复检查在续跑前失败；Short80 和 B1～B4 均为 0。真实 C0 存在且哈希完整，不需要通过 CPU fixture 假称成功。没有新轨迹评价结果。

候选源码 `5d357c1d3079de134dd8b41a20a00632da37f0b0`。C0 state SHA `18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92`。

`raw_evidence` 是原始执行文件的脱敏公开副本。`source_diff` 给出两个本轮 commit 的完整差异；`candidate_source` 是最终候选的 SHA 核验源码子集，完整源码对应仓库 `source/DROID-W` 导出树。`test_tools` 是实际执行的测试/调度工具，依赖既有环境和私有资产，不能视为自包含环境。

公开清单覆盖除清单自身外的全部交付文件。ZIP CRC、内部哈希和 GitHub 匿名读取在发布收据记录。C0 Tensor/权重/RGB/GT/Arena/Rerun 二进制仅保存在原研究存储。

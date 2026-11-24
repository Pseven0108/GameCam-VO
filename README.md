# GameCam-VO

VIPER / DROID-W / stride=1。研究深度先验、不确定性、优化与关键帧调度。

## 最新评审：Format 闭合、真实 C0 与 RGB019 运行器

- [最终报告](reviews/task004c-b-format-runner-20261124/FINAL_REVIEW.md)
- [请先读](reviews/task004c-b-format-runner-20261124/README_请先读.md)
- [真实GPU C0](reviews/task004c-b-format-runner-20261124/TASK004C_B_GPU_C0_FINAL_REPORT.md)
- [跨进程恢复及停止原因](reviews/task004c-b-format-runner-20261124/TASK004C_B_RESTORE_FINAL_REPORT.md)
- [最小后续方案，未实施](reviews/task004c-b-format-runner-20261124/NEXT_MINIMAL_RUNNER_FIX_PROPOSAL.md)
- [状态与预算](PROJECT_STATUS.md) · [历史评审索引](REVIEW_INDEX.md) · [源码身份](source/SOURCE_PROVENANCE.json)

**Format及完整CPU模型恢复通过，217/217发布前CPU测试通过。真实GPU C0保存成功（854文件），新GPU进程完整状态恢复通过（18,143节点）；进入RGB019前因native输出目录冲突退出。**

本轮GPU：C0采集1次成功，恢复检查1次在续跑前失败。RGB019未处理，Short80 0/4，B1～B4 0/4；没有新487帧轨迹或算法改善结论。遵守失败即停，无自动重试，3090保持在线。

运行候选：`5d357c1d3079de134dd8b41a20a00632da37f0b0`。本分支：`codex/task004c-b-format-runner-20261124`。公开发布commit与运行源码commit独立记录；默认分支和仓库可见性保持。

报告和原始执行日志为脱敏公开副本，内部SHA对公开字节计算；原始→公开映射另附。权重、RGB、GT、C0 Tensor载荷、Arena、Rerun二进制保留在原研究存储。旧阶段评审全部保留。

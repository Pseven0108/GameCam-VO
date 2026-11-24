# GameCam-VO

VIPER / DROID-W / stride=1。研究深度先验、不确定性、优化与关键帧调度。

## 最新评审：ConfigDict专项修复

- [最终报告](reviews/task004c-b-configdict-closure-20261124/FINAL_REVIEW.md)
- [请先读](reviews/task004c-b-configdict-closure-20261124/README_请先读.md)
- [完整模型新进程恢复](reviews/task004c-b-configdict-closure-20261124/TASK004C_B_REAL_MODEL_ROUNDTRIP.md)
- [CPU最终准入](reviews/task004c-b-configdict-closure-20261124/evidence/TASK004C_B_CPU_FINAL_GATE.json)
- [完整源码diff](reviews/task004c-b-configdict-closure-20261124/CONFIGDICT_FULL_SOURCE_DIFF.patch)
- [下一步最小枚举适配方案](reviews/task004c-b-configdict-closure-20261124/NEXT_MINIMAL_ENUM_ADAPTER_PROPOSAL.md)
- [状态与预算](PROJECT_STATUS.md) · [历史评审索引](REVIEW_INDEX.md) · [源码身份](source/SOURCE_PROVENANCE.json)

**ConfigDict：14/14专项通过、152/152历史回归通过、6个实际ConfigDict / 24节点子图精确比较通过。完整真实模型跨进程恢复仍失败，阻断为独立的timm.layers.format:Format。**

恢复后的forward、gradient与完整Storage/47状态族对比尚未到达。ConfigDict专项额度使用1/2；没有挪用剩余额度修改独立枚举。新GPU C0 0/2、短程0/4、正式四组0/4；3090保持在线。

运行候选：`aa0cca3ed0d6e5d381422d8219234b8c0c6ad065`。本分支：`codex/task004c-b-configdict-closure-20261124`。发布提交与运行候选提交分别记录；没有更改默认分支或仓库可见性。

报告、日志、源码和SHA清单使用脱敏公开副本。历史评审保留；模型权重、RGB、GT、Tensor payload和Arena保存在私有研究存储。本轮没有新增轨迹精度、尺度改善或因果效应结果。

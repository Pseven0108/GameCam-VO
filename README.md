# GameCam-VO

VIPER / DROID-W / stride=1。研究深度先验、不确定性、优化和关键帧调度的关系。

## 最新评审 · Task004C-B 自动连续执行

- [最终报告](reviews/task004c-b-autonomous-20261124/TASK004C_B_AUTONOMOUS_FINAL_REVIEW.md)
- [CPU闭包修复](reviews/task004c-b-autonomous-20261124/TASK004C_B_CLOSURE_FIX_REPORT.md)
- [真实CPU跨进程验证](reviews/task004c-b-autonomous-20261124/TASK004C_B_CHECKPOINT_CPU_ROUNDTRIP.md)
- [152项回归](reviews/task004c-b-autonomous-20261124/TASK004C_B_CPU_REGRESSION.md)
- [完整评审索引](REVIEW_INDEX.md)
- [状态与预算](PROJECT_STATUS.md)
- [源码身份](source/SOURCE_PROVENANCE.json)

**实际结果：CPU恢复被ConfigDict阻断。两轮Checkpoint修正已用尽；152/152既有回归通过，但真实模型恢复未通过。新GPU C0 0/2，短程0/4，正式四组0/4。3090保持在线。**

已核验71个identity函数；真实权重CPU前向、输入梯度及RNG检查完成。新进程在ConfigDict构造时失败；字典条目也未被现有__dict__编码保存，不能仅改构造器来绕过。

候选源码`a324b57760fdaf4929385f2271991d773533799d`，父提交`02f8c8308274489ff7eff83fa9b87b98db74122e`。本仓库提交是发布快照，与运行候选提交分开。当前分支`codex/task004c-b-autonomous-20261124`；没有自动改仓库默认分支。

本阶段公开材料已脱敏，公开SHA清单与原始→公开SHA映射均可读。RGB、模型权重、Arena、CPU夹具Tensor档案保留在私有数据盘，不进入公开包。历史评审不覆盖。

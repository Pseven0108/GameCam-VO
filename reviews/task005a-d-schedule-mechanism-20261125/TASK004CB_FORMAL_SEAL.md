# Task004C-B 正式封存决定

状态：FORMALLY_SEALED_FIRST_COMPLETE_FOUR_ARM_CONTROLLED_CROSSOVER。

按用户2026-11-25指令，Task004C-B 固定为**本项目第一项完整四组受控交叉实验**。这不是“文献首创”声明。原实验的实现、配置、轨迹、统计、失败记录和评审包均不再修改。后续分析和候选修复只能进入新的任务目录。

- 固定实验评审 Commit：a24ba97a515ec4fb6e4fd195922b4ac25e532d74。
- 独立收尾 Commit：d9656b66eb541b6f3889e41cd8329898edc6f0c8。
- [完整历史评审目录](https://github.com/Pseven0108/GameCam-VO/tree/a24ba97a515ec4fb6e4fd195922b4ac25e532d74/reviews/task004c-b-crossover-full-20261125)。
- [原完整ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task004c-b-crossover-full-20261125/TASK004C_B_CROSSOVER_FULL_REVIEW_20261125.zip)：234,629,566 bytes。
- 原ZIP SHA-256：765f2d39054faa21578393b4b131cfaf6652480663bc1f682ba5551cdf64b96a。
- 原ZIP包含654成员；内部653项文件SHA已在原发布中验证，本轮又复核ZIP整体SHA。
- 本轮封存清点1772个原文件的大小/mtime_ns，以及85个关键文件内容SHA；检查原目录和外部R3原始证据目录。不把85项内容校验写成1772项全量内容SHA校验。
- Task005A开始/结束复核均在00_seal保存；不将新报告或缓存写入旧实验目录。

受控范围：共同C0、同一val_007、Seed43、stride=1、640×360、buffer=500；D仅在前端main-loop Local BA切换。S1/S0固定离散插入/剔除/图拓扑/BA调用调度，连续Pose、disparity、U、target、weight仍自行演化。

完整四组：B1=D1/S1、B2=D0/S1、B4=D0/S0、B3=D1/S0，全部487帧完成；这不是原生E0从零初始化，也不是总体泛化结论。

保留历史限制：原运行曾记录53个资源采样点低于10 GiB余量，最低8.6362 GiB；Rerun记录已保存但浏览器真实渲染未核实；此前工程失败未混入四组成功结果。Task005A不改写这些事实。

当前服务器沿用上轮已停止状态；本轮未连接远端，未重新核实云端状态，未启动或再次关闭实例。

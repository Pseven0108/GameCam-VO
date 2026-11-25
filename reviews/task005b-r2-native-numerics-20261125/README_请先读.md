# TASK005B-R2 评审入口

先读 FINAL_REVIEW.md，再读 R2_FEEDBACK_TRACE.md 和 R2_CANDIDATE_READINESS.md。

本轮已完成10次真实GPU双迭代BA重放。仅用D0_S1_RGB233一个真实输入；未启动S0或模型前缀。

关键发现：原安装扩展自身重复就能触发原端点容差；观测到的最早差异是第一轮Jjj_data，早于J_linear。候选的严格U Native端点准入仍未通过。

公开Git目录包含全部报告、CSV、源代码、收据、两张图及小型原始trace。完整REVIEW.zip另含本轮10份完整原生数组、完整日志、独立观测.so和唯一完整输入快照，内含SHA清单。Git目录的FILE_SHA256_MANIFEST覆盖可浏览文件；ZIP内部另有覆盖全部大文件的SHA清单。

数值归因必须区分：直接记录、源码推导、CPU复算、尚未隔离的atomic/编译因素。禁止把本轮称为S1/S0反转解释或轨迹性能提升。

# Task004C 评审入口

先读TASK004C_FINAL_RESEARCH_REVIEW.md、TASK004C_A_FIXED_STATE_REVIEW.md、TASK004C_B_BLOCKER_AND_MINIMAL_NEXT_PLAN.md，再查看results中的四分支指标、共同有效支持残差、状态恢复收据与源码。

A已完成，B未执行。新A不是历史状态的逐位复现，也不是完整前端重启状态。2次328帧前缀与4次BA重放不能写成4次487帧轨迹实验。B缺失成绩为空，不计算不存在的ATE。

小包包含报告、CSV、输入/恢复哈希、少量真实位姿数组、测试、配置、适配器和保全核验。GB级输入、DINO张量、observer日志、RRD在单独TASK004C_FIXED_STATE_RAW_EVIDENCE.zip中；RAW_ARCHIVE_STATUS标明其SHA，清单不做递归自哈希。

GT仅用于离线评分，比例沿用历史固定尺度。两种方向诊断参照不同，分别报告。无同D重复，不称统计显著；无B结果，不估计中介效应。

请重点复核：分支是否只切换prior；D=0是否同时切换eta；E1先验与几何冲突；负视差计数与端点质量的分离；B共同重启与强制调度的证据缺口。

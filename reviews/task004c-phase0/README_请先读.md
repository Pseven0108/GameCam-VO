# 请先读

这是Task004C **Phase0证据与最小恢复方案包**，不是A/B成功结果包。当前GPU保持在线，资源正常；但历史完整快照缺失，故A/B均未启动。

先读 TASK004C_FINAL_RESEARCH_REVIEW.md、TASK004C_PHASE0_CHECKPOINT_AUDIT.md、TASK004C_MINIMAL_RECOVERY_PROPOSAL.md。

results目录中的A/B表是明确标注NOT_EXECUTED/UNAVAILABLE的交付状态，不是实验成绩。两份历史归档保留在原路径，未重复塞入本包；其成员CRC、SHA与大小已实读验证。evidence保存目标调用原始日志摘录、资源记录、源码证据、缓存覆盖和共同初始化对照。tools保存本次只读检查、归档核验和报告构建脚本。

SHA清单覆盖所有payload文件，清单自身不递归包含自身；ZIP容器SHA在包外。未包含权重、RGB或历史完整video.npz。不关机、不自动启动恢复采集或重试。

# Task004C-B 共同初始化与关键帧调度协议评审包

本包为协议设计和源码证据包，**不是新的GPU实验结果包**。请先读 TASK004C_B_PROTOCOL_FINAL_REVIEW.md。

关键结论：初始化含两阶段、共24次graph.update；原始D会参与初始化；需唯一D=0共同C0。当前C0尚未采集，现有runner也没有完整恢复与事件重放能力。最后磁盘实测13.28GiB，保留10GiB后3.28GiB不足以容纳保守四臂结果方案。正式四臂未执行。

10份要求的交付文件都放在ZIP根目录：源码审计、C0规范/设计manifest、调度协议与S1/S0 schema、四臂矩阵、恢复验收、资源预算、最终评审。JSON中明确NOT_CAPTURED/设计模板的字段不能解释为实际快照。

source_evidence仅包含本次检查所需的源码片段/文件，不含模型权重、RGB、GT或完整仓库。evidence包含历史身份、真实输出尺寸、最后资源记录和本轮只读核验。EXECUTION_LOG.md与logs保留本地审计的stdout、stderr、退出码。FILE_SHA256_MANIFEST.json覆盖本包全部其他文件（自清单不作递归自哈希）；包外PACKAGE_VALIDATION.json记录ZIP CRC和全部内部SHA核验。

评审重点：共同C0的语义边界、完整对象/RNG/alias闭包、同Schedule全过程图事件、同D短验证的预算与容差、磁盘方案。没有GPU运行授权扩张，没有修改原始R2或算法，没有自动关机、重启或删除历史成果。

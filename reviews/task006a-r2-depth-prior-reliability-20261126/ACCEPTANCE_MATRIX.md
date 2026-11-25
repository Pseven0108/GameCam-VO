# 用户验收逐项状态

| 项目 | 状态 | 证据/限制 |
|---|---|---|
| 实际模型/权重/代码 | PASS | 283 blobs + checkpoint SHA |
| Confidence 路径与训练 | PASS_SOURCE | 具体源码及 mask CPU复算 |
| 输出 shape/分布实际推理 | BLOCKED | GPU未确认 |
| 区分 depth/normal/DINO/R1 | PASS_SOURCE | 源码报告 |
| Baseline为何丢弃score | PARTIAL | 行为确认，动机UNVERIFIED |
| 核心论文与代码适用性 | PASS_READING | 阅读范围记录，不称全面代码复现 |
| VIPER/MVS本地模态 | PASS_AUDIT | 已实际检查，非全官方模态结论 |
| GT像素/几何 | PARTIAL | 非零基线支持；不是时钟/独立精度证明 |
| GT物理单位 | BLOCKED | native units未核实 |
| 独立校准/测试划分 | BLOCKED | 只有1条完整GT序列 |
| 无效GT处理 | PASS_CONTRACT | Inf sky排除，原文件不修改 |
| Native/TTA/bin真实评价 | NOT_EXECUTED | 不填假数据 |
| 梯度候选 | DEFERRED_BY_PROTOCOL | A/B/C未评价不是失败 |
| 模型计算开销实测 | NOT_EXECUTED | 只有理论forward次数 |
| 最终信号/环境适用性 | INSUFFICIENT_EVIDENCE | 暂不选择 |
| 联合设计决策 | NO-GO | 证据不足，非算法否定 |

本任务没有达到全部最终验收项，按用户停止条件交付部分证据包。

# 结论与证据等级

| 命题 | 等级 | 判定 |
|---|---|---|
| D效果在S1与S0反转 | OBSERVED | 固定共同72KF及全487导出均成立 |
| 反转已出现在前端 | OBSERVED | 前端共同支持分数复算成立 |
| Final BA/Filler首次制造反转 | CONTRADICTED_AS_SOLE_ORIGIN | 更早快照已有反转；不宣称两者完全无影响 |
| 全局尺度拟合或支撑集合差异足以解释全部反转 | CONTRADICTED_AS_SUFFICIENT_EXPLANATION | 共同支持Sim(3)反转依然存在 |
| D同时改变深度对角和先验梯度 | SOURCE_DERIVED | 冻结Git对象核验、原生CUDA1878–1899 |
| 固定图意味着连续输入相同 | CONTRADICTED | call26前六类Tensor均已分化 |
| U与有效权重随D变化 | OBSERVED_ASSOCIATION | W/U开关相同，但实际值演化；独立中介效应未识别 |
| S0的边更少，所以更弱 | CONTRADICTED_AS_STATED | Predecision边中位数188对S1的80 |
| S0真实Schur系统病态 | UNRESOLVED | 无完整Jacobian/Schur/特征值 |
| Metric3D真实深度不准 | UNRESOLVED | 无独立Depth GT；保存先验一致性不是准确性 |
| 负视差越多必定轨迹更差 | CONTRADICTED | B2负值多于B1而ATE更低 |
| D在S1偏置代价、S0稳定收益的平衡不同 | SUPPORTED_MECHANISTIC_HYPOTHESIS | 数学可行，分项原生反事实未执行 |
| RGB233就是物理故障起始帧 | UNRESOLVED_NOT_CLAIMED | 只是时变前缀指标首次过零 |
| D应被永久关闭 | NOT_SUPPORTED | 条件效果相反，单场景单种子 |

指标边界：反转针对Sim(3)位置ATE，统一历史尺度诊断和姿态误差并不具有同样反转；不能将结果等同于米制尺度恢复或所有轨迹指标的改善。

统计边界：每臂n=1；不使用BA事件做独立样本，不生成伪精确置信区间。S1/S0为生产臂内生调度包；图拓扑、保留时刻、调用次数共同变化，不隔离关键帧数量。

数据边界：GT仅用于本轮离线评分。未重新读取RGB；native video.npz仅读取timestamps、mono_disps、droid_disps、uncertainties，不加载images数组。没有反序列化模型、C0或Tensor checkpoint。

观测边界：native完整活动grid census可以量化负值/floor；几何残差和权重是最多24边、步长4像素的CPU重建；η是采样统计。三类范围必须区分。

研究状态：现象和数学路径已闭合；主导机制与分项因果归因未闭合。完整科学结论不能写为PRIMARY_ROOT_CAUSE_FOUND。

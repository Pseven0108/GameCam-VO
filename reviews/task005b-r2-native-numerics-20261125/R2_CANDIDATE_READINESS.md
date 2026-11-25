# 当前候选是否可继续机制归因

|准入项|结论|证据|
|---|---|---|
|真实输入身份和完整性|PASS|同一state SHA；所有克隆值/metadata/alias验证|
|D0第一轮计算语义|PASS（本状态范围）|4份观测C/w/Q、dx/dz逐位一致|
|原安装自身严格重复性|FAIL|6个dx、5559个dz超差|
|重新编译reference严格等价|PARTIAL|与原安装2/4配对通过；安装自身也失败|
|未埋点reference-paths端点|PASS（本次2×2配对）|4/4，非4次独立重复|
|观测reference-paths端点|PARTIAL|仅1/4配对通过|
|归因到单一atomic位置|INSUFFICIENT_EVIDENCE|Jjj输出首先变化；J_linear输入也已有变化|
|完整U Native候选发布准入|NOT PASSED|原容差未满足；不可挑选通过配对|
|恢复S1/S0机制矩阵|NOT STARTED|等待用户评审|

建议下一步先评审现有“单次跨实现差异阈值”的科学含义。原实现自身触发同门槛，说明失败不是候选独有指标；但不能自动放宽。

信息增益最高的最小新实验：从已保存中间态分离同J_total/feature/temp的linear归约探针，再分离同输入的Jjj散射；不经过模型或序列前缀。必要时以固定U双迭代做机制对照。需要新授权后执行，本轮没有做。

不建议立即修改atomicAdd、不引入确定性替代算法、不重跑487帧，也不将该波动直接当作D开关在S1/S0反转的原因。

# U 单通道反馈隔离

同一完整状态，reference/paths各Native U和Fixed U两模式，每模式4次双迭代BA。Fixed U保留affine/temp原生更新，记录U_computed后仅恢复U到调用起点。

固定U控制验收：True；affine/temp确实继续更新：True；每次第一轮→第二轮状态接缝核验：True。

|实现|输出|Native重复RMS SD|Fixed重复RMS SD|Fixed逐位重复|
|---|---|---:|---:|---|
|reference|iter2_H_raw|8.5461917e-06|0|True|
|reference|iter2_rhs|1.3007565e-08|0|True|
|reference|iter2_dx|1.096873e-07|0|True|
|reference|iter2_dz|1.5582593e-07|0|True|
|reference|affine_weights|1.0733542e-10|1.1106262e-10|False|
|reference|temp_y_cdot|2.7359548e-09|2.4696668e-09|False|
|paths|iter2_H_raw|9.6951007e-06|0|True|
|paths|iter2_rhs|1.6569524e-08|0|True|
|paths|iter2_dx|1.0120672e-07|0|True|
|paths|iter2_dz|1.5306655e-07|0|True|
|paths|affine_weights|1.1324252e-10|1.1806231e-10|False|
|paths|temp_y_cdot|2.6810848e-09|2.7002998e-09|False|


本状态Fixed U下第二轮几何正规方程及dx/dz是否在各自4次重复中逐位一致：**True**。具体每个中间字段和全部配对见BA_GROUP_DISPERSION.csv、BA_FIRST_DIFFERENCE_TIMELINE.csv。

当Native U的第二轮存在差异而Fixed U第二轮几何和求解重复时，支持U→几何权重通道将第一轮归约波动传入第二轮。这是本受控状态的通道隔离证据，不是原模型全部误差的归因，也不证明D/S1/S0效果反转已经解释。

固定U仍保留affine/temp反馈，不能宣称整个优化状态完全确定。该干预同时移除正常U更新和噪声；Native/Fixed均值差不是纯噪声放大效应。Fixed重复标准差为0时，比例没有有限分母，CSV使用null，不能报告无限统计放大倍数。

32个实际记录的阻尼Pose系统采用原生LLT下三角语义分析（16次诊断BA×2轮）；全部SPD=True，条件数范围264242–266887。原安装4次没有内部矩阵trace，未伪造其内部系统。这些系统不是奇异矩阵，但条件数约2.6×10^5，不能把SPD解释为不存在数值敏感性。

几何权重另有显式源码公式审查：R3_GEOMETRY_WEIGHT_AUDIT.md。CPU FP64代理与真实GPU几何方程分开记录，未冒充原生逐位权重转储。

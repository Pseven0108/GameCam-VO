# 原安装扩展数值重复性

两次独立状态克隆，同进程串行调用原安装.so；原RNG每次恢复，全部有效输入SHA一致，内部iterations=2。

|字段|数值发生变化的元素|超原容差元素|最大绝对差|
|---|---:|---:|---:|
|dx_last|72|6|1.8300488591194153e-6|
|dz_last|49335|5559|4.202127456665039e-6|
|Pose|43|0|1.9073486328125e-6|
|disparity|48327|0|4.291534423828125e-6|
|uncertainties|2327|0|1.1920928955078125e-7|
|temp_y_cdot|12404|0|2.384185791015625e-7|
|affine_weights|48|0|9.313225746154785e-10|

这直接否定“相同状态的原安装双迭代BA必然通过当前容差”的假设。它不证明所有浮点差异对轨迹无影响，也不提供新的噪声容差。

比较方向使用CSV右列为reference：abs(left-right) <= 1e-6 + 1e-5*abs(right)。审计用float64计算误差；CPU测试确认本轮所有原字段的PASS与历史np.allclose(float32)一致。

全部15个未埋点配对保留在04_analysis/PLAIN_PAIRWISE_ERRORS.csv，含元素数、变化数、超差数、最大/RMS误差、逐位一致性。配对不是独立重复样本。R1原失败记录与R2六个输出的84项对照见HISTORICAL_ENDPOINT_COMPARISON.csv。

本任务的Depth直接优化参数是disparity。完整原始disps保留；另仅在双方正值域计算1/disparity，排除零/负值，不clamp、不改写原状态，不解释为米制GT。见RAW_DISPARITY_VALIDITY.csv和DEPTH_RECIPROCAL_COMPARISON.csv。

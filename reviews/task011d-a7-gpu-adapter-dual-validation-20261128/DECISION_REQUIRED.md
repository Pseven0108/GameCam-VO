# 需人工评审，不是本轮算法结论

Route A 和19窗口已按批准完成，无需重复申请数据准入。下一步仍未获准：真实Native FSR、
GPU Pilot、缓存模型推理、285次SLAM。当前没有生成approved runtime文件。

请评审次指标阈值。以下均为B历史数据形成的候选，未批准、未应用：

|指标|历史A0/A1绝对差P95|候选容限|单位|
|---|---:|---:|---|
|raw_path_ratio_abs_error|0.0213025|0.1|dimensionless absolute difference|
|single_global_sim3_RPE_translation|1.38857|2.77715|native camera units|
|single_global_sim3_RPE_rotation_deg|0.238757|0.477514|degrees|
|runtime_tracking_child_seconds|0.0613756|0.2|relative overhead fraction|

候选规则max(明确建议的实用下限,2×历史P95)不是科学上已证明的容忍度。较宽的RPE候选
尤其需要人工判断，不能因波动大就将实际退化合理化。

另外须在未来真实采集前评审实际快照存储预算与归档位置。当前10GiB逐写安全门槛已实现，
但不能保证全体BA快照最终容量。不得通过删除历史实验腾空间。

工程准备不回答“A5是否优于A7”。只有后续独立FSR/E2E结果才能支持该研究判断。

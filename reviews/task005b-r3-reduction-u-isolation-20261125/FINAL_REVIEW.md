# TASK005B-R3：CUDA 归约与 U 反馈隔离评审

2026-11-25（Asia/Shanghai）。状态：**DIAGNOSTIC_COMPLETE_U_FEEDBACK_ISOLATED_NATIVE_GATE_NOT_PASSED**。

## 核心结果

**两个原生浮点归约在固定输入下各自可波动；仅冻结U、保留affine/temp更新后，两个诊断实现的第二轮几何方程、dx和dz在各自四次重复中逐位一致。Native U严格端点门槛仍未通过。** 这次把“归约自身波动”和“U进入下一轮BA”分开测量，没有把Jjj的波动传给独立J_linear实验。

|字段|固定输入调用数|逐位相同配对|原容差通过配对|最大绝对差|变化元素|最大ULP|
|---|---:|---:|---:|---:|---:|---:|
|Jii_data|16|120/120|120/120|0|0|0|
|Jjj_data|16|0/120|120/120|2.2888184e-05|9931|6|
|kf_count|16|120/120|120/120|0|0|0|
|J_linear|16|0/120|120/120|1.6763806e-08|5775|92624|


本轮实际完成16次Jjj、16次J_linear和20次双迭代BA（40轮内部迭代）。全部输出有限，没有OOM、自动GPU重试、模型运行或RGB前缀。原安装二进制4次，其余reference/paths × Native/Fixed U各4次。

## U反馈及候选差异

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


Fixed U的第二轮几何/求解在每个实现内部逐位重复：**True**；U-only干预验证通过：**True**；affine/temp继续更新：**True**。

Fixed U只恢复U，不关闭enable_update_uncer，不冻结affine或temp。Native模式与Fixed模式正常状态演化本来不同，均值差不能全归为浮点噪声。完整比较见R3_U_FEEDBACK.md。

|比较|调用数/模式|相关配对数|七个最终字段全部通过|
|---|---:|---:|---:|
|original_native|4|6|2|
|reference_native|4|6|3|
|paths_native|4|6|3|
|reference_fixed|4|6|6|
|paths_fixed|4|6|6|
|original_vs_reference_native|4 vs 4|16|7|
|original_vs_paths_native|4 vs 4|16|9|
|reference_vs_paths_native|4 vs 4|16|7|
|reference_vs_paths_fixed|4 vs 4|16|16|


**Native U的严格端点准入通过=False。** 不改变原容差，不把部分通过的配对、Fixed U结果或工程测试当成完整Native等价性证书。

原安装自身6个相关配对中仅2个通过七字段联合门槛；主要超差字段为dz_last，1个配对的dx_last也超差。原安装与paths的16个相关配对为9个通过，不能解释为统计通过概率。Fixed U下reference与paths为16/16通过原容差，但并非七字段全部逐位一致。分项最大误差及超差元素数见04_analysis/BA_FINAL_FIELD_COMPARISON_SUMMARY.csv。

## 归因边界及科研决策

已有直接证据：两个归约各自非逐位重复；原安装自身的重复对照；Fixed U控制及第二轮几何、正规方程和dx/dz的实际变化。源码支持的传播通道为 Jjj/J_linear → affine → U → 几何权重 → 第二轮Schur系统。

尚未证明：精确atomic执行顺序、两处归约分别占最终误差的百分比、独立编译/观测影响为零、所有候选状态均等价。仅一份D0_S1_RGB233，不解释S1/S0深度正则反转的最终根因。

建议保持原CUDA及R1/R2封存，先审查本轮通道隔离和数值合同。若要严格确定性证书，应单独评审诊断实现及标准，不覆盖Baseline，不自动恢复S1/S0。

## 验证、保护与交付

30/30 CPU测试，144/144独立公式复算通过；78个保护文件SHA保持一致。结束数据盘可用11.662GiB，本轮新增约447.00MiB，保留10GiB底线。GPU结束无计算进程，实例未关机。

完整ZIP包含原输入tar、固定R2中间态、52份原始输出、逐轮状态、诊断.so、源码差异、运行日志与SHA清单。GitHub展开报告与CSV便于直接审查；ZIP的CRC、所有内部SHA及匿名下载另作发布验收。

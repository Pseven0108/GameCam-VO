# TASK006A-R1 最终评审

2026-11-26（Asia/Shanghai）。**CPU float64 数学原型已完成，结论为 PASS_CPU_MATHEMATICS_WITH_RECORDED_LIMITATIONS。**

核心判断：CADP 的 prior-off 正则化边缘协方差与 eta/alpha 插值端点在指定数学体系中成立；分块对角方案值得进一步工程验证。尚无证据证明其改善真实DROID-W轨迹，也没有完成原生GPU等价性或概率校准。

## 验收结果

|项目|实际结果|证据范围|
|---|---|---|
|最终自动化测试|97/97 PASS|CPU、合成矩阵与合同|
|协方差独立验证|24个系统、96次分块对照PASS|联合precision直接求逆及SciPy sparse solve|
|完整/分块与联合逆最大绝对差|7.105e-15|float64合成小系统|
|D0/D1端点|18组全部CPU精确一致|C、b、dx、理想及原生guarded回代|
|连续rho|45组联合求解验证PASS|固定alpha=0.01，含eta小于/大于alpha|
|自适应完整CPU链|9组PASS|几何→Sigma对角→u→rho→深度项→联合增量|
|信息强弱排序|9组帧级顺序验证PASS|3种子×3帧组，仅限合成|
|稳定性|17个预设结果全部符合|含应当拒绝的病态、NaN/Inf、零曲率|
|72×54,000合成系统|4种分块全部PASS，最大差2.842e-14|没有分配54,000²完整矩阵|
|真实VIPER、C0、模型与GPU|均未运行/读取|本轮授权边界保持|

最终科学结果固定为 `results/research_003/RESEARCH_RESULTS.json`。前两个开发验证目录完整保留，不叠加计数为更多独立实验。

## 三个必须保留的限制

**1. 几何弱不等于先验准。** 相同u对准确和错误Metric3D先验产生相同rho。本轮反例中，错误prior使合成位姿增量误差由0.20增加至0.33925。该例反驳无条件收益，不能据此推断真实VIPER上的CADP胜负。

**2. 协方差有明确的估计器边界。** 公式对应固定W/U、eta和gauge下的正则化联合precision逆。原生depth backsub的ix<=0分支与理想联合估计器不同，已另行转录并测试，未改动源码。未认证原生估计器的误差传播协方差。

**3. 原生工程与校准尚未完成。** R3缺少完整E，本轮没有从Schur反推或读取C0；k/tau、真实Vf、最低支持率、双轮rho冻结、Native-U数值门槛、在线耗时和显存均未完成生产验证。

## 建议决策

值得提交R1人工评审，并以明确上述局限为前提考虑R2工程可行性。R2须先明确真实E的合法取得方式、原生guard/gauge合同、分解复用与多RHS方案、mask与校准协议；不得用本次数学PASS替代这些关卡。

**本轮未启动R2、未修改生产源码/配置/权重、未编译CUDA、未发布GitHub。** 本包保留来源、全部代码、合成输入、逐项日志、对照CSV、执行收据、保护哈希和SHA清单。归档最终验收以外置 `deliveries/ZIP_VALIDATION.json` 为准。

最终状态：**TASK006A_R1_COMPLETE_WAITING_FOR_HUMAN_REVIEW**。

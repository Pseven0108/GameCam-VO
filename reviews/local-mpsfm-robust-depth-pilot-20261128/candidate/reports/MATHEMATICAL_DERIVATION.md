# MP-SfM Cauchy 思路迁移：数学合同

本实验只迁移鲁棒化思想，不声称复现 MP-SfM 的完整优化问题。
固定来源为 cvg/mpsfm `fa49640862391437865b2fd89ca3db3e6948b63b`。
官方 `bundle_adjustment.py` 使用 Cauchy 深度损失，并通过
`create_depth_bundle_adjuster(..., logloss=True)` 构建对数深度项。
本实验保留 DROID-W 的线性 inverse-depth/disparity 残差和原始目标，
需要重新推导；直接复用 MP-SfM 的数值参数并不构成单位等价。

## 定义与正目标

令 `d` 为当前 disparity，`dm` 为未经尺度修正的 Metric3D disparity，
`m=1[dm>0]` 沿用原生有效性定义，`a` 为已有 A5 系数（不使用 A5 时为1），
`alpha=gamma_depth=0.01`。每个有效像素使用

`r=d-dm`, `tau=max(0.1*abs(dm),1e-6)`，

`F_prior(d)=0.5*m*a*alpha*tau²*log(1+r²/tau²)`。

`0.1` 在评分之前固定，来源为官方 Metric3D-large 配置的相对噪声下限0.05
与 `rob_std=2` 的乘积。深度到 inverse depth 的相对误差只在小扰动下近似
保持；这里是明确声明的迁移选择，不是经过 VIPER GT 校准的概率或方差。
不迁移 MP-SfM 的完整像素方差、MAD 动态尺度和单位相关绝对噪声下限。

## 梯度与正定 IRLS 近似

`q=1/(1+(r/tau)²)`，因此

`g_prior=m*a*alpha*q*r`，`C_prior(IRLS)=m*a*alpha*q`。

这是 Cauchy 损失的正权重 IRLS / Gauss-Newton 近似，不是其精确 Hessian。
精确二阶导为 `m*a*alpha*(1-(r/tau)²)/(1+(r/tau)²)²`，
在大残差时可以为负，不直接送入要求稳定深度对角块的原生消元器。
由于 `log(1+s)` 对 `s` 凹，固定本轮 `q` 的二次函数在当前点相切且上界原目标。
CPU 测试验证梯度、相切与全区间上界。

## 阻尼必须独立

既有 A5 修改的局部对角阻尼为 `(1-m*a)*eta`。它是更新量的阻尼，
不是把当前 `d` 拉向0的目标。鲁棒权重 q 不允许进入这条分支。

因此原生几何量 `Cg,bg,A,E` 保持不变，替换深度块为

`C=Cg+m*a*alpha*q+(1-m*a)*eta`

`b=bg-m*a*alpha*q*(d-dm)`。

这区别于直接把 A5 系数换成 `a*q` 的启发式；后者会额外改变
`(1-m*a*q)*eta`，同时干预两个因素。

## Schur 与原生迭代

`Q=1/C`, `S=A-E Q Eᵀ`。沿用原生 Schur 后阻尼
`diag(ep+lm*diag(S))`、相机更新、disparity retraction、U/affine/temp 更新。
`dz=Q*(b-Eᵀ dx)`。

q 在原生 `for(itr...)` 内根据该轮最新 d 重算，保留单次调用中的两轮 BA，
没有拆成两次外部调用。用于观测的 trace 不回流到算法。
初始化、Final BA 和 Filler 直接调用原安装扩展，不启用新损失。

## 端点与限制

- Robust OFF：原生 A5 或 BASE，保留原始控制公式。
- `q=1`（零残差或无限尺度极限）：恢复原二次先验的 C/b。
- `a=0`：恢复 `C=Cg+eta, b=bg`。
- `m=0`：保留原生 eta 分支，无先验牵引。
- 先验梯度有界：`|g_prior|<=m*a*alpha*tau/2`。
- 没有其他几何约束且没有阻尼时，单个 prior 的 IRLS 更新仍可到达 dm。
  有界梯度不意味着任何 BA 状态下的位移更新都被硬性截断。
- 地图错误也会导致大残差，正确先验可能被误降权。鲁棒权重不是深度 GT。
- 本实验没有 LM 接受/拒绝策略、完整非线性单调下降保证或新米制尺度约束。

## 四组含义

BASE：原始二次 prior。A5：既有像素系数。ROBUST：仅 Cauchy。
ROBUST_A5：A5 与 Cauchy 结合，阻尼仅由 A5 决定。
主要比较 ROBUST 对 BASE、ROBUST_A5 对 A5。
单窗口、单 seed 的数值改善不能解释为统计显著或跨场景结论。

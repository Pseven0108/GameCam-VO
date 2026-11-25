# 原生数学端点与协方差定义审计

证据：官方 `src/lib/droid_kernels.cu:1876–1899`、`SparseBlock::solve():1289–1306`；R3 文件保留完整官方 CUDA 前缀。以下为源码推导，未执行 R1 数学原型或 GPU 端点测试。

## 1. 原始端点

对有限输入，定义 `m=(d_m>0)`、alpha=`gamma_depth=0.01`、`Cg=accum(Cii)`、`bg=accum(wi)`。

\[
C_0=C_g+\eta,\qquad b_0=b_g
\]

原生 D0 通过全零 prior 使 m=0；原生 D1 为：

\[
C_1=C_g+m\alpha+(1-m)\eta,\quad
b_1=b_g-m\alpha(d-d_m).
\]

方案所写 CADP：

\[
C_\rho=C_g+m\rho\alpha+(1-m\rho)\eta,
\qquad b_\rho=b_g-m\rho\alpha(d-d_m).
\]

代入 rho=0 或 1，分别还原 C0/b0 或 C1/b1。**代数层面对应正确。** 这不等于候选 Native U 双迭代的逐位或混合容差等价性已经通过；R3 的 Native 门槛仍未通过。

还需注意：

- `C_rho` 是在 eta 和 alpha 之间过渡，不是始终在 `Cg+eta` 上额外加 `rho*alpha`。
- 曲率关于 rho 的导数是 `m*(alpha-eta)`；只有对应像素 alpha>eta 时才随 rho 增大，不能无条件称“增大 rho 就增大所有曲率”。
- 当前原生 mask 只有 `>0`，并非完整 `isfinite` 检查。上述等式不替代 NaN/Inf 合同；0 乘 NaN 也可能产生 NaN。未来 R1 必须单独定义异常输入处理，不能擅自改变原生端点语义。
- rho 的两个端点必须同时保留曲率分支、右端项、eta、后续原生阻尼和 U/W；不能只匹配先验梯度。

## 2. 原生阻尼的确切位置

设 `Ehat` 是已按全局位姿/深度 ID 聚合的交叉块。先做深度消元：

\[
Q_0=\mathrm{diag}(C_0)^{-1},\quad
H_0=A-\hat E Q_0\hat E^T.
\]

原生 `SparseBlock::solve()` 接收的是 H0，而不是消元前的 A。它复制矩阵后执行：

\[
L_0=H_0+\operatorname{diag}(ep+lm\operatorname{diag}(H_0)).
\]

因此方案中的 Lambda_x 需要具体写成**基于先验关闭 Schur 矩阵 H0 对角线**的上述阻尼。不能替换成 `lm*diag(A)`，不能直接复制 Pi3MOS 的 `1.0` 阻尼。

当实际 CADP 优化使用 C_rho 时，原生优化阻尼应继续根据对应 H_rho 构造；计算 u 的先验关闭阻尼 L0 与实际优化 L_rho 的角色不同，不应将同一份 L0 强行用于所有优化端点。

## 3. 计划中的协方差对象

在固定线性化点、固定当前 W/U、固定 gauge/窗口/eta 的条件下，拟采用：

\[
\Sigma_d=Q_0+Q_0\hat E^T L_0^{-1}\hat E Q_0.
\]

这是加数值正则后的局部近似，不是经过噪声标定的物理真值协方差。它仍依赖 learned weight 的尺度、原生 `.001` 归一、U/W、eta、pose damping、自由变量窗口和 gauge。若前序状态已经受到 D 的影响，在该状态移除当前 prior 并不抹除历史影响；应称“当前状态下 prior-off 的几何协方差”，不能称完全独立的几何真相。

对每个深度列 j，只需：

\[
q_j+q_j^2 e_j^T L_0^{-1}e_j.
\]

若 L0=RR^T，可分块解 `R F=Ehat*Q0`，用列平方和得到修正项；无需形成深度×深度的完整协方差矩阵。这只是后续可行性审查的数学方向，本轮没有实现、测试精度或计时。

`Cg^{-1}` 或 `1/(Cg+eta)` 只包含条件深度项，缺少位姿—深度边缘化修正，不得当成完整 Sigma_d。

## 4. 两个既有实现细节必须保留并在 R1/R2 检查

1. `EvT6x1_kernel:1202` 对 `ix<=0` 返回，因此深度回代跳过自由变量索引 0 的贡献，而 Schur 系统仍有该索引。此处是原有分支，不是本轮引入。逆 Hessian 协方差描述的是装配系统，不自动等于这条原生回代实现的误差传播协方差。R0 不认定其为本研究最终根因、不修代码；未来需明确算子定义并独立核验。
2. `schur_block` 对目标 ID 的判定为 `j>=t0 && j<=t1`，但窗口尺寸是 `t1-t0`；有效协议应保证所有自由目标 ID `<t1`。不能在移植时忽略这个半开区间差异，也不能未经批准顺手修原实现。

## 5. 状态与结论

D0/D1 公式和 RHS 符号：CONFIRMED_SOURCE_DERIVATION。实际多轮数值端点：UNVERIFIED_FOR_CADP。协方差正定性、gauge 敏感性、分块解与稀疏解一致性：待 R1/R2，未执行。以上区分不影响 R0 完成，但禁止据此宣称 CADP 模块已完成。

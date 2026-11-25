# CADP CPU 数学推导

2026-11-26，TASK006A-R1。本文给出固定线性化状态上的数学对象，不是原生 CUDA 多轮求解的等价性证书。

## 1. 变量、输入与原生约定

令 x 为当前窗口自由位姿的局部切空间增量，d 为所有关联源帧的 disparity/inverse-depth 增量。P 个自由位姿一般对应 6P 维；K 个深度源帧不必等于 P。本文矩阵约定为

\[
\begin{bmatrix}A&E\\E^T&C\end{bmatrix}
\begin{bmatrix}\Delta x\\\Delta d\end{bmatrix}
=\begin{bmatrix}b_x\\b_d\end{bmatrix}.
\]

C 是对角矩阵，代码中仅存对角向量。Cg、bg 是冻结当前观测权重（包含现有 W/U）后的几何深度块和 RHS。eta 也是当前原生阻尼路径的输入。alpha 固定为真实封存运行的 `gamma_depth=0.01`，不采用基础 YAML 的 0.001。

源码证据：独立复制件 `evidence/R0/evidence/sources/DROID-W-official/src/lib/droid_kernels.cu` 的 1878–1899 行；原生消元后阻尼为 1294 行。官方提交为 `c3414af6047d06bafc1a6645d09f23247f3b2cdc`。

## 2. Prior-off 协方差的精确对象

先完全排除当前 Metric3D prior 的注入：

\[
C_0=C_g+\eta,\quad Q_0=\operatorname{diag}(1/C_0),\quad
H_0=A-EQ_0E^T.
\]

严格保留原生消元后阻尼顺序：

\[
\lambda_0=ep+lm\,\operatorname{diag}(H_0),\qquad
H_d=H_0+\operatorname{diag}(\lambda_0).
\]

本原型主要采用 Local BA 参数 lm=1e-4、ep=0.1。不能给 A 预先施加 `lm*diag(A)`，也不能把 Pi3MOS 的常数 1.0 搬到这里。

定义局部正则化 precision：

\[
K_0=\begin{bmatrix}A+\operatorname{diag}(\lambda_0)&E\\E^T&C_0\end{bmatrix}.
\]

当 C0 对角严格为正且 Hd 正定时，块消元得到 K0 正定，且其逆的深度边缘块恰为

\[
\Sigma_d=Q_0+Q_0E^T H_d^{-1}E Q_0.
\]

自动验证以 `numpy.linalg.solve(K0,I)` 的深度子块为独立 oracle；另用 SciPy sparse solve 交叉验证。oracle 不调用本原型的块逆表达式。

这不是 `1/(Cg+eta)`：后者仅为条件深度方差，缺少位姿不确定性传播。Sigma 的对角不小于 Q0；修正项在上述 SPD 条件下半正定。单位为 disparity 的平方；代码不会把它称为米制 depth variance。

## 3. 分块不会丢掉跨块耦合

若 Hd=LLᵀ，令 F=L⁻¹EQ0，则

\[
\Sigma_d=Q_0+F^TF,\qquad
\sigma_j=q_j+\sum_i F_{ij}^2.
\]

只需求对角时，对 E 的深度列分块求三角方程，并逐列求平方和。所有块共享同一个完整 Hd 分解，因此仍保留全部位姿相关性；这不是将协方差近似为互不相关的帧块。需要指定 off-diagonal 子块时，使用 `F_Iᵀ F_J` 加上相同深度索引的 Q0 项。

原型 `full_covariance()` 只允许默认不超过2048个深度变量的小系统。54,000维只执行精确对角和选定块计算，不分配54,000²矩阵。大系统合成样本由公开生成器与种子重建，没有从 R3 的 H/Schur 推造 E。

## 4. 当前 prior-off 不等于消除了历史先验影响

`prior_off()` 和 `build_adaptive_plan()` 的 API 不接受 dm、alpha 或 rho；测试确认改变 dm/bg 不改变同一几何输入的 covariance。这只保证**当前线性化下没有直接 prior 注入**。

当前 Pose、d、图结构及 W/U 可能来自先前受到 D 影响的状态。它们仍会改变 A/E/Cg/eta。所以不能称该量完全独立于 Metric3D 历史反馈，或称其为纯物理几何真值。

## 5. 帧级统计与动态权重

每个帧的候选像素必须有有限、正 disparity、至少一次观测、有限正方差。零/弱 Cg 不作为删除条件。集合与 mono prior mask 无关：

\[
u_f=\operatorname{median}_{p\in V_f}
\frac{\sqrt{\sigma_{f,p}}}{|d_{f,p}|+\epsilon},\qquad
\rho_f=\operatorname{sigmoid}(k(u_f-\tau)).
\]

epsilon=1e-6 是本合成原型的显式分母保护，不是冻结生产参数。k>0 时 rho 关于 u 单调不减；浮点饱和可精确到0或1。使用两分支稳定 sigmoid，不为防溢出改写自变量的物理意义。

偶数有效像素时采用 NumPy midpoint median。Pi3MOS 使用 Torch median 的下中位数；二者并不始终数值一致。本迁移方案选择 midpoint 是明确的 CPU 定义，不是复现 Pi3MOS 输出。真实集成前须冻结同一种中位数规则。

空帧/低于显式 min_valid 的帧返回缺失值与原因，不提供 fallback rho，广播进入深度项时停止。观测数为零的像素被报告为 unsupported；原型没有把全图支持率不足伪装成高置信度。最小支持率和真正投影有效集仍未生产冻结。

## 6. CADP 端点与实际求解阻尼

原生 mask 对有限输入为 m=(dm>0)：

\[
C_\rho=C_g+m\rho\alpha+(1-m\rho)\eta,
\qquad b_\rho=b_g-m\rho\alpha(d-d_m).
\]

rho=0：C0=Cg+eta、b0=bg。

rho=1：C1=Cg+m alpha+(1-m)eta、b1=bg−m alpha(d−dm)。

无效非正 prior 保持 eta 分支；非有限输入会被原型拒绝，不用 `0*NaN` 产生的结果冒充原生有限输入端点。

每个实际求解都基于对应 Cρ 重建 Hρ 和其原生顺序阻尼。不能将估计 u 时的 Hd0 强行用于所有 rho 的优化。端点比较覆盖 C、RHS、dx 和两种明确区分的深度回代算子。

曲率导数为 m(alpha−eta)：rho 增加不一定增加曲率，eta>alpha 时反而减少。gamma=0 也不是 D0。中间 rho 的 Pose 结果一般不是两个端点的线性插值。

## 7. 原生 depth-backsub 索引差异不能被隐去

原生 `EvT6x1_kernel` 在1202行对自由位姿索引 ix<=0 返回。首个自由位姿的6维增量参与 Schur，却不参与 depth backsub 的 Eᵀdx。CPU 提供 `native_guarded_backsub()` 对其代数行为单独转录，证明 rho 两端在相同 guard 下仍恢复原生深度分支。

但是，Sigma 是 K0 逆的深度块，**不是这条非对称 guarded estimator 的已验证误差传播协方差**。测试明确展示两种回代可能不同，未修复或改动该原生分支。R2 必须判断 covariance 的用途是否仅为局部 information proxy，或是否需要另行审查 estimator-covariance 定义。不能把本次数学 PASS 表述为原生运行协方差校准已经完成。

同样，目标位姿须满足半开区间 [t0,t1)；target=t1 在原生 Schur 边界与回代存在歧义，原型选择 fail closed。重复 E 行按全局 pose/depth ID 累加，不允许直接 reshape，也不假定 K=P。

## 8. 成立范围

上述逆 Hessian 是冻结线性化、冻结 W/U 与 gauge、保留 eta 和 pose damping 的局部正则化近似。未经噪声尺度、learned weight 和真实误差标定，不能解释为校准的概率置信区间。正则化使矩阵可逆，不代表单目尺度或无视差自由度在数据上可观测。

原型不包含非线性 relinearization、Pose manifold retraction、原生 U 双迭代、clamp、Trajectory Filler 或真实相机轨迹。R3 Native-U 端点未通过的历史门槛仍然保留。

# 协方差所需张量与生命周期

## 1. 完整交叉块不能直接拿局部 E reshape

定义自由位姿数 P=`t1-t0`，每帧 BA 像素数 R=`ht*wd`，自由及关联深度帧数 K=`len(kx)`。

原生构造：

```
ts     = arange(t0,t1)
ii_exp = cat(ts,ii)
jj_exp = cat(ts,jj)
kx,kk_exp = unique(ii_exp, sorted=True, return_inverse=True)
Ei     = accum(Eii,ii,ts)
Erows  = cat(Ei,Eij)
```

`Erows` 形状为 `[P+num_edges,6,R]`，不是 `[6P,KR]`。一行 r 的目标位姿是 `jj_exp[r]`，深度来源是 `kx[kk_exp[r]]`。要构造全局交叉块 Ehat，必须将行贡献加到：

\[
\hat E_{6(jj\_exp[r]-t0)+a,\;kk\_exp[r]R+p}
\mathrel{+}=Erows[r,a,p],
\]

仅对目标位姿落在 `[t0,t1)` 的行执行，重复行累加，窗口外固定 pose 不新增自由列/行，但其关联 source depth 仍可能出现在 kx 中。

**不能假设 K=P，也不能只取窗口内 Cg、丢掉窗口外 source depth。** 封存 R3 状态为 `t0=52,t1=64`，P=12，而 eta 第一维为 15，即 K=15；深度变量为 54,000，位姿变量为 72。

## 2. 生命周期与采集位置

|对象|构造位置|生命周期|协方差用途|现有 R3 是否完整保存|
|---|---|---|---|---|
|poses/disps/intrinsics|DepthVideo + BA 输入|跨 BA 的可变状态|固定线性化状态|输入快照/逐轮记录存在|
|target/weight|FactorGraph 更新网络|本次 BA 调用|几何观测及原权重|输入快照存在|
|U/temp/affine|DepthVideo 与 BA 更新|跨轮可变|保留原生 U/W 作用|输入及逐轮记录存在|
|eta|FactorGraph 阻尼路径|本次 BA 调用|prior-off 深度对角正则|输入快照存在|
|ii/jj/kx/kk_exp|BA 索引扩展与 unique|本次 BA 调用|深度组与位姿组映射|ii/jj/kx 可核验，kk_exp 可按源码恢复|
|Hs/vs|projective_transform_kernel|逐轮覆盖|装配 A/bx|R3 有逐轮记录|
|Cii/wi|同 kernel|逐轮覆盖|聚合 Cg/bg|R3 有逐轮记录|
|Eii/Eij|同 kernel|逐轮覆盖|装配 Ehat|**R3 未导出**|
|A|SparseBlock.update_lhs/rhs|每轮 Eigen 对象|pose Hessian|R3 有矩阵记录|
|H/S/L|Schur 与 solve|每轮临时|消元与原生阻尼|R3 有矩阵记录，但并非所有路径的 prior-off 矩阵|
|Eigen LLT solver|SparseBlock::solve 局部变量|本次 solve 返回时销毁|多 RHS 分块求解|未暴露复用接口|
|Cg/Q0/L0|未来诊断计算|首轮当前状态|prior-off covariance|当前没有 CADP 输出|
|Sigma 对角/u/rho|未来计算|本次 BA 首轮计算，后续轮冻结 rho|先验权重|当前不存在，不可伪造|

当前 R3 trace 没有 `trace.push_back(E/Eii/Eij)`。仅有 `A-H=E Q E^T`，无法唯一恢复每个深度列及其归属，更不能从 pose-only Schur 对角冒充深度边缘协方差。完整原输入 tar 存在并通过旧包完整性核验，未来可通过获批的 CPU 几何重建或独立观测导出获得 E；本轮未反序列化该输入或重算几何。

建议诊断读取位置是在首轮 projective kernel 完成之后、原始 prior 加入之前；在同一输入状态上复制所需值，不能先做 retraction 再回头计算“当前轮前”的协方差。Native U 两轮状态应保持；rho 在一次 BA 调用内固定，不能因第二轮 U 变化而悄悄重算 rho。

## 3. 现有求解器限制

`SparseBlock::solve()` 每次创建 Eigen `SimplicialLLT`，只对一个 `VectorXd b` 求解，返回 dx；分解对象不跨调用复用。`get_dense()` 已存在，但不等于具备多 RHS 在线协方差能力。Eigen 默认列主序与 Torch 张量解释还需显式检查，不能直接假定任意矩阵导出都按预期行主序排列。

方案 A（小 pose 稠密矩阵、GPU 分块）与方案 B（Eigen 分解复用、多 RHS 分块）均为后续 R2 待审方案。本轮不评定哪个实现更快，不修改 API 或编译扩展。

## 4. 存储量提示，不是性能验收

按现有单一 R3 状态：Ehat 为 `72×54,000`。仅一份 Ehat 的 float32 原始数组为 15,552,000 bytes，float64 为 31,104,000 bytes。分解、临时块、索引和诊断副本要另计。

若照搬 Pi3MOS 的 `F^T F`，将生成 `54,000×54,000` 中间矩阵：float64 原始数组为 23,328,000,000 bytes（约 21.73 GiB），尚未计模型与其他显存，不能据此进入在线集成。

只计算列二次型或分块三角求解有望避免这个中间矩阵，但这只是结构分析；未测耗时、未测显存、未证明能满足 20%/1.5GB 的预算。前端实际窗口可能变化，不能把此单一状态尺寸当成峰值上界。

## 5. 有效像素定义尚待冻结

现有 prior mask m 与几何有效集合 V_f 是两回事。V_f 需要有限正 disparity、可核验投影观测/权重，并明确低观测数、空帧的处理。不能仅用 `Cg>0` 过滤掉所有几何弱约束像素，再把剩余像素的低不确定性当成整帧可观测性。

当协方差不正定、非有限或有效集合为空时，应按获批协议停止或标记不可计算；本轮没有自行设定 fallback rho，也没有校准 k/tau。

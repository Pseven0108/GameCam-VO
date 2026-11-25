# 原生两轮 BA 的数学重建

本轮保存每轮真实的几何深度对角 `C_geometry`、深度右端 `w_geometry`、耦合块 `E`、Pose-only `A,v`、Schur 减项、阻尼系统以及 dx/dz。

对有效先验掩码 m=(mono>0)，曲率因素 c∈{0,1}、梯度因素 g∈{0,1}：

```text
C(c) = C_geometry + c m α + (1 − c m) η
w(g) = w_geometry − g m α (d − mono)
Q(c) = diag(1 / C(c))
H(c) = A − E Q(c) Eᵀ
b(c,g) = v − E Q(c) w(g)
L(c) = H(c) + diag(ep + lm diag(H(c)))
L(c) Δx(c,g) = b(c,g)
```

α为原配置gamma_depth。本轮不调参。C=0保留eta，不是取消全部深度正则。曲率路径通过Q同时改变Schur矩阵和消元右端项，因此不能把B−D全部解释为单纯的条件数变化。

在第一轮固定线性化且固定曲率时，A/B或C/D具有相同L，因此：

```text
Δx(c,1) − Δx(c,0) = L(c)⁻¹ [b(c,1) − b(c,0)]
```

`GRADIENT_IDENTITY_CHECKS.csv` 使用原生保存的L和b独立求解上述差异。第二轮各格已经产生不同Pose/Disparity，不能继续要求这个固定线性化差分恒等式成立。

原生深度回代是Q*(w−accum(Eᵀdx))，但原有`EvT6x1_kernel`显式忽略局部索引<=0或>=dx.size(0)的项。CPU重建严格复现此既有guard，没有替原版修改其行为。Schur组装本身包含窗口内的第0个Pose块。该实现细节原样保留，其独立影响未在本任务中识别；不能把它作为本次候选新增的缺陷，也不能据此宣布已找到完整轨迹反转根因。

`CPU_SCHUR_RECONSTRUCTION.csv`逐深度变量聚合所有对应Pose的E块，重算EQEᵀ、EQw和带原guard的dz。采用float64累加，与CUDA float32归约允许浮点舍入差异；原生端点判据仍为预设atol=1e−6、rtol=1e−5，不随CPU重建误差改变。

四格定义：A=(1,1)、B=(1,0)、C=(0,1)、D=(0,0)。向量差分：

```text
curvature = B − D
gradient = C − D
interaction = A − B − C + D
total = A − D = curvature + gradient + interaction
```

这些是基于D格的有限差分分解，不等同于方差解释比例，也不是唯一的归因分摊。极大、反向的gradient/interaction可能抵消成较小total。

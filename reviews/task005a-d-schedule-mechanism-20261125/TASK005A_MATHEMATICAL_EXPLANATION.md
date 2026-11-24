# 深度正则如何通过Schur系统影响Pose

证据等级：SOURCE_DERIVED；源文件与冻结c3414af6047d06bafc1a6645d09f23247f3b2cdc的Git Blob一致。没有执行CUDA源码。

设x为位姿增量，z为disparity增量。将当前几何线性系统写为：

    [ A  E ] [dx] = [v]
    [Eᵀ  C ] [dz]   [w]

其中A、E和几何深度对角C_g由当前投影、对应关系和权重决定。令d为当前disparity，d_m为mono prior，m=1[d_m>0]，α=gamma_depth，η为网络生成的深度阻尼。

原生代码src/lib/droid_kernels.cu:1878–1899：

    C = C_g + m α + (1-m) η
    w = w_g - m α (d-d_m)
    Q = C⁻¹
    (A - E Q Eᵀ) dx = v - E Q w     [随后使用原生lm/ep求解阻尼]
    dz = Q (w - Eᵀ dx)

源码SparseBlock把矩阵和右端一起装配，公式是其块系统含义；不是本轮已获得全部原生矩阵的声明。

D=0传zeros使m=0，因此C_0=C_g+η，w_0=w_g。D=1在先验严格为正处C_1=C_g+α，w_1=w_g−α(d−d_m)。缺失或非正先验处仍走η分支。

所以D的切换有两条直接路径：

- CURVATURE_PATH：改变深度对角与Q，继而改变Schur矩阵和位姿—深度耦合。
- PRIOR_FORCE_PATH：改变深度右端，再经E Q w影响位姿右端。

这两条路径在现有D开关中同时变化。不能把D1−D0只解释成“深度先验梯度”的贡献，也不能把D0描述为“完全无正则”。

日志γ_depth=.01；采样η中位数约1e−7，α/median(η)约1e5。这只是两项正则系数的数量级诊断：没有包含C_g，不是完整C的比值，更不是系统条件数。m为正的缓存比例接近1，也不是独立深度准确率。

原生每次retraction后还可能根据新Pose/disparity更新U。下次BA重新生成target/weight/eta并使用演化后的U，因此同一个离散图不对应同一个连续线性系统。跨调度的效应可写作：

    Δ_D(S) = Y[ D=1, S, state evolves ] - Y[ D=0, S, state evolves ]

Task004C-B识别的是给定S1或S0的路径总效应。S1/S0是各生产臂生成的内生调度包，不是随机独立处理；不能把二者之差直接解释为随机化“关键帧数量”的纯因果效应。

## 仅用于说明的CPU反例

TASK005A_SYNTHETIC_SCHUR_ILLUSTRATION.json用两个标量(p,d)，真实值(1,2)，相同有偏先验2.5，α=.01、η=1e−7。

- 在良好约束几何中，加先验把pose绝对误差从约6e−7增至.0147。
- 在近共线且含少量噪声的几何中，加同一个先验把误差从2.001降至.5001。

这证明相同先验在不同几何条件下可以有相反误差效果；**不能据此认定真实S1是良态、S0是病态**。该反例不是原生BA重建，不是对真实数据拟合参数，也不是新模型实验。

## 尚缺的归因证据

缺少代表性晚期状态的完整几何Residual/Jacobian、完整C_g/E/A、Schur矩阵、准确每像素η和同状态交叉分项求解。observer的均值/分位数不能恢复这些量。因而不能报告真实条件数、特征值、哪一项解释了多少百分比，也不能声称已证明Metric3D深度错误。

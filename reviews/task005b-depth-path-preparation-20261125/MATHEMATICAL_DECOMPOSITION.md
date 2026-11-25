# 固定状态的双路径定义

证据级别：SOURCE_DERIVED + CPU_SYNTHETIC_TESTED，非GPU结果。

固定真实输入theta={pose, disparity d, cached mono d_m, K, target, weight, U, temp_y_cdot, DINO, affine_weights, eta, ii/jj, t0/t1及全部标量}。m=1[d_m>0]必须始终由真实缓存mono决定；D0来源调用传入的zeros不能替代该缓存。

令c、g为曲率与梯度开关；W=源端UBA，与这里的深度右端w不同。

    C_c = C_geometry + c m alpha + (1-c m) eta
    p = m alpha (d-d_m)
    w_g = w_geometry - g p
    Q_c = inverse(C_c)
    H_c = A - E Q_c E^T
    L_c = H_c + diag(ep + lm diag(H_c))
    b_cg = v - E Q_c w_geometry + g E Q_c p
    dx_cg = inverse(L_c) b_cg
    dz_cg = Q_c (w_g - E^T dx_cg)

四格命名为A(1,1)、B(1,0)、C(0,1)、D(0,0)，与历史B1/B2/B3/B4不是同一命名层。

在同一初始线性化、固定c时，开启梯度的直接位姿差精确为：

    dx_c1 - dx_c0 = inverse(L_c) E Q_c p

因此两条路径交互为：

    I = [inverse(L_1) E Q_1 - inverse(L_0) E Q_0] p

梯度开关在第一轮不改变H/L的谱；曲率开关会改变H、右端的几何消元项及lm相关位姿阻尼。第二轮因pose/depth已经变化，梯度也可间接改变矩阵谱。这是局部求解器因果关系，尚不能直接解释整轨迹ATE反转。

必须同时给出条件对比A-B、C-D、A-C、B-D及交互A-B-C+D。相加关系为A-D=(B-D)+(C-D)+I；向量贡献不能用范数之和伪造百分比。对误差标量另行计算，不把dx大小直接当成误差。

跨路径的B/C通常不是原始先验损失的一致Gauss-Newton近似。例如C保留先验梯度但用eta曲率；它可能产生很大步长。这是用于归因的受控局部系统，不是可直接部署的估计器。其失稳不能直接证明原始DROID-W实现错误。

## 条件性与残差

保存未阻尼H和实际求解L，并分别报告原始不对称范数。原生Eigen SimplicialLLT默认使用下三角；谱诊断应明确使用下三角自伴矩阵，不悄悄平均上下三角。分别记录特征值、奇异值、数值秩、正定性和kappa2；秩缺失时不填有限条件数。平移/旋转量纲混合及固定窗口规范会影响数值，因此同时保留未缩放谱及可选对角平衡谱，不能拿alpha/eta充当条件数。

原生LLT分解失败会返回零dx；不能仅凭进程退出码或dx为0判定求解成功。真实运行需复查保存的L、求解残差及原生端点等价性。

几何评价保存完整残差、原始权重、源端/目标端门控与有效性。报告固定before权重/共同有效支持下的前后SSE及原生自适应权重SSE，防止通过降低权重或失去投影支持制造“改善”。无独立depth GT，不宣称Metric3D预测正确或错误。

源码依据：冻结src/lib/droid_kernels.cu中的ba_cuda和SparseBlock::solve。官方[固定版本源码](https://raw.githubusercontent.com/MoyangLi00/DROID-W/c3414af6047d06bafc1a6645d09f23247f3b2cdc/src/lib/droid_kernels.cu)。本地Git blob为9c171af1bfafc278e9776f2f89667054a66dc2bf，候选生成前硬校验。

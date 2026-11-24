# 原生公式和离线数学复核

源码依据：source/src/lib/droid_kernels.cu，深度先验公式见1878–1881行附近。Cg/bg是CPU重建的初始线性化几何项，不是捕获的原生中间矩阵。

    m = (mono > 0)
    C_D1 = Cg + m*gamma_depth + (1-m)*eta
    b_D1 = bg - m*gamma_depth*(disp-mono)
    C_D0 = Cg + eta
    b_D0 = bg
    Q = 1/C

prior同时改变深度右端项与曲率/阻尼分支，并可通过Schur消元影响位姿。CPU重建使用实际边、target、weight、pose、disp与初始U；核对MIN_DEPTH=0.25、0.001权重缩放、source UBA和self-edge stereo约定。重投影残差单位为80×45网格像素，不冒充640×360像素。

COMMON_SUPPORT_RESIDUALS.csv 在 BEFORE/D1/D0 都有效的同一edge-pixel交集上比较，主要SSE固定初始U；另报更新U和各自有效域结果。共同支持像素：E0为252000，E1为313821。CPU float64与CUDA float32舍入和归约次序不同，重建值不称逐位原生残差。

E0输入disparity-minus-prior L2约6.873，先验右端L2约0.0687，几何右端L2约5.056。E1对应约293.083、2.931、1.474。E1正先验像素约56.60%的先验曲率大于初始几何曲率，E0约11.67%。这支持“当前几何状态与先验的冲突程度影响D响应”这一候选解释，未隔离出各项精确因果贡献。

没有完整原生Schur/联合Hessian、每次内部迭代Jacobian、求解残差或完整目标函数。不能给出原生条件数或完整目标下降证明。native返回dx/dz仅为最后一次内部迭代；pose/disparity before→after是两次迭代累计结果，不混为一谈。

RGB312/328对应Camera311/327，历史固定尺度19.1341794347。GT仅在运行结束后本地离线读取，单位是游戏世界单位，未声称米。世界方向诊断使用每状态BEFORE前缀拟合的一次旋转，并在两分支保持不变；相对相机方向与该世界方向的参照不同，分别报告。

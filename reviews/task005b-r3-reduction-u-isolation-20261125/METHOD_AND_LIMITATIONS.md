# 方法与解释边界

## 三个不同的估计对象

独立 Jjj 实验固定R2第一轮几何更新后的Pose/disparity、U、DINO特征、图、K、target；同一原生kernel同时生成Jii及Jjj。Jii是逐像素独立写入，Jjj向重投影的四邻目标像素做float atomicAdd散射。只有输出初始化为零，不在原输出上继续累加。

独立 J_linear 实验固定R2第一轮的J_total、temp、U、kx和同一封存feature。不会在重复之间重新生成J_total，也不使用本轮Jjj结果。每个block处理一个keyframe，特征通道和bias用float atomicAdd累加，再除像素数。原始kernel中的uncertainties形参主要提供索引/尺寸，本体保留不动。

双迭代BA实验在同一完整状态上分别克隆唯一storage，核验alias、dtype、shape、stride、offset和数值，恢复同一RNG；NoGrad，每调用内部迭代两轮。重复在一个Python进程内完成，不是独立进程或独立序列样本。原安装Native U 4次，独立reference/paths × Native/Fixed U每组4次。

## Fixed U 的单通道干预

每轮先按原生流程完成feature重投影、J_linear、affine和uncertainty_update_kernel。记录U_computed后，仅将uncertainties原位恢复为调用起点U；保留affine和temp的实际更新。U_after是下一轮真正使用的值，不能把U_computed冒充生效U。此控制故意暂时打破U=log(1.1+exp(temp))关系，不是可部署改进方案。

原生源端权重为 w_U=clamp(1/max(45U-35,0.1),0,1)，本状态bidirectional=false。固定U切断U→第二轮几何权重的反馈，但仍允许affine/temp及它们的J_linear反馈存在。不能把关闭enable_update_uncer（整个更新块）当作本实验Fixed U。

这个干预同时移除正常的U更新和其数值波动。Native/Fixed的重复离散度差异能够支持通道隔离；不能将两个模式均值之差全部解释为微小浮点噪声的因果效应，也不能从不同单位的Jjj误差与dz误差的比值构造放大倍数。

## 数值评价

保持R2逐元素标准：abs(a-b) <= 1e-6 + 1e-5 abs(a)。比较方向和参考a在CSV中明确。额外报告逐位相同、ULP、max abs、RMS、L2及重复离散度。最大绝对差大于1e-6不自动代表失败；相对容差同样参与。

16次调用产生120个相关配对，4次调用产生6个相关配对。配对数量不等于独立重复数，不能据此报告高置信度总体概率。没有跨GPU、跨编译器、跨状态或场景的泛化证据。

## 数学记录与观测影响

A、S、H=A-S、rhs、实际阻尼L从原生Eigen对象只读复制为row-major CPU float64，原求解函数不改。SPD与条件数使用原生LLT下三角自伴语义。只读trace仍会增加同步和复制，可能改变atomic调度，不能声称观测副本与原二进制具有相同的具体累加顺序。

孤立实验能够证明两个归约位置各自可波动；未记录每条atomic指令的执行顺序，也未使某一位置确定性后进行另一位置的定量贡献分解。编译差异独立效应仍未完全识别。所有结论限定为一个真实D0上下文，不能替代C/G=1或S0的端点验证。

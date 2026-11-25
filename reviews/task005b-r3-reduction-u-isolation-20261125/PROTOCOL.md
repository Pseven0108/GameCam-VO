# TASK005B-R3：CUDA 归约与 U 反馈隔离

2026-11-25；唯一真实上下文为封存 D0_S1_RGB233，不重新采集输入。

## 固定预算与顺序

1. 固定 R2 trace_reference_1 第一轮几何更新后的 Pose/disparity、初始 U、原有 feature/graph/target/K，独立调用原文不变的 dino_feats_projective_transform_kernel 16次。每次清零输出；保存 Jii、Jjj、kf_count，输入逐值及元数据哈希前后核验。
2. 固定同一 R2 文件第一轮 J_total/temp/U/kx，以及封存 feature，独立调用原文不变的 linear_transform_kernel 16次。此阶段完全不调用 Jjj，不把阶段1输出传入阶段2；每次清零 J_linear。
3. 原安装二进制 Native U 重复4次；独立诊断 reference/paths(0,0) × Native U/Fixed U ×4次，共16次。总计20次双迭代BA，每次保留内部两轮，串行、同进程独立状态克隆，不拆成两次单轮。

## Fixed U 的干预定义

保留 enable_update_uncer=true、enable_affine_transform=true、enable_udba=true。Affine 和 temp 始终按原生公式更新；每轮先记录原生计算出的 U_computed，再仅将 uncertainties 原位恢复为调用起点的完整 U，记录实际 U_after。Native U 无回写。此控制有意使 temp 与 U 的非线性关系暂时脱钩，用于隔离 U→下一轮几何权重通道，不作为可部署算法或完整关闭不确定性模块。第二轮 affine/temp 内部反馈仍被保留。

原安装二进制没有只冻结 U 的入口，仅作为 Native U 参考；不通过关闭 enable_update_uncer 冒充单因素 Fixed U。诊断副本新增参数及记录，不修改原安装/R1/R2扩展。所有调用D0：reference/original传零prior，paths传真实mono但C=G=0，分别记录有效实参SHA，不能称其prior实参字节一致。

## 分析合同

保持 atol=1e-6、rtol=1e-5，逐元素误差同时报告bitwise、absmax、RMS、超差数。配对共享调用，只作描述性范围，不把120个配对当成120次独立重复。区分不同单位张量，不以Jjj绝对误差除dz绝对误差充当放大倍数。用同一输出量的跨重复离散度比较 Native/Fixed U，并报告两者的有意干预均值变化。

逐轮记录 Cii/wi/Hs/vs、C/w/Q、Pose正规方程A/S/H/rhs/阻尼L、dx/dz、Jii/Jjj/J_total/J_linear、affine、U_computed/U_after、temp。正常方程按原生Eigen下三角自伴语义分析，不平均上下三角。

## 保护与停止

原始扩展、R1候选、R2源码/结果、权重和配置不改；新独立扩展编译一次。保留数据盘10GiB，预算本轮新增不超过1.25GiB；每次保存前检查。非有限值、OOM、身份不符、运行异常立即停止，无自动GPU重试。原容差失败本身是诊断对象，不伪装为通过。无S0、无剩余S1矩阵、无RGB前缀、无模型加载/训练、无下一阶段、无关机。

## 交付

完整日志、全部原始输出、输入快照引用及原始快照副本、逐轮分析、CPU合同测试、源码差异、保护核验、SHA清单；独立GitHub评审目录和完整ZIP Release，完成后等待评审。

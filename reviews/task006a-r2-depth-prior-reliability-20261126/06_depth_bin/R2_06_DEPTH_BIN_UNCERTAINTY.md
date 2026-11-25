# R2-6 Depth-bin 统计

**256 bins 已由实际源码确认；真实分布未提取。**
RAFTDepthNormalDPTDecoder5.py:761 定义 num_depth_regressor_anchor=256；794–836 生成 log-spaced anchors、
执行 softmax 并计算期望。期望用于初始深度，再经 8 轮 RAFT 修正。
不能把初始 entropy 解释成最终深度方差，不能把 anchor 编号的方差当深度方差。

未来使用只读 depth_regressor forward hook，返回 None，读取实际 logits 和真实 depth_expectation_anchor。
output_dict 的 pred_logit=None 不是证明模型没有 bin 分支。hook 不重写 decoder、不增加训练或 CUDA kernel。
Prepared runner 会取原生 hook，但没有 GPU smoke 通过收据，不能视为已认证可运行。

统计公式：H=-sum(p log p)，归一化 H/log(K) 另外命名；
mean=sum(p*d_anchor)，V=sum(p*(d_anchor-mean)^2)，pmax=max(p)，Neff=exp(H)。
Variance 单位是 canonical depth squared，不能乘错 fx 线性比例；若映射物理深度，方差应乘尺度平方。
低分辨率 bin 网格与 full-resolution 最终深度必须显式对应，物体边缘分层，不能静默改 GT。
CPU 测试验证稳定 softmax、均匀/尖峰分布、非均匀 anchors 以及无效输入。
原始 entropy 与初始/最终误差之间的关系、以及超出 Native Confidence 的增益，均未测。

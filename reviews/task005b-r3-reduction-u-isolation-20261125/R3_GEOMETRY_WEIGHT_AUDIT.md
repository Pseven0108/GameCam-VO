# U 到几何权重的源码公式核查

真实 GPU 记录包括 U_before、几何 Cii/wi/Hs/vs、Schur 系统和 dx/dz。本补充不新增 GPU 计算，从已保存的 U_before 按源码公式计算 CPU FP64 权重代理：

`w_U = clip(1 / max(45 U - 35, 0.1), 0, 1)`。

本状态 enable_udba=true、enable_bidirectional_uncer=false。原 kernel 将源端权重乘到 `.001 * graph_weight`，另受投影深度有效性控制。这里统计 kx 唯一深度槽位像素，未按图边重复，也不声称已经捕获全部有效边的最终权重。FP64 公式不模拟 CUDA 的浮点舍入、FMA 或有效性掩码，不能作为 native 权重的逐位证书。

逐调用分布见 U_GEOMETRY_WEIGHT_PROXY_STATISTICS.csv；重复离散度见 U_GEOMETRY_WEIGHT_PROXY_REPEATABILITY.csv。

Fixed U 第二轮代理在各实现内部逐位重复：True。Native U 第二轮代理在两个实现中都存在变化：True。几何方程与解的真实 GPU 变化另见 BA_GROUP_DISPERSION.csv，不能用本代理替代。

最终七字段分项通过数、逐位相同数、最大绝对差及单个配对最多超差元素见 BA_FINAL_FIELD_COMPARISON_SUMMARY.csv。所有配对共享调用，不能视为独立样本。

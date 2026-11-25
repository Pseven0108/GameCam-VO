# 原安装、reference 与 paths(0,0)

未改变atol=1e-6、rtol=1e-5；七字段为dx_last、dz_last、Pose、disparity、U、temp、affine。

|比较|调用数/模式|相关配对数|七个最终字段全部通过|
|---|---:|---:|---:|
|original_native|4|6|2|
|reference_native|4|6|3|
|paths_native|4|6|3|
|reference_fixed|4|6|6|
|paths_fixed|4|6|6|
|original_vs_reference_native|4 vs 4|16|7|
|original_vs_paths_native|4 vs 4|16|9|
|reference_vs_paths_native|4 vs 4|16|7|
|reference_vs_paths_fixed|4 vs 4|16|16|


Native原始参考与paths的全字段严格门槛通过：**False**。不能只选择某个通过配对认定整体等价。Fixed U的通过只覆盖本D0状态及有意干预模式，不替代Native U准入。

原安装/reference使用零prior，paths传真实mono但C=G=0；有效D0语义相同，prior实参字节不同。其他输入以实际SHA、元数据和alias合同核验。

独立归约实验已证明原文kernel可波动，原安装自身重复也作为对照；这降低了“任何端点差异均由候选路径错误导致”的解释力。尚未独立识别编译器/布局/观测同步的贡献，不能反向宣称候选没有任何缺陷。两种诊断实现第一轮与Fixed U第二轮的语义证据，应与Native严格门槛分开评审。

# 实施审查

新A7在TASK011D独立副本中修改，C/B保持原字节。GPU缓存仅保存64个输入帧的原生网格；
每次按真实source union索引，时间戳映射和mean均在设备上执行。只有14列摘要跨设备。
完整strength分配是原生接口要求，不是完整A5/validity Buffer重算或回传。

CPU参考仍复用C的数学定义。FP32计算、独立FP64审计、空mask null、非有限STOP、
有效域内A5零值STOP及正支持集一致性未放宽。Pair-invalid先采用原A5的Native-only fallback，
再均匀化；不能声称A7最终仍保留不同像素的fallback系数。

A0/A1/A4/A5的实际控制代码仍是冻结TASK011B实现。生成的native_driver仅变更任务级路径、
种子、A7路由、授权与A0只读观测器，完整差异见reproducibility/experiments/TASK011D/reports/NATIVE_DRIVER_ADAPTER_DIFF.patch。
原始Python/config git对象身份与现存candidate .so的SHA已锁定；没有修改或编译Native。

Native入口、缓存推理、FSR均有独立授权动作。任务参数绑定冻结job，快照必须是本任务已登记、
哈希相符的A0状态，输出目录在原生重放前原子创建，避免重复运行后才发现旧结果。
工程Ready指静态/接口/合成测试通过，不声称完整Linux模型已经执行。

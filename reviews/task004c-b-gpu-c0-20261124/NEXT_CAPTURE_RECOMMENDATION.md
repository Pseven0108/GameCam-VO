# 下一次采集前的最小修复建议（未应用）

唯一已确认的前置缺陷是无深度数据的表示约定。建议只修改独立候选的NativeViperRGB适配层，不修改BaseDataset、原R2、BA公式或阈值。

两种可评审方案：

1. 明确父类零占位合同：仅在depth_paths=None、pose=None且depth为预期shape/dtype的全零Tensor时接受；保留原tuple给Tracker，仍禁止任何非零depth/pose标签。
2. 在上述严格核验后将无标签占位规范化为None，以维持适配层对外接口；先证明与历史R2实际输入路径等价。

不建议简单删除depth检查或对非零深度无条件放行。也不能因为depth非None就推断发生了GT泄漏。

未来CPU验证应真实调用RGB_NoPose父类，覆盖：真实RGB001；zero placeholder；depth=None；非零depth拒绝；pose非None拒绝；shape错；Frame ID错；seen不应在失败后前进；连续RGB001至RGB018在CPU中逐帧校验。记录是否读取任何标签文件。

这些是建议，不是已完成的新测试或修复。本轮未应用补丁，未更改668a88c7，未再启动模型。修复经过评审并另行获批后，才执行一次新的GPU C0采集；仍不自动进入restore、跨D或B四臂。

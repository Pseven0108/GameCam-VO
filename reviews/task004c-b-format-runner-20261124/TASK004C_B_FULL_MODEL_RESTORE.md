# 完整真实模型 CPU 恢复

最终候选 `5d357c1d3079de134dd8b41a20a00632da37f0b0`：全新 CPU 进程通过，退出码0，312.628119s。此前仅 Format commit 也通过一次；最终源码版本是本轮 CPU 总门槛的依据。

源/恢复进程 PID 5069 / 5180 不同。18,062 节点、849 Storage、6 ConfigDict、47 必需状态族、71 identity callable；完整图重编码、原始Storage内容、Tensor alias/shape/stride/offset、RNG 和 buffer 对比通过。加载过程不改变 RNG，捕获的 RNG 另行恢复。

恢复后重新执行 Metric3D 固定输入、FiT3D 特征、DroidNet fnet/cnet、带权 LoRALinear 输出和输入梯度，全部历史 SHA 精确一致；未放宽数值标准。

边界：该 CPU_NATIVE_INTERFACE_FIXTURE 具有真实预训练权重，但 Tracker/cache/cursor 为 CPU 合成状态；使用上游无 xformers attention fallback 和同公式 CPU 常量适配。CUDA未初始化。它不是原生 RGB C0，也不证明 GPU kernel 等价；GPU C0 的独立证据见对应报告。

原始 stdout/stderr/退出码及固定输入输出摘要：`raw_evidence/cpu_tests/REAL_MODEL_FINAL_SOURCE_ROUNDTRIP_R1/`。

# Short80 调度

状态：CPU_CONTRACTS_PASS / NATIVE_GPU_NOT_STARTED。

固定顺序：record_S1 → replay_D0_S1 → record_S0 → replay_D1_S0，均从同一 C0 进入，真实上限 RGB080。

实现哈希链离散事件日记：Motion Filter、关键帧取舍、图边、BA事件、稳定RGB ID、图拓扑以及终止标记。仅重放离散调度，不复制连续 Pose、深度、U 或求解结果。未知/未配对/拓扑差异失败关闭。

20项 stage 模拟中包含 S0/S1 相关范围与日志读写合同，152项历史测试也保留；这不是实际80帧验证。由于 RGB019 阶段停止，四个Short80目录均不存在，运行额度0/4。没有真实 S0/S1 schedule，不生成伪造的真实 schedule CSV。

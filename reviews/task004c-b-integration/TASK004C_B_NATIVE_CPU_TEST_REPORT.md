# CPU验证结果

**最终118/118通过，退出码0，CUDA未初始化。** 原有54项为54/54，新增原生接口相关测试为64/64。

原有54项测试源码保持不变，旧任务测试记录未覆盖。本任务每次修订均保存独立stdout/stderr、逐测试退出状态、耗时、种子和输出SHA。最终原始报告：`evidence/CPU_handoff/artifacts/CPU_SUITE_handoff/CPU_TEST_REPORT.json`。

| 修订 | 总数 | 通过 | 说明 |
|---|---:|---:|---|
| initial | 96 | 85 | PyTorch2.1 mmap要求字符串路径，错误已保留 |
| revision02 | 106 | 104 | 实际方法体fixture缺少observer模块绑定，已修正 |
| revision03 | 112 | 112 | 首轮完整通过 |
| revision04 | 116 | 116 | 增加RNG与槽管理核验 |
| final | 117 | 117 | 增加无构造器恢复测试 |
| release | 117 | 117 | 双向S0/S1接口复核 |
| handoff | 118 | 118 | 增加真实counter/timestamp与稳定RGB映射不符的拒绝测试 |

使用小型torch.nn合成fixture；没有构造DROID-W、Metric3D、FiT3D或DINO真实预训练模型。实际FactorGraph、Final BA、Filler的Python方法体在CPU fixture中运行，CUDA与神经前端由mock代替。新进程恢复也是合成状态，不能登记为原生C0恢复。

四份原YAML的参数检查、原Runner dry-run和启动保护均通过。正式runner的require_approved_runtime未删除。新有限runner只接受6种具名验证模式，硬限制RGB080，拒绝B1和487帧参数。

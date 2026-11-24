# TASK004C-B-NATIVE-RELEASE-FIXES 最终评审

**结论：CPU修复与合成验证完成，提交人工评审；真实C0及B四臂未启动。**

| 验收项 | 状态 | 证据 |
|---|---|---|
| 唯一093完整基线 | PASS | 新commit `668a88c74c7f7a88a572679d2bd8e86c0a05514b`，父提交为`0931141cf88247dc8fb0c7628c1d91b6531fea90` |
| Local BA严格失败关闭 | PASS_CPU | 缺失/错配marker、motion_only、原vanilla边界全覆盖 |
| INIT_D=0及非Local范围 | PASS_CPU | 三个初始化与非Local pass-through测试 |
| 保持buffer=500 | PASS_STATIC_CPU | 原尺寸双CPU存储2,246,400,000 bytes |
| 不占用大型tmpfs存储 | PASS_CPU_SYNTHETIC | 双spawn读写一致，shm增量60KiB |
| dtype/shape/stride/offset/alias | PASS_CPU_SYNTHETIC | 小型view/alias测试+原尺寸压力测试 |
| 真实Tracker/Rerun完整链路 | NOT_EXECUTED | 本轮禁止模型/GPU；CPU worker替身 |
| 完整C0精确逻辑预算机制 | PASS_CPU_SYNTHETIC | 实测38,616/38,616 bytes，逐文件空间门禁 |
| 真实完整C0大小及四臂总空间 | UNKNOWN / NOT_ADMITTED | 未创建真实闭包；保留多arena会超过当前容量 |
| 完整回归 | PASS | 原118+新增34=152/152 |
| 历史与BA数学保护 | PASS | 3721路径、14保护pin、1906核心路径核验；扩展调用AST不变 |

关键发现：原生Torch对file-backed Tensor默认spawn传递并不能保证继续使用数据盘文件。候选使用仅作用于注册storage的重建方式，不改变BA公式。完整CPU证据已经建立，但尚不能将其宣布为真实模型运行准入完成。

当前数据盘可用25.0400GiB。真实C0包含Video以外未知状态；未来多个attempt的2.2464GB arena累积必须单独预算，不自动清理。

本轮已完成授权范围：五份指定报告、相关源码、相对093的patch、原118记录、全部修复过程与失败记录、最终152项日志、API负对照、原尺寸共享proof及合成预算fixture。大合成payload已在无活动map后回收；历史删除0。

GPU0、CUDA初始化0、模型加载0、真实C0=0、RGB前缀0、B1/B2/B3/B4=0。未降低buffer、未改原R2、未改BA公式、未编译扩展。未关闭或重启实例。状态：**STOPPED_FOR_USER_REVIEW**。

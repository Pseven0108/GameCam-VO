# CPU 测试与准入报告

## 实际执行结果

| 测试 | 结果 | 证据范围 |
|---|---|---|
| ConfigDict 专项 | PASS，14/14，exit 0 | 空/嵌套、顺序、键类型、alias、循环、parent/key、字段缺失、冻结/解冻、错误 pin 和未知类型失败关闭 |
| 历史完整回归 | PASS，152/152，exit 0，37.448 秒 | 历史 118 项及既有 34 项；无真实 RGB、预训练模型或 CUDA 初始化 |
| 实际加权源模型固定输入 | PASS | 保存前与归档 SHA 比较断言通过；不代表恢复模型已通过 |
| 完整新进程恢复 | FAIL，exit 1，271.928 秒 | 子进程在 Format 分配失败，完整图、恢复前向和梯度比较未到达 |
| 实际 ConfigDict 精确子图诊断 | PASS，4.069 秒 | 6 个 ConfigDict、24 个可达节点，mapping/attrs/类型/顺序/alias/cycle 的规范化对象图一致 |
| GPU C0 | NOT_EXECUTED，0/2 | CPU 总门槛不通过 |
| S0/S1 短程交叉 | NOT_EXECUTED，0/4 | 不以 CPU 子图通过替代真实恢复 |
| 完整 B1～B4 | NOT_EXECUTED，0/4 | 正式阶段 runner 接入仍待完成 |

专项、回归、完整模型与子图诊断是不同的验收范围，不能把它们相加为一个“全部通过”的总测试数字。特别是子图诊断只对实际 ConfigDict 可达状态作精确比较，明确排除了无 ConfigDict 祖先的 FiT3D Format 对象。

## 执行记录身份

完整 real-model 测试脚本 SHA：`ea0bfd3605bbb88c1e27042e25b51d1c8e46a28d620cb054fc6a0375a7e120be`。

- stdout SHA：`84dba7e5adc1f54c1111db1ab2837694d70c08e96c5b7e26f2f50a32246fe957`
- stderr SHA：`a4274936339954f40d928d3f1a9667e62e5c5be6ac4384703ea060b7d1613578`
- 新 CPU 源快照 state SHA：`2fc3f3cd64675a6a931d1c9c6e89f8f70abf4f713d823c7e9f3cf26177322e53`
- 子图 state SHA：`30efff2ea7bd399c5068426b76b39f2322c34bcc17ac370c4976de2aa0289c1a`

原始本地证据为 `evidence/VERIFIED_CONFIGDICT_UNIT_TESTS.json`、`evidence/VERIFIED_CPU_TEST_REPORT.json`、`evidence/VERIFIED_CPU_LEGACY152_CONFIGDICT_R1_RECEIPT.json` 以及完整测试和子图诊断 stdout；公开日志须经过脱敏，不能直接发布 SSH 传输层 stderr。

## 门槛与预算

CPU_FINAL_GATE = FAIL。ConfigDict 修复轮次为 1/2，并未耗尽。失败原因是独立的 timm Enum 分配，不是 GPU 环境故障。严格停止条件生效：无 C0、无恢复 RGB019、无交叉或完整序列 GPU 运行。CPU 进程记录 CUDA 未初始化；不将其扩大描述为历史任务从未使用 GPU。

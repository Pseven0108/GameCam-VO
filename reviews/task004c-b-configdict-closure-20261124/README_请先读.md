# 请先读：ConfigDict专项修复评审

当前状态：ConfigDict修复通过，完整真实模型CPU恢复被独立timm Format枚举阻断。

先读[最终报告](FINAL_REVIEW.md)，再读真实模型新进程恢复报告、CPU最终门槛和原始失败日志。

| 证据 | 结果 |
|---|---|
| ConfigDict专项 | 14/14通过 |
| 历史回归 | 152/152通过 |
| 实际ConfigDict子图 | 6个ConfigDict / 24可达节点，精确比较通过 |
| 完整真实模型跨进程恢复 | 失败；timm.layers.format:Format |
| 恢复后的forward/gradient及完整Storage比较 | NOT_REACHED |
| ConfigDict专项预算 | 1/2使用；不是预算耗尽 |
| 新GPU C0 / 短程 / 正式四组 | 0/2、0/4、0/4 |

候选源码aa0cca3ed0d6e5d381422d8219234b8c0c6ad065。完整diff只涉及ConfigDict Adapter和Snapshot；Metric3D Adapter不变。

此包包含报告、源码差异、候选源码、真实stdout/stderr/退出码、对象图诊断、保全记录及公开SHA清单。没有模型权重、RGB、GT、Tensor payload、Arena、SSH连接材料。CPU fixture不是原生C0；子图通过不能替代全模型验收。GPU保留在线，未自动启动。

raw_evidence内为真实执行记录的脱敏副本；test_tools仅复现CPU检查，依赖既有模型/快照资产，不能当作自包含环境。旧152项测试实现与历史评审/源码同源，本包附本轮实际回归结果。

公开SHA针对脱敏后的字节。原始到公开SHA映射在publication/SANITIZATION_MAP.json。原始私有证据仍保存在本地及远端。报告写入/同步阶段曾因保护既有元数据而拒绝覆盖；改用独立review_final命名空间后18个文件回读校验通过，这不是模型重试。

后续只提出精确Format枚举Adapter方案，本轮未实施；正式阶段runner接入仍待完成。不得把本轮工程修复写成轨迹精度或尺度改善结果。

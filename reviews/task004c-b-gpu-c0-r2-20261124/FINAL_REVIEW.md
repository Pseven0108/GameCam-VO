# TASK004C-B-GPU-C0-R2 最终评审

**阶段状态：BLOCKED_AT_C0_CLOSURE_UNREGISTERED_LORA_DROPOUT_FUNCTION。首帧修复和真实初始化通过；完整C0未生成。**

| 验收项 | 结果 |
|---|---|
| 仅修NativeViperRGB | PASS，运行候选`02f8c8308274489ff7eff83fa9b87b98db74122e`，父提交668a88c7 |
| 真实父类/真实RGB CPU测试 | 21/21通过；连续18帧通过 |
| 原152项完整回归 | 最终152/152通过；首次缺对照文件的151/152记录保留 |
| 487张RGB与原资产 | SHA一致，模型/扩展/原R2未改 |
| 唯一一次真实GPU运行 | 已执行，56.164秒，exit1，无自动重试 |
| 真实共同初始化 | RGB001～018完成；第一阶段16、第二阶段8次graph.update |
| Native BA | 24次调用均有begin/end；当前帧完成后进入保存callback |
| C0保存 | **未生成**，状态闭包检查拒绝未注册函数 |
| 47族、model buffer、RNG持久化核验 | **未完成**，不得记PASS |
| 真实C0大小 | **UNKNOWN**；完整预算尚未计算 |
| Restore / S0/S1 / 跨D / B1-B4 | 全部未执行 |

已确认首个保存阻断：Metric3D `LoRALinear.lora_dropout`函数对象不在序列化器注册范围。安装源码的LoRALayer用`lambda x: x`表示无dropout，符合该异常路径；没有修改模型或放宽闭包检查。

完整状态没有持久化，因此本任务的“可验证完整C0”成功目标尚未达到。初始化完成不能替代完整C0，也不能证明恢复成功或轨迹性能改善。

本轮GPU采样峰值13865MiB，shm峰值288KiB；结束数据盘约22.2907GiB可用。两块含有效数据的Arena及所有失败现场保留，GPU进程已退出、无活动映射。服务器保持在线，历史删除0。

请优先读`TASK004C_B_GPU_C0_R2_REPORT.md`、`C0_CLOSURE_BLOCKER.md`和47族状态清单。源代码修复、21项/152项逐项日志、首次测试资产缺失、GPU stdout/stderr、trace、资源采样与全部SHA都随包保存。

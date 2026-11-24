# Task004-A 串行运行器审计

`tools/scheduler.py:63` 实现独立八组串行调度，本轮可执行目标仅是打包的 `fixtures/mock_child.py`。`tools/scheduler.py:28` 为未来原生运行生成绑定资产的启动计划，校验已提供的路径和 SHA，返回 `REAL_PLAN_ONLY`。`--native` 明确拒绝启动。`assets/candidates/task004_run_segment.py:5` 仍在导入模型、加载权重之前调用 `require_approved_runtime()`，原有保护未调整。**当前 ZIP 不具备原生批量执行能力。**

每组以独立 `序号-组名-随机ID` 建目录；调度器先锁定固定组序和八份策略、再计算本组可用空间，写 `LAUNCH_INTENT.json` 后才创建 CPU 子进程。收据记录组、策略散列、配置/输入散列、计划参数、输入和输出路径、进程身份，`PROCESS_RECEIPT.json` 记录完成时间、退出码和耗时。现有目录无法重试。任一步出错立即停止后续组，记录失败和未运行状态，保存局部输出，已有产物不删除。

完成收据要核对：真实进程退出、487 个输入/补位/输出 ID、冻结预处理后的 RGB 张量 SHA、实际 loader K、只有两个可改路径的配置、无位姿输入、原生追踪子进程和 Rerun 流的收据、关键帧 ID 与最终轨迹文本/数组一致、原生 BA 往返日志和归档接收回执。实现见 `tools/attempt_contract.py:17`、`tools/trace_audit.py:139` 和 `tools/archive.py:38`。Mock 用合成产物测试拒绝逻辑，哈希字段中的参考值只作为测试合同常量。

| 本轮实际执行 | 结果 |
|---|---|
| `evaluation/mock_campaign_03/CAMPAIGN_RESULT.json` | 8/8 CPU 替身按 E3→E4→E7→E0→E8→E6→E1→E2 完成 |
| `evaluation/mock_receiver_03/*.verified.json` | 8/8 本机接收副本通过独立验证 |
| `logs/release_tests_02.stderr.txt`、`.exit.txt` | 14/14 回归通过，退出码 0 |

正式放行仍需独立批准、可信会话的真实路径/源构建/权重/扩展/输入复核、资源测量、部署中的原生 Rerun 浏览器探针，以及实际异机接收端与串行启动收据的绑定。至少对首组核对真实 native 调用前记录的 `metric_depth_prior_selected`、有效支持点和 `enable_udba`/`enable_update_uncer`；出现缺报、配置漂移、运行失败、浏览器渲染失败或归档失败便停止待判断，不跳组不重试。

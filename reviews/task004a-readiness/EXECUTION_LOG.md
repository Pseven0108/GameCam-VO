# Task004-A 本地执行记录

| 操作 | 结果 | 原始收据 |
|---|---|---|
| 上一轮 ZIP 复开、CRC、SHA；复用 24 项资产、核验八份策略 | 80 个成员，79/79 哈希 | `evidence/TASK004_INPUT_ARCHIVE_VERIFICATION.json` |
| 冻结代码和 Task003 历史只读核验、离线端点回放 | 208 Blob、3 Gitlink；历史解析成功，退出码 0 | `evidence/FROZEN_SOURCE_AND_HISTORY_RECHECK.json`；`logs/historical_replay.*` |
| 策略、过程、输出、接收副本串行替身 | 最终迭代 8/8，退出码 0 | `evaluation/mock_campaign_03/CAMPAIGN_RESULT.json`；`logs/mock_campaign_03.*` |
| CPU 回归及 F0/F2 方法体替身 | 第 1 轮有 1 个合成端点断言失败；第 2 轮 14/14，退出码 0 | `logs/release_tests_01.*`、`logs/release_tests_02.*`；`evidence/F0_CONTROL_FLOW_CPU_MOCK.json` |
| 本机 Rerun 合成探针 | 第 1–4 轮失败记录保留；第 5 轮 HTTP、WS、画面均通过，退出码 0 | `_local_probe/probe_05/`；`logs/rerun_probe_*.txt` |
| 生成并检查待运行端点表 | 三张表各 8 行 `NOT_RUN`，无运行编号和观测数值 | `TASK004_*ENDPOINT*.csv` |
| 最终评审包 | 由明确的载荷清单生成；复开校验结果在 ZIP 同目录 | `FILE_SHA256_MANIFEST.json`、`TASK004A_ZIP_VALIDATION.json`（后者在 ZIP 外） |

CPU 子进程禁用 CUDA 设备可见性。命令只在本地任务目录读取既有实验资产、运行纯替身和合成 viewer；无远端进程、无 GPU 消融或清理。当前平台运行条件留给后续获批预检。

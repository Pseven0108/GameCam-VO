# Task 003 执行记录

- 本机工作区：`D:/aaa/GameCam-VO/experiments/DROID_W_TASK003_VAL007_OBSERVATION_R1`。
- 已核验远端：`sc01-ssh.gpuhome.cc:31217`，主机 `jupyter-6g08vd8ezmzwvd1k`；目录 `/root/rivermind-data/DROID_W_TASK003_VAL007_OBSERVATION_R1`。
- 正式运行收据 `remote/capture/LAUNCH_RECEIPT.json`：2026-11-22T19:07:13Z 使用 1/1 授权。模型 PID 1203，终态 `COMPLETE_NATIVE_OUTPUT`，退出码 0，结束时间 `2026-11-22T19:10:55.695581Z`。模型 stdout/stderr 按运行器原样合并保存在 `remote/capture/run.log`，外层监督 stdout/stderr 分开保存。
- 最终预检记录 24 GiB 共享内存、13.51 GiB 可用数据盘（14,510,059,520 bytes）、24,108 MiB 空闲显存、100 GiB 容器内存上限。此处磁盘数是正式启动前观测，与更早检查记录不同。
- `remote/capture/observer.jsonl`：44,365,711 字节，SHA-256 `62d385b24f5c83f7ae09033e7ef2c5ae1a146d49c412f1f5d4a40dc250ff3e10`。5,353 条事件均解析。`TASK003_TRACE_PROCESSING.json` 的 `runtime_process_exit_code` 留空，是因为转换器只读日志；正式退出码见 `attempt.json` 和监督日志。
- 观测器计时累计约 17.38 秒采集与摘要（包含约 3.31 秒张量读回）和 4.78 秒编码写入。这是埋点内部计时，不能用来直接推算无埋点耗时。GPU 结束状态与历史资产哈希见 `logs/remote_postrun_check.txt`。

| 步骤 | 退出码 | 原始证据 |
| --- | ---: | --- |
| 独立副本准备与静态核验 | 0 | `logs/stage_remote.*.txt`、`evidence/STAGE_VERIFICATION.json`、`remote/incoming/PATCH_VERIFICATION.json` |
| Rerun 启动与无模型验证 | 0 / 0 | `logs/rerun_remote_start.*.txt`、`logs/rerun_smoke.*.txt`、`evidence/RERUN_REMOTE_START.json`、`evidence/RERUN_BROWSER_ADMISSION.json` |
| 单次推理与监督 | 0 | `logs/run_supervisor.*.txt`、`remote/capture/run.log`、`remote/capture/RERUN_RUNTIME.log`、`remote/capture/resource_samples.csv` |
| 证据收集与原件身份核验 | 0 | `logs/collect.*.txt`、`evidence/POSTRUN_ASSET_PRESERVATION.json` |
| 观测转换成阶段数据表 | 0 | `logs/trace_processing.*.txt`、`TASK003_TRACE_PROCESSING.json` |
| CPU 离线评价 | 0 | `logs/offline_evaluation.*.txt`；Sim(3)、SE(3)、原始帧间隔、尺度比、旋转 RPE 和静止排除自检；核对 GT ID、有效配置、轨迹及原生导出矩阵 |
| 独立端点复算 | 0 | `logs/verify_targets.*.txt`；独立的四元数矢量公式反演 C2W，复核 16 条区间记录的位移长度和位移比 |

原生进程日志还保留了 Python 多进程退出时清理一个 semaphore 的警告，进程仍返回 0。浏览器入口为 `http://127.0.0.1:20636/?url=ws%3A%2F%2F127.0.0.1%3A20637`，需现有转发在线。

CPU 回算所需以下历史参考均只读，以 `D:/aaa/GameCam-VO/experiments/` 为路径前缀。`tools/evaluate_observation.py` 使用原目录结构。查看包里的结果无需运行模型；`tools/run_once.py` 仅作本次运行器存档。

| 参考 | 相对路径 | SHA-256 |
| --- | --- | --- |
| 冻结协议 | `DROID_W_TASK003_VAL007_RUNTIME_LOCALIZATION/evidence/sealed_r2/PROTOCOL_LOCK.json` | `a58aa17c022990d1c5b01b0afae0adb06dc86a8ec1c6c6e345d003ef026d1eb5` |
| 历史 R2 轨迹 | `DROID_W_TASK003_VAL007_RUNTIME_LOCALIZATION/evidence/sealed_r2/wild_reference/val_007_full_00001-00487/trajectory.npz` | `7db5457fd92a43e6f3bd4408c4f7f14e84c53c0449a2b51e7dd756894a03054a` |
| GT | `DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/offline_gt/val_007.npz` | `91fb149c066bb488ac6071602a4b50fe1540243f2db3369a3706f63b705d7008` |
| 冻结评分器 | `DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/pipeline/offline_evaluation.py` | `be1a605d1a0fbfa22db61ae7f4eabbde080bb12ce01110ee8f2684aeaefc477e` |

归档 SHA-256 清单覆盖全部载荷文件（清单本身和承载它的 ZIP 不自列）。归档校验包括 ZIP CRC、逐成员 SHA-256/大小，以及主要运行证据的独立哈希核对。归档不消耗运行授权，服务器未关机。

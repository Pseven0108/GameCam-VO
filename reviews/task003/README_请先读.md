# GameCam-VO Task 003 评审入口

**DROID-W `val_007` 已完成唯一一次 487 帧 GPU 观测和离线评价。** 从 [最终评审](TASK003_FINAL_REVIEW.md) 开始。[分阶段图](figures/TASK003_STAGE_DISPLACEMENT.png) 和 [区间评分](TASK003_VAL007_INTERVAL_ANALYSIS.csv) 可单独提交给评审者，不必先读取整包。

| 要审查的内容 | 入口 |
| --- | --- |
| 平移从何时开始缩短 | [312→328 局部 BA 时间线](TASK003_312_328_LOCAL_BA_TIMELINE.csv)、[阶段图](figures/TASK003_STAGE_DISPLACEMENT.png)、[关键优化步骤](figures/TASK003_OPTIMIZATION_STEPS.png) |
| 输入配置及运行授权 | [最终预检](evidence/TASK003_FINAL_PREFLIGHT.json)、[有效配置差异](evidence/CONFIG_EFFECTIVE_DIFF.json)、[实际运行终态](remote/capture/attempt.json) |
| 五阶段观测与埋点 | `remote/capture/observer.jsonl`、`TASK003_*_LOG.csv`、`TASK003_*_SUMMARY.csv`、[观测补丁](remote/incoming/TASK003_INSTRUMENTATION_PATCH.diff)、[埋点说明](tools/TASK003_INSTRUMENTATION_MAP.md) |
| 轨迹、评价和 CPU 复核 | [轨迹图](figures/TASK003_FINAL_TRAJECTORY.png)、`remote/capture/trajectory.npz`、[评价明细](evidence/TASK003_RUNTIME_EVALUATION.json)、[复算输出](logs/verify_targets.stdout.txt) |
| 浏览器是否显示了真实数据 | [实跑画面](evidence/RERUN_BROWSER_TRACKING.png)、[运行后重开画面](evidence/RERUN_BROWSER_REOPEN.png)、[传输证据](evidence/RERUN_BROWSER_FINAL_TRANSPORT.json) |
| 执行和归档核验 | [执行日志](EXECUTION_LOG.md)、`FILE_SHA256_MANIFEST.json` |

`remote/incoming/native_config.yaml` 是冻结的 R2 YAML，`remote/capture/native_config.yaml` 是本次实际生效的 YAML。`remote/incoming/TASK003_RUNTIME_CONFIG.json` 保存的是较早的无卡准备状态，其中的 `BLOCKED` 和 `0/1` 仅适用于准备时点。正式运行结果以 `remote/capture/attempt.json` 为准。

本包含逐帧评价表，无原始 RGB、权重、原始 GT 归档或完整源码仓库。原生 `video.npz` 留在服务器，其 [身份记录](evidence/REMOTE_NATIVE_VIDEO_IDENTITY.txt) 提供路径、字节数和 SHA-256。

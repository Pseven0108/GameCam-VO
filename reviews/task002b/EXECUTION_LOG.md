# Task 002B｜本地执行记录

按冻结协议进行只读 CPU 审计。作用域仅限 Task 002B，未复跑任何历史实验。

| 实际步骤 | 状态 | 证据 |
| --- | --- | --- |
| 原始 ZIP、协议锁、Task 002A 同源清单及 49,815 个原始 JPEG 的身份；280 样本与两个整段像素回放 | exit 0 | `analysis_only/pixel_audit.{stdout.log,stderr.log,exit.txt}` |
| 回执、导出轨迹、GT 和锁定评价器；2,944 行复算 | 两次辅助脚本为 exit 1；最终 exit 0 | `analysis_only/motion_audit*.{stdout.log,stderr.log,exit.txt}`。先处理历史字段别名，再排除预检与运行的耗时字段；不改原始脚本或历史回执 |
| 统计、源序列 bootstrap、压缩筛查和排序对照 | exit 0 | `analysis_only/summarize_motion.{stdout.log,stderr.log,exit.txt}` |
| 验证原 Camera ZIP 及重建封存 K | 系统 Python 缺 NumPy、exit 1；已安装的 `gamecam-vo` 环境 exit 0 | `analysis_only/calibration_audit*.{stdout.log,stderr.log,exit.txt}`；未安装或修改依赖 |
| 报告与打包 | SHA 清单覆盖 ZIP 的全部其他成员，校验结果记录在 ZIP 同目录 | `analysis_only/prepare_review_bundle.py`、`CHAT_REVIEW_PACKAGE/ZIP_VERIFICATION.json` |

未运行 GPU 设备枚举、CUDA、模型、训练、消融或 SSH。独立脚本使用 CPU，只在 Task 002B 下写报告。没有改动冻结图像、Camera 标注、模型、配置、提交身份或历史结果。

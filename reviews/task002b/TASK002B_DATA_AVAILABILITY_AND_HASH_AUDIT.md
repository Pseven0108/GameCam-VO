# Task 002B｜原始证据、帧覆盖与哈希审计

只读复核通过。唯一纳入的实验协议是 `VIPER_MATCHED_DUAL_BASELINE_R2_V1`：VIPER Validation、640×360、stride=1、92 个独立初始化区段、47 条源序列、49,815 张 RGB。不使用 stride=4、旧 64 帧实验或其他数据集的成绩。

| 证据 | 复核结果 |
| --- | --- |
| 原始 R2 评审 ZIP | 10,653,960 bytes；2,391 个成员 CRC 通过；SHA-256 `582c778c5649d13b06d0f8ac16160441c37b06f5eb6dd644a1279393d6162315`，符合任务书 |
| 冻结协议和清单 | 本地 R2、原始 R2 ZIP、Task 002A 一致；冻结清单 SHA-256 `b991fd5019307373601b5e2fd5460a83049ffea517140e1fcf6401996a091acb` |
| 源码身份 | DROID-SLAM `2dfd39f0dcad44012ca7bbb8aa70b55edbfa9c99`；DROID-W `c3414af6047d06bafc1a6645d09f23247f3b2cdc`。读取 Task 001 核验的归档快照；快照没有可切换的 Git 工作区 |
| 原始 RGB | 五个本地 ZIP 中 49,815/49,815 个 JPEG 成员 CRC、尺寸字节数、SHA-256 和区段 frame ID 核验；读取 10,614,139,224 bytes；无相同 JPEG SHA 的组。此处“无重复”仅指编码字节，不排除近重复或不同编码的相同画面 |
| GT 和 Camera K | 47/47 个 Validation Camera CSV 成员 CRC、SHA-256 通过；49,815 行原始 K 从投影矩阵逐行复算且与封存 K 完全相同；47 份 GT 同时匹配 R1 来源账本和 R2 冻结 SHA |
| 轨迹和回执 | 184/184 组轨迹文件核对原 ZIP、终态回执及冻结哈希；两模型各有 92/92 区段完整导出、49,815/49,815 个有效 pose、0 缺失、0 无效 |
| 关键帧 | DROID-SLAM 8,042；DROID-W 12,568。数量与终态记录一致；非关键帧允许由 Trajectory Filler 补位 |
| 评价程序 | `pipeline/offline_evaluation.py` 与原始 R2 ZIP 一致，SHA-256 `be1a605d1a0fbfa22db61ae7f4eabbde080bb12ce01110ee8f2684aeaefc477e`；原 CPU 自检通过 |

原始 R2 ZIP 位于 `D:\aaa\GameCam-VO\experiments\VIPER_MATCHED_DUAL_BASELINE_R2\evaluation\VIPER_MATCHED_DUAL_BASELINE_R2_REVIEW_PACKAGE.zip`。封存 GT、K 及 Camera 来源账本位于同级实验目录 `DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1`。归档 `D:\aaa\GameCam-VO\audits\VIPER_PRIMARY_ADMISSION_R0\02_samples\val_camera.download` 的实际大小是 12,039,423 bytes，SHA-256 为 `19f8e1d36ac8066b21f9d8b6a6d75394cf7fcfbfd4c4914ea9e30ba0fdcb5dc9`。路径取自 R1 来源账本，未改名。

**帧与坐标。** 每个区段的输入 RGB ID 与输出 ID 等长且严格连续。GT 的 Camera ID 是 `RGB_ID−1`，逐完整源序列核对；47 条序列没有用其他帧填补缺口。封存 GT 按 R1 `pipeline/audit_viper.py:41–65,182–197` 从 OpenGL View 矩阵构造：`F = diag(1,−1,−1,1)`，`C2W = F @ inv(View) @ F`。检查了有限性、旋转正交性、行列式及齐次末行；估计文件按 `c2w_xyzw` 读取，检查了四元数范数、位姿掩码及关键帧 ID。原始 DROID-SLAM `droid.py` 的终止出口包含 W2C→C2W 反演；DROID-W 使用封存的全帧 C2W 导出。没有单独证明曝光时刻与 Camera 标签共享物理时钟，15 FPS 只作名义时间换算，平移沿用 game units。

**证据文件。** `TASK002B_FROZEN_EVIDENCE_AUDIT.json`（总计及复算误差）、`RGB_SOURCE_SEGMENT_AUDIT.csv`（各区段原始输入）、`R2_TRAJECTORY_AND_GT_INTEGRITY.csv`（184 对应轨迹/GT 记录）、`R2_RUNTIME_INPUT_RECEIPT_PARITY.csv`（92 个运行回执）、`R2_CAMERA_K_PROVENANCE_*`（从原 Camera CSV 到 K 的逐序列/区段记录）。日志保留了校验脚本的初次失败及最终通过记录；没有改写原始文件来通过校验。

**不能由完整导出推出的指标。** 未留存可判断每一帧是否被前端直接跟踪的日志。`valid_pose_coverage=100%` 是导出覆盖率，不是跟踪成功率或 SLAM 全程无失锁证明。没有重新推理、训练、读取 GPU、连接服务器或启动消融。

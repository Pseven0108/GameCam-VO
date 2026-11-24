# GPU C0首次真实采集：失败取证包

先读FINAL_REVIEW.md，再读FIRST_FRAME_INPUT_CONTRACT_DIAGNOSIS.md。

**1次GPU启动，0帧进入跟踪，0次BA，没有C0。** 原因已由CPU真实loader实读确认：无GT深度时父类返回全零占位Tensor，与适配层要求None冲突。

包内包含实际运行日志、资源采样、CPU诊断、配置/源码锁、原CPU proof、临时Arena生命周期、源代码证据和启动器。没有真实模型权重或RGB数据。2255-byte Rerun文件留在远端并记录SHA，不能作为可视化几何成功证据。

新建议未应用，未自动重跑；完整C0大小和恢复能力仍未知。SHA清单覆盖除自身外的全部包内文件，ZIP另有外部CRC/SHA验证。

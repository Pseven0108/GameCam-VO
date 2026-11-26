# GameCam-VO 项目状态 · TASK007D

2026-11-26（Asia/Shanghai）。当前阶段：**TASK007D来源追溯完成；用途B（相对/辅助诊断），严格米制GT仍NO-GO**。

[最终评审](reviews/task007d-metric-scale-provenance-audit-20261126/FINAL_REVIEW.md) · [完整证据](reviews/task007d-metric-scale-provenance-audit-20261126) · [完整Review ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task007d-metric-scale-provenance-audit-20261126/GAMECAM_TASK007D_METRIC_SCALE_PROVENANCE_REVIEW.zip)

- GitHub main完整可达历史26提交、6个CSV版本及3个UID已核查。2026-03-21新增484行Metric Scale列，其余字段未变；当前CSV与发布时字节一致。
- Reader只读取/应用尺度；未找到绑定三UID的生成程序、拟合帧、独立物理标尺或误差界。
- 作者旧的MoGe-2近似建议不能当作当前因子的生产事实；是否使用Metric3D或Test拟合仍未知。
- 不启动Metric3D Confidence校准/NLL/Coverage。模型运行0、GPU/CUDA0、新原始数据/权重下载0。
- TASK007A/B/C封存141项SHA通过；不改历史Release、VIPER主线或Baseline。
- VKITTI2训练家族重叠纠正继续有效；Scalix、CADP与Confidence-aware BA不启动。

完整历史入口保留在[上一固定提交](https://github.com/Pseven0108/GameCam-VO/tree/30c4149863ce202f4545a872707f0a6fc6a0bfb1)。本次不自动进入下一阶段。

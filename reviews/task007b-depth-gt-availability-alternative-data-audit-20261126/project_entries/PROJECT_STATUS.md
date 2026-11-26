# GameCam-VO 项目状态 · TASK007B

2026-11-26（Asia/Shanghai）。当前阶段：**TASK007B 数据源可行性审查完成，正式像素校准仍阻断**。

[最终评审](reviews/task007b-depth-gt-availability-alternative-data-audit-20261126/FINAL_REVIEW.md) · [完整材料](reviews/task007b-depth-gt-availability-alternative-data-audit-20261126) · [完整评审ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task007b-depth-gt-availability-alternative-data-audit-20261126/GAMECAM_TASK007B_DEPTH_GT_AVAILABILITY_REVIEW.zip)

- TASK007A：STOPPED_AT_DATA_ADMISSION；没有校准/NLL/coverage结果。
- TASK007B：官方渠道、归档补查、候选数据与划分设计完成；新增GPU前向0、原始数据下载0、拟合0。
- VIPER继续是VO主线，DROID-W保持冻结；没有更换数据集或改原有划分。
- 推荐Virtual KITTI 2.0.3作为独立深度校准候选；实际GT样本尚未取得，尚未批准其推理或训练。
- MVS-Synth只可考虑已观察数据的尺度不变探索；不作为米制/新鲜独立测试证明。
- Scalix预测头、Confidence-aware BA和CADP接入继续暂缓。

所有根目录状态入口已在本次评审提交中统一；历史完整状态保存在[上一提交](https://github.com/Pseven0108/GameCam-VO/tree/f1ca13c49f13ebe0e7cb1a6f99c4c0d618b91dfe)及REVIEW_INDEX。


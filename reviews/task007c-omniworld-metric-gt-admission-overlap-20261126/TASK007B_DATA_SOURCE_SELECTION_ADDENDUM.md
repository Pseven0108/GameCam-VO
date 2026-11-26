# TASK007B 数据源选择增补纠正

2026-11-26。本文件是新增纠正记录；不倒改已经封存的 TASK007B ZIP、报告或历史提交。

**撤回“Virtual KITTI 2 可作为 Metric3D 训练未见的独立测试集”的推荐。**
已固定的 Metric3D 公开 ViT-Large 训练配置在 `data_array` 中启用 `Virtual_KITTI`，
并导入 VKITTI 配置及 train.json。故至少存在训练数据源/家族层面的重叠证据。
当前检查不能确认实际权重中的 VKITTI 版本、2.0.3 的具体帧或 Train/Test 精确交集。
不把“精确成员未知”当作“可以证明无重叠”；也不反向捏造每张2.0.3图均参与训练。

TASK007B 关于 VIPER dense 归档为 RGB、公开像素GT尚未准入、MVS单位局限的证据保留。
本轮不下载 Virtual KITTI 2，不重跑 Metric3D，不更改 VIPER VO 主线。
详见 [训练重叠审计](METRIC3D_PRETRAINING_OVERLAP_AUDIT.md) 与 [本轮最终报告](FINAL_REVIEW.md)。

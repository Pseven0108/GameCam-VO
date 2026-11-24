# Task 002B-Addendum 图表说明

`val_007` 图标出最终轨迹、关键帧及四组区间。目的是检验压缩是否已经出现在最终 BA 的锚点。跨环境图比较相同 RGB ID 或相同 RGB 端点上的误差，显示配对的序列数量及数据不足的组。

来源：`VAL007_FRAME_SERIES.csv`、`VAL007_CASE_INTERVALS.csv`、`VAL007_ANCHOR_INTERVALS.csv`、`POSE_ERROR_ENVIRONMENT_PAIRED.csv`、`RPE_ENDPOINT_ENVIRONMENT_PAIRED.csv`。绝对位置和位移比均使用本区段的一套 Sim(3)。环境图显示序列 RMSE 的中位数，代表性 RPE 偏移为 60；完整四种偏移在 CSV。区间和帧不是独立样本。图不包含原始 RGB，也不用于证明组件因果作用。

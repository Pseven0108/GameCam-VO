# 指标定义与证据追溯

使用冻结的 `VIPER_MATCHED_DUAL_BASELINE_R2_V1`，640×360，stride=1，按 `Camera ID = RGB ID−1` 使用已配对离线 GT。时间只按名义 15 FPS 表示。固定 K 和虚拟相机分开统计。不跨区段连接位姿或相对运动对。

## 位姿与 RPE

- 读入导出 `c2w_xyzw`，核对 `rgb_ids`、关键帧本地索引、位姿有效标志和相机编号。KEYFRAME 来自实际最终保留关键帧 ID。FILLED_FRAME 为该模型其余有效导出帧。MISSING、INVALID 分开记录；本次二者均为 0。`pose_origin` 说明 K 位姿是否来自直接 BA 锚点覆盖。
- 每模型每区段从全部有效相机中心拟合一次 Sim(3)：`p_aligned = s R p_est + t`，`R_c2w,aligned = R R_c2w,est`。位置误差为相机中心差的范数；绝对旋转误差为 GT c2w 与对齐 c2w 的相对转角。所有按类别、时段及直接锚点的汇总复用原有对齐。
- 公式沿用现有 `pipeline/offline_eval.py`：同一 RGB pair `(i,j)`，原生相机到世界 Pose 记为 `(R_i,p_i)`，起点坐标下的平移/旋转为 `d = R_i^T (p_j−p_i)`、`Q = R_i^T R_j`。平移 RPE 是 `||s d_est−d_gt||`，旋转 RPE 是 `Q_gt^T Q_est` 的转角（度）。对齐的全局旋转和偏移在相对运动中抵消，尺度仍使用区段的同一个 `s`。正式有效对要求精确原始 RGB 差且区间完整有效。分类保留每个端点真实身份，F→F 不承诺区间内部没有关键帧。
- `scaled_displacement_ratio = s ||d_est|| / ||d_gt||`，GT 位移≤1e−6 时不计算。位移长度比不含方向信息，不能用它替代平移 RPE。相邻关键帧对用 `actual_rgb_gap`，案例还保留 16、52 帧间隔；均不冒充正式 offset=1。
- `OWN` 使用模型自己的类别和序列，`MATCHED` 在相同 RGB ID 比较；`MATCHED_CLASS_GRID` 在相同 RGB 对分别记录两侧模型的有序端点类别。表中的 RMSE 分布按原始序列先合并 SSE 和样本数；分环境的配对均值差重抽样以序列为单位。逐对分位数和序列 RMSE 分位数含义不同。

## 找到原始证据

| 要追查 | 表与索引 |
|---|---|
| 单帧身份和误差 | `FRAME_TYPE_MANIFEST.csv`、`KEYFRAME_POSE_ERROR.csv`、`FILLED_FRAME_POSE_ERROR.csv`，按 `(segment, model, rgb_id)` 查找；`trajectory_row_0based` 是数组中的导出行号。每行有 `camera_id` 和轨迹 SHA-256。 |
| 读取被冻结的轨迹成员 | `KEYFRAME_ID_AUDIT.csv` 按 `(segment, model)` 找 `trajectory_member`、SHA、原始回执、实际关键帧比例。轨迹来自历史 `VIPER_MATCHED_DUAL_BASELINE_R2/evaluation/VIPER_MATCHED_DUAL_BASELINE_R2_REVIEW_PACKAGE.zip`，源哈希在 `evidence/NUMERICAL_VERIFICATION.json`。 |
| 正式 RPE 逐对 | `RPE_PAIR_DETAIL.csv` 用 `segment_index` 连接 `RPE_PAIR_SEGMENT_INDEX.csv`，用 `start_rgb`、`start_rgb+offset` 得两端 ID；索引表列出 GT 和两轨迹 SHA。端点码 0/1/2/3 分别表示 K→K/K→F/F→K/F→F。`*_trans_error_sq` 为平方误差，逐对平移误差取其平方根。`temporal_third` 按帧对中点归入区段时间三分位。 |
| 从帧对到环境统计 | `RPE_BY_ENDPOINT_TYPE.csv` → `RPE_ENDPOINT_TYPE_BY_SEQUENCE.csv` → `RPE_ENDPOINT_ENVIRONMENT_PAIRED.csv`。用 `calibration_branch`、`offset`、端点类型及 `paired_sequence_ids` 核对各组入选序列。`RPE_PARTITION_RECONCILIATION.csv` 对照原 Task 002B 的未分组 RMSE。 |
| 绝对位姿、锚点对照与压缩案例 | `evidence/R2_STAGE_AND_ALIGNMENT_INDEX.csv` 给出每个区段的 `s,R,t` 和阶段选项；`DIRECT_FINAL_BA_ANCHOR_COMPARISON.csv` 与 `MATCHED_KEYFRAME_ANCHOR_PAIR_DETAIL.csv` 跟踪直接锚点复核；`VAL007_*` 给出指定 RGB 对与同类参照。 |
| 源码与历史保护 | `evidence/SOURCE_PROVENANCE.csv` 记录提交、blob ID、SHA 和文件行号；`evidence/FILLER_SOURCE_EXCERPTS.txt` 保存可读摘录；`evidence/ORIGINAL_EVIDENCE_PRESERVATION.csv` 记录原始证据文件身份。 |

大表只收录于完整版。轻量包保留案例行、环境及敏感性汇总；它不含待评分原始轨迹、GT 或 RGB。分析脚本需要本机既有 `GameCam-VO/experiments` 下的冻结源与 Task 002B 评价代码，不能依靠轻量包独立重算。

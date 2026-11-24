# RGB 312→328：固定导出与关键帧端点评价

`TASK004_ENDPOINT_RETENTION.csv`、`TASK004_FIXED_RGB_ENDPOINT_METRICS.csv` 与 `TASK004_DIRECT_KEYFRAME_ENDPOINT_METRICS.csv` 各有八行。正式筛选待授权，所有组为 `NOT_RUN`，未观测字段为空。`evaluation/mock_campaign_03/SYNTHETIC_*.csv` 仅为测试样本。

| 层次 | 取值证据 | 缺失处理 |
|---|---|---|
| A 固定 RGB 端点（主要端到端指标） | 最终 `trajectory.npz` 与原生 `est_poses_full.txt` 的 RGB 312、328 位姿，匹配 observer 最终导出；记录实际来源是保留关键帧回填或 Filler | 任一端点缺失则留空、标记原因；逐组报告有效性 |
| B 直接关键帧端点（机制指标） | `keyframes.json` 最终保留索引与 `final_phase_2_done` 快照内，真实保留的 312、328 原生位姿 | 任一端点未被保留或位姿无效，报告 `ENDPOINT_UNAVAILABLE`；不插值、不拿临时位姿替代 |
| 局部 BA 诊断 | 同一 `(pid, ba_id)` 的前、原生返回、钳制后记录；标注两端都在快照中、都在可优化窗口、都被观测边触及、是否互为直接边 | 若没有共同记录则报告缺失；两端同现不等于被同一直接边约束 |
| Filler 诊断 | `filler_batch_result` 中的两端临时位姿及批号；与最终导出来源核对 | 批号、有效性和诊断值独立记录；保留关键帧以重新插入后的位姿为最终值 |

两端各报告 `retained_kf`、`export_valid`、`export_origin`、`filler_temp_valid` 和 Filler 批号。端点关键帧保留率为两端保留数除以 2；全段保留率为最终关键帧计数除以 487。`joint_local_ba_return` 表示两端同现于一个完整返回的前端主循环 BA，再分别核对窗口与观测边。直接关键帧结果按可用性报告；不要把仅剩的可比较组当成完整因子矩阵。

RGB 312/328 对应 Camera ID 311/327。GT 由既有离线映射和文件 SHA 核验，不传入模型进程。原生快照按 W2C `tx,ty,tz,qx,qy,qz,qw` 转为 C2W，反演一次；最终导出按 C2W 读取。`tools/endpoints.py:40`、`:64`、`:74`、`:112`、`:150` 分别检查约定、映射、输出一致性、指标和来源。

位移比为 `100 × 19.1341794347 × ||p328−p312|| / ||g328−g312||`；尺度来自已封存的 Task003 全轨迹参考并对所有组共用。另报离 100% 的绝对差（百分点）、平移 RPE（游戏单位）、旋转 RPE（度）及方向误差（度）。每组全轨迹拟合尺度只作诊断，方向误差使用全轨迹对齐旋转；不对目标区间单独拟合尺度。GT 位移退化时位移比为空，对齐退化时方向为空。

历史回放核对：Task003 最终 86/487 个关键帧，312 与 328 均保留，第一次共同局部 BA 为 552（事件 2600/2601/2602）。固定 RGB 最终导出位移为 GT 的 **16.00948%**，直接关键帧为 **16.00955%**；两种来源的微小差异保持原样。见 `evidence/TASK003_HISTORICAL_REPLAY.json`，此条仅验证评价合同，不是 E0。

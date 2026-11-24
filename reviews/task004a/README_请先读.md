# 请先读

本包是八组真实GPU消融后的结果和数据评审包。先读 TASK004A_FINAL_CAUSAL_SCREENING_REVIEW.md。evaluation/ 包含逐帧误差、RPE、三组目标区间、直接关键帧和最终导出的分离指标、BA时间线、U及disparity计数、因子效应。

raw_trajectories/ 保存八组完整轨迹及关键帧身份；raw_run_receipts/ 保存运行、配置、策略、模型输出、stdout/stderr和退出码收据；完整 observer.jsonl 和原生 video.npz 位于本机 raw_archives/ 中的八个独立原始数据ZIP，清单为 RAW_DATA_ARCHIVE_INDEX.json。完整原始归档不重复塞入轻量包。

FILE_SHA256_MANIFEST.json 覆盖包内全部有效载荷，自身不参与递归自校验；ZIP校验结果存于包外 PACKAGE_VALIDATION.json。所有指标的单位及尺度口径见评价合同。

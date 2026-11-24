# E5-F0 最终 BA 跳过分支复核

**结论：`BLOCKED_FOR_NATIVE_EXECUTION`。** CPU 替身通过 F0/F2 的控制流对照；还无法确认 F0 跳过后端重建、深度有效掩码刷新后的原生状态及输出。F0 独立保留，八组主矩阵始终运行两段 Final BA。

冻结 `src/backend.py:20–34` 的 `Backend.__init__` 绑定网络更新函数、视频、设备和后端参数。候选 `assets/candidates/preview/src/slam.py:57–60` 已在 SLAM 构造时创建 Backend 与 Filler。终止时再次调用 `backend()` 原本会临时关闭 `video.metric_depth_reg`、重建 Backend，再运行两段 `dense_ba()` 并恢复开关（同文件 `130–151`）。`dense_ba` 内原生保存链涉及 `set_dirty` 和 `update_valid_depth_mask`（冻结 `src/backend.py:70–91`）。F0 跳过整个终止时的 `super().backend()`，构造阶段的 Backend 仍存在，但不能假定视频缓存和深度有效掩码与经过 Final BA 的状态一致。

`assets/candidates/task004_run_segment.py:164–184` 在调用父级终止流程前保存保留关键帧索引；F0 写 `final_pre`、`final_ba_skipped` 后返回。父级随后保存 `video.npz`，对 `RGB_NoPose` 流建立 Filler 特征提取并补位、导出（`assets/candidates/preview/src/slam.py:184–224`）。F0 没有触发局部 D 的设置去修改全局 `metric_depth_reg`；Mock 中进入/离开跳过分支均保持 `true`，F2 在两次稠密 BA 时为 `false`、保存与 Filler 时恢复为 `true`。

`tests/f0_mock.py` 以 AST 提取真实候选方法体，对后端、缓冲区、Filler 和写盘使用替身。F0、F2 均观察到 4 个所设关键帧索引、保存调用、487 帧补位和导出调用；文件写入、深度掩码数值、原生补位质量、锁及子进程退出都没有因此通过真实验证。原始记录：`evidence/F0_CONTROL_FLOW_CPU_MOCK.json`，`logs/release_tests_02.*` 中第 13 项测试。无需修改原始 runner。若要放行 F0，单独批准并核验跳过前后缓存、计数和实际保存产物，再确认其观察协议可提取无 Final BA 的边界，不复用强制要求两个 Final BA 阶段的主矩阵验收器。

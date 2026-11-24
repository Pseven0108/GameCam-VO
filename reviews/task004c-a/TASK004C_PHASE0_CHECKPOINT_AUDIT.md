# Task004C 检查点审计与恢复结果

历史 Task004A/B 的日志、video.npz 与 Metric3D 缓存不足以还原完整原生 BA 输入。没有将 observer 位姿记录冒充 checkpoint。此前 Phase0 已封存，未覆盖。

用户追加批准后，本轮执行两个 RGB1–328 新前缀采集，在真实 droid_backends.ba 入口保存完整一次原生调用输入。E0 新状态为 BA552、71个活动关键帧、70条有向边；E1 新状态为 BA656、123个活动关键帧、94条有向边。它们不是历史 BA550/BA660 的逐位重建。

每个状态均验证 RGB312 和 RGB328 在优化窗口内，存在两个方向的直接边。保存 poses/disps/K/prior/target/weight/U/temp_y_cdot/DINO/affine/eta/ii/jj，以及全部标量、mono/zeros/timestamp。文件与内容哈希、dtype、stride 和实际 GPU 恢复收据完整。

这些检查点的范围为 ONE_NATIVE_BA_CALL_FIXED_NETWORK_TARGETS，足以冻结网络已生成的 target/weight/eta 后重放一次原生 BA。没有保存完整 frontend hidden/context/correlation/RNG/cache 重启状态；不能作为 B 的共同初始化。D1/D0各从原始检查点恢复独立副本，没有将一个分支输出当作另一分支输入。

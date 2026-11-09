# 启动屏障风险

FULL_MODEL_STARTUP_TIMING_UNVERIFIED

启动屏障保持15秒、活跃监控3秒。当前合成Torch导入+CUDA初始化约2.531秒；真实CPU DepthVideo含导入构造约5.388/4.473秒。合成测试不能替代真实完整模型启动计时。

实际代码先启动Guard并发布CUDA心跳，再导入Tracker依赖、装载checkpoint和构造视频/网络。真实GPU当前未授权，无法实测完整启动、GIL/内核阻塞、prior加载期间心跳及时性和后续峰值。完整checkpoint加载耗时不应错误全部计入首个CUDA心跳的15秒，仍可能导致活跃3秒门槛风险。预启动的hash核验也单独计时，不延长Worker15秒。

不延长任何门槛；不根据本轮合成耗时声称真实启动必然成功。

# 冻结协议与测量定义

- DROID-W commit：c3414af6047d06bafc1a6645d09f23247f3b2cdc。
- 原R2 YAML SHA256：a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc。仅运行内存中的setup_seed按44/45设置；保存的原YAML字节未更改。
- 487帧RGB输入、640×360、stride=1、buffer=500，模型输入没有GT位姿。GT只进入本地CPU离线评价。
- D=0仅不向指定局部BA传入缓存Metric3D先验；不停止模型预测/缓存。W=0禁用源端UBA，U=0停止对应局部U更新。目标端门控、初始化、Final BA、Filler保持既有合同。
- 全局Sim3/SE3公式、四个RPE offset、三个固定端点区间均复用Task004A代码。Seed43的48项关键复算值与原交付逐项匹配。
- U_event_medians_median是每次局部BA采样U中位数的运行内中位数；P90/P95同理。不是将全视频全部像素汇集后计算的分位数。Effective weight来自已记录的确定性CPU边/像素子采样，不代表捕获全部CUDA权重场。
- 负disparity/floor像素事件会在多次BA中重复计数，不是独立像素数。clamp_pixel_events_from_new_floor按每次native-after与clamp-after的floor数量增量累计，是新变成floor的像素事件数，仍会重复计入同一空间位置。clamp_calls_changing_grid仅统计观测前后计数结构发生改变的调用；不能解释为唯一被clamp的像素数。
- Motion filter分数是既有delta的CPU norm代理；frontend_distance是记录的原生距离标量。两者不混同。
- Local candidate rejection rate分母为出现Predecision BA的不同候选RGB帧，原始决策和完整调用CSV另附。

# Fixed-State Replay

参考：同序列、同seed的A0已安装原系统，57次参考运行是285次中的子集，不另加57次SLAM。
收集全部实际FRONTEND_MAIN_LOOP_LOCAL_BA、非motion-only、metric_depth_reg=true调用。
不按结果选择调用，不记录初始化/第二阶段初始化/在线全局/最终BA/Filler。

快照含30原生参数、源槽位/时间戳、A5场、A7场、native-valid、mono mask及RNG。
Torch序列化复制保留storage alias、dtype、shape、stride、offset。三个独立分支A5_first、
A7、A5_repeat都从同一快照恢复；原始输入逐项哈希一致，原快照不被分支污染。

“U/UBA保持相同”指分支起点与配置相同，不关闭原生U更新。分支内部U可以随原算法变化。
同一candidate binary、同一两轮BA、同一Geometry Need=false，只改变strength空间分布。
记录pose/disparity/dx/dz/U差异、时间、均值与A5-A5重复波动；没有原生残差时标记不可用，
不改Native求解器。波动达到对比差异的0.5倍即保守警示数值不确定；这是预注册诊断规则，
不是显著性检验，也不是一个重复对就能建立的数值噪声置信区间。

同序列多个BA是嵌套观测，不能当独立N。没有完整轨迹，不报告FSR的ATE/RPE。
较小更新不是准确性证据；若没有准入的局部目标或GT，FSR只能证实机制差异和数值尺度。

每次保存前按唯一Storage估算预算并保留10GiB，超限STOP，保留部分输出，不自动清理历史。
真实快照大小和总量未知。采集开销单独记录，不能忽略其对A0总时间的影响。

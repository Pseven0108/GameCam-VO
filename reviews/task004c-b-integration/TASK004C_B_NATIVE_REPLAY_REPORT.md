# 跨D调度接入

S1定义为共同INIT_D=0后D=1自然记录；S0为同一C0下D=0自然记录。W/U使用原生模板；最初8次初始化原生enable_udba=False保持不变。D只在全部初始化阶段设为0，在后续frontend main-loop local BA依据分支选择。其他BA阶段保留原生开关。

Replay在Motion Filter和保留/删除决策之前选择源调度，在图primitive处强制相同增加、移除、窗口和调用次序。每个结果点验证真实有序拓扑。不能执行、不兼容的边/槽、无记录拓扑/age变化、帧或BA次序不符，均停止。当前范围只支持原Frontend使用的尾部候选删除；其他compaction会拒绝。

各分支重新计算RGB特征、Corr、net hidden updates、target、weight、damping、Pose、disparity和U。没有回放连续优化结果。CPU使用真实FactorGraph Python方法体和数值mock，已双向验证D0重放S1、D1重放S0时图事件一致而disparity不同。

这仍不是原生跨D成功证据。真实S0/S1、真实重放、真实下一次BA顺序均待GPU验证。自然关键帧选择的原始分数保留在诊断日志，源调度是明确的离散干预，不能声称所有连续输入在运行期间保持相同。

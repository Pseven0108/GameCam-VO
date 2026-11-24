# Task 004｜阶段范围与调用计数

**干预只进入前端主循环的两个可达局部调用路径。** 单靠观察阶段字符串不足以触发干预：调用必须有显式 task004_phase，阶段须与观测上下文一致，须为位姿和深度联合更新，且原始 R2 的局部 D/W/U 配置完整匹配。缺失或冲突抛错，未标记的非目标路径沿用原实参。源码行号取冻结版本。

| 阶段 | 源码入口 | factorial 配置 D/W/U | Task003 原生返回数（历史） |
| --- | --- | --- | ---: |
| 初始化邻域 | src/frontend.py:127–140 | 1/0/1 | 8 |
| 初始化邻近边 | src/frontend.py:141–148 | 1/1/1 | 8 |
| 初始化第二段 | src/frontend.py:173–188 | 1/1/1 | 8 |
| 主循环，候选插入后、保留判定前 | src/frontend.py:56–79 | 组别 D/W/U，三个 update 循环 | 609 |
| 主循环，候选保留后 | src/frontend.py:86–111 | 组别 D/W/U，两个 update 循环；启用 loop 才可到未接入的备用路径 | 148 |
| Online Global BA/Loop | src/tracker.py:120–130、src/frontend.py:88–99 | 冻结配置关闭 | 0 |
| Final BA 1 | src/slam.py:128–137、src/backend.py:42–85 | 0/1/0 | 7 |
| Final BA 2 | src/slam.py:139–143、src/backend.py:42–85 | 0/1/0 | 12 |
| Filler pose-only | src/trajectory_filler.py:43–99 | 0（仅 pose，未使用深度项）/1/0 | 372 |
| 最终导出 | src/slam.py:145–235 及 src/utils/eval_traj.py 的补位与导出链 | 无因子改写 | — |

历史计数仅验证分类覆盖，未来运行次数可随关键帧选择而变。Final BA 原生阶段号为外层 7 和 12，不与各次 native BA 内层 iterations 混用。

## 执行与认定

1. Motion Filter 不插入候选、前端未执行更新时，没有局部调用，没有计数。
2. 插入后先运行 predecision 优化。在配置的保留判断处，若候选被删除，前三次已经返回的 BA 依然记录，并按决策日志标明该候选被剔除；不把被拒绝的候选算作保留关键帧，也不丢弃实际已执行的 BA。
3. 候选被保留才继续 retained 优化。源代码仍用原始距离阈值、强制规则和窗口；不锁定历史关键帧 ID。
4. 将 ba_before 与同进程同 ba_id 的 ba_after_native 配对才纳入执行统计。未返回的调用保留为中断证据，不能计为成功；clamp 缺失单列。把相同 RGB ID 在事件中的槽位重新对应，区分临时候选、正式关键帧和补位槽。
5. 同一调用前后的位移变化只作机制诊断。跨组比较固定 RGB ID 和已有关键帧对；前端末端点丢失时按 [指标合同](TASK004_METRIC_AND_STATISTICS_PLAN.md) 记录。把下游状态改变与下游开关改变区分，原生 Final BA 和 Filler 在主矩阵仍按原规则消费传入状态。

## 隔离核验

候选传参：src/frontend.py 显式标签 → src/factor_graph.py 的 update keyword → src/depth_video.py 的 local_flags。因为 loop=false，未把 loop 的 fallback 映射到主矩阵。CPU Mock 校验初始化和非目标控制调用、候选未插入、拒绝与保留路径、失败无返回、E0 实参及 clamping；分别验证实际操作点与观察状态。候选 F0/F1 改动只属于单独的 E5-F campaign；对 factorial 固定 final_phases=2。

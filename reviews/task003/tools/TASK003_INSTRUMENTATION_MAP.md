# Task 003 埋点与证据边界

以下行号对应**未加埋点的冻结源码**。`evidence/PATCH_VERIFICATION.json` 记录每个插入锚点、文件前后 SHA 和 AST 对照，`TASK003_INSTRUMENTATION_PATCH.diff` 给出完整可审查差异。32 处插入是额外调用，8 个文件另加 observer import；查询不回写算法张量或配置。仅候选副本允许应用。

| 位置与函数 | 插入锚点（原行号） | 捕获内容、形状与设备 |
| --- | --- | --- |
| `src/tracker.py` · `Tracker.run` | 58、67、69、121 | 已生效配置、原始输入序号、本帧最终关键帧决策与初始化标记、在线全局 BA 分支见证。标量来自 Python / CPU；保留槽位的 timestamp 与 `[7]` 位姿从 GPU 读回。Line 121 只在在线 BA 分支到达时记录。 |
| `src/motion_filter.py` · `MotionFilter.track` | 80、97、110 | 第 1 帧显式单位位姿与单位视差；后续候选取当前槽位。记录插入前原始 `delta` 的 CPU 流幅值代理、门限、强制标记、插入后 `[7]` W2C、`[45,80]` disparity／mono prior 和预测深度的有限值、正值比例与分位数。保留动作从实际控制流确认；代理不替代实际判定。 |
| `src/frontend.py` · `Frontend.__update` | 71、77、95、107 | 本地 BA 的 predecision、loop fallback 和 retained 标签，原有距离 `[1]` 与两个相邻槽位。Loop 在 R2 关闭；保留该埋点以便检测异常路径。 |
| `src/frontend.py` · `Frontend.__initialize` | 130、138、145、171 | 初始化开始／第一阶段结束的 `[N,7]` 位姿；邻域与邻近图各实际外层更新通过共享 BA 埋点捕获。 |
| `src/frontend.py` · `Frontend.initialize_second_stage` | 175、184、212 | 第二阶段开始／结束和每次外层更新上下文。 |
| `src/slam.py` · `SLAM.backend` | 131 前、137 前后、139 前后 | 最终 BA 入口、阶段 1／2 各自入口和出口的 anchor `[N,7]`，及深度先验启用状态。保留原 7、12 个请求外层更新；实际次数由 trace 验证。 |
| `src/factor_graph.py` · `FactorGraph.update_lowmem` | 331 | 记录实际外层更新编号和所属 phase；下一次原生调用仍按 `Backend.backend_ba` 的 `itrs=2` 执行。无有效 edge 时可能不进入外层循环，不能用预期次数填充 CSV。 |
| `src/depth_video.py` · `DepthVideo.ba` | 347 前、378 前后 | 原生 BA 入口、返回时及上游 clamp 后。Pose `[N,7]`、边 `(ii,jj)`、范围 `[t0,t1)`、参数与 UBA/U 更新开关；disp/U `[N,45,80]` 按网格抽样；权重/targets 视图 `[E,2,45,80]` 取抽样；K `[4]`（1/8 网格坐标）。深度正则启用时记录实际 depth-slot 集合与 `mono_disps > 0` 支持。 |
| `src/trajectory_filler.py` · `PoseTrajectoryFiller.__fill` | 78 后、92 前后、95 前 | N 个 anchors 与 M 个临时槽位，插值 bracket 和 `[M,7]` 初始值，每批 12 次已有外层 pose-only 更新、批输出。源侧 UBA 仍启用、目标侧关闭、U 不更新；joint depth 分支不参与目标。 |
| `src/utils/eval_traj.py` · `full_traj_fill` | 150 后 | CPU `[487,4,4]` C2W、实际 anchor RGB ID，位于最终关键帧重插后、位姿文本导出前。记录观察开销；实际导出还须核验 runner 的终态、轨迹文件和哈希。 |

- GPU 张量只读经 `detach().cpu()`，由 CPU 计算摘要；这会同步并增加延时，可能影响在线可视化的更新节奏。事件提供 `capture_and_summary_ns`、`copy_to_cpu_ns` 与总 I/O；本次没有实测开销。JSONL 上限 384 MiB，超限会停止并应保存已有日志。没有记录完整特征图、相关体、Schur 矩阵或 CUDA 迭代内的 Jacobian／求解量。
- 原始变量与重建结果分开。Pose、原生调用参数、逻辑分支和计数直接取自现有状态。几何残差和有效权重由采样数据在 CPU 重建：每调用最多 24 条确定性选边，优先覆盖六个诊断帧，像素网格每隔 4 个低分辨率位置取样。结果标记 `CPU_RECONSTRUCTION`；它们是调用边界代理量，不是所有 native 内层迭代的残差、代价或贡献精确分解。
- `event` 确认时间序列；`ba_id` 连接 `ba_before`、`ba_after_native` 和 `ba_after_clamp`。`rgb_id` 原始帧号不能代替槽位 `slot` 与 `pool`：候选被拒后同一槽位会复用，Filler 可为 anchor 的 RGB ID 分配另一个临时 pose。`filler_batch` 和 `outer_iteration` 区分组与轮。正负视差变化须核对采样覆盖和 clamp 前后；没有观测时不可记为零。
- `enable_online_ba=false` / `enable_loop=false` 是经核验的配置；本次未执行任何阶段。源侧 UBA 与 U 更新是不同实参：最终 BA 由 `src/slam.py:137` 和 `:139` 传入 UBA 开关，`src/backend.py:70` 使用 `enable_update_uncer=False` 默认值。`SLAM.backend` 两阶段暂时禁用 Metric3D 正则再恢复；恢复 flag 不意味着 pose-only Filler 会使用深度目标。
- 待实际 trace 时，每条轨迹用自己完整导出的轨迹拟合一次全局 Sim(3)，固定到所有阶段和区间。在 W2C→C2W 转换后，用同一状态中的两个 pose 评估位移、方向和相对旋转，勿将不同关键帧接受时刻的 pose 当作同时快照。F→F / F→K 的前端精确端点可能不存在，须写 `UNAVAILABLE_AT_STAGE`，可单独列相邻 anchor；不同 Filler 批次或临时和原生位姿应明确来源。以 BA 前后同一 ID／槽位的位姿分别报告平移 (norm) 与相对旋转 (deg)。无最终导出时只报告本尺度下能确认的更新，不能另拟局部尺度补数。

`tools/process_runtime.py` 仅在本机把观察 JSONL 转为证据表，保留原始 JSONL 供复核。原始导出矩阵留在 JSONL；六张 CSV 保留用于定位的 ID、状态、pose 和摘要。程序报告合法前缀、实际事件数、BA 返回数和 SHA；有终态记录也不等于进程退出 0 或所有阶段覆盖完整。

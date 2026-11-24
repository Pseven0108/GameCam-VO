# Task004A：干预范围复核

**当前八组的估计对象是 `TOTAL_FRONTEND_EFFECT`。** D、W、U 只在主循环的两个局部 BA 调用处被替换；这两处的输出可以改变本次及后续关键帧、图状态和优化输入。所以比较的是整条流水线对前端干预的响应，不能据此报告 `CONTROLLED_DIRECT_BA_EFFECT`。

| 调用位置 | 实际顺序 | 对本次及后续状态的可能影响 |
| --- | --- | --- |
| `frontend_local_predecision` | 先添加/回收边，再执行 `iters1` 次 `graph.update()`；随后调用 `video.distance()`，结合距离阈值、连续丢弃上限、强制保留条件选择是否移除新候选 | 位姿和视差变化可以改变运动距离以及本次保留决策。即使候选被移除，之前 BA 对共享状态的更新也已经发生；后续图、权重状态和姿态可以不同。 |
| `frontend_local_retained` | 在接受分支、不开启 Loop 的锁定配置下执行 `iters2` 次 `graph.update()` | 不会改变**已经执行的本次**去留决策；之后准备下一候选的位姿、视差及 U，因而可影响后续的分支和图。 |

调用链：`frontend.py:67–87, 104–126` → `factor_graph.py:238–281` → `depth_video.py:349–383` → `droid_backends.ba()`。`depth_video.py:258–287` 的 `distance()` 使用当前位姿、视差和内参，双向距离取平均。`task004_controls.py:56–68` 对两个阶段采用同一 arm 策略，核对阶段标记、原始运行条件、非 `motion_only` 以及 Loop 关闭。上述源码均在上一轮 `assets/candidates/` 下，模型本轮未执行。

| 因子 | 两阶段的实际开关 | 应如何验证 |
| --- | --- | --- |
| D | `mono_disps` 与 `zeros` 两个原生入参分支；不改全局 `metric_depth_reg`，不取消 Metric3D 推理、缓存或 eta 阻尼 | 核对 `metric_depth_prior_selected`、`metric_depth_branch_active` 和实际 `metric_depth_positive_support`；即使选择了先验，支持点为零也要如实记录。 |
| W | `enable_udba`：源端 UBA；目标端双向门控在锁定配置下关闭 | 核对 `source_uba`，同时核对 `target_uba=false`。 |
| U | `enable_update_uncer`：该调用更新 U 的控制；保留缓存、特征和原更新初始化流程 | 核对 `update_u`。冻结这里的更新不等于整个系统的 U 恒定。 |

D/W/U 对初始化、最终 BA 两阶段及 Filler **没有直接改开关**，但前端传下去的场景状态可能改变。前端接受逻辑保持自然执行；不得固定去留或根据结果筛出共同关键帧再宣称消除了选择偏差。E0 是计划中的新实验组，历史 Task003 只用作审查与背景对照。

**本地真实记录复算。** `DROID_W_TASK003_VAL007_OBSERVATION_R1/remote/capture/observer.jsonl` 中，两个局部阶段各有 609 和 148 次完整的 before/native-after/clamp-after 调用，总计 757 次，决策前占 **80.45%**。其中 387 次属于最后被局部判断拒绝的候选（129 个候选帧）；另有 272 个 RGB 在进入该局部判断前就被运动筛选拒绝。后启用主循环的原生距离共 203 次，其中 74 保留、129 拒绝。另 12 个候选进入初始化（其中 11 个事件记 `RETAINED_WARMUP_PENDING`，完成初始化的一个记 `RETAINED`）。共保留 86 个关键帧，封存 487 个导出位姿。RGB312/328 同时位于优化窗口并被图边观测的第一个局部 BA 是决策前的 `ba_id=552`，事件 2600/2601/2602。该事实确定观测发生位置，不能从调用占比推断位姿误差的因果贡献。

保留 `E3 → E4 → E7 → E0 → E8 → E6 → E1 → E2`、487 帧、640×360、stride=1、buffer=500、seed=43、原始 R2 内参与权重、Final BA、Filler 和原生 Rerun。八份策略文件本轮重新与 `assets/TASK004_FACTORIAL_MATRIX.csv` 的 SHA-256 比对。`TASK004A_ARM_PHASE_STATISTICS.csv` 记录八组各两条预期策略，正式观测字段为空、状态 `NOT_RUN`。

证据入口：`TASK004A_LOCAL_EVIDENCE.json` 中的 `historical_task003_trace` 给出历史实际分布、调用数、最终关键帧 ID；`TASK004A_PHASE_EFFECT_INTERPRETATION.md` 给出将来应填的统计合同。源码、观察器和运行器均保持原样。

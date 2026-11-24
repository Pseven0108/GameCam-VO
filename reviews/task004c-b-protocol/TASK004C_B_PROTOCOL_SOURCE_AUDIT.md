# Task004C-B：源码只读审计

日期：2026-11-24（北京时间）。本轮未连接服务器、未导入 PyTorch、未初始化 CUDA、未运行模型或 BA。

## 审计对象和证据身份

冻结目标 c3414af6047d06bafc1a6645d09f23247f3b2cdc。执行副本采用已保存的 Task004B/Task003 观测代码；原始算法和 CUDA 扩展均不修改。source_evidence/execution 是执行源码证据，source_evidence/frozen 是从历史官方源码树逐 Blob 核对的补充文件。8份补充文件 Blob 均匹配官方树；前5份还匹配上一轮远端冻结源码 SHA。不得把项目父目录 Git HEAD 当成 DROID-W HEAD。本轮一度尝试在无独立 .git 的源码副本上 git show，未取到文件；已改用保存的官方树和文件 Blob 核验，未切换或修改任何仓库。详见 evidence/EXTRA_SOURCE_IDENTITY.json。

## 实际初始化链与 C0 边界

1. 执行 src/slam.py:286–306 采用 spawn；Tracker 真正创建于 tracking 子进程（91–108）。父进程没有 Tracker.run 的局部变量和 MotionFilter 隐状态，不能只保存父进程 SLAM。
2. src/tracker.py:62–73：stream[i] → MotionFilter.track → Frontend.__call__。Frontend 在 counter==warmup==12 时进入第一阶段（frontend.py:226–237）。
3. frontend.py:132–180：邻域图8次 graph.update，加 proximity 图8次 graph.update；设置下一槽位的 Pose/disparity/U、is_initialized、last_pose/last_disp/last_time，并转存旧边。每次 graph.update 默认调用原生 BA 的2次内部迭代。
4. 这仍不是完整初始化结束。tracker.py:113–122 在同一输入帧检测 warmup，再调用 initialize_second_stage；frontend.py:182–224 还有8次 graph.update、边龄回调、下一槽位、last_* 和旧边清理。
5. 共同检查点必须在 tracker.py:144–145 完成本帧收尾后、62–63 下一次 stream[i] 之前建立；所有本帧分支、有效深度掩码、初始化第二阶段和可视化共享写入均已停稳。只钩 frontend_init_first_done 不够；只钩 frontend_init_second_done 也未覆盖 Tracker 本帧局部变量收尾。
6. 历史初始化结束于 RGB018，12个初始化ID为 [1,4,6,8,10,11,12,13,14,15,16,18]；这是历史观察。新 C0 必须按语义门槛触发并记录真实 last_rgb/next_index，不能硬编码“到18就停”。如果实际边界不同于18，应停止提交差异，不能跳过输入或伪造19为下一帧。

## D 是否参与初始化

**是，CONFIRMED_SOURCE。** 三段初始化 graph.update 均没有 task004_phase 标记；task004_controls.py:56–68 对 phase=None 返回 video.metric_depth_reg，原始 R2 为 true。depth_video.py:350–384 因而选择 mono_disps；不是历史 E1 的局部 D=0 就意味着初始化 D=0。

本协议采用共同 INIT_D=0：仅在上述24次初始化 BA 输入选择中传入原生 zeros 分支，保持 Metric3D/DINO 推理、深度结果保存、U生成和原始初始化 W 模式。第一段邻域初始化 W=false，后两段 W=true，U按原始模板更新；不能把“后续 W=U=1”误写成强制所有初始化 BA 的 W=true。

共同 D=0 是本协议明确的新初始条件，不能把历史 E1 初始化或 RGB328 的原生调用快照冒充它。保留原始 R2 YAML 的字节和 SHA；未来只允许在独立、另行审查的执行层选择参数，不改模型/BA公式。现有 local_flags 不提供该初始化覆盖及恢复入口，**本轮不实现覆盖**。研究估计对象为初始化之后的 D 效应，不包括初始化 D 的总效应。

## 首次分叉与离散决策入口

| 入口 | 源码位置 | 协议要求 |
|---|---|---|
| Motion Filter 门槛 | frozen/src/motion_filter.py:63–115 | 在97行分支之前固定 admission，不能改函数返回值充当 admission。返回值实际是 force_to_add_keyframe；接纳分支会修改 net/inp/fmap、count并调用 video.append。 |
| 候选插入 | motion_filter.py:99–110；depth_video.py:112–145 | 固定候选事件、插槽和RGB身份，但网络特征由当前分支正常计算。即使候选随后被删，MotionFilter 的最新候选隐状态也不能回滚成最后保留关键帧。 |
| Predecision BA | execution/src/frontend.py:57–80 | 3次 graph.update，每次2个原生内部迭代；窗口、边顺序和调用序列冻结，残差/target/weight/eta 正常重新生成。 |
| Local accept/drop | frontend.py:79–115 | 固定距离门槛、连续丢弃上限和force_flag共同决定的离散分支；native BA 没有独立“优化接受”返回值，日志中的接受指关键帧判决，不捏造solver成功标准。 |
| Retained BA | frontend.py:105–115 | 仅保留分支再执行2次更新；强制保留后必须执行，不能只在最终ID列表补一帧。 |
| 删帧与重排 | factor_graph.py:190–232 | 原生 rm_keyframe 复制缓冲内容并重排活跃/非活跃边；保留原生副作用，不顺手修复未复制字段。 |
| 增删图边 | factor_graph.py:114–187,428–488 | proximity按当前几何距离、NMS、排序和边上限筛选；记录实际请求、去重结果、容量驱逐和store标志。仅最终ii/jj不够。 |
| Graph update | factor_graph.py:237–285 | graph.net/inp/corr/damping/target/weight、inactive support与age都是运行状态；最后age+=1也要记录。 |

历史 RGB021 的决策差异不能证明初始化差异由 D 导致：历史初始化 Pose 已不同，且全状态哈希不存在。

## 最终 BA 与 Filler 也有离散图

- slam.py:129–151：最终 BA 先临时关闭深度正则，分别 dense_ba(7)、dense_ba(12)，之后恢复 metric_depth_reg。保持此原生流程，不把局部 D 扩散到最终 BA。
- frozen/src/backend.py:48–90：每个最终阶段创建新的 AltCorr 图，按当前 Pose 再建边。若只冻结前端关键帧而让这里自由建图，就不能声称“同一Schedule全过程图结构相同”。本协议选择完整离散调度：记录并交叉约束这两次建图、edge顺序、非空分支和BA窗口/步数；数值计算及2个原生内部迭代不变。
- frozen/src/trajectory_filler.py:42–97,116–137：按16帧批次临时追加（N+M<=500）、选t0/t1锚点、插入两组边、12次 motion_only graph.update，再回退counter。固定批次、锚点、临时槽位和边序，插值与优化数值由当前分支自己算。它会对输入中的关键帧也产生重新插入的估计，最终全帧Pose不能自动归类为直接关键帧Pose。
- R2 enable_loop=false、enable_online_ba=false、mapping.enable=false。恢复后必须仍为false；若出现这些额外阶段，立即停，不按“新自动事件”悄悄继续。

## 生命周期与已确认缺口

18份 Python 证据静态解析得到303处 self 属性写入位置；这是定位清单，不是运行时对象完整性证明。参见 SOURCE_MUTABLE_ATTRIBUTE_INVENTORY.json。

C0必须另存 Tracker.run 的 prev_kf_idx/curr_kf_idx/prev_ba_idx、下一输入游标，以及MotionFilter状态、Graph相关金字塔、网络buffer/模式、实际tracking子进程完整RNG。当前seed_receipt只保存RNG摘要，不是可恢复RNG。Rerun还会写video.dirty（保存的可视化源码116–127行），因此仅持video锁不能保证它不再写；需要显式读者/写者屏障和确认。

**结论：边界可按源码定义；现有证据不能构成完整C0；现有runner不支持完整前端恢复或强制事件重放。没有发现必须改BA公式的理由，但需要另行批准实现独立保存/恢复和调度门控。现在不具备四组运行准入。**

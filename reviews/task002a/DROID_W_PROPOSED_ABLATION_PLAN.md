# Task 002A｜DROID-W 严格消融设计（待审批）

**建议（INFERRED）：** 先把直接深度先验与 UBA 做成两个可核对的因素，再单独检验 U 更新。优先做同状态对照，确认开关只作用于指定入口，然后才衡量整段轨迹的累积效应。所有候选均为设计，**UNVERIFIED：未实现、未运行、无消融结果**。

## 1. 对照基准与共同条件

**CONFIRMED：** E0 使用 [正式 R2 有效配置](/D:/aaa/GameCam-VO/experiments/DROID_W_TASK002A_ABLATION_SWITCH_DEPENDENCY_AUDIT/DROID_W_R2_CONFIG_VERIFICATION.md)。对应 DROID-W `c3414af6047d06bafc1a6645d09f23247f3b2cdc`、92 个冻结片段、47 条序列、49,815 输入帧，`stride=1`，640×360；每个片段使用自己的冻结 K 与 RGB 顺序。正式 R2 的 DROID-W 结果沿用已封存的 R1 运行。`stride=4` 结果排除，历史 E0 保留。保留 `gamma_depth=0.01`、两个 U `activate=true`、`enable_affine_transform=true`、`enable_opt_dyn_mask=true`、`enable_bidirectional_uncer=false`、`mapping.enable=false`、`normalize=false`、在线 BA/回环关闭、Final BA 默认开启。R2 不做 filler 的 FiT3D 前向，filler 原有 UBA 开启。

**INFERRED（冻结要求）：** 若后续获批，先用统一实验入口做一组不改变行为的 E0 对照。锁定源码、依赖/扩展、权重、初始仿射权重和随机种子、输入和 K、缓冲区、可视化/进程配置、结束流程以及评价口径。任何无法匹配的项都应记录；不能把入口变化、精度变化、新权重或 `stride=4` 结果混入效果量。GT 仅给离线评价，运行入口仍只读已批准的 RGB 输入合同。

## 2. E0–E5 矩阵

| 组 | 唯一预定干预／对照 | 保留条件及解释边界 | 只改现有设置可行性 |
| --- | --- | --- | --- |
| **E0 原始 DROID-W** | 无，复用历史配置和输入身份作对照；新入口需先确认其无干预路径 | 紧邻各实验组保留同一 runner、调度与采样；历史输出本身不重写 | **CONFIRMED**：已有完整配置和回执。**UNVERIFIED**：未在新入口复验 |
| **E1 无直接 Metric3D BA 约束** | `tracking.backend.metric_depth_reg=false`，保留 `gamma_depth=0.01` | Metric3D 构造、前向、mono 缓存和归档保留；前端 joint BA 的正 prior 分支改成无 prior 的 `eta` 分支。Final 本已没有直接约束，仍可能承接不同起点。mapping 保持关闭 | **CONFIRMED**：上游有此配置；[冻结 runner](/D:/aaa/GameCam-VO/experiments/DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/pipeline/run_segment.py:197) 拒绝，需独立 runner，求解器不用改 |
| **E2 无 UBA 几何附加权重** | 把原本为 `true` 的 `enable_udba` 在**局部跟踪、Final、filler** 都改为 `false`；原本为 `false` 的暖机首段不变。未来若开放在线/回环，须另行定义其范围 | `enable_update_uncer` 原有调度和初始化不变；Final、filler 原本就不更新 U。保留 FiT3D、现行 U 优化核、learned weight、Metric3D 和投影有效性条件。轨迹反馈可引起 U 数值变化 | **CONFIRMED**：求解器实参可独立；完整 R2 无独立 YAML，硬编码 filler 也需传参。**INFERRED**：用隔离调度适配层，不更改 CUDA 数学 |
| **E3 无 native U 更新** | 在前端各段将 `enable_update_uncer=false`；Final/filler 已是 `false`。在每段保留 E0 的 `enable_udba` | 保留生产 U 所需的特征、缓存和**同一初始仿射投影**；暖机第一段也不学习。整段试验使用初始仿射参数为新帧生成 U，允许复制/插值；同状态试验复制 E0 采样时刻的 U 和仿射状态，之后禁用 native 更新。这是两个不同估计对象，不混合报告 | **CONFIRMED**：独立 native 参数存在；没有独立 YAML。**INFERRED**：禁止将 U 填成 1、`activate=false` 或 `lr=0` 作为替代 |
| **E4 无直接 Metric3D BA 约束且无 UBA** | E1 与 E2 精确组合；U 更新保留 | 与 E0/E1/E2 构成深度先验方案 × UBA 的 2×2 对照。允许两因素交互，E4 不作为单因素结论 | **INFERRED**：同时需要 E1 runner 放行和 E2 实参适配 |
| **E5-F Final BA 阶段** | 在同一跟踪终点分叉：一组执行 7+12 外层 Final BA，一组跳过。两组从各自末端状态运行相同 filler 与导出 | 局部 BA 相同；mapping 与在线/回环均关。分别报告关键帧 pre/post 和经过相同补位协议的全帧轨迹，记录实际边数与内外层次数 | **CONFIRMED**：上游有 `final_ba`。冻结 runner 拒绝 `false` 且只在 `backend()` 返回后把 phase 改为 filler；需让新入口观测真正的 filler 入口，不能仅放行布尔值 |
| **E5-L 局部 BA 阶段** | 另从同一已初始化的状态分叉，比较一次指定局部更新前后；如需仅隔离几何求解，固定同一图/目标/权重/阻尼并保留其余调度 | 暖机和整段跟踪都依赖局部 BA；直接关闭局部 BA 会改变图构建、选帧和初始化，不能把该结果解读为「最终 BA 的反面」 | **CONFIRMED**：无 standalone YAML；**INFERRED**：需要独立状态对照工具或隔离 wrapper。不是首批整段必跑项 |

> **CONFIRMED：** `enable_opt_dyn_mask=false` 混合 E2/E3 的前端干预，还留下 filler UBA，不能打 E2 或 E3 标签。`enable_bidirectional_uncer=false` 已是 E0，仅关目标端权重。`lr=0` 仍可能因仿射 `weight_decay` 与重算 U 改变状态，不能声明停 U 更新（`src/lib/droid_kernels.cu:1941–1959`）。`gamma_depth=0` 不恢复正 prior 像素的 `eta`，也不替代 E1（`src/lib/droid_kernels.cu:1876–1882`）。

## 3. 同状态求解与全轨迹是两类证据

1. **INFERRED（同状态）：** 在获批后，选择预先声明的阶段，例如 `val_007` 一次已启用 UBA 的前端更新。两组从同一 `poses`、`disps`、`mono_disps`、U、FiT3D 特征、仿射参数、K、图 `ii/jj`、`Target`、原始 `Weight`、`eta` 与 `lm/ep` 启动。确认实际参数与起点哈希；先观察一轮内层，再观察后续内层，分离直接几何权重效应与下一步 U 反馈。E3 在这一轮先看 U/affine 写回；若第一步从相同 U 开始，第一步几何方程不因关闭 U 更新就自动不同。E1 同时记录深度方程 prior 残差与 `eta` 的分支替换；不得把它解释成固定 Hessian 上只改 RHS。E5-F 对照要有跟踪结束的真实状态，历史 Final 后的 `video.npz` 不能充当该状态。
2. **INFERRED（全轨迹）：** 允许候选通过、位姿、视差、U 和边随处理演化，记录每阶段的触发与实际布尔对、RGB/补位覆盖、关键帧接受/丢弃、成功/失败、轨迹尺度和正式 R2 离线指标。比较同一冻结片段；报告配对覆盖与失败，不能只保留两组都成功的片段而忽略失败数。把 E2 的整段干预理解为各阶段的合计效果；如需分辨贡献，再预先登记仅局部、仅 Final 或仅 filler 关闭 UBA 的对照，其余阶段固定。E3 的保持初始化并停更新，与回放某时刻的历史 U 不是同一问题。
3. **INFERRED（交互）：** 对共同有效的配对片段，注明指标方向并报告 `E0 − E1 − E2 + E4`，以及各单因素差值。若无法取得同状态快照或某臂无法完成，保留失败及原因，不以另一套配置填补。
4. **UNVERIFIED（准入）：** 没有运行这些组合，没有数值或轨迹结论；将来需记录每次 native 调用的阶段、两项布尔值、是否选择正深度 prior、是否执行 filler 和输出完整性。先审方案，再批准新代码或 GPU 运行。

## 4. 彻底停止网络计算：另设工程对照

- **Metric3D（CONFIRMED：无现成开关）。** **INFERRED（最小设计）：** 在独立入口增加明确的 estimator 模式，使 `MotionFilter.__init__` 可跳过构造、首帧及候选分支可跳过预测；保持 `DepthVideo` 张量契约并显式置空或清零相应 prior 槽，要求 mapping 和深度落盘关闭或另有合法输入。要单独估计计算开销，使用 E1 的 no-prior 对照，比较都不使用深度先验时是否运行 Metric3D；如需保留原 BA 深度约束，只能使用同输入、同权重、同数值精度的已验证缓存做回放，不能把换成无深度说成只省算力。
- **FiT3D/DINO（CONFIRMED：没有能安全关掉全流程前向的配置）。** **INFERRED（最小设计）：** 将 extractor 构造及预测拆成明确的 live / verified-cache / disabled 三态。仅测开销时，用一致的、经逐帧哈希和数值核验的特征回放，保留 U 数据流，同时避免 [filler setup](/D:/aaa/GameCam-VO/experiments/DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1/sources/DROID-W/src/trajectory_filler.py:33) 再建模型。完全去掉特征信息时，要另外定义 U 初始化/更新、filler 和归档兼容性，且标清 U 学习机制同时变更。不能让缺失属性、特征全零或假造 U 担任等价对照。当前没有证明可复用的逐帧特征缓存完整。
- **适配层（INFERRED）：** 在未来独立实验入口为各阶段显式指定 `update_uncer` 与 `udba`，开放必要的 E1/E5 配置，并把日志挂到实际阶段入口；先验证无干预 E0。保持冻结源码、历史配置、权重、协议与产物原样。此报告没有生成补丁、启动实验或申请 GPU。

源码与开关证据见 [开关矩阵](/D:/aaa/GameCam-VO/experiments/DROID_W_TASK002A_ABLATION_SWITCH_DEPENDENCY_AUDIT/DROID_W_ABLATION_SWITCH_MATRIX.md)、[依赖图](/D:/aaa/GameCam-VO/experiments/DROID_W_TASK002A_ABLATION_SWITCH_DEPENDENCY_AUDIT/DROID_W_MODULE_DEPENDENCY_GRAPH.md)、[BA 阶段报告](/D:/aaa/GameCam-VO/experiments/DROID_W_TASK002A_ABLATION_SWITCH_DEPENDENCY_AUDIT/DROID_W_BA_STAGE_CONTROL_REPORT.md)。本阶段到此，等待人工审批。

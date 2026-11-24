# Trajectory Filler｜冻结源码、运行配置和导出差异

本审计以已经封存的实际运行版本为准：DROID-SLAM `2dfd39f0dcad44012ca7bbb8aa70b55edbfa9c99`、DROID-W `c3414af6047d06bafc1a6645d09f23247f3b2cdc`。源码取自本地 `DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1/sources/`，核验关键文件的 Git blob 字节和 Task 001 的 `SOURCE_ENTRY_VERIFICATION.csv`。另核验两份运行器（R2 ZIP 原字节、R1 已锁 SHA）；路径、散列、行号见 `evidence/SOURCE_PROVENANCE.csv` 与 `evidence/FILLER_SOURCE_EXCERPTS.txt`。

`CONFIRMED` 表示冻结源码和/或运行回执可直接核实；`INFERRED` 是由控制流判断在这些配置下应发生的行为；`UNVERIFIED` 表示封存材料没有中间数据，未实跑作证。输入像素核对沿用 Task 002B 的已有结论，本轮不读 RGB。

| 项目 | 原始 DROID-SLAM | DROID-W | 实质差异及证据等级 |
|---|---|---|---|
| 输入帧 | `trajectory_filler.py:42–49,87–110` 遍历 `(tstamp,image,K)`，按 16 个批处理，可处理当前已是关键帧的时间戳；转换 BGR→RGB 再除以 255，执行 DROID `fnet`。 | `src/trajectory_filler.py:42–51,72–78,115–142` 遍历全部 stream 帧，用 `get_intrinsic()` 的固定 K，公共 DROID encoder 使用已为 RGB 的流，归一化后调用 `fnet`。 | **CONFIRMED**：两边使用完整 stream、临时缓存 E 步，均把入口内参除以 8 存入对应特征层缓存；运行中逐个 W Filler encoder 输入张量未封存。 |
| 锚点与时序 | `droid.py:71–85` 先执行 `backend(7)`、`backend(12)`，再调用 Filler。`trajectory_filler.py:50–65` 从 buffer 读保留关键帧。 | `src/slam.py:127–151,174–179,217–227` 的顺序为 tracking 结束、可选预诊断、最终 BA、Filler、导出。最终 BA 暂时关闭 Metric3D 深度正则，运行两阶段再恢复。 | **CONFIRMED**：Filler 使用最终 BA 的锚点。92 份 W 配置均 `final_ba=true`、`eval_before_final_ba=false`。W `keyframes.json` 是 tracking 后记录的保留 ID，未保存当时的 pose（R1 `run_segment.py:155–165`）。 |
| SE(3) 插值 | `trajectory_filler.py:50–65` 取最后一个 `ts≤t` 锚点 `t0` 和其后 `t1`，末尾无后锚点时取同一个；`exp((t−t0)/(t1−t0+1e−3) · log(P1 P0⁻¹))P0`。 | `src/trajectory_filler.py:53–70` 同样的构造、顺序和 `1e−3` 分母保护。 | **CONFIRMED**：姿态用 SE(3) 对数和指数，不是直接对轨迹位置逐项线性混合；同公式不代表插值相同，锚点身份和质量都不同。 |
| 深度/视差 | `trajectory_filler.py:71–79` 临时帧视差初始化为 1，不输入深度图。几何重投影仍使用缓存视差；`src/droid_kernels.cu:1394–1402` `motion_only` 不执行联合深度求解。 | `src/trajectory_filler.py:76–92,130–137` 在实际调用中传入 `depths=None`，临时视差也为 1；`src/depth_video.py:332–378` 把缓存视差传给 BA，`src/lib/droid_kernels.cu:1867–1881` 的 `motion_only` 分支跳过联合深度求解。 | **CONFIRMED**：没有独立非关键帧深度插值或每帧 Metric3D 预测接入。已有锚点视差仍影响几何；两模型包装层仍有视差下限裁剪（SLAM `depth_video.py:213–225`，W `src/depth_video.py:378`），不得称深度缓存完全不被写。两模型锚点深度的差异无法由最终轨迹反推。 |
| FiT3D/DINO | 有 DROID 特征与对应更新，没有 W 的独立不确定性特征提取门控。 | `src/slam.py:206,220` 调用 extractor setup；`src/trajectory_filler.py:31–35` 按 `activate` 调工厂，`115–129` 必须同时 `use_dino_features=true` 才预测 Filler 帧特征。工厂可能选择 FiT3D/DINOv2 等（`src/utils/mono_priors/img_feature_extractors.py:68–85`）。 | **CONFIRMED**：92 份本轮 W 配置均 `activate=true`、`traj_filler.use_dino_features=false`；因此 Filler 的逐帧 DINO/FiT3D 预测分支关闭，不能推导 extractor 初始化也关闭或 tracking 不再抽特征。具体 Filler 模型工厂的初始化耗时未封存。 |
| 不确定性 U | FactorGraph 的 DROID 对应权重。没有上述 W 单独插值的 U 缓存与 UDBA。 | `src/trajectory_filler.py:80–92` 先按两锚点插值 U，再把 `enable_udba=True` 和 `enable_update_uncer=False` 传给 pose-only BA。`src/factor_graph.py:267–281`、`src/depth_video.py:332–378` 传至 CUDA 内核，`src/lib/droid_kernels.cu:320–335,1915–1920` 区分几何门控和 U 更新。 | **CONFIRMED**：实际配置 `enable_bidirectional_uncer=false`；边 `t0/t1→临时帧` 按源锚点 U 加权，不用目标侧双向门控。即使为临时帧写入插值 U，也不能说此配置把它通过目标端门控用于每条边。**UNVERIFIED**：未获得 U 数值、有效门控强度或对异常的影响。 |
| Pose 更新 | `trajectory_filler.py:74–84` 从附近锚点到临时槽建边，6 次 `graph.update(N,N+M,motion_only=True)`，求解帧窗口是 `[N,N+M)`，然后克隆并缩回计数。 | `src/trajectory_filler.py:86–97` 同形状的边和更新窗口，12 次 `graph.update`，保留 W 特有的权重路径。 | **CONFIRMED**：6/12 是图更新循环次数，不能解释为等量原生线性求解或精度差的原因。在临时窗口优化位姿，锚点 Pose 不在这个求解窗口内。 |
| 输出 | 原版 `terminate` 返回全部 Filler 位姿的 c2w 导出。R2 `pipeline/run_original.py:118–137` 另保存 `keyframe_ba_c2w_xyzw`，便于直接看最终 BA 锚点。 | `src/utils/eval_traj.py:143–160` 先对 Filler 输出取逆生成 c2w，再对最终关键帧时间戳用直接的最终 BA pose 覆盖，最后导出；R1 `pipeline/run_segment.py:214–230` 将这些结果打包并映射 RGB。 | **CONFIRMED**：主时间轴的 K 标签是最终身份，SLAM 的主轨迹同一时刻来自 Filler，W 的来自直接锚点覆盖。对 3,092 个共同 K→K 帧对改用 SLAM 直存锚点，同一对齐下主结论不变。 |

`motion_only` 在此用于临时帧位姿求解；有位姿优化不等同于执行联合 pose–depth BA。锚点质量、已有视差以及权重都可能影响后续 Filler，不能对照更新次数直接进行组件归因。**INFERRED**：已有压缩锚点能够传给插值初值；其影响的方向和幅度要按具体帧从快照核对。

### 封存证据能回答到哪里

- 已有：最终保留关键帧 ID 及索引、最终 c2w、SLAM 直接的后 BA 锚点、实际配置及运行回执。`FRAME_TYPE_MANIFEST.csv` 区分 KEYFRAME、FILLED_FRAME、MISSING、INVALID；不按形状猜帧身份。历史运行成功后清理了临时重型 `native/video.npz`（R1 `pipeline/remote_batch.py:185–189`）。
- **UNVERIFIED（匹配的 stride=1 缺失）**：逐次关键帧接受/删除事件、最终 BA 前的有效锚点 Pose、BA7/BA12 的中间 Pose、Filler 插值初值与覆盖前逐轮 Pose。原始 R2 ZIP 的相应观察快照未发现；`VIPER_VAL007_STAGE_OBSERVABILITY_R2` 是另一条 stride=4 运行。不能把它的记录混进本次统计。
- 用直接锚点复核：固定 K 中 SLAM 的导出/直接锚点位置差中位数 0.000664（已经乘全局尺度），p95 0.00440，最大 0.86721；角度差中位数 0.00476°，最大 0.73906°。在共同 K→K、offset=60 的 592 对中，SLAM 序列平移 RMSE 中位数从 1.678867 变到 1.678958，W 仍为 12.001694。完整不同 offset 与虚拟相机分支见 `MATCHED_KEYFRAME_ANCHOR_SENSITIVITY.csv`。

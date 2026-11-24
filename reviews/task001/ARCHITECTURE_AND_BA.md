# 架构、位姿更新与 BA：正式 stride=1 路径

`S:` 和 `W:` 分别指 `D:\aaa\GameCam-VO\experiments\DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1\sources\DROID-SLAM` 与同级 `DROID-W`。行号对应固定提交 `2dfd39f0dcad…` 和 `c3414af6047d…`。`R2:` 指 `D:\aaa\GameCam-VO\experiments\VIPER_MATCHED_DUAL_BASELINE_R2`。以下 `CONFIRMED` 说明源码确实实现该行为；开关取自正式 `val_007` 的存档配置。源码存在分支不等于有逐次运行记录。

## C–D. 架构对照、计算影响与数据流

| 环节 / 分类 | 原版 DROID-SLAM | DROID-W | 计算影响与适用范围 |
|---|---|---|---|
| 入口 `CONFIRMED` | `R2:pipeline/run_original.py:27–56` 锁定同步 `Droid`；`S:droid_slam/droid.py:61–69` 调度 motion filter 和 frontend。 | `W:src/slam.py:89–111,278–347` 调度跟踪进程；`W:src/tracker.py:44–69` 投递 RGB/K。 | 正式原版无异步后端；W 有进程调度，但其在线全局 BA、loop 和 mapping 在该配置关闭。原生可视化不是这里的 pose 求解分支。 |
| 输入与内参 `CONFIRMED` | `S:droid_slam/motion_filter.py:52–88` 将 BGR 字节转 RGB，再 `/255`、减均值除方差；存储 1/8 网格 K。 | `W:src/motion_filter.py:52–80,97–110` 接收 loader 的 RGB float，调用自身的均值方差归一化，按 `video.down_scale` 保存 K。 | 共同 640×360、固定 K；跟踪/BA 网格为 80×45。输入清单相同不能证明模型内归一化张量或后续特征逐值相同。 |
| 匹配与上下文编码 `CONFIRMED` | `S:droid_slam/droid_net.py:146–169`：128 通道 fnet（instance norm），256 通道 cnet（无 norm），上下文拆分隐状态与输入。 | `W:src/modules/droid_net/droid_net.py:156–161`；`W:src/motion_filter.py:39–64` 保留相同职责，运行模块单独组织。 | DINO 不替换 `fnet` 或 `cnet`。相同 tracker 权重是输入控制之一；初始 pose、图和 GRU 状态仍可不同。 |
| 相关性 `CONFIRMED` | `S:droid_slam/modules/corr.py` 的 `CorrBlock` 与 `AltCorrBlock`，在线和低内存路径分别使用。 | `W:src/modules/droid_net/corr.py:39–90,111–161` 保留图边相关性金字塔和低内存采样。 | 相关性查找围绕当前重投影；相同 RGB 或同名函数不能锁定查找坐标、对应关系和图边。不是新增独立相机平移头。 |
| ConvGRU / 更新头 `CONFIRMED` | `S:droid_slam/droid_net.py:44–143` 的 `GraphAgg` / `UpdateModule.forward`：GRU 更新，预测二维 `delta`、`weight`，按源帧聚合 `eta` 和上采样掩码。 | `W:src/modules/droid_net/droid_net.py:48–153` 有同样职责，`W:src/modules/droid_net/gru.py:19–48` 为运行时 `ConvGRU`。 | `delta` 是投影坐标的修正；`weight` 是两个坐标方向的观测权，不是动态分割标签，也不是直接输出的 SE(3) 平移。 |
| 跟踪候选与关键帧 `CONFIRMED` | `S:droid_slam/motion_filter.py:68–88` 首帧保留、后续按平均 `delta` 模长；`S:droid_slam/droid_frontend.py:65–108` 局部更新后比较 `t1−4/t1−2`，可能移除 `t1−3`。 | `W:src/motion_filter.py:81–112` 增加强制入队选项（正式配置 `−1`）；`W:src/frontend.py:56–110` 比较最新两候选，可能移除 `t1−1`，有连续删除上限。 | 正式原版/W 的 filter 门槛 2.4/3.0，关键帧参数 4.0/3.0，但比较的对象和实际谓词不同。候选即使最终删除，也可能先进入局部 BA 并影响存活关键帧。 |
| 初始状态与局部图 `CONFIRMED` | 首帧传单位位姿、视差 1；`S:droid_slam/droid_frontend.py:49–64,110–155` 暖机 `8+8` 次图更新，后续位置与分位数视差种子。 | 同样首帧单位位姿、视差 1；`W:src/frontend.py:112–169` 用前一帧位姿与均值视差；首批 `8` 次只更新 U、不应用 UBA，之后 `8` 次启用二者。`W:src/tracker.py:109–118` 与 `W:src/frontend.py:173–212` 还有计数门限触发的第二阶段 8 次更新。 | 正式暖机阈值 8/12；图窗口、状态种子和不确定性启用时机不同。W 的 `init_w_mono_disp` 调用行被注释，不能说首帧状态已被 Metric3D 覆盖。 |
| 观测目标与网络权重 `CONFIRMED` | `S:droid_slam/factor_graph.py:215–258`：当前位姿/视差投影，查询相关性，`Target=coords1+delta`，缓存原始 `Weight`、阻尼和可用旧边。 | `W:src/factor_graph.py:236–282` 同样生成目标，额外传递 UBA 和 U 更新开关；`src/factor_graph.py:289–368` 对全局低内存路径亦然。 | 目标生成和 UBA 在不同位置。改 BA 状态后，后续图更新会重投影并可能重新产生目标；不能把最终轨迹差完全分解为三个独立模块的固定偏置。 |
| 逆深度先验 `CONFIRMED` | `S:droid_slam/depth_video.py:78–99,213–225` 支持正传感器视差；正式单目传 `depth=None`。 | `W:src/motion_filter.py:68–80,97–110` 在追加候选时调用 Metric3D；`W:src/utils/mono_priors/metric_depth_estimators.py:118–156` 缩放、填充、恢复深度并用 `cfg[cam][fx]/1000` 换算；`W:src/depth_video.py:127–131` 写入正深度的倒数。 | 该先验依赖 RGB 和输入焦距。正先验在 joint BA 替换对应像素的 `eta` 对角正则并增加深度 RHS；不是外部真值，也不等于当前优化后的逆深度。 |
| FiT3D/DINO 与不确定性 `CONFIRMED` | 无这条在线特征一致性分支；用网络 `Weight`、几何有效性和学习到的 `eta`。 | `W:src/utils/mono_priors/img_feature_extractors.py:16–85,110–176` 提取 `dinov2_reg_small_fine`，`W:src/depth_video.py:145–167` 将特征插值至工作网格，`U=log(1.1+exp(Fa+b))`。`W:src/lib/droid_kernels.cu:1444–1760,1915–1984` 从更新后投影的特征一致性和正则更新 U/仿射。 | `U` 是在线估计的不确定性状态；特征不一致可由错位、遮挡、渲染、真实运动等产生，不能读成真实动态掩码。`enable_bidirectional_uncer=false` 是关闭目标端几何门控，与 U 更新的双端特征梯度不同。 |
| 联合 BA `CONFIRMED` | `S:droid_slam/depth_video.py:213–225` → `S:src/droid.cpp:93–109` → `S:src/droid_kernels.cu:1323–1445`。 | `W:src/depth_video.py:332–378` → `W:src/lib/droid.cpp:118–167` → `W:src/lib/droid_kernels.cu:1763–1997`。 | 共用 SE(3) 位姿、像素逆深度与 Schur 消元骨架。W 先改有效几何行的权，再改深度块；几何回写之后才更新 U。 |
| 最终全局 BA `CONFIRMED` | `S:droid_slam/droid.py:71–85` 结束时 `backend(7)` 和 `backend(12)`；`S:droid_slam/droid_backend.py:24–42` 原版单目无传感器视差时，在每次全局调用前执行尺度归一、重建全局图。 | `W:src/slam.py:128–143,145–183` 临时撤下直接 Metric3D 正则，`dense_ba(7)`/`dense_ba(12)`；`W:src/backend.py:42–95` 新建 graph，先固定起始 pose；正式配置 `normalize=false`。 | 都是两次外层全局更新计划，单次 `update_lowmem` 调用可含两个内部求解。W 保留配置的源端 UBA，最终阶段不更新 U。早期先验仍可通过传入位姿、逆深度和 U 影响它。 |
| 全帧补位与导出 `CONFIRMED` | `S:droid_slam/trajectory_filler.py:42–110` 在临时位姿槽插值并做 pose-only，`S:droid_slam/droid.py:84–85` 返回逆变换。 | `W:src/trajectory_filler.py:42–98,100–163` 构造临时图并做 pose-only，保留 UBA、固定 U；`W:src/utils/eval_traj.py:143–151` 逆成 c2w，按时序索引用优化后的关键帧覆盖。 | 同样的最终导出帧数不能证明关键帧轨迹或被补位的位姿等价。区间端点若不是当时的关键帧，不能拿近邻关键帧当作原端点。 |

```text
正式 R2 的同一 RGB 序号序列 + 相同固定输入 K
  -> 各自的解码张量约定与归一化 -> fnet / cnet -> 候选与图边选择
  -> 按当前 (T_cw, rho) 重投影 -> 相关性查找 -> ConvGRU
  -> Target = 当前投影 + delta; Weight_net; eta
       W: 候选 RGB -> Metric3D -> rho_prior ----------> 深度对角与 RHS
       W: RGB -> FiT3D / DINO -> U -> 源端门控 ---------> 有效几何权
  -> 残差与 Jacobian -> (H,E,C,v,w) -> Schur -> (dx,dz) -> 几何回写
       W 在线: 此轮回写后的几何 -> 更新 U/仿射 -> 下轮读 U
  -> 最终重建全局图与 BA(7,12) -> Filler pose-only -> c2w 导出
  -> GT 仅离线对齐与评分
```

## E–F. 平移来自哪里，深度与不确定性何时介入

**CONFIRMED：** 内部位姿是世界到相机 `T_cw=(R_cw,t_cw)`。可检查 `S:droid_slam/geom/projective_ops.py:165–198` 与 `W:src/geom/projective_ops.py:110–137` 的 `T_ji=T_j T_i^{-1}`，以及导出时的取逆。相机中心是 `C_w=−R_cw^T t_cw`；原生 7 元组的前三项是坐标变换的平移分量，不能直接当作相机世界坐标。轨迹区间比较需使用 `C_b−C_a` 或显式的 SE(3) 相对变换，旋转与平移分别报告。

**CONFIRMED：** 设源像素齐次射线 `x=K^{-1}[u,v,1]^T`，逆深度为 `ρ`。相对姿态下 `q=R_ji x+ρ t_ji`，几何预测 `p=π_K(q)`。原生用 `r=Target−p`（`S:src/droid_kernels.cu:185–445`；`W:src/lib/droid_kernels.cu:187–487`）。显式深度雅可比为 `Jρ=Jπ(q)t_ji`，相对平移的直接局部导数为 `ρJπ(q)`。实际 `Jp` 包含相对旋转及其对两个端帧的扰动传播；两个世界位姿不是直接相减。有效性门控用变换后齐次量的第三分量 `q_z` 与阈值 `0.25` 比较，不能把它解释为游戏单位的深度阈值。

**CONFIRMED：** 网络的 `Weight` 先乘原生 `0.001` 与有效性门控；W 启用 UBA 时另乘 `g(U)=clip(1/max(45U−35,0.1),0,1)`，源端 U 对同一像素两个坐标方向共用。W 可选从目标坐标双线性取 U 再乘，正式配置关闭（`W:src/lib/droid_kernels.cu:317–362`）。这段代码不修改已经预测出的当轮 Target，不对某个平移分量直接乘常数；它改变 H/E/C 及 RHS 中观测的贡献。几何回写以后更新仿射和 U，故影响下一次内部迭代，而非倒过来改变已执行的更新（`:1899–1984`）。

## G. 从正规方程到在线和最终更新

**CONFIRMED：** 固定本轮 Target，按像素权矩阵 `Ω` 写加权线性化，位姿增量 `dx` 与逆深度增量 `dz` 的方程是：

```text
H = Jp^T Ω Jp       E = Jp^T Ω Jρ       Cg = Jρ^T Ω Jρ
v = Jp^T Ω r        wg = Jρ^T Ω r
m = 1[ρ_prior > 0]
C = Cg + m α + (1−m) η      w = wg + m α (ρ_prior−ρ)
Q = C^-1
S = H − E Q E^T            b = v − E Q w
dx = solve(S + diag(ep + lm·diag(S)), b)
dz = Q (w − E^T dx)
```

`C` 以源帧像素为单位累积；`η` 已包含 `FactorGraph` 的 `0.2·damping+EP`。原版可选传感器 `α=0.05`；formal RGB-only 中 `m=0`。W 的直接先验 `α=gamma_depth=0.01`（正式 `val_007` 常态配置），只在正先验且直接深度正则开启的位置用于 joint；非支持位置仍用 `η`。移除正先验同时改变 `C` 和 `w`，不能只把右端项置零来模拟完整的无先验分支。来源：`S:src/droid_kernels.cu:1395–1437`、`W:src/lib/droid_kernels.cu:1857–1914`。

**CONFIRMED：** 原生使用 Eigen `SimplicialLLT` 解加对角阻尼后的稀疏系统。分解失败时返回零位姿增量的代码存在；本轮没有正式 `val_007` 的逐次求解日志，不能说它实际失败（`S:src/droid_kernels.cu:1197–1218`；`W:src/lib/droid_kernels.cu:1289–1309`）。`motion_only` 改为解带阻尼的 `H dx=v`，不执行先验与 Schur，而不是联合求解完再丢掉 `dz`。W `depth_only` 是另一个选项，但正式 Python 调用传 `False`。

**CONFIRMED：** 位姿以 SE(3) retraction 回写，逆深度以 `ρ←ρ+dz` 回写（`S:src/droid_kernels.cu:907–956`；`W:src/lib/droid_kernels.cu:955–1004`）。Python clamp 发生在整次 native BA 返回后，原版 `min=0.001`、W `min=1e-5`。所以边界差异存在，但历史其他实验的负逆深度不能证明正式 stride=1 的 `val_007` 出现同样问题。

**INFERRED：** 若近处、长基线或对平移方向敏感的观测被选择性降权，固定阻尼在弱约束方向上可能更主导；即使旋转仍被较多观测支持，平移长度也可能偏短。先验经 `C,w` 与 `E` 改写 Schur 系统，作用方向取决于实际残差与几何，源码不能推出它总是加剧或缓解压缩。单目 `t→s t,ρ→ρ/s` 保持 `q` 不变的全局规变，与正式结果在全段只做一次 Sim(3) 后仍可见的局部压缩，是两个问题。

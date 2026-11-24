# Task 002A｜DROID-W 的 BA 阶段控制

**CONFIRMED：** `enable_online_ba=false` 停止周期性的在线全局 BA，前端局部 BA 继续。正式 R2 就是这个组合。上游的 `final_ba=false` 停止末尾的两轮全局 BA，**仍执行非关键帧的只优化位姿补位**。冻结 R2 启动脚本另外拒绝 `final_ba=false`，以下区分源码语义与入口限制。

本文 `W:` 指 `D:\aaa\GameCam-VO\experiments\DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1\sources\DROID-W`（`c3414af6047d06bafc1a6645d09f23247f3b2cdc`）。`R1:` 指 `D:\aaa\GameCam-VO\experiments\DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1`。`D` 表示当时的 `video.metric_depth_reg`；`M` 表示 `tracking.frontend.enable_opt_dyn_mask`。表内 `(更新 U, UBA)` 是传入 native BA 的布尔值模式，从源码和 R2 配置求得。

| 阶段 | 启动条件、调用与次数 | `(更新 U, UBA)` | 直接 Metric3D BA 约束 | 正式 R2 / 证据 |
| --- | --- | --- | --- | --- |
| Frontend Local BA，暖机第一段 | 候选数首次等于 `warmup=12`；邻域图；8 次 `graph.update`，每次默认 2 次 native 内层 | `(M, false)`，R2 `(true, false)` | 联合 pose/disp 求解；`D` 且正 prior 处用 `gamma_depth` | CONFIRMED（源码调度）；`W:src/frontend.py:127–139,214–225` |
| Frontend Local BA，暖机第二段 | 同一次 `__initialize()` 加近邻候选边后，再 8 次外层更新 | `(M, M)`，R2 `(true, true)` | 同上 | CONFIRMED；`W:src/frontend.py:141–148` |
| Frontend Local BA，`initialize_second_stage` | `Tracker.run` 发现关键帧索引变化、已初始化且计数等于 `warmup` 时额外 8 次外层；触发条件在 mapping 分支外 | `(M, M)`，R2 `(true, true)` | 同上 | CONFIRMED；`W:src/tracker.py:109–118`、`W:src/frontend.py:173–187` |
| Frontend Local BA，常规跟踪 | 每次候选入队先走 `iters1=3`；检查关键帧距离后，保留关键帧默认再走 `iters2=2`。候选被删除前可已影响活跃状态 | `(M, M)`，R2 `(true, true)` | 同上 | CONFIRMED；`W:src/frontend.py:19–25,56–110,222–225` |
| 回环 BA | `enable_loop=true`、保留候选、关键帧数 `>frontend.window` 才尝试；建低内存图并复制部分局部图状态；有边则承担该次后半段更新，`n_edge==0` 才回退正常局部更新 | 有效回环 BA 硬编码 `(true, true)`，不读 `M` | 同期 `D`，使用低内存 joint 路径 | CONFIRMED；R2 关闭；`W:src/frontend.py:85–110`、`W:src/backend.py:96–120` |
| Online Global BA，第一次 | 已初始化、关键帧索引变化，非二次暖机分支；`enable_online_ba` 且距上次至少 `ba_freq=20` 个索引；`dense_ba(2)` | `(M, M)` | 同期 `D` | CONFIRMED；R2 关闭；`W:src/tracker.py:109–131` |
| Online Global BA，后续 | 同上；`dense_ba(2)` | `(false, M)` | 同期 `D` | CONFIRMED；R2 关闭；`W:src/tracker.py:124–131` |
| Final Global BA | `terminate()` 按 `final_ba` 调 `SLAM.backend()`；两次 `dense_ba`，分别 7、12 次外层；每次独立建图 | `(false, M)`，R2 `(false, true)` | 调用前暂置 `D=false`，两次均传零 prior；之后恢复 | CONFIRMED；R2 回执有阶段样本；`W:src/slam.py:128–143,176–179`、`W:src/backend.py:70–90` |
| Trajectory Filler，pose-only BA | 不受 `final_ba`/`enable_online_ba` 控制；按 16 帧一批插入暂存槽，并对邻居关键帧的边做 12 次 `graph.update`，每次默认 2 次 native 内层 | 硬编码 `(false, true)`，不读 `M` | `motion_only=true`，不走直接深度残差，也不联合求解 `dz`；关键帧已有深度仍参与投影 | CONFIRMED；`W:src/slam.py:217–227`、`W:src/trajectory_filler.py:42–97,114–142`、`W:src/lib/droid_kernels.cu:1836–1888` |

## 1. 局部和全局怎么进入同一个求解器

**CONFIRMED：** `Tracker.run` 在每帧先走 `MotionFilter.track` 再调用 `Frontend`；在线全局 BA 是之后的独立分支。因此 `enable_online_ba=false` 连 `Backend` 构造也不会跳过（`W:src/tracker.py:26–35,58–72,109–131`）。没有前端局部 BA 的独立 YAML 开关。`warmup`、窗口、关键帧阈值会同时改初始化、跟踪和图，不能用作局部 BA 的关闭开关。

**CONFIRMED：** 局部用 `FactorGraph.update`，全局和回环用 `Backend.backend_ba → FactorGraph.update_lowmem`。两条路径都用原生更新头计算 `Target=当前投影+delta`、网络 `Weight` 和阻尼，再调用同一 `DepthVideo.ba → droid_backends.ba → ba_cuda`。局部常用 `lm=1e-4, ep=0.1` 和 `lr/weight_decay`；全局路径用 `lm=1e-5, ep=1e-2` 和 `gba_lr/gba_weight_decay`。低内存阶段 `Backend.backend_ba` 显式 `itrs=2`；每个外层重算目标、权重和阻尼。Final BA 的 **7+12 是外层**；若两个图都有边并跑完所有步，则安排 38 次 native 内层迭代。没有边时提前返回，不能用配置或回执假定实际内层次数。`enable_wq` 传到 `update_lowmem` 形参后无分支消费，不能用它关闭 UBA。见 `W:src/backend.py:42–90`、`W:src/factor_graph.py:236–282,289–342`、`W:src/depth_video.py:332–378`、`W:src/lib/droid.cpp:118–165`。

**CONFIRMED：** Final BA 优化的 `poses/disps` 与跟踪使用同一 `DepthVideo`。全局图固定第一位姿（`t0=0+1`），允许回写其它参与求解的关键帧位姿和视差。R2 `normalize=false`，消融也应维持该值；打开会在全局调用前用平均逆深度对活动位姿平移和逆深度重标定。看 `W:src/backend.py:53–64,70–90`、`W:src/depth_video.py:236–243`、`W:src/lib/droid_kernels.cu:1876–1912`。**UNVERIFIED：** 本次不推断任何具体 R2 片段的 Final BA 改变量或效果方向。

## 2. 关闭最终 BA 后还会发生什么

- **CONFIRMED，上游：** `final_ba=false` 跳过 `SLAM.backend`。同一个键也参与 `mapping.eval_before_final_ba` 快照的条件；启用 mapping 时还控制 `mapper.final_refine`。R2 已关闭 mapping 与 pre-final 诊断，因此这些条件在 R2 型对照中不会叠加成为额外干预（`W:src/slam.py:145–213`）。常规末尾 `save_video` 仍执行，R2 的 RGB-only 路径不读 GT 做内部评价。
- **CONFIRMED，上游：** 仍调用 `setup_feature_extractor → full_traj_fill → full_traj_eval`（`W:src/slam.py:217–227`）。补位对整条输入迭代，用时间邻近关键帧初始化临时帧位姿，并仅优化临时 pose 窗口。`W:src/utils/eval_traj.py:143–165` 对结果取逆到 c2w，再按帧序号将真实关键帧位置写回整段轨迹，导出 `est_poses_full.txt` 后才判断 GT 是否存在。
- **CONFIRMED，上游：** Filler 的图边为 `ii=t0/t1`（已有 KF）、`jj=临时帧`，其 `motion_only` 不取消 UBA。R2 `enable_bidirectional_uncer=false` 时几何权重读 **源关键帧**已有 U；临时帧插值 U 不参与目标端权重。若开启双向，目标坐标有效时才会读取临时帧插值 U（`W:src/trajectory_filler.py:57–92`、`W:src/lib/droid_kernels.cu:320–359`）。
- **CONFIRMED，历史 runner：** `R1:pipeline/run_segment.py:197–201` 拒绝 `final_ba=false`。`ObservedSLAM.backend()` 原本在 Final BA 返回时才把 phase 改为 `filler`；如果未来只放宽 guard，`ViperRGB.__getitem__` 不会增加正式补位计数，`ObservedSLAM.tracking()` 的完整性条件会失败（同文件 127–132、137–147、152–171）。未来独立实验 runner 应观测实际补位入口，继续保留输入和导出门禁。

## 3. 所有阶段统一解释的边界

- **CONFIRMED：** U 更新发生在 native 几何状态回写以后，若后续内层启用 UBA 才会读取新 U。关闭更新不会自动清除已保存的 U。`enable_opt_dyn_mask=false` 在 R2 会关掉前端的两个布尔路径和 Final BA 的 UBA，**补位的 UBA 仍开启**；若另开回环，硬编码的回环 `(true,true)` 也不受它限制。
- **CONFIRMED：** Final BA 不直接从 Metric3D prior 形成残差，但起点是前端已经优化过的 pose/disp；最终结果仍可间接承接此前深度先验的影响。Filler 也同样继承关键帧状态。
- **INFERRED：** 任何全段级开关都会允许之后的状态、残差或选帧随处理变化；若要把改变归因到当轮几何权重或直接 prior，必须用同初始状态、同图、同目标的对照。**UNVERIFIED：** 本审计未执行新 solver、模型、GPU 或数据实验。

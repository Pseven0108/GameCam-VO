# Task 002A｜正式 R2 配置核验

**结论（CONFIRMED）：** 正式 VIPER R2 的 DROID-W 对照来自 47 条 Validation 序列的 92 个冻结片段，输入共 49,815 帧，`stride=1`。92 份实际运行配置均记录 `metric_depth_reg=true`、`gamma_depth=0.01`、跟踪 U 开启、在线全局 BA 与回环关闭、最终 BA 开启。基础 YAML 的 `gamma_depth=0.001` 不能用作 E0。`stride=4` 的分支与结果未纳入本次核验。

## 1. 源码身份及工作区状态

下文 `W:` / `S:` 分别指向 `D:\aaa\GameCam-VO\experiments\DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1\sources\DROID-W` / 同级 `DROID-SLAM`；`R2:` 指 `D:\aaa\GameCam-VO\experiments\VIPER_MATCHED_DUAL_BASELINE_R2`；`R1:` 指 `D:\aaa\GameCam-VO\experiments\DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1`。行号对应固定文件。

| 检查 | DROID-W | DROID-SLAM | 证据级别 |
| --- | --- | --- | --- |
| 目标完整提交 | `c3414af6047d06bafc1a6645d09f23247f3b2cdc` | `2dfd39f0dcad44012ca7bbb8aa70b55edbfa9c99` | CONFIRMED |
| Git tree SHA-1 | `5b0eb293baf41b8267fc656ca34c23a7b421c44f` | `7ab46b59d34893957fe7c88d5d8d6e6bb842e4dc` | CONFIRMED |
| 本地实际读取对象 | 固定源码快照；208 个 blob、3 个子模块指针通过 | 固定源码快照；104 个 blob、2 个子模块指针通过 | CONFIRMED |
| 历史入库 HEAD、状态 | 完整提交匹配，历史入库 status 0 行，历史部署 tracked 差异 0 | 完整提交匹配，历史入库 status 0 行，历史部署 tracked 差异 0 | CONFIRMED（历史记录） |
| 当前 live HEAD / 工作区 | 指定快照无 `.git`；live HEAD/status 不适用 | 指定快照无 `.git`；live HEAD/status 不适用 | UNVERIFIED（当前远端及递归依赖内容） |

证据见 [Task 001 源码身份报告](/D:/aaa/GameCam-VO/experiments/DROID_SLAM_DROID_W_TASK001_STATIC_AUDIT/evidence/SOURCE_IDENTITY_VERIFICATION.json) 和 [只读核验器](/D:/aaa/GameCam-VO/experiments/DROID_SLAM_DROID_W_TASK001_STATIC_AUDIT/verify_static_sources.py:242)。本轮不带 `--record` 复核，退出码 `0`；两个 Git commit/tree 对象、312 个 blob、5 个 gitlink 通过。冻结对象没有版本差异，因此继续分析指定快照。历史工作区记录不能代替当前 live `git status`；没有使用其它版本的本地源码替代。

## 2. 正式运行身份证据

1. **CONFIRMED：** [冻结片段清单](/D:/aaa/GameCam-VO/experiments/VIPER_MATCHED_DUAL_BASELINE_R2/VIPER_R2_FROZEN_VAL92_MANIFEST.csv) 有 92 个唯一片段，其 SHA-256 `b991fd5019307373601b5e2fd5460a83049ffea517140e1fcf6401996a091acb` 等于 [协议锁](/D:/aaa/GameCam-VO/experiments/VIPER_MATCHED_DUAL_BASELINE_R2/VIPER_R2_PROTOCOL_LOCK.json) 记录。DROID-W 一侧沿用封存的 R1 实际推理产物；R2 并未为这 92 个对照重新执行 DROID-W。参见 [冻结脚本](/D:/aaa/GameCam-VO/experiments/VIPER_MATCHED_DUAL_BASELINE_R2/pipeline/freeze_inputs.py:74) 和 `R2:evaluation/BASELINE_VERSION_AUDIT.md`。
2. **CONFIRMED：** 对每个片段，`wild_reference/<segment>/native_config.yaml` 的 SHA-256 与清单 `wild_config_sha256` 及 [原始制品哈希账本](/D:/aaa/GameCam-VO/experiments/VIPER_MATCHED_DUAL_BASELINE_R2/evidence/R1_PRESERVATION_AND_SCORE_CHECK.json) 的 `results/.../native_config.yaml` 一致。92 份 `attempt.json` 同样匹配原哈希；`status=COMPLETE`、`exit_code=0`、提交匹配、实际读取与补位帧数等于清单，且逐片段匹配输入 manifest SHA。核对了正式 R2 ZIP 外层 SHA 与内部 187 项：92 份配置、92 份回执、片段清单、协议锁与原始制品哈希账本。ZIP 中协议锁名为 `PROTOCOL_LOCK.json`，与本地 `VIPER_R2_PROTOCOL_LOCK.json` 内容相同。
3. **CONFIRMED：** 锚点是 [val_007 运行回执](/D:/aaa/GameCam-VO/experiments/VIPER_MATCHED_DUAL_BASELINE_R2/wild_reference/val_007_full_00001-00487/attempt.json) 和 [val_007 实际配置](/D:/aaa/GameCam-VO/experiments/VIPER_MATCHED_DUAL_BASELINE_R2/wild_reference/val_007_full_00001-00487/native_config.yaml:94)：487 帧，`stride=1`，W 提交匹配。回执 SHA-256 `96285f1e5718777192cc2fd777fc27e7db3e2b089f461a4d3ad1f83d207a3830`；配置 SHA-256 `a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc`；输入 manifest SHA-256 `5547cdd407e022ba27a8b9af18f1ef4e9471ea58c1e0df96aec38fee180aa537`。

## 3. E0 取值：基础 YAML、实际快照、运行语义

下表默认值指 `W:configs/droid_w.yaml`，不是每个上游数据集配置的通用默认。行号以 `val_007` 快照为例。92 份 YAML 中所有审计键一致；完整 YAML 叶子只在 `cam.{fx,fy,cx,cy}` 与 `data.{input_folder,output}` 六处随片段变化，后续仍应以各片段自己的 K 和清单为准。

| 位置或配置键 | 基础 YAML | 正式 R2 | 证据 / 解释 |
| --- | --- | --- | --- |
| `stride` / `cam.W_out,H_out` | `1` / `640,360` | `1` / `640,360` | CONFIRMED；快照 1–11、93；回执和输入清单 |
| `tracking.backend.metric_depth_reg` | `true` | `true` | CONFIRMED；基础 118、快照 102；Final BA 内临时置 `false` |
| `tracking.uncertainty_params.gamma_depth` | `0.001` | **`0.01`** | CONFIRMED；基础 126、快照 135；YouTube 覆盖项给出 `0.01` |
| `tracking.uncertainty_params.activate` / `.enable_affine_transform` | `true` / `true` | `true` / `true` | CONFIRMED；基础 122、131；快照 130–131 |
| `tracking.uncertainty_params.enable_bidirectional_uncer` | `false` | `false` | CONFIRMED；基础 132、快照 132；仅目标端 UBA 门控关闭 |
| `tracking.uncertainty_params.{gamma_data,gamma_prior,lr,weight_decay,gba_lr,gba_weight_decay}` | `0.1,0.05,0.1,0.002,0.1,0.002` | 相同 | CONFIRMED；基础 124–130、快照 134–141；用于 U 更新，不代替 U 更新开关 |
| `tracking.frontend.enable_opt_dyn_mask` | `true` | `true` | CONFIRMED；基础 103、快照 113；一个键影响多个阶段的 U 更新和加权 |
| `tracking.frontend.{enable_online_ba,enable_loop}` | `false,false` | `false,false` | CONFIRMED；基础 95–96、快照 111–112 |
| `tracking.backend.{ba_freq,normalize,final_ba}` | `20,false,true` | `20,false,true` | CONFIRMED；基础 105–119、快照 95–106；在线调度未启用，`ba_freq` 不触发生效 |
| `tracking.{warmup,buffer,force_keyframe_every_n_frames}` | `12,350,9` | `12,500,-1` | CONFIRMED；基础 83–85、134，快照 108–109、142 |
| `mapping.{enable,full_resolution,eval_before_final_ba}` | `false,false,true` | `false,false,false` | CONFIRMED；基础 16–20、快照 53–57；跳过 final 前诊断，保留 Final BA |
| `mapping.uncertainty_params.activate` / `.vis_uncertainty_online` | `true` / `false` | `true` / `false` | CONFIRMED；基础 68–72、快照 76–84；mapper 关闭不阻止 MotionFilter 构造 FiT3D |
| `mono_prior.depth` / `.save_depth` | `metric3d_vit_large` / `false` | 相同 | CONFIRMED；基础 154–155、快照 86–87；独立 `.npy` 不保存，内存保留 |
| `mono_prior.feature_extractor` / `.save_feature` | `dinov2_reg_small_fine` / `false` | 相同 | CONFIRMED；基础 156–157、快照 88–89；特征照算，跟踪缓存照存 |
| `traj_filler.use_dino_features` | `false` | `false` | CONFIRMED；基础 13、快照 143–144；无补位特征前向，补位的 UBA 仍可用 |
| `debug` / `droidvis` / `save_gt_poses` | `false` / `false` / `true` | `false` / `true` / `false` | CONFIRMED；快照 17、19、90；配对设计保留相同可视化与数据边界 |
| Final BA 调度 | 不在 YAML | `dense_ba(7)` 再 `dense_ba(12)` | CONFIRMED（源码）：`W:src/slam.py:128–143`；每个外层默认 2 次 native 内层，图为空时可提前返回 |

**CONFIRMED（覆盖链）：** [实际 runner](/D:/aaa/GameCam-VO/experiments/DROIDW_VIPER_ZERO_SHOT_TRANSFER_R1/pipeline/run_segment.py:184) 读取 YouTube YAML → [继承与合并](/D:/aaa/GameCam-VO/experiments/DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1/sources/DROID-W/src/config.py:29) → [YouTube 的 gamma 覆盖](/D:/aaa/GameCam-VO/experiments/DROID_SLAM_TO_DROID_W_SOURCE_DIFF_EVIDENCE_MAPPING_R1/sources/DROID-W/configs/Dynamic/YouTube/youtube.yaml:25) → runner 按冻结片段设定输入、K、缓冲区和诊断开关 → `run_segment.py:205` 保存合并快照。runner 与 R2 协议锁所指的 R1 封存 ZIP 成员同字节，runner SHA-256 `428ca308f9df4d9375251f463fb560673c323aa9e62c9a2fcc98ffa6e99180e6`。

**CONFIRMED（运行入口限制）：** `R1:pipeline/run_segment.py:197–201` 要求 `metric_depth_reg=true`、`final_ba=true`、`gamma_depth=0.01`，否则抛出 `ValueError('upstream YouTube tracking contract changed')`。这是冻结 E0 的门禁。补位计数的 phase 标记也由 `ObservedSLAM.backend()` 切换（同文件 127–132、137–147、152–171），所以只放行 `final_ba=false` 仍不足以让旧 runner 正确记录补位。详见 [消融设计](/D:/aaa/GameCam-VO/experiments/DROID_W_TASK002A_ABLATION_SWITCH_DEPENDENCY_AUDIT/DROID_W_PROPOSED_ABLATION_PLAN.md)。

**UNVERIFIED（逐调用运行证据）：** 92 份回执都有 `final_ba` 阶段资源采样，可确认进入该阶段；不能据此证明每次 native 调用的两项 U 标志、边数、实际 solver 成功次数、U/affine 更新幅度，或当轮深度先验贡献。R2 的 `enable_update_uncer` 与 `enable_udba` 不是两个已保存 YAML 键，它们的阶段取值是由固定源码和快照静态推得。

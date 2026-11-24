# Task 004｜E0～E8 参数差异与封存

## 共同基线

所有组共用 [封存 YAML](candidates/r2_sealed_config.yaml)，SHA-256 为 a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc。这是按字节保留的 Task003 已封存配置副本。Task003 实跑 YAML 与封存 YAML 在排除 data.output、data.input_folder 两个运行路径后字节一致，见 [历史配置取证](evidence/HISTORICAL_INPUTS.json)。该文件保留绝对路径原样作为证据；未来只有隔离输出与经核验的输入目录可在内存配入。原 R2 YAML、Task003 配置及资产不覆盖。

| 参数 | 全组共同值或处理 |
| --- | --- |
| 容量、步长、种子 | buffer=500，stride=1，setup_seed=43（A 阶段）；独立 spawn 进程 |
| 视觉输入 | 487 张同序 RGB，原 R2 相机变换和 640×360 输出；模型输入不含 GT 或 GT 派生 pose |
| K 验收 | loader 输出 [386.01129150390625, 386.01129150390625, 319.5, 179.5]；保留冻结网格内参传递。输入 manifest SHA 5547cdd407e022ba27a8b9af18f1ef4e9471ea58c1e0df96aec38fee180aa537；处理后 RGB tensor 流 SHA 2e27f696f9553821d1e43cdd673118c90e3932904b9df652d887105f04fbb26a。 |
| 深度、特征、U | metric3d_vit_large，dinov2_reg_small_fine；metric_depth_reg=true，gamma_depth=0.01；activate=true、enable_opt_dyn_mask=true、enable_bidirectional_uncer=false；C/CUDA 扩展和权重原封不动。 |
| 阶段配置 | enable_online_ba=false，enable_loop=false，mapping.enable=false，final_ba=true，traj_filler.use_dino_features=false，droidvis=true；主矩阵 Final BA 保留 7+12 外层次数。 |
| 观测 | 固定同一 Task004 候选埋点和 Rerun 0.22.1；每组配独立结果目录与记录，确认期如改观测版本须重新确认比较口径。 |

## 独立策略相对于 E0 的差异

| 组 | 局部 D/W/U | 指定调用内的唯一参数差异 |
| --- | --- | --- |
| E0 | 1/1/1 | 同原始局部机制。 |
| E1 | 0/1/1 | 现有 zeros 替代 mono_disps 入参。 |
| E2 | 1/0/1 | 只传 enable_udba=false。 |
| E3 | 1/1/0 | 只传 enable_update_uncer=false。 |
| E4 | 0/0/1 | 同 E1＋E2。 |
| E6 | 0/1/0 | 同 E1＋E3。 |
| E7 | 1/0/0 | 同 E2＋E3。 |
| E8 | 0/0/0 | 同 E1＋E2＋E3。 |

八组 [策略](policies) 的 SHA 与启动顺序见 [矩阵](TASK004_FACTORIAL_MATRIX.csv)。只删除策略绑定的目标调用参数是无效实现；必须按底层实际实参和返回事件验收。配置本身没有修改全局布尔开关。

策略载荷绑定封存 YAML 哈希，加载仅接收绝对文件路径和准确策略 SHA；严格校验 schema、组别与 D/W/U 一致、两类 campaign 范围与 Final BA 阶段数。一进程一次策略，spawn 子进程继承对应路径和哈希。未来正式运行前仍需对启动目录、产物独占写入、输入隔离和多进程行为做无模型核验。当前 runner 在任何模型或 torch 导入之前退出；禁止把策略文件当成 GPU 启动许可。

# TASK009 源码、权重和许可证审计

2026-11-27。本轮以独立实验代码完成候选移植，未修改原项目的冻结 DROID-W。
版本与许可证原始文件 SHA 见 `evidence/intake/source_identities.json`；表中的根许可证不是全部依赖或权重的自动授权证明。

| 项目 | 核验版本 | 实际复用模块与接口 | 许可证和迁移判断 |
|---|---|---|---|
| DROID-W / MoyangLi00/DROID-W | c3414af6047d06bafc1a6645d09f23247f3b2cdc | `DepthVideo.ba` 输入 `[1,E,H/8,W/8,2]`；Frontend、Backend、TrajectoryFiller；U 保留 | 根 Apache-2.0；仅独立候选做构建兼容修改，BA 公式未改 |
| π³MOS / PRBonn/Pi3MOS-SLAM | 缓存生成 1b81d729c4259a5a775eb4aae41f959eea38ae14 | TASK008 已生成的 RGB301..332 动态概率、conf、local_points z；本轮读取连续概率 | 当前参考克隆 HEAD 是 c56453704eeff0c0fef673fb4d9282c147889a23，与缓存生成版本不同；未在其根找到许可证，不能推定无条件再分发。只发布自有适配器、统计与派生展示，不复制模型正文/权重 |
| BA-Track / wrchen530/batrack | a66925e1f78b57ae81e2fa02760e37d7fafcb49d | `main/frontend/md_tracker.py:MDTracker.forward`：RGBD `[B,T,4,H,W]`；total_xy、static_xyz、visibility、dynamic_probability | 根 Apache-2.0；官方训练权重 strict 加载。Static 的前三维含图像 x/y 和深度，不能整体当欧氏 XYZ |
| WildGS / GradientSpaces/WildGS-SLAM | 11e85220bf25ba0a27172e5b91453c4b324fd9e8 | `src/utils/dyn_uncertainty/uncertainty_model.py:MLPNetwork.forward`；384 维输入，输出不是校准动态概率 | 根 Apache-2.0；实际使用 WW_A/WW_B 场景训练 head，非随机初始化。eval 下函数式 dropout 仍运行；384 维相同不代表 FiT3D 分布匹配。禁止据此替换原 U |
| Easi3R / Inception3D/Easi3R | 146a77d77c863ddd0bd7a559fa35f69722fc3c50 | DUSt3R 双图 `[B,3,H,W]`；六有向帧对 attention、pts3d、conf；仅抽取外部原函数做聚合/聚类/Otsu | 根 CC BY-NC-SA-4.0；外部隔离，不把正文混入核心。本轮不是完整 Easi3R，不运行 RAFT/SAM2/全局优化 |
| LEAP-VO / wrchen530/leapvo | 7667cf31acc62e27e9278940ce093c6fc95b952a | 作者页 `https://wrchen530.github.io/projects/leapvo/` 指向官方仓库；LEAP kernel 小窗口输出 tracks、vis、cov、dynamic | 根 CC BY-NC-4.0；独立加载，不复制核心、不运行完整 VO、不接入 DROID |

Metric3D 固定 `eb5b6fac0dc155e4e52f576e304fbf11655ff339`（根 BSD-2-Clause）；FiT3D 固定 `18200c21f047b5add8b7e796d6aab97fba25e790`（根 MIT）。
LieTorch 为 archive 导出而非独立 Git repo：`0fa9ce8ffca86d985eca9e189a99690d6f3d4df6`，Eigen `824272cde8ca2541e8b67b0887f5ded92b128d1f`。逐文件身份和完整候选补丁已封存。

## 权重身份

| 权重 | SHA-256 | 使用方式 |
|---|---|---|
| DROID tracker | 46476ef64cde45a97504910d6f3de2eef7b398ec1c6e4e668815c29076024526 | 历史官方原件只读复用，按官方接口裁剪输出头并 strict 加载 |
| Metric3D | 15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972 | 历史官方原件只读复用 |
| FiT3D | 09db495b0788df23591de1bc9ccb721b182dfb511136398a2caed3896a39c8e4 | 历史官方原件只读复用 |
| MDTracker tensor-only | c1189d8d6912798e66b99b3e853ce644f587ed57837a5e7bb768405980dc1422 | 官方文件提取 210 tensor，移除 module. 前缀，strict 加载 |
| WildGS WW_A | fea6b224bdaec5c2ab1138134a8135efb5c71c9d6bc902039c73c203d730badf | 真实场景训练 head，仅迁移探针 |
| WildGS WW_B | ca26e3715eadbcd6bfda144bd599456c3f0ebf5ef6a91d3f711433bb93c652cc | 同上 |
| LEAP kernel | 8bd20f5dde2015748840c509b6dd5b40a78785e06dce5778a35b60749e27c124 | 官方 leap_kernel.pth，strict 加载 |
| DUSt3R | 9f194a32e34fc124ed10f64115b8e848b7da87c2d1ed131d34b4806721c19dbd | 官方 512 DPT checkpoint，strict 加载，128×224 探索输入 |

本轮核对了仓库许可证、权重来源及身份，但不将源码许可证自动等同为每份权重/训练数据的独立许可证。没有单独明确条款者记录为未独立核验，不对外分发权重、外部模型源码或训练数据。

## 实际资源与优先级

MDTracker 32 帧 FP32 的峰值 tensor allocated 0.477 GiB；LEAP 16 帧 0.279 GiB；Easi attention 3 帧 2.211 GiB。
这些测量是各自独立模型前向，不能相加解释为并行驻留需求，也不能预测完整 SLAM 的显存。
迁移顺序为 π³MOS 门控 → MDTracker 静态目标 → WildGS 准入审查 → Easi3R/LEAP 独立验证。
轨迹结果反过来支持优先保留静态目标辅助，而不是模块越多越好。

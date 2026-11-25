# TASK006A-R2｜Metric3D 深度先验可信度阶段研究报告

2026-11-26 · GameCam-VO · **PARTIAL / 明确阻断后停止**。
**NO-GO — 当前证据不足，不应接入 CADP 或 BA；不是认定原生 Confidence 无效。**

## 首页：七个核心问题

| 问题 | 当前回答 | 原因 |
|---|---|---|
| 1. 能否识别 GTA-V/VIPER 错误深度？ | INSUFFICIENT_EVIDENCE | 未执行模型与独立 GT 比较 |
| 2. Night/Rain/Snow/低纹理/远距可靠吗？ | UNVERIFIED | 没有相应独立误差实验 |
| 3. 需要后处理校准吗？ | 若要解释为概率则必须定义事件并校准；当前排序表现未知 | 原生输出没有概率约束 |
| 4. Flip TTA 有独立提升吗？ | UNVERIFIED | 评价器已测，模型 TTA 未执行 |
| 5. Depth-bin entropy 有额外信息吗？ | UNVERIFIED | 初始 256 bins 已确认，真实提取与 GT 未测 |
| 6. 最终应选哪种信号？ | 暂不选；优先实测 Native | 不能由理论成本选择准确性优胜者 |
| 7. 足以进入联合控制器吗？ | NO-GO_INSUFFICIENT_EVIDENCE | GPU 推理和 GT 准入均未完成 |

## 研究背景与实际执行

R1 已验证 prior-off Schur 几何协方差的 CPU 数学定义，未证明 Metric3D 先验本身可靠。
本轮追踪原生质量 score，独立审计数据和评价器，不改变 BA、RAFT、U/W 或调度。
已实际执行：可信 SSH 只读核查、实际源文件身份核验、全文及官方代码相关部分阅读、
100 帧真实 RGB/EXR/相机审计、300 文件来源比对、非零基线投影对照及 61/61 CPU 合同测试。
不是只交方案；但也不是完整的推理评价完成包。

## 源码与模型身份

实际 Metric3D eb5b6fac0dc155e4e52f576e304fbf11655ff339，283/283 Git blobs 与官方固定提交一致。
权重 SHA 15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972，大小 1,647,972,663 bytes；未反序列化。
DROID-W 目标 c3414af6047d06bafc1a6645d09f23247f3b2cdc，入口与封存 R0 对照相同；gamma_depth=0.01 保留。
生产 torch.hub.load 没有版本 pin；运行缓存已单独核验，不能用注释旧 commit 冒充实际版本。

Confidence 是联合 depth/normal RAFT 状态中的单独深度 score，经 8 次更新和凸上采样输出，
没有最终 sigmoid 或 [0,1] 约束。Normal concentration、DINO U 和 R1 几何协方差都不是这个 score。
Confidence loss 的相对误差分母为 GT；relative error>=1 的像素被该项监督 mask 排除。
这给出严重错误风险的可检验假设，不能代替实际失败证据。
生产入口丢弃 score 的行为已确认，作者动机 UNVERIFIED。
[官方 decoder](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/mono/model/decode_heads/RAFTDepthNormalDPTDecoder5.py)，
[官方 loss](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/training/mono/model/losses/GRUSequenceLoss.py)。

## 文献依据

阅读 Metric3D v2（TPAMI 2024）、GrUMoDepth（ECCV 2022）、UfM（ICRA 2022）、DepthCov（CVPR 2023）
的相关方法、实验和局限；完整记录在 02_literature。作者实验不等于本项目复现。
Native score、翻转一致性、初始 bin 分布、梯度是不同的证据源；
UfM 依赖运动，不适合当独立 GT；DepthCov 需训练，本轮不实现。

## 真实数据结果

VIPER 审阅的 11 个本地 RGB ZIP 与 camera 输入没有配套 Dense Depth GT；不声称官方永远没有。
MVS-Synth 0000 有 100 RGB/100 EXR/100 pose，960×540，45,412,636 个有限正深度，
6,427,364 个 Inf sky，NaN 0。300/300 当前文件与镜像清单匹配，历史官方子集 13/13 复核。
没有把子集比对扩大到所有文件的官方身份。

非零基线 49→50 与 98→99 的 Z-depth 中位跨视图相对差约 0.0872% 和 0.0890%，
ray-range 假设约 2.67% 和 3.18%。错配深度明显更差，支持样本几何与网格对应。
0→1 几乎静止，不具有 Z/range 区分力。上述不是模型准确性、米制标定或物理时钟证明。
GT 物理单位仍未知；本地只有一条完整序列，另外四条只有 RGB 预览，不能独立校准/测试。
[数据作者说明](https://phuang17.github.io/DeepMVS/mvs-synth.html)。

## 已执行实验与未执行部分

61/61 CPU 测试覆盖 GT 准入、防泄漏、relative/log error、tie-aware AUROC/AP、risk-coverage、
raw AbsRel AUSE/AURG、概率事件门禁、分组 bootstrap、TTA 逆转与 bin anchors、监督 mask。
数值对照包括 sklearn 指标 oracle 和枚举 tie 排列；这些是评价工具验证，不是模型 score 准确性。
合成 consistently-wrong TTA 反例说明“稳定”不等于“正确”，不是 Metric3D 实测失败案例。

| 项目 | 真实执行状态 |
|---|---|
| Confidence 数值分布/热图 | 未执行，无 GPU |
| Native score 对 GT 的 Spearman/AUROC/AP/AUSE | 未执行，GT 单位/划分未准入 |
| Flip forward/效果/性能 | 未执行 |
| bin hook 的真实输出与初始/最终误差 | 未执行 |
| 梯度反向传播 | 未执行，A/B/C 还未评价，不满足备用阶段前提 |
| 概率校准/独立测试 | 未执行 |
| CADP/BA 接入 | 禁止，未执行 |

CSV 的空值表示未测，NaN/Inf 计数也没有擅自填 0。
没有预测图时不以审计 GT 图冒充 RGB/GT/Pred 三联图。

## 资源与停止原因

当前可信端点 sc01-ssh.gpuhome.cc:30601 的 nvidia-smi 返回 Exec format error。
未确认可用 GPU，不修驱动、不重启、不申请卡。数据盘探针可用 12,522,487,808 bytes，/dev/shm 2 GiB。
模型 checkpoint 加载、CUDA context、GPU inference、训练、SLAM、C0 读取均为 0。
本地使用 CPU Python 3.9.13/NumPy 2.0.2/SciPy 1.13.1。
OpenEXR 3.3.3 和 pypdf 5.9.0 只放进本研究 runtime_site，不替换既有核心依赖。
没有下载新数据；论文 PDF 与小型工具依赖的网络读取不能误报为“完全零网络”。
独立 GPU 脚本已准备、未 smoke；其 12000 MiB 保护是保守预算，非模型最低显存实测。

## 方法比较与阶段结论

没有证据选择 Native、TTA 或 bins 中的优胜者。Native 理论额外 forward 最少，
TTA 和 bins 是否带来独立信息尚待配对 GT 实验。也没有证据声明某个环境中已有效，因此不是 CONDITIONAL GO。
下一步是恢复小规模模型输出实测，并建立独立 matched-unit depth GT；不是重新跑 SLAM 或训练新网络。
详见 09_final_design 和 CODEX_HANDOFF。后续 GPU 可先做分布审计，GT 问题不妨碍其统计；
但准确性结论仍必须等 GT 准入。新阶段不得自动开始。

# R2-3 数据与 GT 审计

**100 帧真实数据审计已执行；独立模型误差评价未准入。** 所有原始数据只读。

## VIPER：审计范围内没有 Dense Depth GT

读取当前本地 11 个 RGB ZIP 的中央目录，以及已有 train_camera.zip（78 个成员）与冻结 R2 清单。
RGB 包为 JPG/TXT；当前审阅输入中没有配套逐像素深度。已有 dense 的目录索引二进制不是数据载荷。
Camera/K/天气与帧身份可用于无 GT 的模型分布检查，但不能由 pose 或 DROID-W 深度生成伪 GT。
没有把语义/instance 当成已读取的稠密标注；本轮相应可用性仍为未核验。
这不意味着官方 VIPER 从未提供其他模态，只说明本轮已审计本地资产不含所需深度。
val_007 是 Night、487 帧 stride=1 的历史样本，不重新运行 SLAM。

## MVS-Synth：一条完整 RGB/Depth/Pose 序列

路径：D:\aaa\GameCam-VO\data\mvs_synth\GTAV_540\0000。
实际读取 100 PNG +100 EXR +100 JSON。RGB/GT 均为 960×540，EXR 的 Y 通道为 float16，
45,412,636 个有限正深度，6,427,364 个 +Inf，NaN 为 0。官方说明 sky 为 +Inf，保持原值并排除评价。
GT 来源独立于 R1，但单位到米的换算未建立。frame0000 的有限正深度中位数 223.125 是 native game unit，不能写成米。
相机 JSON 的 W2C 上块 determinant 约 -1；直接相对变换 Et @ inv(Es) 保留其坐标约定，没有强行改成 SO(3)。

300/300 文件当前 SHA 与既存镜像清单一致。镜像 revision c886d86505054f18f79d0a1c838150d9e98935b2；
历史官方子集 13/13 当前复核一致，官方 revision 73e4b0abff2806a67c0f9bc038c3a1ac5df9ef0b。
没有把 13 文件官方对照扩大描述为 300 文件全部官方逐字节核验。
另有 0001/0039/0079/0119 的 12 张 RGB 预览，但没有相应完整 GT，不能作为独立测试集。

[作者页面](https://phuang17.github.io/DeepMVS/mvs-synth.html)描述 GTA-V 的 120×100 帧 RGB/EXR/相机数据，
540p 归档约 9GB，research/educational use。没有新增下载；完整论文与数据的许可、单位仍需按来源分别核验。

## 实际多视图一致性诊断

网格每 8 像素采样，使用 target 最近邻深度，不缩放 EXR。比较 Z-depth 与 ray-range 假设，报告遮挡/采样边界影响。

| 对应帧 | Z 假设中位相对差 | ray-range 中位差 | Z 差 <1% 比例 | 解释 |
|---|---:|---:|---:|---|
| 0000→0001 | 约 1e-15 | 约 9e-16 | 100% | 相机几乎静止，不能区分 Z 与 range |
| 0049→0050 | 0.00087188 | 0.0267152 | 97.329% | 非零基线，支持 Z-depth 与网格对应 |
| 0098→0099 | 0.00089048 | 0.0317710 | 92.337% | 非零基线，同样支持 Z-depth |

错配 target-depth 对照的 Z 中位差分别约 0.45257 和 0.78070，远大于正确配对。
0→1 的平移只有 2.34e-13 native units；其小误差不能当作有效可观测性证据。
此处约 0.09% 是 **GT 跨视图数值一致性**，不是 Metric3D 误差或独立采集时钟/米制准确性证书。
光栅化、遮挡、动态物体、EXR HALF 量化以及最近邻采样均可能影响残差。

## 评价网格与有效 mask

准入后在原始 GT 网格评价，保留有限正 GT，Inf sky 不参与。原始深度不重写、不填空、不截成看似有效的常数。
输出 depth/score 使用显式相同 unpad/crop 对应，GT 不做 bilinear 混边；物体边缘作为独立分层。
有效 GT 上非有限/非正预测必须保留失败信息并停止该 sample，不能过滤后报告漂亮指标。
深度分层范围要在单位核实后冻结；不能把当前 native-unit 数值直接命名为近/中/远米制阈值。

## 划分与准入

当前唯一完整序列 0000 只做数据审计，未拟合 scale、confidence calibration 或选择阈值。
不能随机拆相邻帧形成伪独立 Calibration/Test。单条序列未来可以作探索性评价，但不能同时校准与独立验证。
未知单位不意味着永远不能做排序研究：可先获得可信的物理换算，或预注册仅在校准序列拟合一个全局数值单位映射，
再在另一完整序列测试，并明确该操作不证明物理米制。当前两个条件均不足，严格误差阶段保持停止。

DATA_ADMISSION.json、MVS_PROVENANCE_OBSERVABILITY_ADDENDUM.json 和逐帧 manifest 给出全部范围与原始 SHA。
图 R2_03_DATA_ALIGNMENT_EVIDENCE.png 是真实 RGB/GT/mask，未包含任何模型预测。

# TASK006A-R2.1 最终评审

 **实际 GPU 推理已完成；正式绝对米制 GT 评价仍阻断；不接入 CADP，不进入 TASK007。**

 - RTX 3090 24GB；已验证新 SSH 31136 的原可信主机密钥，没有重启、修改驱动或更换环境。
 - 16 张唯一 RGB：VIPER 五环境各 2 张，共 10 张；MVS 两序列各 3 张，共 6 张。
 - 成功阶段共 33 次前向：单张 Smoke 3 次（含无 hook 对照）+15 张 Pilot 各 native/flip 两次。
 - 单帧 hook/no-hook 的 depth、confidence 最大绝对差都为 0；实际 bins=256，网格154×266。
 - 全部原始 Confidence 有限，但范围约 -2.518557～6.544111，不是概率。
 - 最新 CPU 套件 61+13=74 项通过；一次完整 CPU 数值复算的重复结果另有 SHA 比对收据。

 下表仅来自**单序列标定后的次级诊断**：Calibration0000 拟合单一 scale，Test0001 的 3 帧宏平均。
 不能当作 Metric3D 原始米制零样本成绩，不能当作跨场景显著性。

 | 信号（预先约定高值=风险） | AUROC，AbsRel>0.2 ↑ | AUSE raw AbsRel ↓ | Spearman(error,risk) ↑ |
 |---|---:|---:|---:|
 | NativeConfidence | 0.812184 | 0.070793 | 0.209430 |
| FlipRelative | 0.675236 | 0.064586 | 0.237490 |
| InitialBinEntropy | 0.276615 | 0.165091 | -0.234103 |

 Native 更善于该高误差事件识别；Flip 的 AUSE 略低。因此没有一个信号在全部指标上支配其他信号。
 初始 entropy 按预定方向表现反向，没有根据 Test 结果翻转其符号；不能直接当最终深度风险。

 新取得第二条完整序列（100 RGB+100 EXR+100 pose，85,484,738 bytes），300 文件镜像身份核验通过，
 与旧序列无精确 RGB 重复。限定官方归档前缀比对 5/5 文件一致，**不是300文件官方认证**。
 作者公开单位问题没有明确答复；MoGe 的 depth_unit=0.1 是其他预处理管线的约定，未证明本项目 raw EXR 的物理换算。

 另外，MVS0001/0099 有 7 个有效 GT 上的零预测：canonical 为正，bicubic 恢复负值被原生 clamp 归零。
 原严格入口确实停止，未放宽门禁伪称 PASS。次级诊断完整保留这些错误及 infinite log error。

 **决策：GPU 工程验证 PASS；继续独立先验质量研究 CONDITIONAL GO；接入联合控制器 NO-GO。**
 详见 [完整报告](R2_1_FINAL_RESEARCH_REPORT.md)、[GT与协议限制](05_reports/GT_ADMISSION_AND_LIMITATIONS.md)、
 [原始数据索引](04_evaluation/diagnostic_zero_extension_002/RAW_OUTPUT_INDEX.json)。

# TASK006A-R2.1｜真实 GPU 小样本验证

**GPU_PILOT_COMPLETE / FORMAL_GT_ACCURACY_BLOCKED / CADP_INTEGRATION_NO_GO。**
16 个独立 RGB 样本，33 次真实模型前向，74 项 CPU 评价/空间与真实输出回读测试通过。
没有运行 SLAM，没有训练/微调网络，没有修改模型权重或生产源码。

请先读 [FINAL_REVIEW.md](FINAL_REVIEW.md) 与 [完整研究报告](R2_1_FINAL_RESEARCH_REPORT.md)。
完整包包含本轮全部 16 份原始推理 NPZ（包括一份真实 raw-bin logits）、配置、日志、阶段失败记录、
GT 来源/哈希、CPU 代码、结构化指标和图。原始 RGB/GT 数据集不随评审包分发。

严格 GT 入口在零预测处按合同停止。另行标注的 secondary diagnostic 保留七个零预测为 AbsRel=1，
保留 infinite log error，不删点、不重写原始 TTA NaN。其结果不是严格门禁通过或物理米制认证。
Calibration 0000 与 Test 0001 分开；全局 scale 只在 0000 拟合，未用 0001 调参。
图像与数字反映小规模、一个 held-out GT 序列，不能授予 VIPER Night 准确性结论。

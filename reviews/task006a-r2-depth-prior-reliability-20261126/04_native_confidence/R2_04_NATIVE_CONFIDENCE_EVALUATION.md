# R2-4 Native Confidence 评价状态

**NOT_EXECUTED — GPU_UNAVAILABLE / GT_ADMISSION_INCOMPLETE。**
没有得到 native confidence map，因此没有 Spearman、Pearson、AUROC、AUPRC、AUSE、AURG、ECE 或模型失败案例。
空 CSV 数值不是零。不能回答 Night 是否可靠，也不能据源码监督风险宣布已经失败。

已实现并实际测试独立 CPU 评价器 reliability_metrics.py；61 项合同与数值测试通过。
AUROC 使用 tie-aware rank；AUPRC 明确定义为 average precision（阶梯 recall 积分），与 sklearn 对照。
单类别事件返回 UNDEFINED，不填入虚假 0/1；恒定信号的相关系数同样未定义。

后续固定方向：raw c 越高应越可靠；用于高误差检测的 risk=-c。
同时保留 error-vs-c 的原始相关性。若方向相反，报告相反，不根据测试结果静默翻向。
AbsRel 和 absolute log error 需要独立正深度 GT、像素对齐、坐标约定与匹配单位全部准入。
error>0.1/0.2/0.5 全部报告，不挑最有利阈值。

Risk-Coverage 以保留 k/N 像素的 mean AbsRel 定义，score ties 用均匀置换的期望前缀风险。
AUSE=积分(risk-oracle)，AURG=积分(random-risk)，本实现使用原始 AbsRel，不是归一化论文指标。
恒定分数恰好等于 random baseline，避免 tie 的输入顺序带来虚假提升。
以 coverage=0 的右极限补点后梯形积分；不同定义的论文数字不能直接横比。

分桶图只能称 score-error diagram，不能称概率 reliability diagram。
ECE 需明确定义 P(error<=t)，在序列隔离的 Calibration Split 拟合后，才允许在 Test 评价。
工具会拒绝 calibration/test 序列交叉；尚未执行校准。
近/中/远、纹理、边缘/平面、物体边界分层与天气分层待有 GT 后预注册。
语义类别需要真实标签，不用图像直觉冒充 semantic GT。

Bootstrap 按独立序列重采样，先算每序列指标再做等权 macro。
一条序列的 frame bootstrap 最多描述同一场景内不确定性，不能代表跨环境泛化；本轮不提供此类置信区间。

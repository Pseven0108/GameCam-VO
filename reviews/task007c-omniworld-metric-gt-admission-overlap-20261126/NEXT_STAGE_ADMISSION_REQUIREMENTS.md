# 下一阶段准入条件与停止位置

本轮不自动进入Metric3D Confidence真实推理或统计校准。

1. 取得现有Metric Scale因子的生成来源，以及目标UID独立物理锚点/精度证据；
   或由用户明确批准不同目标，只研究源缩放参考/尺度不变形状，不声称米制校准。
2. 解决RGB与Depth逐像素/动态边缘对齐和同步的可量化验证；不能用观察3张缩略图代替。
3. 建立3个严格TP且场景来源分离的Calibration/Development/Evaluation组；
   当前开发组空缺，已观察材料保持标记，最终测试不拟合。
4. 将Metric3D精确训练成员未知列为局限；VKITTI家族明确列为有重叠，不能作为训练未见结论。

以上通过且另获阶段授权后，才按硬件分工：本地RTX5060做小批量实测、3090做正式实验。
本轮不联系作者、不再下载、不训练Scalix、不改Metric3D/DROID-W、不启动CADP/Confidence-aware BA。

# R2-8 对照：当前没有可宣告的实测优胜者

| 方法 | GT 排序/高错识别 | 校准 | 额外 forward | 当前证据 |
|---|---|---|---:|---|
| Native Confidence | 未执行 | 未执行，非概率 | 0 | 完整关键生成/监督源码 |
| Flip TTA | 未执行 | 未执行 | 1 | 独立 CPU 评价器、反例 |
| Depth-bin statistics | 未执行 | 未执行，非最终后验 | 0（hook 及统计另有成本） | 实际 256 bins 与公式测试 |
| Gradient uncertainty | 按条件延后 | 未执行 | 通常额外 1 加 1 backward | 论文与官方入口研究 |

Native score 与深度共 forward，理论额外推理最少；实际热图/搬运开销未测。
不能由计算量推导可靠性，也不能由训练 mask 风险推导失败。
夜间/雨雪/低纹理/远距表现、TTA 独立增益、bin 独立增益、校准必要性、系统性盲区均为未建立。
R2 用合成 wrong-but-consistent 反例验证了评价逻辑的必要性，没有声称该现象已在 Metric3D 实际发生。
当前不选择组合权重或融合网络，不进入 CADP/BA。

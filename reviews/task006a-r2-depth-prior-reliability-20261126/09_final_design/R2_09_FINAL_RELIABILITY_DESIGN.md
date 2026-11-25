# R2-9 独立质量接口候选（DESIGN_ONLY / NOT_ADMITTED）

当前不发布经过校准的 prior reliability。仅定义可审计的实验输出结构，禁止接入优化。

输入：RGB uint8 H×W×3；sample/sequence ID、RGB SHA；输入 K/fx、输入尺寸、原生预处理记录；
固定 model commit/checkpoint SHA。真实 depth GT 只进入离线 evaluator，不进入推理。

输出候选：

| 字段 | dtype/形状 | 范围/方向 | 约束 |
|---|---|---|---|
| depth | float32 H×W | 深度，单位必须声明 | 与 baseline 恢复规则相同并记录 clamp |
| native_confidence_raw | float32 H×W | 未限定范围；预期高值可靠 | 不强行 sigmoid，不称概率 |
| native_confidence_canonical | float32 616×1064 | 原生 score | 保留原始值和 padding 信息 |
| flip_relative_disagreement | float32 H×W | >=0，高值表示不一致 | 仅追加推理后可填；不是误差 |
| flip_log_disagreement | float32 H×W | >=0，高值不一致 | 同 fx、恢复方向、mask |
| bin_entropy | float32 低分辨率网格 | [0,log K]，高值分散 | 不是最终深度后验 |
| bin_variance | float32 同 bin 网格 | >=0，canonical unit squared | 必须保存 actual anchors |
| validity | bool H×W | 有效/无效 | confidence 无效必须独立标记 |
| probability_good_depth | optional float32 H×W | [0,1] | 仅有独立校准及事件定义时存在 |
| frame_summary | JSON | quantiles、无效率、事件统计 | 不把未校准分位数称正确概率 |

Confidence 非有限或 depth 非正/非有限时保留失败记录与独立 valid 标识，不把无效值映射为最高可靠度。
Frame-level quality 暂不聚合成固定 rho；公式及阈值需要独立测试后确定。
校准元数据必须包含事件、方法、calibration/test sequence IDs、单位、适用场景、SHA 与版本。
无 GT 的 VIPER 分布观察只能说明输出变化，不能授予准确性或 Night 使用范围。
当前所有环境都处于 accuracy UNVERIFIED，已知失效场景尚未由模型实验建立。

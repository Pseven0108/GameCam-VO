# 深度恢复：独立数值修复与实现验证

## 问题与隔离

R2.1封存canonical深度均为正值。DROID-W wrapper去padding后使用bicubic恢复，再fx/1000、clamp[0,300]。
cubic插值核含负系数，在正值深度不连续处可以下冲为负。截零只隐藏负值，并非有效正深度。
本轮固定canonical预测，只在独立评估器把恢复核换成bilinear。

输出坐标到源像素中心为u=(x+0.5)W_in/W_out-0.5；边界采用edge extension。
bilinear输出是四个相邻源值的非负权重凸组合：
z'=(1-a)(1-b)z00+a(1-b)z01+(1-a)b z10+ab z11。
对有限严格正值源深度，恢复不会产生负值或零。本实现拒绝不合法canonical输入，
不用epsilon、掩码或其他像素填充伪造正值；Confidence可为任意分数，另走通用插值函数。

## 实际验证

- 原生PyTorch2.1.0+cu118环境中，只用CPU tensor和F.interpolate；CUDA_VISIBLE_DEVICES为空。
- 没有模型导入、checkpoint反序列化、CUDA API或前向。
- 16图×Native/Flip=32图，旧bicubic CPU与保存GPU值最大差≤1.5258789e-5，均通过原对照容差。
- Confidence的CPU重放与保存值逐位一致（最大差0）。
- 独立NumPy float32坐标/权重复算32图，全部满足rtol=3e-5、atol=3e-4，最大绝对差0.000968933。
- 6个独立CPU fixture覆盖单行、单列、单像素、非整数比例、降采样和恒等映射。

初版float64坐标算术与float32原生结果比较，有940个像素超过上述容差、最大差约0.006105。
失败记录保留；依据原生dtype实现float32算术后通过，未放宽标准。
此处PASS表示约定混合容差内一致，不能写成逐位相同，也不是GPU生产接入认证。

## 结果

32图旧负值与截零237个→0；有效MVS GT上的Native零值7个→0。
七个位置全部列在`04_evaluation/ORIGINAL_SEVEN_ZERO_PIXELS.csv`，原始坏预测完整保留。
恢复后它们的AbsRel仍约0.0499–0.5590；修复正值不保证每个深度准确。

## 原图网格

MVS GT/RGB为960×540，已直接恢复到其原图网格。
VIPER模型输入640×360，原RGB1920×1080；五环境各保存canonical→input→source两步恢复示例。
这只是图像网格放大，不凭空增加深度细节，不因第二次图像放大再次乘深度单位。
没有VIPER配对深度GT，本轮不评价VIPER绝对深度准确性。

源码：`code/depth_restoration.py`、`code/common.py`、`code/remote_cpu_restore.py`。
数值证据：`02_restoration/INTERPOLATION_INDEPENDENT_VALIDATION.json`及原生CPU收据。
生产DROID-W wrapper、CUDA、权重、R2配置均未接入或修改。

# R2-5 Flip TTA

**真实模型未执行。** 无单帧/双帧推理时间、GPU 型号实测、显存或正确率数据。
两次 forward 是理论调用次数，不能宣称耗时恰为两倍。

保留整个输入原图，沿水平方向 flip 后使用与 native 完全相同的 resize/normalize/padding。
先分别 unpad 并恢复到相同原始网格，再 flip 回第二个输出；非对称 padding 不能直接在 canonical map 上逆转。
fx 在水平翻转中不变；完整 K 的主点若涉及几何处理应采用 cx'=W-1-cx，并记录像素中心约定。
当前 Metric3D 包装器只把 fx 用于 depth canonical 恢复，不把完整 K 作为 model 输入。
native 与 flip 的 fx/1000 必须相同，不逐帧或逐图拟合 scale 以减少差异。

指标：abs(D1-D2_restored)/(abs(D1)+eps)；另记录 abs(log(D1+eps)-log(D2_restored+eps))。
Confidence 同样保留 raw 两份及 flip-back 后差异；不做无依据的概率变换。
CPU 测试覆盖正确逆转、padding 奇数边界、zero-bottom-pad、防止无效深度被变成可信零。
一个模型两次都预测 2×GT 时 flip disagreement=0，真实 AbsRel=1；这一合成反例说明一致性不等于准确性。

真实增益需用同一独立 GT/valid mask，与 Native Confidence 配对评价，边缘带单独报告。
Native+Flip 的任何参数只能在独立 calibration 序列确定。当前没有拟合组合，也没有入选组合模块。

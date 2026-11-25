# R2-1 Metric3D 原生 Confidence 源码结论

**生成与监督路径已确认；实际输出统计未测。** 所有行号对应 eb5b6fac0dc155e4e52f576e304fbf11655ff339 快照。
代码保存在 evidence/sources/Metric3D-eb5b6fac，SHA 见 SOURCE_COPY_MANIFEST.json。

## 身份与预处理

283 个实际缓存文件与官方 Git blob 对应；权重 SHA 为 15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972。
DROID-W loader 使用 torch.hub.load("yvanyin/metric3d", depth_model, pretrain=True)，没有 revision 锁定。
当前真实缓存 HEAD 不能用入口注释中的旧提交代替。

输入形状 B×3×H×W，ViT Large canonical 616×1064。按 min(616/H,1064/W) resize，整数尺寸，
ImageNet normalize 后以零填充，左右/上下余数保留。输出深度先移除相同 padding，再 bicubic 到原网格，
乘实际输入 fx/1000，并 clamp 到 [0,300]。源码在 DROID-W-runtime/metric_depth_estimators.py:121–164。
这些是现有代码规则，不能根据它自动确定外部 GT 的米制单位。

## Confidence 生成链

1. mono/model/monodepth_model.py:10–13 的 inference 返回 depth、confidence、output_dict；入口使用 no_grad。
2. decode_heads/RAFTDepthNormalDPTDecoder5.py:915–930：ViT/DPT 的 ref_feat 分解为共享深度/法线特征、
   深度 confidence 初值、normal confidence 初值。深度 confidence 是独立通道。
3. 同文件 FlowHead:314–327 输出线性增量；959–984 在每次 RAFT 中把增量加入坐标状态，
   其中深度 confidence 与深度共同迭代更新。最后一次（第 8 次）confidence 随最终 depth 返回。
4. 858–872 的 mask softmax 用于局部凸上采样；983–995 从上采样状态第 1 通道取 depth confidence。
   softmax 不是对最终 confidence 进行概率归一化。GRU 的 sigmoid gate 也不是输出 confidence sigmoid。

深度 confidence 没有末端 sigmoid/softmax 或固定 [0,1] 约束，不能直接作为正确概率、方差或标准差。
源码允许无约束实数，但本轮没有推理，不能声称实测有负值、极值、NaN 或 Inf。
静态预期 canonical 形状 B×1×616×1064；实际 shape、min/max/quantiles 一律待测。
研究脚本会保存原始 map；恢复到输入网格使用同一 unpad 后 bilinear，避免 bicubic 对 score 额外过冲。
这是显式研究选择，不冒充上游已有 confidence resize 生产规则。Confidence 不乘 fx/1000。

## 训练监督的精确定义

training/mono/model/losses/GRUSequenceLoss.py:33–37 中，令 t 为 GT target，z 为 prediction：

M = valid_mask AND (abs(t-z) < t)

c_target = (1 - abs((z-t)/t)) * M

L_conf = sum(abs(c - c_target) * M) / (sum(M) + eps)

误差分母是 GT t。相对误差 >=1 的位置被这项 confidence loss 排除，
并不是以零 confidence 作为有效监督。有限正 GT 域的独立复算测试确认：改变这些被排除位置的 c，不改变该项 loss。
这是监督盲区风险，**不是已经观察到测试 Confidence 失败**。其他深度/法线损失仍可能影响共享表示。
同文件 84–98 逐次迭代应用 confidence loss。

官方 training 配置列出 GRUSequenceLoss loss_weight=0.5、loss_gamma=0.9、stereo_sup=0.0，
混合实拍和合成深度数据，法线使用独立 loss。配置不能证明指定 checkpoint 的全部训练历史，
也不能证明 VIPER 的 Night、Rain、Snow 已充分覆盖。

## 四种不确定性必须分开

| 信号 | 来源/约束 | 本轮允许的解释 |
|---|---|---|
| Depth confidence | RAFT 更新的单通道，输出不受 [0,1] 约束 | 待实测的预测质量 score |
| Normal confidence | normal 输出第四通道，ELU(raw)+1+0.01 等正值变换（237–243） | 法线集中度相关量，不是深度置信度 |
| DINO/FiT3D U | DROID-W 特征与优化反馈状态 | 不能冒充独立深度误差标签 |
| R1 几何协方差 | prior-off Schur 系统及原生阻尼 | 几何模型量，不是原生 Confidence GT |

## Depth-bin 与输出字典

同文件 761 显式定义 256 anchors，794–836 为 log 间隔 anchor、logit softmax 和初始深度期望。
anchor 由真实配置产生，不能用随意线性 bin 代替。实现的 get_bins 硬编码 CUDA；
本地 CPU-only 且无 Torch 环境不适合伪装成完整官方 CPU 推理。
最终 output_dict 的 pred_logit=None（987–995），即使前面计算了 binmap。
独立只读 forward hook 可读取 depth_regressor 输出，必须返回 None 且验证不改变模型输出。

## 入口丢弃行为及未决问题

DROID-W-runtime/metric_depth_estimators.py:150 附近使用 pred_depth, _, _。
可确认的是没有传播/保存 native Confidence；丢弃的设计理由没有直接证据，不填成 CONFIRMED。
输出数值审计和真实 heatmap 因 GPU 不可用未执行，见数值 CSV。

官方固定来源：
[decoder](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/mono/model/decode_heads/RAFTDepthNormalDPTDecoder5.py)、
[confidence loss](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/training/mono/model/losses/GRUSequenceLoss.py)、
[模型接口](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/mono/model/monodepth_model.py)。

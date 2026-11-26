# TASK006A-R2.1｜GPU 恢复与 Metric3D 真实推理验证

 2026-11-26，GameCam-VO。**GPU 阶段完成，正式 GT 准入部分阻断。**

 ## 研究结论

 1. 实际 GPU 可用，固定权重的 Metric3D 在独立脚本中完成了 16 张图的三候选输出。
 2. Native Confidence 有实测的误差排序信息，但仅在一次单序列标定后的 held-out 小样本诊断中建立。
 3. 不能证明 Night、Rain、Snow 中的准确性：这些 VIPER 样本没有被独立深度 GT 评价。
 4. Flip 在 continuous risk-coverage 上略优，而 Native 对 AbsRel>0.2 的识别更强；组合独立增益没有测试。
 5. 初始 bin entropy 的预定风险方向在此诊断反转；未翻号或选择有利阈值救结果。
 6. 原始 Confidence 不是概率，简单跨序列概率映射也没有获得可靠校准证书。
 7. **现在不接入 CADP 或 BA，不进入 TASK007。** 先解决物理单位、原生深度恢复的零值及独立 GT 扩展验证。

 ## GPU、环境和身份

 新可信 SSH：sc01-ssh.gpuhome.cc:31136；原用户确认的 ED25519 指纹核验成功。
 GPU RTX3090，UUID GPU-18dd1d45-8dca-2400-dddb-af8cd9bd5fae；启动前空闲24,125 MiB，无其他计算进程。
 驱动580.119.02，nvidia-smi 显示支持CUDA13.0；PyTorch实际构建为2.1.0+cu118、CUDA11.8。
 这是驱动能力与框架构建的区别，没有安装或替换 CUDA。
 /dev/shm=24 GiB；起始数据盘空闲12,522,430,464 bytes，独立输出期间保留10 GiB安全余量。

 Metric3D commit eb5b6fac0dc155e4e52f576e304fbf11655ff339，工作区 tracked clean；
 checkpoint 1,647,972,663 bytes，SHA-256：15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972。
 DROID-W 生产入口 SHA 与封存版本一致。该源码目录不含 .git，本轮不将其 git 查询失败伪称 HEAD 验证成功。
 本任务不运行 DROID-W，只审查入口及独立调用 Metric3D。

 ## 单帧 Smoke 与兼容性修正

 初次严格加载在 missing key `depth_model.encoder.mask_token` 停止，前向次数0。
 沿实际 ViT_DINO_reg.py 确认该参数原生零初始化，只在 masks!=None 时读取，普通 RGB 推理不进入该分支。
 独立启动器只允许这一条 missing key，其余缺失/多余键仍停止；增加 encoder 输入只读检查，全部33次记录 masks=None。
 没有删除模型参数、重写 checkpoint 或更改原模型代码；初始失败与两个成功阶段均保留日志。

 单帧 Night val007/00001：native_without_hook、native_with_hook、flip_with_hook。
 前两次输出 depth/confidence 逐位一致，max abs diff=0。hook 返回 None，只采集 depth_regressor 输出。
 实际 canonical 输出1×1×616×1064，原生 bins256×154×266。真实 logits 的 CPU 独立熵/方差/期望复算通过。
 保留一份原始 bin logits，所有16样本保留原生输出和实际 anchors/派生统计，未用随机图代替。

 ## 样本和预处理

 VIPER：Day001、Night007、Sunset008、Rain018、Snow021，每个环境取冻结首段的首帧和时间中点。
 Night 首帧在 Smoke 使用，Pilot 不重复计入唯一图片。VIPER 使用既有640×360 INTER_LINEAR与冻结fx，
 MVS使用原始960×540和该帧fx。样本清单在预测误差查看前固定。
 两者进入相同原生616×1064 resize/normalize/pad；深度遵循现有 wrapper 的 unpad/bicubic/fx/1000/clamp[0,300]。
 Confidence 同 unpad 后 bilinear，保持 raw 数值，不乘深度尺度、不加 sigmoid。
 翻转在原输入图像上执行，分别恢复至输入网格后反向翻转输出；没有在非对称 padding 的 canonical 网格上直接翻回。

 ## 实测数值与开销

 16份原生恢复后的 Confidence 总体最小 -2.51855707，最大 6.54411077，
 Confidence NaN/Inf 数量均0。完整 min/max/mean/median/SD/分位数与环境分组在 OUTPUT_NUMERICAL_AUDIT.csv。
 大于1或小于0是当前无约束 score 的实测，不应直接称模型故障，也不应解释为概率。

 native+hook 前向中位 0.449751s，flip+hook 中位 0.448570s，
 峰值 allocated=2,515,347,456 bytes，reserved=2,816,475,136 bytes。
 首次无 hook 冷前向1.004974s。时延包含该 forward 的 hook 同步/取值，不包含全部PNG解码、CPU统计和归档时间；
 冷/热与 hook 不同，不能据此宣称 hook 免费或求严格增量时延。
 TTA确实多执行一次前向，不推断整套SLAM速度恰为两倍。

 ## GT 来源与正式准入

 复用旧 MVS0000；限定获取 pinned mirror 的完整0001，共300文件85,484,738 bytes，全部按LFS SHA/Git blob核验。
 100个RGB/100个EXR/100个pose完整解码；41,827,301有限正GT，10,012,699 Inf sky，NaN0。
 两序列无精确RGB哈希重复；仅证明sequence身份区分，录制会话与物理相机独立性UNKNOWN。
 固定官方归档流读取180,000,000 bytes即停止，5个完整目标成员与镜像一致；没有下载10.49GB全包或认证全归档CRC。
 新数据总payload265,484,738 bytes（约253.2 MiB，元数据另计），没有扩展整个数据集。

 新序列Z-depth跨视图中位差约0.08%～0.11%，支持网格/深度-相机的一致性；不证明米制或物理时钟。
 作者单位讨论[issue25](https://github.com/phuang17/DeepMVS/issues/25)没有建立换算；
 作者曾确认历史540p对齐问题，当前样本是960×540且进行了实际投影诊断，不能把历史问题直接套到全部当前文件。
 [Microsoft MoGe配置](https://github.com/microsoft/MoGe/blob/74fbce054ebed49800de42d0ad0e83495065719a/configs/train/v2.json)
 使用MVS depth_unit=0.1，但其预处理到本项目raw EXR的单位链没有核实，不能当作创作者米制证明。

 ## 严格门禁失败与次级诊断

 原严格评价在任何GT有效位置出现非正预测时停止，确实捕获 Test0001/0099 的7个零值。
 canonical最小为0.100006，bicubic恢复后unclipped最小为-3.769418，再被既有clamp归零。
 保留 STRICT_GT_GATE_FAILURE.json；没有修改模型或把它标成PASS。
 零值位置的 raw confidence 中位约0.9075，但这是恢复管线制造的错误，不能只归因网络confidence训练。

 为保留研究价值，在未拟合scale或查看GT排序结果前，记录了独立的次级修订协议：
 对有限非负预测，AbsRel按原数学式计算，零值为1；log error为+Inf，保留数量与空均值状态。
 TTA用用户给定的epsilon公式从不变原始两份深度重新算，含零值；原始TTA中的NaN不覆盖。
 所有有效GT点保留，未删除七个坏点。此分析明确为 **SECONDARY_ZERO_EXTENDED_DIAGNOSTIC**，不是原门禁通过。

 ## 单序列校准后的结果

 Calibration0000的三帧拟合一个全局正scale=15.9855070375，冻结后应用Test0001三帧。
 此scale同时吸收模型偏差与数值单位差，不是物理米制换算证明，不是原始Metric3D零样本精度。
 没有为测试帧、候选信号或初始深度另拟合scale。GT有效mask仅为有限正值，没有为了指标选深度上限。

 | 候选，预定高值表示风险 | AUROC，AbsRel>0.2 ↑ | AUSE raw AbsRel ↓ | Spearman(error,risk) ↑ |
 |---|---:|---:|---:|
 | NativeConfidence | 0.812184 | 0.070793 | 0.209430 |
| FlipRelative | 0.675236 | 0.064586 | 0.237490 |
| InitialBinEntropy | 0.276615 | 0.165091 | -0.234103 |

 三个高误差阈值0.1/0.2/0.5都保留，AUPRC明确定义为average precision。
 Native在0.2事件识别更好，Flip的连续误差风险排序/AUSE略好，不能只选有利指标断言全面胜出。
 Entropy的预定方向在测试反向；没有Test翻号救结果，初始entropy也不是最终深度误差后验。
 保留每帧、距离tercile/纹理/边缘代理分层，不把像素当独立样本或给跨序列显著性；测试仅1个序列。

 单维概率后处理只在Calibration0000的stride8网格拟合，事件为scale后AbsRel>0.2，风险系数约束非负。
 Native测试ECE约0.124～0.214，简单校准没有取得跨场景可靠证书。
 Entropy映射可退化为常数基准率，某帧ECE较低不说明它有排序能力；需与AUROC/Brier一起解读。
 没有把raw score直接算概率ECE，没有训练新网络。

 ## 决策和下一步

 **运行能力PASS；独立先验质量研究CONDITIONAL GO；联合控制器/优化接入NO-GO。**
 Native值得优先继续验证，Flip作为对照保留；目前不选择组合，不以初始entropy直接控制深度先验。
 恢复物理GT单位链、独立更多序列、明确零值处理及新的预注册协议后，再进行正式准确性评价。
 0001已经被本轮观察：若据其结果改方向、组合或阈值，需新的未见序列，不能再称0001为新盲测。
 不自动进入TASK007/CADP，不运行SLAM，不训练或微调，不重启/关机本实例。

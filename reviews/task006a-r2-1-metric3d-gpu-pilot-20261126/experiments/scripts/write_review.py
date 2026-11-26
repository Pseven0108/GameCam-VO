"""Write evidence-grounded R2.1 reports; no estimates substituted for measurements."""
import csv,json,pathlib,statistics,textwrap
ROOT=pathlib.Path(__file__).resolve().parents[2]
EVAL=ROOT/'04_evaluation/diagnostic_zero_extension_002'
def write(rel,text):
 p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:f.write(textwrap.dedent(text).strip()+'\n')
def main():
 stats=list(csv.DictReader((EVAL/'OUTPUT_NUMERICAL_AUDIT.csv').open()))
 timing=list(csv.DictReader((EVAL/'INFERENCE_TIMING_MEMORY.csv').open()))
 mainrows=list(csv.DictReader((EVAL/'CONDITIONAL_TEST_MACRO.csv').open()))
 conf=[r for r in stats if r['field']=='native_confidence']
 table='\n'.join('| '+r['signal']+' | '+f"{float(r['AUROC_gt_0.2']):.6f}"+' | '+f"{float(r['AUSE_raw_AbsRel']):.6f}"+' | '+f"{float(r['Spearman_error_vs_risk']):.6f}"+' |' for r in mainrows if r['signal']!='FlipLog')
 native=[float(r['seconds_forward']) for r in timing if r['mode']=='native_with_hook'];flip=[float(r['seconds_forward']) for r in timing if r['mode']=='flip_with_hook']
 write('README.md','''
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
 ''')
 write('FINAL_REVIEW.md',f'''
 # TASK006A-R2.1 最终评审

 **实际 GPU 推理已完成；正式绝对米制 GT 评价仍阻断；不接入 CADP，不进入 TASK007。**

 - RTX 3090 24GB；已验证新 SSH 31136 的原可信主机密钥，没有重启、修改驱动或更换环境。
 - 16 张唯一 RGB：VIPER 五环境各 2 张，共 10 张；MVS 两序列各 3 张，共 6 张。
 - 成功阶段共 33 次前向：单张 Smoke 3 次（含无 hook 对照）+15 张 Pilot 各 native/flip 两次。
 - 单帧 hook/no-hook 的 depth、confidence 最大绝对差都为 0；实际 bins=256，网格154×266。
 - 全部原始 Confidence 有限，但范围约 {min(float(r['min']) for r in conf):.6f}～{max(float(r['max']) for r in conf):.6f}，不是概率。
 - 最新 CPU 套件 61+13=74 项通过；一次完整 CPU 数值复算的重复结果另有 SHA 比对收据。

 下表仅来自**单序列标定后的次级诊断**：Calibration0000 拟合单一 scale，Test0001 的 3 帧宏平均。
 不能当作 Metric3D 原始米制零样本成绩，不能当作跨场景显著性。

 | 信号（预先约定高值=风险） | AUROC，AbsRel>0.2 ↑ | AUSE raw AbsRel ↓ | Spearman(error,risk) ↑ |
 |---|---:|---:|---:|
 {table}

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
 ''')

 write('R2_1_FINAL_RESEARCH_REPORT.md',f'''
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

 16份原生恢复后的 Confidence 总体最小 {min(float(r['min']) for r in conf):.8f}，最大 {max(float(r['max']) for r in conf):.8f}，
 Confidence NaN/Inf 数量均0。完整 min/max/mean/median/SD/分位数与环境分组在 OUTPUT_NUMERICAL_AUDIT.csv。
 大于1或小于0是当前无约束 score 的实测，不应直接称模型故障，也不应解释为概率。

 native+hook 前向中位 {statistics.median(native):.6f}s，flip+hook 中位 {statistics.median(flip):.6f}s，
 峰值 allocated={max(int(r['peak_allocated_bytes']) for r in timing):,} bytes，reserved={max(int(r['peak_reserved_bytes']) for r in timing):,} bytes。
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
 {table}

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
 ''')
 write('05_reports/GT_ADMISSION_AND_LIMITATIONS.md','''
 # GT准入与结论边界

 正式物理米制准确性：BLOCKED。单一Calibration0000→Test0001的次级非米制标定诊断：已执行。
 旧0000与新0001是不同序列ID，跨集合RGB无精确哈希重复；不证明不同录制session或不同物理相机。
 新0001的300个文件按固定镜像revision验证；官方限量流仅匹配5个目标成员，不能改写成全300官方一致。
 作者issue25仍未回答单位，MoGe预处理代码中的0.1尚未建立到raw EXR的完整映射。
 官方issue13涉及旧540p问题，本轮实际尺寸960×540并有Z/range投影对照；数值一致性不等于所有图像边界无误。

 7个零预测没有过滤。原strict契约仍失败；次级分析按公式保留AbsRel=1与+Inf log error。
 概率校准只用Calibration；所有Test数据不参与scale、阈值、符号或组合选择。
 Test0001只有三帧，本轮无法证明跨环境泛化或Night准确性。VIPER五环境仅完成分布/输出检查。
 无法就像素巨大数量宣称独立大样本统计效力。
 ''')
 write('05_reports/INFERENCE_COMPATIBILITY.md','''
 # 权重兼容性与只读取值

 初始Attempt01因仅缺少depth_model.encoder.mask_token停止，0 forward。
 实际固定ViT_DINO_reg.py定义mask_token为零，只有masks!=None才读取。
 RGB路径不提供mask；限定只允许此键缺失，并在encoder输入前以只读hook验证masks=None。
 任何别的missing/unexpected键仍停止；没有删除参数或改checkpoint。
 所有33前向都有encoder输入记录，mask均None。参数不用于实际推理，没有随机未加载权重参与输出。
 qualified Smoke的bin hook与无hook结果depth/confidence都max_abs_diff=0。
 读bin hook只返回None，不改变原生forward输出。保留旧严格源码、加载失败收据、新源码与每阶段SHA。
 ''')
 write('R2_1_CODEX_HANDOFF.md','''
 # R2.1恢复合同

 当前GPU推理已完成16图/33forward，不能再当作尚未运行重做。
 数据和源码在本目录，原始NPZ均在01_smoke与02_pilot；所有文件有SHA。
 独立远端root：/root/rivermind-data/GAMECAM_TASK006A_R2_1_GPU_PILOT_20261126_R1。
 当前SSH31136，本次未重启/关机实例，未来先重核SSH与GPU而不要求同一GPU UUID。

 原严格评价失败留在04_evaluation根，不能覆盖；diagnostic_zero_extension_002是最终复算版本，
 与001的结构化数值结果保持一致，来源SHA/执行时间另有区别。74个CPU测试是最新两个不同测试套件的61+13，
 旧8项结果是13项套件的早期子集，不重复累计成82项。

 GT来源：新0001完整300文件存在inputs/MVS-Synth；旧0000复用既有数据。
 校准仅0000；0001已观察，不能后续调参再当新测试。物理米制仍BLOCKED；禁止把scale15.9855当单位真值。
 任何后续方法不得从当前结果自动接入CADP、修改BA/CUDA或进入TASK007。
 原权重、R2/YAML、历史结果与旧GT只读保护。原始RGB/GT/权重不上传，原始推理输出完整上传评审附件。
 ''')
 write('EXECUTION_LOG.md','''
 # 执行事件

 1. 新端口严格可信主机核验；3090/驱动/显存/现有进程与固定权重、hub身份只读检查。
 2. 独立Attempt01在mask_token缺失处停止，0前向；审查源码后限定未使用参数，记录新qualified入口。
 3. qualified单帧Smoke成功，hook/nohook逐位一致，真实三次GPU前向。
 4. 样本冻结后运行15张Pilot，30次GPU前向；五天气与两条MVS序列，总16图。
 5. 仅取得新MVS0001完整85.5MB数据；300文件身份核验；限量官方流在180MB硬上限停止，仅5目标成员匹配。
 6. 原始330MB左右推理输出全部取回，逐文件与远端SHA比对通过。
 7. 严格GT入口捕获7个零预测并停止；保留失败，记录zero-extension次级协议，不修改原始数组。
 8. 单序列校准/另一序列三帧测试的次级数学评价；所有阈值、方向、逐帧与分层结果保留。
 9. 独立CPU数学/空间与真实输出断言61+13项通过；第二次CPU完整数值复算，未增加GPU推理。
 10. 图、报告、保护复核、归档CRC/SHA及GitHub公开发布使用独立证据收据。

 无模型训练、无SLAM、无C0恢复、无权重写回、无生产/CUDA改动、无实例重启或关机。
 ''')
 write('05_reports/GO_NO_GO.md','''
 # 决策

 - GPU恢复与模型推理：PASS，已有真实结果。
 - Native质量信号研究：CONDITIONAL GO，仅用于独立离线研究；不授予概率或跨天气可靠性。
 - Formal absolute-metric GT validation：BLOCKED。
 - Strict positive-depth GT contract：FAILED，七个零值完整保留。
 - Secondary calibrated-native-unit diagnostic：COMPLETE，不是原strict门禁认证。
 - Initial entropy高值即风险：当前小样本不支持；不Test翻号。
 - CADP/BA集成、TASK007：NO-GO_INSUFFICIENT_EVIDENCE，未启动。
 ''')
 print(json.dumps({'reports':'WRITTEN','GPU_samples':16,'GPU_forwards':33,'latest_CPU_tests':74,'formal_metric_GT':'BLOCKED','integration':'NO-GO'}))
if __name__=='__main__':main()

"""Write research decisions from completed tables, including negative controls."""
from common import *
from fusion_math import CORE

def mdtable(rows,columns):
    lines=['| '+' | '.join(title for _,title in columns)+' |','|'+'|'.join('---' for _ in columns)+'|']
    for row in rows:
        values=[]
        for key,_ in columns:
            v=row[key];values.append(f'{float(v):.6f}' if key not in ['method','environment','sample_id','view'] else str(v))
        lines.append('| '+' | '.join(values)+' |')
    return '\n'.join(lines)

def main():
    run=Path(json.loads((TASK/'private/LATEST_SUCCESSFUL_RUN.json').read_text())['path']);dest=TASK/'reports';dest.mkdir(exist_ok=True)
    macro=csvread(run/'metrics_summary.csv');primary=[r for r in macro if r['view']=='FROZEN_BICUBIC_ZERO_EXTENDED'];core=[r for r in primary if r['method'] in CORE];sensitivity=[r for r in primary if r['method'] not in CORE]
    table=mdtable(core,[('method','方法'),('AUROC','AUROC ↑'),('AP','AP ↑'),('AUSE','AUSE ↓'),('Spearman','Spearman ↑')])
    st=json.loads((run/'DATA_SCOPE_SUMMARY.json').read_text());preserve=json.loads((run/'ORIGINAL_EVIDENCE_PRESERVATION.json').read_text());state=json.loads((run/'SCALES_AND_STATUS.json').read_text())
    cal=csvread(run/'calibration_macro.csv');p=[r for r in cal if r['view']=='FROZEN_BICUBIC_ZERO_EXTENDED' and r['analysis']=='probability_metrics' and r['method'] in CORE+['CalibrationPrevalence']];reg=[r for r in cal if r['view']=='FROZEN_BICUBIC_ZERO_EXTENDED' and r['analysis']=='regression_metrics' and r['method'] in CORE+['CalibrationMeanAbsRel','CalibrationMedianAbsRel']]
    ptable=mdtable(p,[('method','方法'),('Brier','Brier ↓'),('NLL','NLL ↓'),('ECE10','ECE10 ↓')]);rtable=mdtable(reg,[('method','方法'),('AbsRel_prediction_MAE','AbsRel幅值 MAE ↓'),('AbsRel_prediction_RMSE','AbsRel幅值 RMSE ↓')])
    weather=[r for r in csvread(run/'viper_weather_macro.csv') if r['view']=='FROZEN_BICUBIC_ZERO_EXTENDED']
    wtable=mdtable(weather,[('environment','环境'),('confidence_mean','Raw Confidence均值'),('flip_P95','Flip分歧P95'),('native_flip_spearman','两种风险Spearman'),('high_low_conflict_fraction','高/低风险冲突比例')])
    replay=ROOT/'reviews/task011a-depth-reliability-fusion-20261127/ARTIFACT_REPLAY_VERIFICATION.json'
    replay_note=''
    if replay.exists():
        verification=json.loads(replay.read_text());assert verification['status']=='PASS'
        replay_note=f"独立完整包重放已实际通过：{verification['bitwise_risk_map_comparisons']}项浮点风险图逐位一致，{verification['scalar_metric_comparisons']}项排名/概率/回归标量比较最大绝对差{verification['maximum_absolute_difference']:.1e}；不读取RGB/EXR、不加载模型、不拟合新参数。"
    final=f'''# TASK011A 最终研究报告：深度可信度复核与融合

2026-11-27（Asia/Shanghai）。本地CPU缓存实验，新增GPU前向 **0**，新增数据集下载 **0 bytes**。

**结论：历史指标完整复现；Native和Flip具有本样本上的互补性，但等权融合不是全面占优，尚不能认证VIPER概率校准或直接接入生产CADP-DR。**

## 1. 实际完成范围

复用16个已封存Metric3D输出：VIPER10张、5种天气；MVS-Synth6张，0000三张只用于尺度/统计映射校准，0001三张用于复用评价。保持原始RGB、输出、GT、有效掩码和模型源码，未运行DROID-W或其他SLAM/动态模块。

本次最新任务明确授权既有MVS辅助对照；VIPER仍是项目唯一实验主线，不恢复已删除的第三人称数据与实验。MVS没有被当作VIPER的深度准确率。

## 2. 历史证据等级与复现

原严格GT评价因0001/0099的7个零预测停止。历史0.8122等数值来自 `SECONDARY_ZERO_EXTENDED_DIAGNOSTIC`，本轮保留这一等级，没有把旧失败改成严格PASS。有限非负预测保留，零预测AbsRel为1；GT有效掩码仅为有限且严格正值，不按预测质量删点。

高误差事件严格为AbsRel>0.2；Native风险=-Raw Confidence；Flip风险=|D−reverse_x(Dflip)|/(|D|+1e−6)。主误差=|scale·D−GT|/(GT+1e−12)。只在0000拟合一个全局正scale，再冻结用于0001。

原scale **15.985507037495662** 完整复现；48项逐帧AUROC/AP/AUSE/Spearman对照的最大绝对差 **{st['historical_max_abs_metric_difference']:.1e}**（预设atol=1e−10）。原生单位GT和尺度对齐不构成物理米制、零样本Metric3D精度或全场景泛化证明。0001早已被观察，不是本轮新盲测，两个序列的录制会话独立性也未建立。

## 3. 四组主对照

每张图先在整个有限预测网格计算经验中秩百分位 `(average_rank−0.5)/N`，不使用GT掩码或误差生成秩。所有候选随后在同一GT有效掩码评价。等权融合=0.5·rank_native+0.5·rank_flip；Max融合=两者最大值。

以下为0001三张图先分别计算、再等权平均；n=3图但仅1个评价序列，不做像素IID显著性或跨序列置信区间。

{table}

等权融合相对Native：AUSE下降、Spearman上升，但AUROC和AP下降；相对Flip，四项宏平均均改善，但逐帧并非全部获胜。等权融合的AUSE相对Native在3/3帧改善，相对Flip在2/3帧改善。Max的AUSE最低，但Spearman低于Flip和等权融合；AUROC/AP仍低于Native。没有一种方案在全部指标与全部图像上占优。

因此“互补”是受这些复用样本支持的描述性结论，不能改写为获得了独立场景泛化证据。完整逐帧、配对差值与敏感性CSV均保留。

## 4. 预定权重敏感性与恢复处理

额外固定Native秩权重0.25、0.75，不在0001上挑选最优权重。

{mdtable(sensitivity,[('method','方法'),('AUROC','AUROC ↑'),('AP','AP ↑'),('AUSE','AUSE ↓'),('Spearman','Spearman ↑')])}

0.75组合的AUROC略高于Native，但AP仍较低，且这是已观察序列上的敏感性结果，不作为新独立测试优胜者。主实验权重仍为0.5。

另完整复用R2.2的双线性、同焦距恢复缓存作为单独敏感性视图。其scale只在0000拟合为 **{state['scales']['R2_2_BILINEAR_SAME_FOCAL']:.12f}**。等权融合的AUROC约0.784884、AUSE约0.059493、Spearman约0.265609；主要取舍方向保持，没有把两种恢复方案混算。恢复改变多个像素，不能把对照解释为只干预7个零值的纯因果实验。

## 5. 连续误差幅值与概率映射

所有一维保序回归和非负斜率Logistic参数只使用0000的stride8固定GT有效网格拟合；0001不拟合、不随机拆像素、不选超参数。输出概率指“校准尺度后AbsRel>0.2”，原Raw Confidence与秩分数本身都不是概率。

{ptable}

融合后的Brier/NLL在本复用序列上较好，ECE也低于两种单信号；但是常数校准基率的ECE更低，且该常数没有风险排序能力。不能只看ECE宣布概率校准成功。这里只有一次校准序列→一次已观察序列的诊断，没有得到独立泛化校准证书，更没有VIPER校准证书。

{rtable}

所有学习式单维误差回归均未胜过校准中位数常数对照的MAE和RMSE。RankFusion的MAE略低于Native，但RMSE更差。校准序列AbsRel图像均值约0.199983，评价序列约0.133120，事件基率约0.257759→0.149496；这些分布差异可描述，不足以归因某个网络训练机制。现有证据支持弱风险排序，不支持准确预测绝对误差幅值。

## 6. VIPER迁移行为

10张图、2,304,000个网格位置的Confidence全部有限；负分数82,079个，≥1分数67,722个。没有clip成概率。下表为每种天气2张图的等权描述；不同天气对应不同序列/场景，不能识别纯天气因果效应。

{wtable}

Night的Flip分歧P95明显高于本组其他天气；Day的两信号风险相关性很低、高/低冲突比例较高。风险区域在空间上具有聚集性，但没有GT，不能称其为真正错误或动态物体，也不能用它计算VIPER AUROC、AP、NLL或检测准确率。

逐帧秩归一化后Native、Flip和等权秩的全图平均数按构造约为0.5，这不是跨天气可靠性稳定的证据。Max风险的分布和拒绝覆盖也与等权不同；若后续采用阈值，必须重新验证覆盖而不是把相同数值阈值视为同等处理强度。

这些样本是首帧与间隔较远的中点，不是连续帧，因此无法认证时间稳定性。原生bicubic在VIPER native/flip两份输出共留下208个零值，主分析明确零扩展处理；双线性敏感性单独保留。高TTA分歧也可能包含恢复/数值因素，不能全部归因场景深度错误。

## 7. 对九个问题的直接回答

| 问题 | 本轮回答 |
|---|---|
| 历史指标能否复现？ | 能，48项逐帧数值与原记录相同；对应次级诊断，不是原严格GT门禁通过。 |
| Rank Fusion优于Native？ | AUSE、Spearman更好；AUROC、AP更差，不全面占优。 |
| Rank Fusion优于Flip？ | 四项宏平均更好，但逐帧不全优，尚非独立泛化。 |
| Max Fusion有价值？ | AUSE更低、事件识别优于Flip；相关性不及Flip，不能作为唯一可靠性信号。 |
| 两信号互补？ | 当前样本的融合/独占风险区域支持互补；未证明跨游戏泛化。 |
| 能预测连续深度误差？ | 有弱排序信息；绝对AbsRel幅值回归未胜常数中位数，不能宣称可靠幅值估计。 |
| 已建立独立概率校准？ | 没有。只有已观察序列上的序列分离映射诊断。 |
| VIPER迁移稳定？ | 有可复现的分布/空间行为差异；无GT准确性与连续时间稳定性证书。 |
| 能支持CADP-DR什么？ | 可支持双通道保留、风险排序接口及受限候选设计；不支持直接生产BA接入。 |

## 8. 工程与完整性

本地Python3.11沿用现有NumPy/SciPy/Matplotlib流程。历史EXR扩展二进制含python39.dll依赖，在当前Python中无法加载；仅在任务私有目录安装同版OpenEXR3.3.3读取器，没有重装Metric3D或改变现有Conda环境。GT文件哈希、dtype及全部历史指标复现共同验证读取一致性。

33项真实CPU测试通过；69份源缓存、RGB、GT与生产源码/配置的SHA、大小和mtime前后一致。执行中的4份核心脚本身份核对一致。所有融合、概率、回归和VIPER统计均实际执行；正式cpu002批处理约{state['elapsed_CPU_seconds']:.3f}秒，不含资产审查、制图、压缩与网络交付。

首次数值批处理的秩函数没有使用GT，但调用顺序先打开了GT；随后仅将秩计算移到GT读取之前，使实际流程也严格符合预定顺序，并以cpu002单独重算。14份结果表/模型文件字节一致，全部已保存数组逐位一致，源数据和参数不改动。两次CPU批处理是同一数据的工程复核，不算两次独立实验或新增GPU推理，原记录均保留。

23张PNG图、7组量化SVG/PDF、16份float64风险图以及最小原始预测字段随完整ZIP提供。最小重放脚本可在没有RGB/EXR、权重、OpenEXR或GPU的情况下复核排名、概率与误差回归数值；原始GT/原图/权重和环境二进制不重新分发。公开展开目录提供报告、代码、CSV和图，较大的连续数组在完整Release ZIP中。测试数、源保护与发布完整性分别记录，不能混为算法准确率。

{replay_note}

## 9. 研究决策

**EVIDENCE_OF_COMPLEMENTARITY_WITH_TRADEOFFS — NO_GO_FOR_PRODUCTION_CADP_DR_INTEGRATION。**

保留Native作为高误差事件识别基准，保留等权Rank Fusion作为连续风险排序候选，Max作为保守风险并集对照。没有根据评价集重选主权重，也没有修改深度预测、U/UBA、CUDA BA、Schur或生产DROID-W。

下一阶段若另获批准，应先明确VIPER可用的独立验证证据与风险覆盖合同，再考虑受控VO评价；当前只完成接口与数学建议，不自动启动下一阶段。详见 `CADP_DR_INTERFACE_DESIGN.md`。
'''
    (dest/'TASK011A_FINAL_RESEARCH_REPORT.md').write_text(final,encoding='utf-8')
    (dest/'TASK011A_R0_REPRODUCTION_REPORT.md').write_text('# TASK011A-R0 复现\n\n原scale15.985507037495662、48项逐帧排名指标均复现，绝对差0，atol1e-10。GT掩码仍为有限正值，7个零预测保留；原严格门禁失败不改为PASS。见intake原配置、historical_reproduction.csv与cache_manifest.csv。\n\n16份原模型缓存均经SHA核验。0000仅校准，0001已观察，不是新盲测；物理米制未认证。10张VIPER无合格DenseDepthGT，不计算深度准确性。CPU读取器仅在私有目录适配当前Python，原模型和数据保持不变。\n',encoding='utf-8')
    (dest/'TASK011A_R1_FUSION_REPORT.md').write_text('# TASK011A-R1 融合结果\n\n'+table+'\n\n经验百分位在全图有限预测网格、GT读取前计算。Native/Flip保留历史风险方向；统一GT掩码，完整保留7个零预测。主权重0.5；0.25/0.75只作固定敏感性，不挑最优。等权融合的连续排序有增益，但对Native的事件AUROC/AP退化。Max AUSE更低但Spearman不及Flip。每帧与全部负面结果均在CSV中。\n\n## 概率映射\n\n'+ptable+'\n\n## 误差幅值回归\n\n'+rtable+'\n\n所有映射只在0000固定stride8网格拟合；0001仅复用评价。不能把概率映射的改进称为独立校准证书，亦不能把弱排名相关称为准确幅值预测。\n',encoding='utf-8')
    (dest/'TASK011A_R2_VIPER_TRANSFER_REPORT.md').write_text('# TASK011A-R2 VIPER迁移行为\n\n'+wtable+'\n\n两张/天气，10张共2,304,000个位置。NegativeC=82,079、C≥1=67,722；分数不是概率。高低冲突定义为一个秩≥0.8、另一个≤0.2；另报高风险XOR/交集IoU与8连通空间聚集。\n\nNight翻转分歧更大，但无DenseDepthGT，不能推断预测错误更多；场景和天气混杂，不做因果解释。每图秩均值约0.5由构造决定，不能拿来证明稳定。所选两帧间隔很远，不能验证时间连续性。原始恢复中存在零值，修复视图单列。\n',encoding='utf-8')
    design=r'''# CADP-DR 接口与数学建议：本轮仅设计

## 证据决定的输入合同

保持两个原始通道：未校准Native Confidence C、Flip相对分歧T，以及独立数值有效性标记。保留源图尺寸、K、缩放、padding、原始帧ID与Flip反转关系。模型输出没有进入本次DROID-W。

等权秩融合适合作为下一轮待验证的排序候选，Native必须保留为事件识别参考。不能把1−rank、Raw Confidence或logit直接称为深度正确概率/方差。逐帧秩丢失绝对严重程度；不同图的0.8不表示相同出错概率。没有把本轮MVS统计映射当成VIPER可信度模型。

## 两条独立的控制量

geometry_need[f]：由DROID-W无深度先验的几何系统、原生Schur后阻尼及必要的交叉块得到的几何不确定性；不是Native Confidence，也不是原生U的别名。本轮不计算新的几何协方差。

depth_reliability[f,p]：未来经独立、目标域验证的深度可靠性。当前不存在可直接获准部署的VIPER概率映射。若未来使用 1−P(AbsRel>0.2)，必须注明事件、尺度语义、校准来源与域外失效条件。

若后续另获批准并通过准入，才研究 bounded s[f,p]=geometry_need[f]·depth_reliability[f,p]，两项都在[0,1]。原生有效先验掩码m、eta与alpha保留，alpha取正式冻结配置，不在本轮调整。

\[
C_s=C_g+m s\alpha+(1-m s)\eta,\qquad
b_s=b_g-m s\alpha(d-d_m).
\]

相同原生m和状态下，s=0对应D=0，s=1对应D=1；中间态同时控制先验曲率与梯度，并保留D=0的eta路径。不能只关梯度却宣称完整关闭深度先验。Schur消元后仍使用原生 Hd=H0+diag(ep+lm·diag(H0))，不更换求解器或阻尼顺序。

## 与U/UBA的边界

本接口只讨论深度先验，不能再次把外部可信度乘入几何观测W、覆盖U或改变其更新、替换UBA。U是原生特征/优化的不确定性机制，与深度误差排序、概率校准和几何边缘协方差分别记录。Frontend初始化、Local BA、Final BA和Filler应在未来实验中明确各自作用范围，本轮没有接入任何阶段。

几何不可靠且深度可靠时，才有增强有界先验的研究动机；几何可靠而深度不可靠时应避免先验错误牵引；两者都不可靠时不能让坏先验主导。当前信号未准入时，候选控制器不启用，保持原Baseline。数值有效性护栏和统计可靠性必须分开。

## 进入后续实验前缺少的证据

1. VIPER目标域上可解释的独立可靠性验证，或明确改用VO下游效用证据而不宣称深度概率已校准。
2. 更清晰的风险覆盖/拒绝率合同，比较Native、Flip、等权融合与Max，避免Max多拒绝导致几何约束不足。
3. 保留未观察评价协议；不再根据当前0001调权后宣称新盲测。
4. 如研究概率，比较常数基率/中位数等简单基线，保留失准和误差幅值回归失败。

本文件不是GPU、CUDA修改、生产BA接入或新数据下载授权；本任务完成后停止。
'''
    (dest/'CADP_DR_INTERFACE_DESIGN.md').write_text(design,encoding='utf-8')
    decision={'status':'COMPLETE','historical_metrics':'REPRODUCED_SECONDARY_DIAGNOSTIC','complementarity':'SUPPORTED_DESCRIPTIVELY_IN_REUSED_MVS_SAMPLE','RankFusion_dominates_Native':False,'RankFusion_macro_improves_all_four_vs_Flip':True,'independent_generalization_established':False,'continuous_error_amplitude_regression_beats_constant_median':False,'independent_probability_calibration_certified':False,'VIPER_dense_GT_accuracy_established':False,'VIPER_temporal_stability_established':False,'CADP_DR_interface_design':'COMPLETE_DESIGN_ONLY','production_CADP_DR_integration':'NO_GO','new_GPU_forwards':0,'new_dataset_download_bytes':0,'automatic_next_stage':False,'primary_fusion_weight_unchanged':0.5}
    dump(dest/'TASK011A_DECISION.json',decision)
    (dest/'FIGURE_QA.md').write_text('# 图表核验\n\n23张实际结果PNG及7组SVG/PDF已生成。逐帧值、图均值与跨帧SD同时展示，无像素IID显著性或95%泛化CI。查看了主排名图、MVS末帧、VIPER夜间及天气对照；初版共用色条相交，通过单独预留色条列修正后重新查看。输入无裁剪/增强，风险统一0–1，AbsRel仅显示截到1且GT无效区域为灰。VIPER缺失GT明确留说明面板，没有伪造误差图。定量源CSV与浮点映射SHA见FIGURE_SOURCE_INDEX。\n',encoding='utf-8')
    (TASK/'EXECUTION_STATE.md').write_text('# TASK011A execution state\n\nActual CPU experiment, analysis, 33 tests, protection69/69 and final figures complete. Source path: runs/cpu_001. Full-array artifact replay/publication are delivery work; no further model or SLAM run is planned. Primary result: mixed ranking gains, no independent calibration or VIPER depth-accuracy certificate. Pending: seal full ZIP, public GitHub verification, remove only delivered local ZIP.\n',encoding='utf-8')
    print('FINAL_RESEARCH_REPORTS_WRITTEN',json.dumps(decision,ensure_ascii=False))

if __name__=='__main__':main()

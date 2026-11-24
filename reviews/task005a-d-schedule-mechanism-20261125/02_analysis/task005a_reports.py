"""Generate evidence-grounded TASK005A reports; never rewrite Task004C-B."""
import os,sys,pathlib,json,csv,hashlib,shutil,platform,datetime
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
import numpy as np
from task005a_analysis import ROOT,OLD,RECEIVER,ARMS,OUT,GT,stage,sha,dump,verify_seal

def rows(name):
 with (OUT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def text(name,content):
 p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content.strip()+'\n',encoding='utf-8')
def main():
 seal=json.loads((ROOT/'00_seal/TASK004CB_IMMUTABLE_SEAL.json').read_text());qa=json.loads((ROOT/'05_tests/TASK005A_CPU_TEST_REPORT.json').read_text());scores=rows('TASK005A_MATCHED_SUPPORT_STAGE_SCORES.csv');phase={r['arm']:r for r in rows('TASK005A_BA_PHASE_SUMMARY.csv') if r['stage']=='frontend_local_predecision'}
 score=lambda a,st,sup:next(float(r['ate_sim3']) for r in scores if r['arm']==a and r['stage']==st and r['support']==sup)
 main_table='| 组别 | D | 调度 | 保留KF | 前端ATE：共同72帧 | 最终KF ATE：共同72帧 | 最终全487帧ATE |\n|---|---:|---|---:|---:|---:|---:|\n'
 for a in ARMS:main_table+=f'| {a} | {ARMS[a][0]} | {ARMS[a][1]} | {127 if ARMS[a][1]=="S1" else 86} | {score(a,"FRONTEND","COMMON_ALL_FOUR_KF"):.6f} | {score(a,"POST_FINAL_BA","COMMON_ALL_FOUR_KF"):.6f} | {score(a,"EXPORTED","ALL_487"):.6f} |\n'
 diag_table='| 组别 | native负视差占比 | clamp后floor占比 | U源端乘子均值 | 采样残差：before→after |\n|---|---:|---:|---:|---:|\n'
 for a,r in phase.items():diag_table+=f'| {a} | {100*float(r["native_full_negative_fraction_event_median"]):.3f}% | {100*float(r["clamp_grid_floor_fraction_event_median"]):.3f}% | {float(r["source_U_multiplier_mean_event_median"]):.4f} | {float(r["residual_before_median_lowres_px_event_median"]):.4f}→{float(r["residual_after_median_lowres_px_event_median"]):.4f} px |\n'
 old_url='https://github.com/Pseven0108/GameCam-VO/tree/a24ba97a515ec4fb6e4fd195922b4ac25e532d74/reviews/task004c-b-crossover-full-20261125'
 old_zip='https://github.com/Pseven0108/GameCam-VO/releases/download/task004c-b-crossover-full-20261125/TASK004C_B_CROSSOVER_FULL_REVIEW_20261125.zip'
 text('TASK004CB_FORMAL_SEAL.md',f'''
# Task004C-B 正式封存决定

状态：FORMALLY_SEALED_FIRST_COMPLETE_FOUR_ARM_CONTROLLED_CROSSOVER。

按用户2026-11-25指令，Task004C-B 固定为**本项目第一项完整四组受控交叉实验**。这不是“文献首创”声明。原实验的实现、配置、轨迹、统计、失败记录和评审包均不再修改。后续分析和候选修复只能进入新的任务目录。

- 固定实验评审 Commit：a24ba97a515ec4fb6e4fd195922b4ac25e532d74。
- 独立收尾 Commit：d9656b66eb541b6f3889e41cd8329898edc6f0c8。
- [完整历史评审目录]({old_url})。
- [原完整ZIP]({old_zip})：234,629,566 bytes。
- 原ZIP SHA-256：{seal['review_ZIP_SHA256']}。
- 原ZIP包含654成员；内部653项文件SHA已在原发布中验证，本轮又复核ZIP整体SHA。
- 本轮封存清点1772个原文件的大小/mtime_ns，以及85个关键文件内容SHA；检查原目录和外部R3原始证据目录。不把85项内容校验写成1772项全量内容SHA校验。
- Task005A开始/结束复核均在00_seal保存；不将新报告或缓存写入旧实验目录。

受控范围：共同C0、同一val_007、Seed43、stride=1、640×360、buffer=500；D仅在前端main-loop Local BA切换。S1/S0固定离散插入/剔除/图拓扑/BA调用调度，连续Pose、disparity、U、target、weight仍自行演化。

完整四组：B1=D1/S1、B2=D0/S1、B4=D0/S0、B3=D1/S0，全部487帧完成；这不是原生E0从零初始化，也不是总体泛化结论。

保留历史限制：原运行曾记录53个资源采样点低于10 GiB余量，最低8.6362 GiB；Rerun记录已保存但浏览器真实渲染未核实；此前工程失败未混入四组成功结果。Task005A不改写这些事实。

当前服务器沿用上轮已停止状态；本轮未连接远端，未重新核实云端状态，未启动或再次关闭实例。
''')
 text('FINAL_REVIEW.md',f'''
# TASK005A：D为何在S1与S0下呈相反效果

日期：2026-11-25。状态：OFFLINE_MECHANISM_ANALYSIS_COMPLETE_PRIMARY_ATTRIBUTION_NOT_CLOSED。

**Task004C-B已正式封存。本轮只分析既有四组证据，新增GPU运行0次、远程连接0次、模型加载0次。**

目前可以解释反转发生的阶段、D影响优化的数学路径，以及哪些简单解释不成立；还不能把反转唯一归因于“Metric3D预测错误”或“S0几何退化”。

## 核心结果

{main_table}
全部ATE为游戏世界单位，越低越好。共同72帧是四组都真实保留的关键帧；每个阶段/支持集合只拟合一个全局Sim(3)。全487帧包含Filler，与直接KF评价分列，不能混用。

在相同72帧上，D_on−D_off：S1前端+16.023818、最终+11.785183；S0前端−13.277679、最终−13.207701。**效果反转已存在于前端，四组Final BA都降低ATE，Filler在共同KF上的ATE差异不足0.0001。** 因而反转既不是不同关键帧采样点制造的，也不是Final BA或Filler首次制造的。

## 反转的评价口径边界

这里的反转明确指全局Sim(3)对齐后的**位置ATE**。沿用封存结果中的统一历史参考尺度S_REF=19.1341794347，再做SE(3)对齐的诊断，D1在两种S中都更差：S1为547.97对107.08，S0为254.98对153.37。该S_REF来自历史GT拟合，并不是模型恢复的物理尺度。

全轨迹对齐后姿态误差也没有同样反转：S1 D1/D0为2.726°/0.944°，S0为12.463°/8.155°。因此不能把“S0上D1改善位置形状ATE”扩大为“尺度、旋转、局部运动都改善”。TASK005A_METRIC_SENSITIVITY.csv/JSON逐项保留这项重要限制；本轮独立复算的四项全487位置Sim(3)ATE与封存分数差值均小于1e-10。

## 为什么D不会只有一个固定方向的效果

源码中D=1在有效先验像素使用gamma_depth=0.01，并加入先验拉回梯度；D=0不是简单把这个梯度删除，而是回到eta深度阻尼分支。它同时改变深度对角项与右端项，经Schur消元影响位姿更新。收益取决于当前图、位姿/深度状态、对应关系及权重，不能从开关名字推出单调改善或单调损害。

真实日志支持这条反馈路径：四组RGB019第一次BA前，poses/disps/U/eta/target/weight六类Tensor的SHA全部一致；该次更新后Pose、disparity、U即分化，第二次BA前六类输入均已不同。固定离散调度不能消除这种连续状态反馈。因此本结果是**调度条件下的前端总效应**，不是每个BA都固定同一状态的直接效应。

S1有127个最终KF、839次Local BA；S0有86个KF、757次。Predecision阶段图边中位数反而是S1=80、S0=188，边RGB时间跨度P90的事件中位数为20与55.5帧。不能将S0概括成“约束更少”；其几何可观测性还缺少完整Jacobian/Schur矩阵证据。

## 已排除或受到限制的解释

1. 仅由全局尺度差异造成：不足。Sim(3)已去除一个全局尺度，形状误差的反转仍然存在。
2. 仅由负视差更多造成：不成立。S1中D0的负值更多却ATE更低，见下表。
3. 仅由不同Metric3D输入造成：共同72个KF的保存先验逐帧字节一致；未据此外推到所有非共同帧，也没有独立深度GT。
4. D能普遍修复S0：不成立。S0最终全帧ATE仍达66.50；312→328长度比从30.79%到33.61%小幅改善，但相机起点坐标系方向误差从1.72°升到31.31°。
5. U/W被独立固定：不成立。W/U开关保持开启，U数值和有效权重是状态演化结果，属于潜在中介；本轮不能隔离其独立贡献。

{diag_table}
负值和floor是全部活动slot像素的native/clamp计数；表格取Predecision事件中位数。U乘子、残差来自最多24条边和步长4像素采样的CPU投影重建。残差前后列分别为事件中位数，不等于配对残差变化的中位数，也不是完整原生目标函数；表格事件不能当作独立实验样本。

## 研究判断

最符合现有证据的解释是：**D的先验牵引和深度曲率改变，与S1/S0形成的不同优化状态及U/对应关系反馈相互作用。** “S1中先验偏置代价更大、S0中正则稳定作用更大”是值得检验的机制假设，尚未证明实际S0线性系统病态，也未分离先验梯度与曲率替换各自的贡献。

下一项最有信息量的候选，是在S1/S0代表性完整BA状态上，固定Pose/disparity/U/target/weight，分离“深度对角项”和“先验梯度”两条路径。本轮没有这种完整矩阵/状态，不能从observer统计补造，且不自动开展新GPU采集或重放。

22/22新增CPU核验通过，封存复核通过。详细推导见[TASK005A_MATHEMATICAL_EXPLANATION.md](TASK005A_MATHEMATICAL_EXPLANATION.md)，机制证据见[TASK005A_D_SCHEDULE_MECHANISM_REPORT.md](TASK005A_D_SCHEDULE_MECHANISM_REPORT.md)，原始文件与读取范围见INPUT_PROVENANCE.json及DATA_AVAILABILITY.md。
''')
 text('TASK005A_MATHEMATICAL_EXPLANATION.md',r'''
# 深度正则如何通过Schur系统影响Pose

证据等级：SOURCE_DERIVED；源文件与冻结c3414af6047d06bafc1a6645d09f23247f3b2cdc的Git Blob一致。没有执行CUDA源码。

设x为位姿增量，z为disparity增量。将当前几何线性系统写为：

    [ A  E ] [dx] = [v]
    [Eᵀ  C ] [dz]   [w]

其中A、E和几何深度对角C_g由当前投影、对应关系和权重决定。令d为当前disparity，d_m为mono prior，m=1[d_m>0]，α=gamma_depth，η为网络生成的深度阻尼。

原生代码src/lib/droid_kernels.cu:1878–1899：

    C = C_g + m α + (1-m) η
    w = w_g - m α (d-d_m)
    Q = C⁻¹
    (A - E Q Eᵀ) dx = v - E Q w     [随后使用原生lm/ep求解阻尼]
    dz = Q (w - Eᵀ dx)

源码SparseBlock把矩阵和右端一起装配，公式是其块系统含义；不是本轮已获得全部原生矩阵的声明。

D=0传zeros使m=0，因此C_0=C_g+η，w_0=w_g。D=1在先验严格为正处C_1=C_g+α，w_1=w_g−α(d−d_m)。缺失或非正先验处仍走η分支。

所以D的切换有两条直接路径：

- CURVATURE_PATH：改变深度对角与Q，继而改变Schur矩阵和位姿—深度耦合。
- PRIOR_FORCE_PATH：改变深度右端，再经E Q w影响位姿右端。

这两条路径在现有D开关中同时变化。不能把D1−D0只解释成“深度先验梯度”的贡献，也不能把D0描述为“完全无正则”。

日志γ_depth=.01；采样η中位数约1e−7，α/median(η)约1e5。这只是两项正则系数的数量级诊断：没有包含C_g，不是完整C的比值，更不是系统条件数。m为正的缓存比例接近1，也不是独立深度准确率。

原生每次retraction后还可能根据新Pose/disparity更新U。下次BA重新生成target/weight/eta并使用演化后的U，因此同一个离散图不对应同一个连续线性系统。跨调度的效应可写作：

    Δ_D(S) = Y[ D=1, S, state evolves ] - Y[ D=0, S, state evolves ]

Task004C-B识别的是给定S1或S0的路径总效应。S1/S0是各生产臂生成的内生调度包，不是随机独立处理；不能把二者之差直接解释为随机化“关键帧数量”的纯因果效应。

## 仅用于说明的CPU反例

TASK005A_SYNTHETIC_SCHUR_ILLUSTRATION.json用两个标量(p,d)，真实值(1,2)，相同有偏先验2.5，α=.01、η=1e−7。

- 在良好约束几何中，加先验把pose绝对误差从约6e−7增至.0147。
- 在近共线且含少量噪声的几何中，加同一个先验把误差从2.001降至.5001。

这证明相同先验在不同几何条件下可以有相反误差效果；**不能据此认定真实S1是良态、S0是病态**。该反例不是原生BA重建，不是对真实数据拟合参数，也不是新模型实验。

## 尚缺的归因证据

缺少代表性晚期状态的完整几何Residual/Jacobian、完整C_g/E/A、Schur矩阵、准确每像素η和同状态交叉分项求解。observer的均值/分位数不能恢复这些量。因而不能报告真实条件数、特征值、哪一项解释了多少百分比，也不能声称已证明Metric3D深度错误。
''')
 text('TASK005A_D_SCHEDULE_MECHANISM_REPORT.md',f'''
# 调度条件下的真实证据链

## 实验封存与估计对象

以Task004C-B四组完整成功运行作唯一数据源；Seed43、val_007、487帧、共同C0。分析没有改写任何历史结果。D仅干预main-loop前端Local BA，初始化INIT_D=0保持；W/U开启。沿用Final BA和Filler。每单元只有一次完整运行，事件数不是样本量，未计算p值或总体CI。

## 第一层：同一帧集上的阶段反转

{main_table}

72共同KF排除了各组保留帧不同的评分支撑问题。全487分数只作端到端复核。前端与后端各用一个全局Sim(3)评分，不按区段独立缩放；对阶段使用独立最优全局对齐，因此“Final BA降低ATE”指这一明确指标，非所有误差皆改善。

共同KF的最终导出位置与post-final直接KF位置ATE差异最高小于0.0001，符合Filler不重新优化这些KF的记录；不外推为Filler对所有非KF无影响。

## 第二层：从相同输入开始的连续分化

四组第一次观测BA为native call25、RGB019；六类输入SHA完全一致。Pose/disparity/U在该次后即不同；call26起target/weight/eta也不同。相同D在不同运行中的输出非逐位一致，存在CUDA数值差异，不宣称完全确定性。

同一S内前端BA离散结构逐调用一致：S1 839/839、S0 757/757，包括rgb、t0/t1、迭代数、edge_slots和slot/RGB身份。完整原始调度相等性沿用已封存Task004C-B证据；本轮另核验这些observer字段。Native连续trace在S1有1230组before/after，S0有1148组，第一组前相同后其余连续输入均出现差异。

## 第三层：S不是只有关键帧数量

S1：127最终KF、839 Local BA=609 predecision+230 retained；S0：86最终KF、757=609+148。两者均469次motion-filter输入决策、203个插入候选。

Predecision边数中位数80对188、边RGB间隔P90事件中位数20对55.5。时间跨度不等于几何视差/基线；更多边不保证更好的可观测性。没有完整Jacobian时不能宣布S0几何退化已证实。

强制调度与当前自然决策不一致：B2=50/203（33次本想保留却强制剔除，17次相反），最早RGB034；B3=26/203（24次本想保留却强制剔除、2次相反），最早RGB051。生产臂为0次。这是固定调度与演化状态失配的证据，不代表如果放开调度自然运行就只改变这些帧；不能据此推断未运行反事实的最终KF数。

## 第四层：随时间的发展

在203个共同候选上，取每个RGB最后一次predecision BA之后、强制剔除之前的快照，在当时四组共同KF上做单一前缀Sim(3)。首次观测到S1效应>0且S0效应<0为RGB233；此后114个候选均保持该符号。

这是一种事后、时变共同支持集合的描述性定位，不能把RGB233当作物理故障起始时刻，不能与固定72帧的终态指标混合。prefix支持集合和当前估计轨迹随时间变化，禁止把曲线点当成独立重复实验。

## 第五层：disparity、U与残差

{diag_table}

S1中关闭D增加native负视差和floor，却显著降低ATE，足以否定“负视差越多必定ATE越大”的单变量解释；不意味着负视差是安全的或有益的。

D1两调度中U的源端平均乘子均更小，但ATE效果相反。U/权重是潜在中介，不能把其关联直接当成原因。乘子中位数在这些汇总中为1，而均值低于1；只看U中位数会遗漏高U尾部降权。

残差是少量边/像素采样的CPU重建；前后分位数不是原生目标全量值，也未固定跨臂连续target/weight。小的加权残差可能来自降权、无效投影剔除或量纲变化，不等于更接近GT。

## 第六层：深度先验一致性与尺度自由度

共同72帧的下采样mono prior逐图SHA一致，D开关不是切换两个不同深度模型。最终保存disparity/prior的中位比值存在显著尺度偏移；本轮额外去掉每张图的median log ratio后比较shape MAD，避免把纯尺度差当作预测错误。

这种final-saved-map诊断经过Final BA，且没有独立Depth GT。它既不是前端同状态先验残差，也无法证明Metric3D预测准确或不准确。详见TASK005A_MAP_DIAGNOSTIC_SUMMARY.csv。

## 当前因果判断

数学上D可以通过深度曲率/先验梯度双路径影响Pose；日志显示连续状态与U/对应关系反馈确实存在，且调度改变了这种反馈所在的图和状态。现有证据**支持调度条件性机制**，尚未唯一分离“先验偏置”“数值稳定”“U反馈”三者。

不将S1有利结果直接推广为永久关闭D，也不因S0的条件收益声称D可修复全局/局部一切错误。
''')
 text('TASK005A_EVIDENCE_AND_LIMITATIONS.md',r'''
# 结论与证据等级

| 命题 | 等级 | 判定 |
|---|---|---|
| D效果在S1与S0反转 | OBSERVED | 固定共同72KF及全487导出均成立 |
| 反转已出现在前端 | OBSERVED | 前端共同支持分数复算成立 |
| Final BA/Filler首次制造反转 | CONTRADICTED_AS_SOLE_ORIGIN | 更早快照已有反转；不宣称两者完全无影响 |
| 全局尺度拟合或支撑集合差异足以解释全部反转 | CONTRADICTED_AS_SUFFICIENT_EXPLANATION | 共同支持Sim(3)反转依然存在 |
| D同时改变深度对角和先验梯度 | SOURCE_DERIVED | 冻结Git对象核验、原生CUDA1878–1899 |
| 固定图意味着连续输入相同 | CONTRADICTED | call26前六类Tensor均已分化 |
| U与有效权重随D变化 | OBSERVED_ASSOCIATION | W/U开关相同，但实际值演化；独立中介效应未识别 |
| S0的边更少，所以更弱 | CONTRADICTED_AS_STATED | Predecision边中位数188对S1的80 |
| S0真实Schur系统病态 | UNRESOLVED | 无完整Jacobian/Schur/特征值 |
| Metric3D真实深度不准 | UNRESOLVED | 无独立Depth GT；保存先验一致性不是准确性 |
| 负视差越多必定轨迹更差 | CONTRADICTED | B2负值多于B1而ATE更低 |
| D在S1偏置代价、S0稳定收益的平衡不同 | SUPPORTED_MECHANISTIC_HYPOTHESIS | 数学可行，分项原生反事实未执行 |
| RGB233就是物理故障起始帧 | UNRESOLVED_NOT_CLAIMED | 只是时变前缀指标首次过零 |
| D应被永久关闭 | NOT_SUPPORTED | 条件效果相反，单场景单种子 |

指标边界：反转针对Sim(3)位置ATE，统一历史尺度诊断和姿态误差并不具有同样反转；不能将结果等同于米制尺度恢复或所有轨迹指标的改善。

统计边界：每臂n=1；不使用BA事件做独立样本，不生成伪精确置信区间。S1/S0为生产臂内生调度包；图拓扑、保留时刻、调用次数共同变化，不隔离关键帧数量。

数据边界：GT仅用于本轮离线评分。未重新读取RGB；native video.npz仅读取timestamps、mono_disps、droid_disps、uncertainties，不加载images数组。没有反序列化模型、C0或Tensor checkpoint。

观测边界：native完整活动grid census可以量化负值/floor；几何残差和权重是最多24边、步长4像素的CPU重建；η是采样统计。三类范围必须区分。

研究状态：现象和数学路径已闭合；主导机制与分项因果归因未闭合。完整科学结论不能写为PRIMARY_ROOT_CAUSE_FOUND。
''')
 text('TASK005A_NEXT_EXPERIMENT_PROPOSAL.md',r'''
# 仅供审批的最小下一步候选

本文件不是执行授权，未启动Task005B。

最有信息量的问题：在代表性的S1/S0完整BA状态上，D的“曲率替换”与“先验拉回梯度”哪一条造成主要Pose差异？

建议在新独立候选目录中，对每个完全相同BA输入分别保留/切换C的alpha-vs-eta路径与w的先验梯度，形成2×2分项对照。固定Pose/disparity/U/target/weight/eta/图、优化迭代与U更新安排；比较求解出的dx、dz、投影残差、Schur矩阵谱诊断。一次replay不等于完整前端性能实验。

状态选择优先覆盖现有前缀指标反转附近及晚期代表性事件；选择规则须在新实验前明确。当前observer统计没有完整矩阵/输入，不能根据分位数恢复。先核查既有完整checkpoint，缺失时提交最小定向采集方案，再等待GPU批准，不默认允许重跑487帧。

Task004C-B完全封存，任何新开关只在新任务候选中实现，不回写原实验、不更改旧分数。取得分项结果前，不实现Improved DROID-W，不建议把D永久关闭作为最终方法。
''')
 text('DATA_AVAILABILITY.md',f'''
# 评审包范围与复算依赖

本包提供Task005A全部主要分析脚本、派生CSV/JSON、CPU测试、源码证据、图表、封存记录和执行日志。大型原始输入沿用已封存Task004C-B及本机保存资产，不复制模型权重、C0、VIPER原始RGB或完整GT到公开GitHub。

[原完整Task004C-B评审包]({old_zip})及[固定Commit展开证据]({old_url})继续有效。INPUT_PROVENANCE.json列出本轮实际读取文件的路径、字节数与SHA；这些本地路径不是下载URL。

重新计算ATE需要用户合法持有的VIPER Camera GT（本地val_007.npz SHA在清单中）及四组保存轨迹/快照。没有这些数据时，本包仍可审查派生证据和公式，但不是无外部数据依赖的一键完整复现包。

读取npz使用allow_pickle=False，不加载images数组。数学反例和单元测试是CPU合成检查，不能替代真实原生solver取证。完整早期失败、资源门槛偏离、可视化限制保留在原包，不被本轮改写。
''')
 text('04_figures/FIGURE_DESCRIPTIONS.md',r'''
# 图表范围

01：相同72个真实KF上的前端/Final BA/导出ATE；每阶段一套全局Sim(3)。两个面板Y轴不同，见刻度。

02：每个共同候选RGB最后一次predecision BA之后、强制决策之前的当时共同KF前缀ATE差。支持集合与对齐随时间变化；不是固定全局尺度的累积误差曲线。

03：Predecision事件的诊断汇总。负值/floor是完整活动grid，U乘子是采样CPU重建；不提供事件独立性或因果归因。

04：四组最终487位姿各自一次全局Sim(3)对齐，投影到GT坐标方差最大的两个世界轴；不是米制尺度恢复，也不是全部3D误差的投影等价表示。

四张PNG均经过本机查看；未调用生成式图像工具。
''')
 text('README_请先读.md',r'''
# Task005A评审入口

先读FINAL_REVIEW.md，再读TASK005A_MATHEMATICAL_EXPLANATION.md和TASK005A_EVIDENCE_AND_LIMITATIONS.md。TASK004CB_FORMAL_SEAL.md说明旧实验已封存，结果未改。

本轮回答：D为何在不同固定调度下出现反向轨迹效果。结论达到“阶段定位+数学路径+若干竞争解释排除”，尚未达到“原生矩阵分项主导原因唯一确定”。

主要数据在03_evaluation；22项CPU测试在05_tests；4张真实数据诊断图在04_figures；原始输入SHA在INPUT_PROVENANCE.json；命令和失败保留在EXECUTION_LOG.md及07_evidence。

GPU新增0次；没有SSH、模型运行、训练、实例启动/关机或历史实验写入。后续GPU实验只给候选方案，等待用户单独批准。

ZIP SHA在外部打包回执，内部FILE_SHA256_MANIFEST.json校验包内除它本身外全部文件。完整公开评审不含模型、C0、原始RGB或完整GT；详见DATA_AVAILABILITY.md。
''')
 # Copy exact source excerpts, keeping immutable upstream files untouched.
 src=json.loads((ROOT/'01_source_audit/SOURCE_PROVENANCE.json').read_text())
 for i,(which,lo,hi,name) in enumerate([(0,1877,1916,'NATIVE_D_SCHUR_EXCERPT.md'),(2,335,390,'DEPTH_ROUTING_EXCERPT.md'),(3,78,118,'OBSERVER_GEOMETRY_SCOPE_EXCERPT.md'),(3,298,317,'OBSERVER_FULL_GRID_SCOPE_EXCERPT.md')]):
  record=src['sources'][which];lines=pathlib.Path(record['path']).read_text(encoding='utf-8').splitlines()
  excerpt='\n'.join(f'{j+1}: {lines[j]}' for j in range(lo-1,min(hi,len(lines))))
  text('01_source_audit/'+name,'# 精确源码节选\n\n来源：'+record['path']+'\n\nSHA-256：'+record['sha256']+'\n\n'+chr(96)*3+'text\n'+excerpt+'\n'+chr(96)*3)
 # Provenance hash of all substantive files actually used.
 inputs=[GT,OLD/'evaluation/CROSSOVER_SUMMARY.csv',OLD/'evaluation/EVALUATION_IDENTITY.json']
 for a in ARMS:
  inputs += [stage(a)/n for n in ['observer.jsonl','native_trace.jsonl','FRONTEND_KEYFRAMES.npz','FINAL_BA_KEYFRAMES.npz','native/traj/est_poses_full.txt','native/video.npz']]
 inputs += [pathlib.Path(x['path']) for x in src['sources']]
 inventory=[]
 for p in dict.fromkeys(inputs):inventory.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
 dump(ROOT/'INPUT_PROVENANCE.json',{'files':inventory,'raw_input_count':len(inventory),'GT_only_offline_scoring':True,'model_checkpoint_loaded':False,'npz_allow_pickle':False,'native_images_loaded':False,'same_sequence_one_seed':True})
 scripts=[p for p in (ROOT/'02_analysis').glob('task005a*.py')]
 dump(ROOT/'REPRODUCIBILITY_MANIFEST.json',{'date_Asia_Shanghai':'2026-11-25','python_executable':sys.executable,'python':platform.python_version(),'numpy':np.__version__,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1','scripts':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in scripts],'execution_order':['task005a_analysis.py','task005a_secondary.py','task005a_tests_and_figures.py','task005a_metric_sensitivity.py','task005a_reports.py'],'no_dependency_install':True,'original_experiment_untouched':True})
 dump(ROOT/'SECURITY_AUDIT.json',{'GPU_requested':False,'GPU_started':False,'GPU_used':False,'CUDA_context_initialized':False,'model_checkpoint_deserialized':False,'C0_deserialized':False,'model_forward_executed':False,'SLAM_executed':False,'new_native_BA_replay':False,'training_executed':False,'SSH_connection_attempted':False,'server_restart_or_shutdown':False,'Task004CB_files_modified':False,'original_weights_modified':False,'original_config_modified':False,'new_GPU_runs':0,'new_CPU_tests':22,'new_task_only':str(ROOT),'github_review_publication_authorized_by_user_history':True})
 text('EXECUTION_LOG.md',r'''
# Task005A真实执行记录

- 2026-11-25，接收“封存Task004C-B、集中解释D×S反向效果”指令。
- 首次探索脚本对B4路径使用D盘位置导致FileNotFound；实际B4/B3在C盘receiver。仅修正新Task005A读取路径，未搬动或修改原始数据，失败检查日志保留。
- 一个探索输出错误地按数值event ID统计，造成冗长诊断；后续改用type。该输出没有被用于科学指标或结论。保留初稿脚本，正式分析使用task005a_analysis.py。
- ANALYSIS_01：共同支持评分、4756次BA三联记录、各阶段/端点/图/深度诊断完成，exit0。
- SECONDARY_01：同调度离散字段相等性、203候选前缀、强制/自然决策、先验尺度归一化、源码Git Blob复核完成，exit0。
- CPU_QA_01：22/22真实执行通过，生成4张Matplotlib图，exit0；四图逐张查看。
- METRIC_SENSITIVITY_01：四组全487位置Sim(3)ATE与封存结果差值均小于1e-10；审计表明确保留尺度/旋转指标不具有同样反转的事实。
- REPORTS_01/02：生成正式证据报告与输入完整SHA清单；02补充评价口径敏感性，不改写Task004C-B。回执/输出保存于07_evidence。
- 全部Python进程显式设置CUDA_VISIBLE_DEVICES为空，未导入PyTorch，未加载模型或C0，无GPU/SSH操作。
- 本机读原有stage/observer/native-trace/选定npz数组；所有新文件只写入Task005A及后续独立发布checkout。
- 原实验ZIP整体SHA、1772文件元数据和85项内容SHA复核保持一致。包装/发布阶段的CRC、SHA和GitHub读取验收由独立回执记录。
''')
 verify_seal();print('REPORTS_COMPLETE',len(inventory),'hashed_inputs',flush=True)
if __name__=='__main__':main()

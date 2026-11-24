"""Write final reports only after complete controls and CPU scoring succeed."""
import csv,json,pathlib,importlib.metadata
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'final_reports';OUT.mkdir(exist_ok=True)
def j(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def rows(n):return list(csv.DictReader((ROOT/'evaluation'/n).open(encoding='utf-8-sig',newline='')))
def put(n,s):
 p=OUT/n;assert not p.exists();p.write_text(s.rstrip()+'\n',encoding='utf-8')
ctrl=j('evaluation/COMPLETED_STAGE_CONTROL_AUDIT.json');res=j('evidence/R3_FINAL_RESOURCE_AUDIT_01.json');ident=j('evidence/R3_FINAL_IDENTITY_01.json')['result'];ev=j('evidence/R3_FINAL_CPU_OFFLINE_EVALUATION_03.receipt.json');checks=j('evaluation/CPU_EVALUATION_SELFCHECK.json')
assert ctrl['formal_complete']==4 and not ctrl['missing'] and ev['exit_code']==0 and checks['failed']==0
sc=rows('CROSSOVER_SUMMARY.csv');by={x['arm']:x for x in sc};GiB=1024**3
table='| Arm | D | Schedule | KF | Sim3 ATE（游戏单位） | 全局拟合scale | RGB312→328位移比例 | Runtime s |\n|---|---:|---|---:|---:|---:|---:|---:|\n'
for x in sc:table+=f"| {x['arm']} | {x['D']} | {x['schedule']} | {x['keyframes']} | {float(x['ate_sim3_game_units']):.6f} | {float(x['global_sim3_fit_scale']):.6f} | {float(x['endpoint312_328_global_sim3_ratio_pct']):.4f}% | {float(x['runtime_s']):.3f} |\n"
d1=float(by['B1']['ate_sim3_game_units'])-float(by['B2']['ate_sim3_game_units']);d0=float(by['B3']['ate_sim3_game_units'])-float(by['B4']['ate_sim3_game_units'])
put('FINAL_REVIEW.md',f'''# Task004C-B：共同C0四组受控交叉实验完整评审

状态：COMPLETE_WITH_LIMITATIONS。四组真实GPU实验完成，等待科研评审。

四组均exit0，完成原生Final BA、Trajectory Filler与487行最终轨迹。从同一个真实GPU C0恢复，每组实际新处理RGB019–487共469帧；RGB001–018属于共同初始化，不重新采集C0。执行顺序B1→B2→B4→B3。未运行DROID-SLAM、训练或追加消融。

## 主要结果

{table}
ATE使用最终全部487帧与GT的一次全局Sim3；端点位移比例使用同一次全局拟合，不按路段重拟合。长度保持VIPER游戏单位，不能自动写成米；scale是GT拟合因子，不是系统自主恢复的物理尺度。GT仅在本地CPU离线评分使用。

核心判断：D的作用依赖离散调度路径。在固定S1下关闭D更好；在固定S0下开启D更好。D_on−off的ATE差在S1为{d1:.6f}，S0为{d0:.6f}，方向相反。不能概括成“关闭深度正则普遍改善”。应研究深度约束与关键帧、拓扑及BA调度的条件关系。

## 身份和干预合同

- val_007、seed43、stride1、640×360、buffer500、INIT_D=0。
- 冻结控制候选commit：5d357c1d3079de134dd8b41a20a00632da37f0b0；tree：c018a65009aaf4f7457e2da5225a5f322a168b77。它是原生控制接入候选，不冒充无控制代码的上游原版。
- C0 SHA256：18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92；真实初始化边界RGB018，counter12。
- B1=D1自然S1 producer；B2=D0回放S1；B4=D0自然S0 producer；B3=D1回放S0。
- 仅干预Frontend main-loop Local BA的D。W/U、Final BA、Filler保留原协议；不改优化公式、原始权重、R2 YAML或CUDA扩展。

固定的是插入/删除、拓扑和BA的离散调度，连续Pose、Disparity和对应关系各自演化。这是固定离散调度下整段条件效果，不是相同Tensor输入的一次BA纯直接效应，也不是原始E0从零运行。

## 控制和阶段证据

COMPLETED_STAGE_CONTROL_AUDIT.json核验9个成功阶段，无缺失：恢复检查1个、短程控制4个、正式arm4个。各新进程恢复18,143个对象节点，Tensor、alias、RNG及下一帧身份匹配。

S1两组8,395个离散事件逐项一致，S0两组8,233个逐项一致，包含context/payload。自C0后S1各1,230次BA三联日志、S0各1,148次；其中Local BA D/W/U实参分别核验839和757次。进程累计计数还包含C0继承的24次BA，不能混用。每对连续状态Pose哈希均有差异，不是复制producer连续解。

S1有127个KF，S0有86个KF。调度组内KF数相同是控制结果，不证明D不影响自然KF选择。S1中312与328均为保留KF；S0中312保留、328不保留。因此S0有固定RGB最终指标，但直接KF312→328必须保持ENDPOINT_UNAVAILABLE，没有插值补造。S0的最终328由Filler生成。

原生full_traj_fill计算全帧，并在保留KF时间戳使用最终KF Pose覆盖。四组KF/导出一致性符合float32与六位文本输出精度，不是bit-exact。Frontend与Post-Final-BA各自在该阶段全部保留KF上做一次全局Sim3；不直接跨阶段比较原始长度规范。487帧ATE与KF子集ATE采样不同，差值不能全部归因于Filler。

## 限制、测试和资产保护

单序列、单seed、每格n=1；没有p值或置信区间，不支持跨环境泛化。S1/S0是producer形成的内生路径，不是随机化外生调度；D×S差分仅描述这两条路径。共同INIT_D=0与原始R2/E0不同，不能直接合并成绩。继承S_REF=19.1341794347仅为历史GT拟合诊断，不是本C0的物理标定。

BA_MECHANISM_TIMELINE.csv与BA_STAGE_DIAGNOSTIC_SUMMARY.csv保留native-after负disparity采样、clamp-after网格floor、U分位数及有效权重。负值采样不是全网格负像素总数；网格floor不是本次新增clamp数。

最终身份核验：候选与原目录各{ident['candidate_files']}文件均匹配；{ident['protected_assets']}个保护资产、{ident['runtime_assets']}个运行库/配置资产和{ident['C0_storage_files']}个C0存储文件均匹配；两个源码工作区clean。详见FINAL_ASSET_PRESERVATION.json。

CPU评价{checks['passed']}/{checks['passed']}自检通过，控制审计及最终评价exit0。两次CPU输出失败分别为NumPy float32 JSON序列化与缺少Matplotlib，完整收据/日志保留。修复仅为数值输出与本机独立画图库，不重跑模型或改变指标公式。

早期R2-B1在Filler离线torch.hub解析处失败，现场保留，不计成功arm，不视为算法精度失败。R3使用冻结cached_priors注册离线模型类后完成四组，完整执行次数可追溯。

## 存储偏离与清理

存储协议不能标为全程PASS。5秒目标采样共{res['records']}条，其中{res['bad_samples']}条低于10GiB，最低{res['minimum_data_free_bytes']/GiB:.6f}GiB。3段偏离的采样近似时长与原始timeline均保留。完成时数据盘{res['final_data_free_bytes']/GiB:.6f}GiB。全部结果下载验证无损坏，不抹去门槛偏离。

14个闲置安装归档共2,134,549,899bytes已下载本地，14/14成员SHA一致，确认无活动FD/maps及身份匹配后删除远端缓存，约1.988GiB。它们此前已转至系统盘，所以最后删除主要释放系统盘，不能说数据盘直接增加1.988GiB。安装库、权重、RGB、C0和历史科研结果未删除。

## 发布与关机

ZIP包含报告、控制源码、配置、完整文本日志（大JSONL无损gzip分块）、轨迹、评价表、测试和SHA。RGB/GT数组、模型权重、完整C0/Arena、RRD和含RGB的video.npz二进制保留本地，公开SHA/大小及必要数组清单，不声称这些二进制均上传GitHub。

原生Rerun记录保留；没有本轮浏览器渲染验收。用户授权归档与GitHub发布核验后终端shutdown。本ZIP封存时尚未关机，实际命令返回和连接观察单独补充回执。

结论：完成共同初始化下的D×离散调度机制实验，得到方向相反的条件效果；尚未证明普遍有效的修复。本轮结束，不自动新增seed、场景、训练或Improved DROID-W。
''')
put('README_请先读.md','''# 阅读入口

先读FINAL_REVIEW.md，再对照evaluation/CROSSOVER_SUMMARY.csv与SCIENTIFIC_INTERPRETATION.md。

请重点检查共同C0身份、S1/S0逐事件一致性、312→328的KF/Filler身份、单次全局Sim3、D条件效果的相反方向，以及低于10GiB的真实存储偏离。

REPRODUCTION_AND_LOG_READER.md说明日志重建与SHA核验。PUBLICATION_EXCLUSIONS.json明确哪些大二进制仅本地保留。这是完整可审查证据包，不是公开再分发VIPER/权重/C0。

用户要求收尾后关机；ZIP记录封存前状态，实际执行另有GitHub补充回执。
''')
put('SCIENTIFIC_INTERPRETATION.md',f'''# 科研解释与可证伪边界

## 直接观察

固定S1：ATE(D_on−off)={d1:.9f}游戏单位；固定S0：{d0:.9f}，方向相反。差中之差{d1-d0:.9f}，仅为四格描述，没有统计显著性解释。

固定RGB312→328：B1比例63.0378%、方向误差0.6939°；B2比例96.5903%、方向误差0.5697°；B4比例30.7923%、方向误差1.7243°；B3比例33.6124%、方向误差31.3095°。位移比例更接近100%不能代替方向、RPE和全轨迹ATE。

S1两端是KF，S0的328是Filler端点。两类指标独立，缺失的直接KF不补造。KF_STAGE_SCORES采用各阶段全部保留KF的一次全局对齐；实际文件为KEYFRAME_STAGE_SCORES.csv。四组Frontend到Post-Final-BA的KF形状ATE均下降，但本轮没有干预Final BA，不能因此认定其普遍或因果收益。

自然S1有127个KF，S0有86个KF。比较B1/B4会同时改变D与调度，不能只归因D。同调度内KF一致是强制控制结果。对照的是自然路径形成后固定其离散事件，并非任意调度分布上的随机化效应。

## 仍未证明

没有独立深度GT检验，不能证明Metric3D预测错误是唯一根因；操纵的是Local BA是否使用深度约束。没有证明DROID-W存在通用实现bug，也没有证明关闭D在其他环境有效。W/U保持原设置，本轮不是新的2³矩阵。

共同INIT_D=0与原始E0从零运行不同。单序列、单seed、每格一次，不计算p值/CI，不当跨环境泛化。历史S_REF与全局scale是GT拟合诊断，不能称为米制尺度恢复。

负disparity只按日志采样，floor是网格处于下界的计数，不能当新增clamp。不同阶段的原始长度有尺度规范差异，应看各阶段整体Sim3后的形状和端点，而不是裸长度比。

## 科研决策

本轮反对“一律关闭D即可修复”的策略，支持深度正则与关键帧/图/BA调度共同作用的候选问题。若获独立授权，可再以小规模独立seed或场景验证这一条件关系，或连接已有同状态BA实验与本轮路径结果。本轮不自动执行。
''')
put('REPRODUCTION_AND_LOG_READER.md',f'''# 证据读取与复核

GT仅本地离线：val_007.npz SHA256 91fb149c066bb488ac6071602a4b50fe1540243f2db3369a3706f63b705d7008；RGB1–487对应Camera0–486。源、权重、配置、C0最终核验见FINAL_ASSET_PRESERVATION.json。

成功组：raw_evidence/R3_OFFLINE/attempts/B1、B2、B4、B3。每组有PROCESS_RECEIPT、SUCCESS、RESTORE_RECEIPT、STAGE_RESUME_INPUT、配置、轨迹、调度、观测日志与stdout/stderr。R2早期工程失败保留在独立namespace，不能混入成功组。

大JSONL按约32MiB未压缩内容无损gzip分块。各chunks.json列出顺序、SHA、字节数；依次解压并拼接，核验public_log_sha256。SSH主机名、实例标识和run token被隐藏时，公开内容hash与本地originalhash分别记录；没有删BA事件。建议逐行读取，避免一次展开全部JSON对象。

FILE_SHA256_MANIFEST覆盖除清单自己以外全部ZIP成员；ZIP整体SHA覆盖清单，避免自哈希循环。PUBLICATION_SANITIZATION_MAP追溯脱敏变化；PUBLICATION_EXCLUSIONS列出本地保留大payload及hash，不意味着它们被上传。

analysis/offline_crossover_r3.py为NumPy CPU评价，--selfcheck包含{checks['passed']}项已知Sim3、SE3、四元数、端点缺失、尺度规范一致性与严格JSON检查。完整评价需本地GT与video.npz，公开包缺少这些payload，不能声称只凭公开包完整复跑所有数值。

最终执行收据：R3_FINAL_CPU_OFFLINE_EVALUATION_03.receipt.json。首次JSON标量失败与第二次本机画图库缺失的stderr/退出码保留；最终exit0，未重跑模型。独立本机绘图库版本见R3_CPU_PLOT_ENVIRONMENT.json。

资源为约5秒采样，不保证捕获瞬时峰值。设备显存包括Rerun和开销，非单模型allocator精确峰值；B1监控从运行中途开始，峰值仅已观察下界。存储安全线偏离完整公开。

ZIP关机前封存，SECURITY_AUDIT记录当时未执行。实际shutdown命令及可达性观察将以独立GitHub材料追加，不改写已封存ZIP。
''')
put('ENGINEERING_CHANGELOG.md','''# 工程修复与变量保护

- 复用共同C0，未创建新初始化。新进程核验Tensor、对象、alias、RNG及下一输入。
- R2早期B1在Filler离线torch.hub解析失败，现场保留。R3恢复前调用冻结cached_priors注册模型类，修复I/O解析，不修改BA公式。
- 重新绑定输出归属，避免日志写回历史目录。video.npz无损压缩，数组数值/dtype/shape/hash不变。
- 同文件MAP_SHARED reducer用于spawn共享；有卡环境24GiB tmpfs，未降低buffer500、改挂载或改CUDA。完整2,246,400,000bytes CPU共享压力测试真实通过。
- 4,597个不可变文件硬链接复用，内容不变；ctime/linkcount会变化，不能称所有元数据未变。
- 完成组日志无损压缩、核验后转存，B4 schedule在B3完成前保留。只在进程退出、FD/maps为空后回收本次临时Arena。
- 14个闲置安装缓存先备份14/14 SHA匹配，再删除远端副本；未删除安装库、模型、数据集、C0和历史结果。其物理位置已转到系统盘，最后删除主要释放系统盘。
- CPU输出遇到NumPy标量和缺少Matplotlib，失败收据保留；严格数值转换及本机独立画图库解决，未重跑模型或改评价公式。
- 存储低于10GiB时未按最初门槛立即停止，真实执行偏离公开，不将事后空间恢复写成全程PASS。
- 本次四组成功不掩盖短程控制和早期失败的真实计算记录，没有训练、追加seed、新数据集或重建CUDA扩展。
''')
put('STORAGE_AND_CLEANUP_REPORT.md',f'''# 存储实录

{res['bad_samples']}/{res['records']}条样本低于10GiB，最低{res['minimum_data_free_bytes']}bytes（{res['minimum_data_free_bytes']/GiB:.6f}GiB）。3段至下一恢复样本的近似时长为5.04、126.75、136.73秒，非连续精确时长；最大采样间隔{res['max_observed_sampling_gap_s']:.3f}秒。

完成时数据盘{res['final_data_free_bytes']/GiB:.6f}GiB，系统盘{res['final_system_free_bytes']/GiB:.6f}GiB，shm余量{res['final_shm_free_bytes']/GiB:.6f}GiB。B3运行采样数据盘最低{res['stages']['B3']['minimum_data_free_bytes']/GiB:.6f}GiB。

闲置安装归档14个，2,134,549,899bytes。下载本地TAR 2,134,579,200bytes，14/14成员SHA一致；TAR SHA：b3b3eff4a5c73712115d6a76a6ebf8ccb2e92e7a42edfe3d8d5ed8f986acf825。确认无活动FD/maps及身份后删除远端缓存；此前缓存已迁系统盘，最后主要释放系统盘。

四组结果均本地归档并逐文件验证；大payload不公开再分发。只回收本任务临时Arena，未删除历史结果、模型、CUDA库、原始C0或冻结RGB。存储执行有真实偏离，不能因最终成功追记全程合规。
''')
put('SHUTDOWN_AUTHORIZATION_AND_SEQUENCE.md','''# 关机授权时序

用户最新指令：实验运行结束后帮我关机这个实例。它覆盖此前保持GPU在线要求，在实验、离线评价、本地归档和GitHub读回验证完成后执行。

目标为当前固定主机密钥验证的实例；使用平台PATH实际提供的shutdown，不修改永久网络/驱动/平台配置。ZIP封存时尚未执行，后续单独保存stdout/stderr、退出码和连接观察。SSH断连不足以证明平台已关机或计费停止，不提前声称成功。
''')
auth=ROOT/'authorization/SHUTDOWN_AFTER_COMPLETION_20261125.txt'
assert not auth.exists();auth.write_text('User: 实验运行结束后帮我关机这个实例。\nOnly after completed runs, verified local archives and verified GitHub publication.\n',encoding='utf-8')
pp=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-VO-Task004CB-20261125\cpu_plot_dependencies')
env={'scope':'Isolated local CPU plotting; remote runtime unchanged','distributions':sorted([{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions(path=[str(pp)])],key=lambda x:x['name'])}
(ROOT/'evidence/R3_CPU_PLOT_ENVIRONMENT.json').write_text(json.dumps(env,indent=2),encoding='utf-8')
print(json.dumps({'reports':[p.name for p in OUT.glob('*.md')],'formal_complete':4,'selfchecks':checks['passed'],'D_on_minus_off_S1':d1,'D_on_minus_off_S0':d0,'difference_of_differences':d1-d0},ensure_ascii=False,indent=2))

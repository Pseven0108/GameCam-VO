"""Prepare complete review, preserving historical evidence and raw input privacy."""
import csv,json,shutil,subprocess
from pathlib import Path
from common import BASE,PARENT,REVIEW,REVIEW_REL,ROOT,TASK,dump,sha

def write(name,text):
    p=TASK/'reports'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text.strip()+'\n',encoding='utf-8')
    q=REVIEW/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())

def copy(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)

def main():
    if (REVIEW/'SHA256_MANIFEST.csv').exists():raise RuntimeError('Do not overwrite a packaged review')
    REVIEW.mkdir(parents=True,exist_ok=True)
    tests=json.loads((TASK/'reports/STAGE1_TEST_RESULTS.json').read_text());framework=json.loads((TASK/'reports/FRAMEWORK_TEST_RESULTS.json').read_text())
    admission=json.loads((TASK/'data/DATA_ADMISSION_DECISION.json').read_text());profile=json.loads((TASK/'reports/PERFORMANCE_PROFILE.json').read_text())
    transfer=json.loads((TASK/'reports/TRANSFER_AUDIT.json').read_text());remote=json.loads((TASK/'reports/REMOTE_FROZEN_ENV_CPU_API_RECHECK.json').read_text())
    if tests['status']!='PASS' or not framework['passed'] or remote['exit_code'] or admission['status']!='PASS_WITH_HISTORICAL_EXPOSURE':raise RuntimeError('Incomplete acceptance')
    locked=json.loads((TASK/'configs/FROZEN_SOURCE_LOCK.json').read_text());changed=[]
    for r in locked['dependencies']:
        if sha(ROOT/r['path'])!=r['sha256']:changed.append(r['path'])
    old=json.loads((ROOT/'experiments/TASK011C/intake/INITIAL_ASSET_PROTECTION.json').read_text())
    for r in old['original_baseline_files']:
        if sha(r['path'])!=r['sha256']:changed.append(r['path'])
    if changed:raise RuntimeError('Protected source changed: '+str(changed))
    dump(TASK/'reports/FINAL_PROTECTION.json',dict(status='PASS',parent_files=len(locked['dependencies']),
        production_source_files=len(old['original_baseline_files']),changed_paths=[],
        native_extension_compiled=False,production_extension_replaced=False,
        weights_loaded=False,models_run=False,remote_weight_fresh_SHA='NOT_CLAIMED_NOT_USED_IN_SYNTHETIC_TESTS'))
    total=tests['total_tests']+framework['tests'];maxerr=max(x['maximum_mean_error'] for x in transfer['cases'])
    p32=next(x for x in profile['cases'] if x['buffer']==500 and x['sources']==32)
    p7=next(x for x in profile['cases'] if x['buffer']==500 and x['sources']==7)
    dtoh=sum(x['args'].get('bytes',0) for x in transfer['profiler']['DtoH_events'])
    write('FINAL_REVIEW.md',f'''# TASK011D — A7 Adapter 修复与双层验证准备评审

2026-11-28，Asia/Shanghai。父提交 `{PARENT}`。唯一数据集：VIPER。

**本轮准备阶段通过：ENGINEERING_READY + DATA_ADMISSION_READY + EXPERIMENT_PROTOCOL_FROZEN + GPU_NOT_STARTED。**

这里 GPU_NOT_STARTED 仅指正式 SLAM / Pilot：两者均 0 次。已在本地 RTX 5060 做合成 CUDA
测试；没有加载 Metric3D、DINO、DROID-W，也没有调用真实 Native BA、编译或替换扩展。
本轮没有产生 A5/A7 的机制或完整轨迹性能结论。

## 1. A7 全 Buffer 回传已消除

每次调用仅处理 `unique(arange(t0,t1)∪ii)`，按这些源槽位提取时间戳并在 GPU 缓存中索引。
不再读取全部 live timestamps，不再构造全 Buffer 的 A5/validity，也不逐源帧 `.item()`。
FP32 均值、掩码、支持集和检查都在设备上完成；只将 `[source_count+1,14]` 的索引/统计包传回。
Native 接口仍收到完整 strength，GPU 上 zeros_like 后 index_copy_，非源帧保持零。

| 合成条件 | 显式 D2H 摘要 | Adapter p50 / p95 | 进程峰值 allocated |
|---|---:|---:|---:|
| Buffer 500，7源帧 |896 bytes|{p7['adapter_wall_p50_ms']:.3f} / {p7['adapter_wall_p95_ms']:.3f} ms|{p7['peak_allocated_bytes']} bytes|
| Buffer 500，32源帧 |3696 bytes|{p32['adapter_wall_p50_ms']:.3f} / {p32['adapter_wall_p95_ms']:.3f} ms|{p32['peak_allocated_bytes']} bytes|

独立 PyTorch Profiler 在32源帧调用记录总 D2H **{dtoh} bytes**：3696 字节摘要加8字节内部小传输。
不能将显式算子审计的3696字节写成所有驱动层流量。两套审计均未出现完整像素 Buffer 回传。
旧 C 路径负对照实际捕获4次全 Buffer 拷贝：A5、validity、mono，另加结果审计；共23,400,000字节。
未虚构速度提升百分比，也未将这个小型测试的显存解释为模型显存。

本地 CUDA 合成探针最大均值误差 `{maxerr:.12g}`，小于固定1e-6，无容差放宽、补偿或掩码变更。
α=0.01，U/UBA、30个原生实参、原生求解器和迭代不改；A0/A1/A4/A5 继续调用冻结 B 实现。

## 2. 原生环境兼容性问题已在模型运行前修复

本地 PyTorch 2.15 支持多维 `all((1,2))`，服务器冻结 PyTorch 2.1 不支持。
远端 CPU 复核直接发现并保留该错误。已改成空间展平后 `all(1)`，保持相同布尔条件。
最终代码在远端 `2.1.0+cu118` 的纯 CPU 合成检查通过，包括源槽位、乱序时间戳、均值和别名复制；
CUDA 未初始化。其最大均值误差2.980232238769531e-7也低于1e-6。

这不是远端3090 Native BA或完整模型证书；Linux原生模型和多进程实际执行仍需后续批准。

## 3. Route A 数据已实际准入

按批准规则：47总序列−20个TASK011B源序列=27；val_014中点GT path约1.0419e-5，
不满足0.0001，因此26条通过既有元数据筛选。按序号升序冻结19条，天气4/4/3/4/4。
这19条均有历史全序列 Baseline 暴露，TASK011B暴露为false，blind_validation=false。
不得称为新数据集、未见数据或盲测。

选定1216张 JPEG 全部完成成员CRC、Pillow完整解码、1920×1080 RGB检查和SHA。
RGB ID−1、完整GT、K偏差、GT path均通过。逐张与原始 BaseDataset 的未修改CPU方法比较，
1216/1216预处理结果逐位一致，内参满足原R2映射；冻结R2 YAML字节哈希未变。
不声称其他未选7条也完成了本轮解码；未下载新数据，未解压全数据集。

## 4. 两套框架已独立建立，但未运行真实实验

**Fixed-State Replay：**未来A0运行的所有合格主循环局部BA调用作为参考，无结果筛选。
保存30个原始参数、源帧映射、A5/A7场、Native-valid、RNG与别名/stride/offset。
A5、A7、A5重复分别从独立状态开始，恢复相同RNG；原生U更新允许在各自分支内发生，
不把“相同初始U”错误实现成冻结整个U更新。输出更新差异和同二进制A5-A5波动，不生成轨迹，
不算FSR的ATE/RPE。没有既有残差时，不添加Native诊断，不把较小更新直接叫作更准确。

**End-to-End：**19源序列×5组×3 seeds=285个独立任务，串行顺序已冻结；各自初始化、
关键帧、BA历史和轨迹独立。A7只匹配自己当前状态的反事实A5，禁止强制跨轨迹对齐状态。
默认CLI仅验证计划，显式授权、参数绑定、源码哈希和一次性输出目录共同保护真正入口。
未授权即在导入模型/Native代码前停止，未生成任何已批准运行文件。

## 5. 测试与统计边界

最终 **{total}/{total} 项通过，无跳过**：原122项回归、新增10项CPU、5项合成CUDA/传输、
{framework['tests']}项框架测试。旧56项Adapter测试通过隔离导入实际针对新D实现运行，没有改原测试文件。
状态复制验证了别名、shape、stride、offset、RNG和原始输入保护；合成Stub不是Native求解结果。

主指标沿用100×Sim3 ATE RMSE / 同窗口GT path；不使用各自估计path作分母。
先在源序列内配对共同可评分seed，再按源序列做10,000次bootstrap，种子20261128、95%CI；
三seed全可评分子集作敏感性分析。失败和对齐退化不填零，独立报告计划/完成/初始化/可评分数。
常量估计轨迹仍保留raw path ratio误差，不伪造Sim3 ATE。

次指标阈值只基于B历史数据形成候选，**没有批准或用于判定**。
A0含快照采集和缓存核验开销，不能拿其总时间当干净算法运行时间；采集耗时单列，
A5/A7无快照采集，但其不同Adapter开销仍须如实记录。

## 6. 保护与待审批事项

父版本 B/C `{len(locked['dependencies'])}` 份文件及原生产源码 `{len(old['original_baseline_files'])}` 份前后SHA一致。
历史B/C代码、报告、Release未覆盖。未加载权重，不声明本轮重新核验了远端全部权重身份。
每次真正保存快照前检查唯一Storage大小并保留至少10GiB；真实快照大小、合格调用数及总存储量
尚未知，不能用合成小样本保证完整FSR容量。不得自动删除历史结果。

请评审批次指标退化边界和下一阶段正式GPU范围；Route A本身已按本次授权落实。
在此之前，不启动Pilot、Native重放或285次运行。

[实施审查](IMPLEMENTATION_REVIEW.md) · [传输审计](CUDA_TRANSFER_AUDIT.md) ·
[数据准入](DATA_ADMISSION_REPORT.md) · [FSR协议](FIXED_STATE_REPLAY_PROTOCOL.md) ·
[E2E协议](END_TO_END_PROTOCOL.md) · [统计方案](STATISTICAL_ANALYSIS_PLAN.md) ·
[待决事项](DECISION_REQUIRED.md)
''')
    write('IMPLEMENTATION_REVIEW.md','''# 实施审查

新A7在TASK011D独立副本中修改，C/B保持原字节。GPU缓存仅保存64个输入帧的原生网格；
每次按真实source union索引，时间戳映射和mean均在设备上执行。只有14列摘要跨设备。
完整strength分配是原生接口要求，不是完整A5/validity Buffer重算或回传。

CPU参考仍复用C的数学定义。FP32计算、独立FP64审计、空mask null、非有限STOP、
有效域内A5零值STOP及正支持集一致性未放宽。Pair-invalid先采用原A5的Native-only fallback，
再均匀化；不能声称A7最终仍保留不同像素的fallback系数。

A0/A1/A4/A5的实际控制代码仍是冻结TASK011B实现。生成的native_driver仅变更任务级路径、
种子、A7路由、授权与A0只读观测器，完整差异见reproducibility/experiments/TASK011D/reports/NATIVE_DRIVER_ADAPTER_DIFF.patch。
原始Python/config git对象身份与现存candidate .so的SHA已锁定；没有修改或编译Native。

Native入口、缓存推理、FSR均有独立授权动作。任务参数绑定冻结job，快照必须是本任务已登记、
哈希相符的A0状态，输出目录在原生重放前原子创建，避免重复运行后才发现旧结果。
工程Ready指静态/接口/合成测试通过，不声称完整Linux模型已经执行。
''')
    write('CUDA_TRANSFER_AUDIT.md',f'''# CUDA传输与性能

本地RTX5060，PyTorch {profile['torch']} / CUDA {profile['CUDA']}；仅合成Tensor。
运行时TorchDispatch审计能看到显式copy-to-CPU与CUDA scalar read，旧路径负对照能实际捕获问题。
独立Profiler同时捕获了32源帧新路径的{dtoh}字节D2H，其中8字节为内部小传输，3696为摘要。
没有[500,45,80]或[64,45,80]像素Tensor D2H。日志统计与设备索引允许传回；没有逐源帧item。

Buffer500/S7：p50={p7['adapter_wall_p50_ms']:.6f}ms，p95={p7['adapter_wall_p95_ms']:.6f}ms，显式D2H=896 bytes。
Buffer500/S32：p50={p32['adapter_wall_p50_ms']:.6f}ms，p95={p32['adapter_wall_p95_ms']:.6f}ms，显式D2H=3696 bytes。
每条件3次warmup、20次计时，包含摘要处理；峰值包含合成缓存/输入/输出，不是模型显存。
完整原始trace、逐次时间、全部测试日志包含在本包reproducibility的TASK011D/reports。

不宣称速度提升百分比，不把本地5060结果当作3090原生运行开销。
远端2.1.0+cu118只做CPU兼容性与别名复制检查，没有初始化CUDA。
''')
    selected=list(csv.DictReader((TASK/'data/SELECTED_19_WINDOWS.csv').open()))
    table='\n'.join(f"|{r['environment']}|{r['sequence']}|{r['rgb_start']}–{r['rgb_end']}|{r['camera_start']}–{r['camera_end']}|" for r in selected)
    write('DATA_ADMISSION_REPORT.md','''# Route A 数据准入

状态：PASS_WITH_HISTORICAL_EXPOSURE。47−20=27，val_014因GT path约1.0419e-5排除，
26条通过既有元数据技术筛选；按既定顺序取19条。全部历史Baseline暴露，非盲测。

|天气|源序列|RGB|Camera|
|---|---|---|---|
'''+table+'''

实际1216张JPEG：CRC、完整解码、原尺寸RGB、文件SHA、原始帧号连续性全部通过。
19组64帧GT和相机索引、窗口K<0.001px、GT path>0.0001 native units全部通过。
逐张比较从原始BaseDataset提取的未修改方法与独立CPU预处理，结果逐位相同。
K640主点按原R2半像素映射生成，再按原配置入口传入，不改原YAML。

原始图片只解压指定成员，存入本轮private/inputs；GT仅供本地离线评分。
GPU_RGB_INPUTS没有GT文件路径，模型不读取GT。原始RGB/GT不发布到GitHub。
已有图像复制总量253,140,598字节，无网络数据下载，未宣称整卷CRC已检验。
''')
    write('FIXED_STATE_REPLAY_PROTOCOL.md','''# Fixed-State Replay

参考：同序列、同seed的A0已安装原系统，57次参考运行是285次中的子集，不另加57次SLAM。
收集全部实际FRONTEND_MAIN_LOOP_LOCAL_BA、非motion-only、metric_depth_reg=true调用。
不按结果选择调用，不记录初始化/第二阶段初始化/在线全局/最终BA/Filler。

快照含30原生参数、源槽位/时间戳、A5场、A7场、native-valid、mono mask及RNG。
Torch序列化复制保留storage alias、dtype、shape、stride、offset。三个独立分支A5_first、
A7、A5_repeat都从同一快照恢复；原始输入逐项哈希一致，原快照不被分支污染。

“U/UBA保持相同”指分支起点与配置相同，不关闭原生U更新。分支内部U可以随原算法变化。
同一candidate binary、同一两轮BA、同一Geometry Need=false，只改变strength空间分布。
记录pose/disparity/dx/dz/U差异、时间、均值与A5-A5重复波动；没有原生残差时标记不可用，
不改Native求解器。波动达到对比差异的0.5倍即保守警示数值不确定；这是预注册诊断规则，
不是显著性检验，也不是一个重复对就能建立的数值噪声置信区间。

同序列多个BA是嵌套观测，不能当独立N。没有完整轨迹，不报告FSR的ATE/RPE。
较小更新不是准确性证据；若没有准入的局部目标或GT，FSR只能证实机制差异和数值尺度。

每次保存前按唯一Storage估算预算并保留10GiB，超限STOP，保留部分输出，不自动清理历史。
真实快照大小和总量未知。采集开销单独记录，不能忽略其对A0总时间的影响。
''')
    write('END_TO_END_PROTOCOL.md','''# End-to-End

19窗口×3seeds(43/44/45)×5arms(A0/A1/A4/A5/A7)=285个串行独立任务。
运行顺序用20261128冻结。64连续帧、640×360、stride1、buffer500、alpha0.01，
保持原R2权重、内参和Native MotionFilter CPU预处理/FP16 autocast协议。

各组独立初始化、关键帧、图结构、BA历史与轨迹，不从别的arm续跑，不强制同步关键帧。
A7只匹配自己当前状态中的反事实A5均值，不能将两条独立轨迹第k次调用强行匹配。
A1为实现端点控制，不称为深度增强新方法。A6/Geometry Need不进入实验。

缓存准备也需要单独允许PRIOR_CACHE动作：未来19×64×2次native/flip前向，另有A0首帧
实时一致性核验。当前均未执行。缓存只有在相同预处理/精度、严格哈希和RNG不推进检查通过
后可替代重复前向，模型构造和每次原有setup_seed流程仍执行；不得借缓存跳过随机初始化路径。

算法初始化失败保留为终态，不换窗；OOM/Native/输出损坏等工程错误停止序列，不自动重试。
输出少于64帧不得标记complete。完成但Sim3退化单列，保留能计算的raw scale/RPE。
默认命令是validate-only；未显式批准时在模型/Native导入前停止。

A0有快照/缓存核验开销，报告总时间与观测开销，不能称作干净速度基线。
真正比较A5/A7成本仍要在未来运行时测量；本轮没有任何轨迹成绩。
''')
    write('STATISTICAL_ANALYSIS_PLAN.md','''# 统计预注册

主比较仅A5−A7。主指标100×全局Sim3 ATE RMSE / 同窗口GT path，负值有利A5。
Sim3对齐不证明米制尺度恢复。RPE、raw path ratio error、SE3、成本独立报告。

源序列为独立单位，三个seed为重复。先在每序列共同可评分seed中算配对差均值，
再10,000次源序列cluster bootstrap，MC seed20261128，95%CI。三seed均可评分子集作敏感性。
失败不填零；计划、终态、完整、已初始化、初始化未知、ATE可评分的分母分开。
未收齐285终态时不输出确认性聚合。雨天只有3序列，天气分组主要描述，不挑组宣胜。

晋级需主CI上界<0、完成率劣势≤5个百分点、已批准次指标边界及数值稳定性同时满足。
CI跨0是证据不足，不是等价。FSR的BA调用数不扩大独立样本数，也不能代替E2E。

次指标候选见SECONDARY_THRESHOLD_PROPOSALS.csv：用B中13条有运动的A0/A1端点对照记录，
给出P95波动及明确标成“建议”的工程阈值。端点差不是同二进制重复噪声；阈值尚未获批。
特别是平移RPE的噪声导出候选较宽，不能自动接受或用于放行A5；可由评审选择更严格边界
或按GT path归一化后重新预注册。无D的新实验结果参与阈值选择。
''')
    proposals=list(csv.DictReader((TASK/'reports/SECONDARY_THRESHOLD_PROPOSALS.csv').open()))
    proposal_text='\n'.join(f"|{r['metric']}|{float(r['historical_A0_A1_abs_diff_P95']):.6g}|{float(r['proposed_margin']):.6g}|{r['unit']}|" for r in proposals)
    write('DECISION_REQUIRED.md','''# 需人工评审，不是本轮算法结论

Route A 和19窗口已按批准完成，无需重复申请数据准入。下一步仍未获准：真实Native FSR、
GPU Pilot、缓存模型推理、285次SLAM。当前没有生成approved runtime文件。

请评审次指标阈值。以下均为B历史数据形成的候选，未批准、未应用：

|指标|历史A0/A1绝对差P95|候选容限|单位|
|---|---:|---:|---|
'''+proposal_text+'''

候选规则max(明确建议的实用下限,2×历史P95)不是科学上已证明的容忍度。较宽的RPE候选
尤其需要人工判断，不能因波动大就将实际退化合理化。

另外须在未来真实采集前评审实际快照存储预算与归档位置。当前10GiB逐写安全门槛已实现，
但不能保证全体BA快照最终容量。不得通过删除历史实验腾空间。

工程准备不回答“A5是否优于A7”。只有后续独立FSR/E2E结果才能支持该研究判断。
''')
    write('CPU_TEST_REPORT.md',f'''# 测试验收

最终{total}/{total}通过，0跳过。Stage1 137项（原122+新增10CPU+5CUDA/传输），框架{framework['tests']}项。
原测试文件不修改；56项原C Adapter测试在新D模块上执行，66项原B测试原样回归。

框架用合成CPU状态和Stub验证签名、别名、offset/stride、独立分支、RNG不推进/恢复、
原始输入保护、同状态均值、授权绑定、一次性输出、统计聚类和评分退化处理。
Stub输出不是原生BA结果。合成CUDA仅Tensor操作，无Native BA和研究模型。

保留首轮4次旧回传而预期3次的负对照测试失败，修正的是审计计数，不是降低均值要求。
保留远端2.1不支持tuple-all的失败及修复复核记录。无自动重试SLAM，模型启动0次。
''')
    decision=dict(status='ENGINEERING_READY + DATA_ADMISSION_READY + EXPERIMENT_PROTOCOL_FROZEN + GPU_NOT_STARTED',
        GPU_NOT_STARTED_definition='formal SLAM/Pilot only; local synthetic CUDA was executed',
        tests_passed=total,tests_total=total,windows=19,RGB_decoded=1216,route='A',historical_exposure=True,blind_validation=False,
        synthetic_CUDA=True,formal_SLAM_runs=0,Native_BA_runs=0,model_forwards=0,GPU_pilots=0,
        planned_E2E_runs=285,FSR_reference_runs_subset_of_E2E=57,real_FSR_snapshots=0,
        secondary_thresholds_approved=False,A5_A7_utility='NOT_YET_TESTED',
        protocol_sha256=sha(TASK/'configs/FROZEN_EXPERIMENT_PROTOCOL.json'),next_action='REVIEW_ONLY_NO_AUTO_EXECUTION')
    dump(TASK/'reports/TASK011D_DECISION.json',decision);dump(REVIEW/'TASK011D_DECISION.json',decision)
    # Exact complete current-stage source/evidence excluding private inputs,
    # binary fixtures, credentials and deferred real outputs.
    for p in sorted(TASK.rglob('*')):
        if not p.is_file() or any(x in p.parts for x in ('private','__pycache__','execution_ledger','runs','cache','fixed_state')):continue
        if p.suffix.lower() in ('.pt','.npz','.npy','.jpg','.jpeg','.so','.pyc'):continue
        copy(p,REVIEW/'reproducibility/experiments/TASK011D'/p.relative_to(TASK))
    for r in locked['dependencies']:copy(ROOT/r['path'],REVIEW/'reproducibility'/r['path'])
    # Minimal fixtures needed by the unchanged inherited test contracts.
    prefix='reviews/task011b-validity-aware-cadp-dr-20261127/reproducibility/'
    for rel in ('experiments/TASK011B/intake/reliability_metrics_frozen.py',
                'experiments/TASK011B/intake/NATIVE_REGRESSION_FORMAL_REAL_FIRST_LOCAL.json',
                'UPSTREAM_LICENSES/DROID-W-LICENSE.txt','UPSTREAM_LICENSES/ATTRIBUTION.md'):
        raw=subprocess.check_output(['git','show',PARENT+':'+prefix+rel],cwd=ROOT)
        p=REVIEW/'reproducibility'/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    write('README.md','''# TASK011D 完整准备阶段评审

先读FINAL_REVIEW.md，再核对TASK011D_DECISION.json。代码、配置、全部当前测试日志、
两次Profiler trace、历史失败/兼容性复核和1216帧解码审计都在reproducibility中。
父B/C源码是不可改的复现依赖，不代表当前阶段状态。当前数据口径以Route A为准。

本包不包含原始RGB/GT、权重、环境、Native二进制。此阶段没有真实FSR或285次轨迹输出。
不能把合成测试解释为A5胜出。完整ZIP与展开文件发布后都可供评审。
''')
    print(json.dumps(dict(status='FULL_REVIEW_PREPARED',tests=total,protected_sources=len(locked['dependencies'])+len(old['original_baseline_files']),
        stage='PREPARATION_COMPLETE',formal_SLAM_runs=0)))

if __name__=='__main__':main()

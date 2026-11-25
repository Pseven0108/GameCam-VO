import os,pathlib,json,sys,csv,tarfile,hashlib,shutil
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=pathlib.Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'GAMECAM_TASK005B_GPU_MECHANISM_20261125_R1'
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-R2-20261125-R1')
EX=RECEIVER/'expanded'
def load(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
def put(name,text):
 p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text.strip()+'\n',encoding='utf-8',newline='\n')
def obj(name,data):put(name,json.dumps(data,indent=2,ensure_ascii=False))
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
 return h.hexdigest()
pre=load(ROOT/'00_intake/PREFLIGHT.stdout.txt');post=load(ROOT/'00_intake/FINAL_PRESERVATION_02.stdout.txt')
groups=load(ROOT/'04_analysis/IMPLEMENTATION_GROUP_SUMMARY.json');feedback=load(ROOT/'04_analysis/FEEDBACK_CHAIN_AUDIT.json')
snapshot_proof=load(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1\snapshot_D0_S1_RGB233.VERIFIED.json')
identity=load(EX/'results/plain/INPUT_IDENTITY.json')
protected={n:pre['files'][n] for n in pre['files']};assert all(post['files'].get(n)==v for n,v in protected.items())
native_path=next(n for n in post['files'] if n.endswith('droid_backends.cpython-310-x86_64-linux-gnu.so'))
assert post['files'][native_path]['sha256']=='6dcf8de36cadc2174023b649b026f04e61b1231420d98763cc5aa3b294a91c3e'
preservation={'protected_input_snapshot_members_and_R1_candidate':len(protected),'all_before_after_SHA_equal':True,'installed_original_SHA_preserved':True,'historical_candidate_worktree_clean':post['historical_status']['stdout']=='','raw_input_snapshot_local':snapshot_proof,'no_history_deletion':True,'no_shutdown':True,'no_R2_YAML_or_weight_write':True,'historical_LOCK_json_at_legacy_path':post['lock']}
obj('ORIGINAL_EVIDENCE_PRESERVATION.json',preservation)
obj('R2_DECISION.json',{'task':'TASK005B-R2','status':'DIAGNOSTIC_COMPLETE_STRICT_ENDPOINT_GATE_NOT_PASSED','gpu_two_iteration_BA_calls':10,'gpu_BA_call_budget':10,'input_contexts':1,'original_repeats':2,'reference_repeats':2,'paths_00_repeats':2,'observed_reference_repeats':2,'observed_paths_00_repeats':2,'native_U_update':True,'atol':1e-6,'rtol':1e-5,'tolerance_changed':False,'native_original_self_repeat_PASS':False,'native_original_self_repeat_dx_violations':6,'native_original_self_repeat_dz_violations':5559,'reference_vs_paths_all_four_final_pairs_PASS':True,'observed_reference_vs_paths_all_four_final_pairs_PASS':False,'earliest_observed_numerical_divergence':'iteration1_Jjj_data','earliest_divergence_before_J_linear':True,'first_iteration_geometry_bitwise_equivalent_across_all_four_observed_calls':True,'proposed_source':'Native floating-point atomic accumulation with affine/U feedback; Jjj output is the earliest observed divergence. Exact summation order was not recorded.','unique_atomic_site_causally_isolated':False,'compiler_effect_separately_identified':False,'candidate_ready_for_unconditional_U_native_mechanism_expansion':False,'S0_runs':0,'RGB_prefix_runs':0,'full_487_frame_runs':0,'remaining_S1_matrix_resumed':False,'next_stage_requires_user_review':True,'instance_shutdown':False})
security={'gpu_used':True,'cuda_context_initialized':True,'cuda_tensors_created':True,'model_checkpoint_loaded':False,'experiment_input_snapshot_deserialized':True,'full_DROIDW_inference_executed':False,'native_BA_replays':10,'iterations_per_native_call':2,'model_training':False,'S0_started':False,'RGB_prefix_executed':False,'remaining_mechanism_matrix_started':False,'installed_CUDA_extension_replaced_or_rebuilt':False,'independent_observation_extension_compiled':True,'original_BA_formula_changed':False,'models_or_R2_YAML_changed':False,'historical_outputs_modified':False,'automatic_retries':0,'ssh_strict_host_key_checking':True,'new_host_key_accepted':False,'instance_restarted_or_shutdown':False,'drivers_modified':False,'historical_data_deleted':False,'publication':'Separate codex branch and complete review ZIP; no default branch or visibility changes.'}
obj('SECURITY_AUDIT.json',security)
put('README_请先读.md','''# TASK005B-R2 评审入口

先读 FINAL_REVIEW.md，再读 R2_FEEDBACK_TRACE.md 和 R2_CANDIDATE_READINESS.md。

本轮已完成10次真实GPU双迭代BA重放。仅用D0_S1_RGB233一个真实输入；未启动S0或模型前缀。

关键发现：原安装扩展自身重复就能触发原端点容差；观测到的最早差异是第一轮Jjj_data，早于J_linear。候选的严格U Native端点准入仍未通过。

公开Git目录包含全部报告、CSV、源代码、收据、两张图及小型原始trace。完整REVIEW.zip另含本轮10份完整原生数组、完整日志、独立观测.so和唯一完整输入快照，内含SHA清单。Git目录的FILE_SHA256_MANIFEST覆盖可浏览文件；ZIP内部另有覆盖全部大文件的SHA清单。

数值归因必须区分：直接记录、源码推导、CPU复算、尚未隔离的atomic/编译因素。禁止把本轮称为S1/S0反转解释或轨迹性能提升。
''')
put('FINAL_REVIEW.md',f'''# TASK005B-R2：GPU 原生数值重复性与端点等价性

执行日：2026-11-25（Asia/Shanghai）。状态：**DIAGNOSTIC_COMPLETE_STRICT_ENDPOINT_GATE_NOT_PASSED**。

## 核心判断

**原始扩展自身的数值波动已被真实重复实验确认。上轮失败不能单独作为新增路径实现错误的证据。** 第一轮几何和求解在四份观测重放中逐位一致，最早记录到的分歧是第一轮 `Jjj_data`；随后进入 `J_total → J_linear → affine → U/temp → 第二轮几何与求解`。这比“第二轮不一致”更具体，也说明不能仅把原因归于 `linear_transform_kernel`。

**严格端点等价性仍不通过。** 本轮没有改变 `atol=1e-6, rtol=1e-5`，没有用扩大容差将失败转成通过。S0、剩余S1机制矩阵和后续算法改进均未启动。

## 实际执行

唯一状态：`D0_S1_RGB233`，state SHA `{identity['state_sha256']}`，原生BA ID394，t0=52、t1=64，94条图边，15个涉及深度槽位、72维Pose更新、54,000个disparity更新。

每条调用均保留原生函数内部两轮，恢复相同完整输入值、storage alias、dtype、shape、stride、offset和RNG；处于no_grad。两次重复是同一Python进程中分别克隆完整状态的独立调用，**不是两次独立进程启动**。

| 路径 | 调用数 | 说明 |
| --- | ---: | --- |
| 原安装 droid_backends.ba | 2 | 原二进制不改动 |
| R1候选 ba_reference | 2 | 同编译模块的原ba_cuda |
| R1候选 ba_paths(0,0) | 2 | C/G关闭，保留原有trace |
| 独立trace_reference | 2 | 原公式只增加只读记录 |
| 独立trace_paths(0,0) | 2 | 同样记录点及C/G关闭 |

共 **10/10次双迭代BA，20轮内部迭代**。无RGB前缀、无模型加载、无自动重试。新增独立观测扩展编译一次，未替换原扩展或R1候选。

## 三种实现的重复性与端点

| 比较 | 七个最终字段全部通过的配对数 | 最大dx绝对差 | 最大dz绝对差 |
| --- | ---: | ---: | ---: |
| 原安装两次自身重复 | 0/1 | 1.83005e-6 | 4.20213e-6 |
| reference两次自身重复 | 1/1 | 1.97440e-7 | 9.53674e-7 |
| paths两次自身重复 | 1/1 | 2.14204e-8 | 9.53674e-7 |
| 原安装 vs reference | 2/4 | 1.59442e-6 | 3.36021e-6 |
| 原安装 vs paths | 0/4 | 1.39605e-6 | 2.86102e-6 |
| reference vs paths | 4/4 | 2.27708e-7 | 1.43051e-6 |

原安装自身重复：dx **6/72**、dz **5,559/54,000** 个元素超差；最终Pose、disparity、U、temp、affine均在原容差内。所有结果有限，无OOM。最大绝对差本身不决定通过与否；每个元素仍按原相对/绝对混合容差判断。

上表4个配对共享原始运行，**不是4个独立实验重复**。每条路径n=2，不能据此建立稳健噪声分布或宣称编译差异为零。

## 第二轮反馈的逐轮证据

四份新观测结果共有6个配对，全部满足：第一轮输入、几何项、C/w/Q、dx/dz、几何后Pose/disparity和Jii_data逐位一致；最早差异均为 `iter1_Jjj_data`。原代码此输出由重投影向目标像素的浮点atomicAdd散射累加形成。

以观测reference自身重复为例：第一轮Jjj最大差7.62939e-6；J_linear最大差9.31323e-9；affine有28个元素变化，最大差9.31323e-10；U最大差2.38419e-7。第二轮入口Pose/disparity仍逐位一致，但U/temp/affine已不同。第二轮dz最大差1.59442e-6，90个元素超差。

观测reference vs 观测paths的最终字段配对仅1/4通过；观测reference自身重复也失败。因此不能挑选未埋点的4/4结果宣称候选整体通过。只读复制与同步会改变执行时序；当前证据不能定量分离其影响。

独立CPU复算40/40通过，包括J_linear到affine增量、affine更新式、affine到temp/U公式、FP64归约对照。它们验证数学链，**不等于复现某次CUDA atomicAdd的确切累加顺序**。

## 原因分层

- 直接观察：原安装二进制自身非逐位重复，且dx/dz可越过原容差；四份观测的最早输出分歧是Jjj_data。
- 源码和复算支持：Jjj散射归约、J_linear归约均有浮点atomicAdd；差异通过affine/U反馈进入第二轮。
- 尚未单独证明：每次atomic指令的确切顺序、Jjj与J_linear两个归约的各自因果贡献、原安装二进制内部首个差异是否与观测副本完全同位、编译差异的独立贡献。
- 没有证据支持：将所有波动归因于新增C/G机制、GT映射、GPU损坏，或把本轮称为Night轨迹压缩的最终根因。

R1 paths记录的72维阻尼系统本轮均为SPD，条件数约2.64e5–2.67e5，相对线性残差1.56e-8–1.44e-7。该系统对小扰动敏感是合理解释，但条件数不单独证明具体误差来源，也没有发现求解器崩溃证据。

## 准入判断与建议

**候选在固定第一轮、D0条件下的计算语义有很强支持；U Native双迭代严格端点门槛仍未达到。** 不恢复S0，不继续矩阵。建议评审后仅做最小固定中间态归约探针：保持同一J_total/feature/temp，比较重复J_linear，另隔离Jjj；与固定U的双迭代对照分开。其目的是识别两处atomic与反馈贡献，而非修改Baseline算法。本轮未执行这些新增实验。

## 资源与资产

RTX3090，当前主机密钥匹配既有可信ED25519。初始数据盘可用{pre['disk']['free']/1024**3:.3f}GiB，结束{post['disk_free']/1024**3:.3f}GiB，本轮远端新增约{post['new_directory_bytes']/1024**2:.2f}MiB；保留10GiB底线。单调用PyTorch allocated峰值约5.27GiB（不含其他进程/驱动开销）。结束GPU无计算进程，实例保持开机。

{len(protected)}个原输入成员/R1扩展前后SHA均一致，原安装.so SHA一致，历史候选工作区干净。原安装目录无.git，故未以其HEAD重新证明c3414af；使用原二进制SHA、已核验候选Git身份以及四个关键函数正文一致性。legacy configs/LOCK.json当前不存在，此事如实记录，没有补写。

16/16 CPU源码合同/证据测试通过；40/40数学复算通过。完整日志、10份NPZ、输入快照、源码差异、编译收据和SHA均保留；见发布包与SOURCE_MAP.md。完成后停止等待用户评审。
''')
put('R2_NUMERICAL_REPRODUCIBILITY.md','''# 原安装扩展数值重复性

两次独立状态克隆，同进程串行调用原安装.so；原RNG每次恢复，全部有效输入SHA一致，内部iterations=2。

|字段|数值发生变化的元素|超原容差元素|最大绝对差|
|---|---:|---:|---:|
|dx_last|72|6|1.8300488591194153e-6|
|dz_last|49335|5559|4.202127456665039e-6|
|Pose|43|0|1.9073486328125e-6|
|disparity|48327|0|4.291534423828125e-6|
|uncertainties|2327|0|1.1920928955078125e-7|
|temp_y_cdot|12404|0|2.384185791015625e-7|
|affine_weights|48|0|9.313225746154785e-10|

这直接否定“相同状态的原安装双迭代BA必然通过当前容差”的假设。它不证明所有浮点差异对轨迹无影响，也不提供新的噪声容差。

比较方向使用CSV右列为reference：abs(left-right) <= 1e-6 + 1e-5*abs(right)。审计用float64计算误差；CPU测试确认本轮所有原字段的PASS与历史np.allclose(float32)一致。

全部15个未埋点配对保留在04_analysis/PLAIN_PAIRWISE_ERRORS.csv，含元素数、变化数、超差数、最大/RMS误差、逐位一致性。配对不是独立重复样本。R1原失败记录与R2六个输出的84项对照见HISTORICAL_ENDPOINT_COMPARISON.csv。

本任务的Depth直接优化参数是disparity。完整原始disps保留；另仅在双方正值域计算1/disparity，排除零/负值，不clamp、不改写原状态，不解释为米制GT。见RAW_DISPARITY_VALIDITY.csv和DEPTH_RECIPROCAL_COMPARISON.csv。
''')
put('R2_REFERENCE_EQUIVALENCE.md','''# 原安装、ba_reference、ba_paths的对照

ba_reference绑定R1候选编译单元内的原ba_cuda。实际读取原安装旁的droid_kernels.cu，ba_cuda、linear_transform_kernel、uncertainty_update_kernel、dino_feats_projective_transform_kernel四个函数正文与R1候选完全一致（SHA见00_intake/SOURCE_BUILD_AUDIT.stdout.txt）。

当前编译器g++11.4、nvcc11.8.89、Torch2.1.0+cu118；独立候选-O3、sm86，无fast-math新开关。安装setup声明多架构，而候选只针对sm86；原安装二进制完整历史构建命令未在本轮重新恢复，因此不宣称二进制编译身份相同。

原安装vsreference：最终7字段2/4配对通过。原安装vs paths：0/4。reference vs paths：4/4。原安装自身重复0/1，故上述失败不能单独识别为重新编译或新增C/G代码错误。

新观测模块保留原R1源文件字节前缀，追加两个函数；删去记录语句后reference计算token与原ba_cuda一致，由CPU测试验证。paths只额外分离mc/mg mask。本轮两者C=G=0。

不能省略的有效输入区别：原扩展/reference的disps_sens全零，paths输入真实cached_mono再内部将mc/mg置零。其他有效实参SHA相同。两条路径的D0有效C/w语义相同；并非声称每个实参字节都相同。

观测副本的第一轮C/w/Q、dx/dz逐位一致，支持D0原公式的计算等价。第二轮U Native仍有超差，不能升级为全路径严格等价PASS。所有配对完整保留；不选择性省略失败结果。
''')
put('R2_FEEDBACK_TRACE.md','''# 第二轮反馈：最早差异与传播

观测函数各一次调用内部保留两轮，每轮31字段；两份reference、两份paths，共4份trace、6个配对。

1. 第一轮Pose、disps、U、temp、affine输入逐位一致。
2. projective_transform的Cii/wi/Hs/vs逐位一致，深度C/w/Q、dx/dz及几何后Pose/disps逐位一致。
3. Jii_data逐位一致，**Jjj_data首次不同**。Jjj由DINO特征重投影向目标像素atomicAdd累加；四个双线性邻点分别累加。
4. J_total受到Jjj扰动。linear_transform_kernel又使用atomicAdd累加J_linear；此处输入J_total已经不同，故不能仅用这组trace单独量化linear_transform自己的归约噪声。
5. du=-lr*mean(J_linear,0)；affine <- affine + (du-weight_decay*affine)。记录affine_du和前后affine，CPU按原算式复算。
6. temp=sum_c affine[c]*feature[c]+bias，U=log(1.1+exp(temp))。原生U Native实际联合更新affine/temp/U，而非单一U独立因素。
7. 第一轮更新后的U/temp/affine与同次调用第二轮入口逐位一致。第二轮入口Pose/disps仍相同，U等已不同，几何权重和正规方程因此可能不同。
8. 第二轮dx/dz出现微小变化，部分越过原容差。

四份观测重复的共同最早差异均在Jjj输出，但只观测到输出，未捕获atomic执行顺序。归因等级：源头输出已定位；浮点归约顺序是强支持解释；两处atomic的独立贡献尚未干预隔离。原安装.so无内部记录，不声称直接观测了该二进制内部Jjj。

CPU用同一封存DINO feature storage直接解码浮点字节，不导入torch：40/40公式检查通过。FP64累加只作独立算式参照，不替代某次FP32 atomic顺序。完整结果FEEDBACK_RECONSTRUCTION.csv。

观测复制采用detach().cpu().clone()，会同步GPU、增加CPU工作。它不改变优化公式，但可能改变调度。OBSERVER_EFFECT_ENDPOINTS.csv保留所有未埋点/观测最终字段对照，不把观测通过率混入原安装重复性。

72维线性系统CPU谱分析使用Eigen LLT对应的lower自伴语义，不平均上下三角。系统SPD，条件数约2.64e5–2.67e5；见LINEAR_SYSTEM_CONDITIONING.csv。条件数解释敏感性，不足以唯一归因。
''')
put('R2_CANDIDATE_READINESS.md','''# 当前候选是否可继续机制归因

|准入项|结论|证据|
|---|---|---|
|真实输入身份和完整性|PASS|同一state SHA；所有克隆值/metadata/alias验证|
|D0第一轮计算语义|PASS（本状态范围）|4份观测C/w/Q、dx/dz逐位一致|
|原安装自身严格重复性|FAIL|6个dx、5559个dz超差|
|重新编译reference严格等价|PARTIAL|与原安装2/4配对通过；安装自身也失败|
|未埋点reference-paths端点|PASS（本次2×2配对）|4/4，非4次独立重复|
|观测reference-paths端点|PARTIAL|仅1/4配对通过|
|归因到单一atomic位置|INSUFFICIENT_EVIDENCE|Jjj输出首先变化；J_linear输入也已有变化|
|完整U Native候选发布准入|NOT PASSED|原容差未满足；不可挑选通过配对|
|恢复S1/S0机制矩阵|NOT STARTED|等待用户评审|

建议下一步先评审现有“单次跨实现差异阈值”的科学含义。原实现自身触发同门槛，说明失败不是候选独有指标；但不能自动放宽。

信息增益最高的最小新实验：从已保存中间态分离同J_total/feature/temp的linear归约探针，再分离同输入的Jjj散射；不经过模型或序列前缀。必要时以固定U双迭代做机制对照。需要新授权后执行，本轮没有做。

不建议立即修改atomicAdd、不引入确定性替代算法、不重跑487帧，也不将该波动直接当作D开关在S1/S0反转的原因。
''')
put('SOURCE_MAP.md','''# 源码与证据映射

|位置（R1 task005b_kernels.cu行号）|作用|R2证据|
|---|---|---|
|1444附近 dino_feats_projective_transform_kernel|几何后的特征/不确定性导数|iter*_Jii_data、Jjj_data、kf_count|
|1645–1648 atomicAdd(Jjj_data)|向目标四邻点散射累加|全部6个观测配对的第一处分歧|
|1725–1761 linear_transform_kernel|J_total与feature/temp到J_linear|iter*_J_linear及之前的输入|
|1752、1755 atomicAdd(J_linear)|特征和bias的浮点归约|有差异，但输入J_total也已不同|
|1951–1952 ba_cuda|du与affine更新|iter*_affine_du、affine_before_linear/after|
|1022–1043 uncertainty_update_kernel|affine→temp→U|iter*_temp_after、U_after|
|1840附近 / 下次itr|新U进入projective_transform|iter2_U_before、Cii/wi/Hs/vs、dx/dz|
|2120起 ba_paths_cuda|R1 C/G候选|plain paths_1/2完整22字段/轮|

R2附带原R1候选完整源码以及只读观测生成脚本、差异、31字段顺序。观测reference删去记录后计算token与原函数一致。原安装关键函数正文的本次读取比对见SOURCE_BUILD_AUDIT.stdout.txt。

原安装.so SHA：6dcf8de36cadc2174023b649b026f04e61b1231420d98763cc5aa3b294a91c3e。
R1候选.so SHA：1edb9685e1569f2513a4dc895b2eddbe699e15d2d684079e4d9c2f77e9a4ad44。
R2观测.so SHA：6485409710451da8207154675ac7206f456ecb26bc4fc3baa82a6de12d1ea94c。
''')
put('REPRODUCIBILITY.md','''# 重现与输入合同

授权边界只包含D0_S1_RGB233。用户未批准扩展到S0或重新获取序列前缀。

本次运行脚本：01_runtime/replay_r2.py。需Linux、既有Torch2.1.0+cu118、nvcc11.8、Eigen和已固定的原扩展。原扩展不得替换；候选独立构建。

输入以完整storage序列化保存；每个唯一storage只克隆一次，再按原offset/shape/stride恢复view并验证alias等价类。每次调用前恢复封存RNG，torch.set_num_threads(2)，torch.no_grad，内部iterations=2。

完整ZIP的raw/input/snapshot_D0_S1_RGB233.tar包含原封存快照，原tar SHA及每成员SHA见00_intake/INPUT_SNAPSHOT_VERIFIED.json。raw/plain/和raw/trace/含10份NPZ及STARTED/receipt、完整stdout/stderr；diagnostic_binary含本次观测.so。所有数组保留原shape/dtype；原disps不clamp，所有输出均有限。

分析脚本04_analysis/analyze_pairs.py、feedback_math.py、extended_diagnostics.py使用CPU NumPy。feedback_math不反序列化模型；对可信快照gzip+torchZIP的storage直接读字节。

原运行器使用服务器绝对路径。本轮完整包不是重新部署环境的自动安装器；重放必须显式核对环境及输入身份。原二进制来自此前冻结环境，本轮未重新安装依赖或编译原扩展。

数值判定保持abs(a-b)<=1e-6+1e-5*abs(b)。未以本轮观察到的最大重复误差构造新通过阈值；也未用n=2估计具有统计保证的误差包络。
''')
put('EXECUTION_LOG.md','''# 执行日志

所有正式操作均为2026-11-25；精确Unix时间见收据，用户时区Asia/Shanghai。

1. 严格SSH pin核验；RTX3090、无其他GPU计算进程、磁盘与快照成员SHA通过。
2. 发布独立R2输入合同与10次调用上限；原输入及原.so只读。
3. plain阶段串行6次调用，PROCESS_RECEIPT exit0；耗时约140.30秒（含状态恢复、逐字节SHA、压缩/清理）。原生调用本身时间单独保留。
4. 独立观测模块-O3/sm86编译一次，95.37秒、exit0、编译时CUDA context未初始化；原.so未改动。
5. trace阶段串行4次调用，约121.46秒、exit0。每次保留内部两轮。
6. 从远端分别接收plain/trace/final只读归档，流式SHA与所有成员SHA复核。复制不删除远端结果。
7. CPU全配对比较、最早分歧分析、40项反馈算式复算、系统谱/残差、历史失败对照和图表。
8. 最终重新核验原输入/R1候选/原安装.so SHA，历史候选git工作区干净；GPU无计算进程，实例不关机。

准备阶段如实记录的问题：观测生成器最初因重复锚点和Windows默认编码检查失败，在部署编译之前修正；只读收尾脚本最初假定legacy configs/LOCK.json存在，随后记录该路径缺失并完成核验；历史tar成员名称查询首次缺少D0字样，修正后只读比较。上述均没有启动额外GPU BA，没有覆盖旧结果。原失败日志仍保留在本轮intake/工具记录。

没有运行错误导致的GPU重试，没有模型/前缀运行，没有新机制矩阵，没有关机。
''')
# Minimal immutable input metadata for public repository browsing.
obj('00_intake/INPUT_SNAPSHOT_VERIFIED.json',snapshot_proof)
obj('00_intake/FINAL_PUBLIC_RESOURCE_AND_PRESERVATION.json',{k:v for k,v in post.items() if k!='logs'})
for name,text in post['logs'].items():put('06_runtime_evidence/'+name,text)
for phase in ('plain','trace'):
 for p in (EX/'results'/phase).glob('*.json'):
  dest=ROOT/'06_runtime_evidence/results'/phase/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
for name in ['BUILD_COMPLETE.json','build.ninja']:
 dest=ROOT/'06_runtime_evidence/build'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(EX/'build'/name,dest)
for p in (OLD/'02_candidate').glob('task005b_*'):
 if p.is_file():
  dest=ROOT/'02_candidate/R1_reference'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
# Recover the exact JSON manifest without materializing the original large tensors.
archive=pathlib.Path(snapshot_proof['archive']);assert sha(archive)==snapshot_proof['archive_sha256']
with tarfile.open(archive) as t:
 name=next(n for n in t.getnames() if n.endswith('/manifest.json'));data=t.extractfile(name).read()
 (ROOT/'00_intake/INPUT_STORAGE_MANIFEST.json').write_bytes(data)
print(json.dumps({'report':'FINAL_REVIEW.md','native_calls':10,'protected_before_after':len(protected),'status':'DIAGNOSTIC_COMPLETE_STRICT_ENDPOINT_GATE_NOT_PASSED'}))

"""Write evidence-grounded preparation reports. No real-experiment result is invented."""
import os,sys,pathlib,json,csv,hashlib,datetime
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def put(p,t):(ROOT/p).write_text(t.strip()+'\n',encoding='utf-8')
tests=read('04_tests/CPU_TEST_REPORT.json');res=read('01_protocol/RESOURCE_STATUS.json');proto=read('01_protocol/TASK005B_EXECUTION_PROTOCOL.json')
assert tests['PASS'] and tests['total']==38
put('FINAL_REVIEW.md',f'''
# TASK005B：双路径机制分解——准备阶段评审

日期：2026-11-25（Asia/Shanghai）。状态：**CPU_PREPARATION_COMPLETE_GPU_EXPERIMENT_NOT_STARTED**。

用户确认当前为无卡启动。本轮完成真实历史证据核查、12个状态上下文的预选择、独立原生求解器候选代码、38/38项CPU数学与源码测试。**没有产生曲率/先验梯度的真实GPU归因结果；TASK005B整体尚未完成。**

Task004C-B继续封存；1772项历史文件大小/修改时间与85项选定内容SHA复核通过。未改动原有四组、模型、配置、已编译CUDA扩展；未进入Task005C/006。

## 已经确定的关键事实

1. D=1同时改变深度曲率与先验梯度；D=0保留eta阻尼。独立候选将二者拆为C/G两个二值参数，A=11、B=10、C=01、D=00。源端UBA仍开启。
2. 原生LM阻尼作用于Schur矩阵的对角。因此曲率干预也会改变位姿求解器的对角阻尼；这属于本轮曲率路径，不能误归因给梯度。
3. U更新发生在位姿/视差retraction之后。第一轮捕获直接效应；保持一次原生调用内部的两轮迭代，再比较固定U与原生更新U，才能观察反馈。不能用两次独立的一轮BA调用代替，因为原生内部临时缓冲生命周期不同。
4. 完整RGB018 C0已存在。**四组的RGB019/233/401目标BA输入均没有完整历史快照**。observer保存的分位数、部分采样和6类哈希不包含完整target/weight/eta、临时U状态与完整线性系统，不能据此恢复。

## 本轮完成的工作

| 项目 | 结果 |
|---|---|
| C0与四组历史状态清点 | 完成，只读元数据；没有反序列化模型/检查点 |
| 目标状态 | RGB019、233、401 × 四个D/S来源，共12个上下文 |
| 原生候选 | 单独ba_paths_cuda入口；原始CUDA文件全文作为未改写前缀保留 |
| 求解器 | 仍调用原生投影、Schur、Eigen LLT与retraction；仅拆分C/w路径并记录诊断 |
| CPU验证 | 38/38通过；第一次37/38，测试fixture只读数组问题已修正，失败日志保留 |
| CUDA编译/原生等价性 | 尚未执行；不能用CPU测试代替 |
| 新GPU重放/新模型前缀 | 0 / 0 |

## 真实执行仍缺什么

目前远端可用磁盘{res['disk_GiB']:.3f}GiB，保留10GiB后仅{res['headroom_above_reserve_bytes']/1024**3:.3f}GiB可用于本轮；/dev/shm为2GiB。nvidia-smi返回Exec format error，用户进一步确认无卡启动，不按驱动故障处理。

不能承诺所有新快照和输出同时留在服务器。单个完整500×384×45×80 FP32 DINO resize缓冲本身约2.575GiB；必须在真实采集前逐Tensor storage计算预算，分状态串行保存、传回本地并校验，禁止删除封存历史。当前不把估算压缩比当准入依据。

最小补采方案是从封存C0恢复4个独立D/S前缀，重放已冻结S1/S0，只推进到RGB401并捕获3个目标点；最多新增1532次RGB前缀输入处理，不运行完整487帧、不执行Final BA/Filler。**这些是新采集的真实状态，不能宣称逐位恢复了历史四组状态。** 具体方案与预算见PROTOCOL.md。

## 对三个研究问题的当前回答

- 主要来自曲率、梯度还是交互？**尚无真实分项重放，不能归因。** 现已给出可检验的解析分解和CPU合同。
- 为什么在S1/S0下相反？原理上两种曲率对应不同Schur传递映射，梯度的位姿影响也随之变化；真实状态中的大小与方向仍待测。
- 是否据此开发自适应正则？**还不应。** 本轮交叉组合是求解器干预，不是已成立的新算法。

本评审包是完整的TASK005B准备证据，不是已完成的GPU实验结果包。下一步需要有卡环境，以及对明确披露的定向补采方案确认；不自动申请/启动租赁GPU、不改动旧实验。
''')
put('README_请先读.md','''
# TASK005B 当前交付

先读FINAL_REVIEW.md，再读PROTOCOL.md、MATHEMATICAL_DECOMPOSITION.md与GPU_CAPTURE_REQUIREMENTS.md。

当前只有CPU准备与实测验证，真实GPU分项结果为0。03_candidate/native提供完整独立CUDA候选与绑定代码；02_source保存与原始BA的差异；04_tests保存全部新测试及第一次fixture错误日志。原历史实验不在本包中重复封装。

FILE_SHA256_MANIFEST.json覆盖除它自身之外的全部ZIP文件。连接原始日志、C0、权重、RGB和完整GT不发布，敏感运行信息只保留本地；公开REMOTЕ审计摘要保留资源实测结果与原始证据哈希。
''')
put('MATHEMATICAL_DECOMPOSITION.md',r'''
# 固定状态的双路径定义

证据级别：SOURCE_DERIVED + CPU_SYNTHETIC_TESTED，非GPU结果。

固定真实输入theta={pose, disparity d, cached mono d_m, K, target, weight, U, temp_y_cdot, DINO, affine_weights, eta, ii/jj, t0/t1及全部标量}。m=1[d_m>0]必须始终由真实缓存mono决定；D0来源调用传入的zeros不能替代该缓存。

令c、g为曲率与梯度开关；W=源端UBA，与这里的深度右端w不同。

    C_c = C_geometry + c m alpha + (1-c m) eta
    p = m alpha (d-d_m)
    w_g = w_geometry - g p
    Q_c = inverse(C_c)
    H_c = A - E Q_c E^T
    L_c = H_c + diag(ep + lm diag(H_c))
    b_cg = v - E Q_c w_geometry + g E Q_c p
    dx_cg = inverse(L_c) b_cg
    dz_cg = Q_c (w_g - E^T dx_cg)

四格命名为A(1,1)、B(1,0)、C(0,1)、D(0,0)，与历史B1/B2/B3/B4不是同一命名层。

在同一初始线性化、固定c时，开启梯度的直接位姿差精确为：

    dx_c1 - dx_c0 = inverse(L_c) E Q_c p

因此两条路径交互为：

    I = [inverse(L_1) E Q_1 - inverse(L_0) E Q_0] p

梯度开关在第一轮不改变H/L的谱；曲率开关会改变H、右端的几何消元项及lm相关位姿阻尼。第二轮因pose/depth已经变化，梯度也可间接改变矩阵谱。这是局部求解器因果关系，尚不能直接解释整轨迹ATE反转。

必须同时给出条件对比A-B、C-D、A-C、B-D及交互A-B-C+D。相加关系为A-D=(B-D)+(C-D)+I；向量贡献不能用范数之和伪造百分比。对误差标量另行计算，不把dx大小直接当成误差。

跨路径的B/C通常不是原始先验损失的一致Gauss-Newton近似。例如C保留先验梯度但用eta曲率；它可能产生很大步长。这是用于归因的受控局部系统，不是可直接部署的估计器。其失稳不能直接证明原始DROID-W实现错误。

## 条件性与残差

保存未阻尼H和实际求解L，并分别报告原始不对称范数。原生Eigen SimplicialLLT默认使用下三角；谱诊断应明确使用下三角自伴矩阵，不悄悄平均上下三角。分别记录特征值、奇异值、数值秩、正定性和kappa2；秩缺失时不填有限条件数。平移/旋转量纲混合及固定窗口规范会影响数值，因此同时保留未缩放谱及可选对角平衡谱，不能拿alpha/eta充当条件数。

原生LLT分解失败会返回零dx；不能仅凭进程退出码或dx为0判定求解成功。真实运行需复查保存的L、求解残差及原生端点等价性。

几何评价保存完整残差、原始权重、源端/目标端门控与有效性。报告固定before权重/共同有效支持下的前后SSE及原生自适应权重SSE，防止通过降低权重或失去投影支持制造“改善”。无独立depth GT，不宣称Metric3D预测正确或错误。

源码依据：冻结src/lib/droid_kernels.cu中的ba_cuda和SparseBlock::solve。官方[固定版本源码](https://raw.githubusercontent.com/MoyangLi00/DROID-W/c3414af6047d06bafc1a6645d09f23247f3b2cdc/src/lib/droid_kernels.cu)。本地Git blob为9c171af1bfafc278e9776f2f89667054a66dc2bf，候选生成前硬校验。
''')
put('PROTOCOL.md','''
# TASK005B 受控实验合同

## 状态选择与层次

只使用val_007、seed43、原始R2权重/K/预处理、buffer500和冻结S1/S0。RGB019为共同C0后的第一项Predecision BA；中期在229—237范围选择距233最近的四组共同Predecision帧；晚期在393—409选择距401最近的共同帧。实测均恰好选到019/233/401，每点取首个Predecision native call。

233来自既有前缀ATE观察，是探索性选点，不是物理故障发生时刻。401预先固定为晚期代表点；不根据本轮分项结果挑选最显著位置。12个上下文保留四个来源，不把它们当12个独立统计重复；019若全部输入、标量、储存关系完全相同可去重执行并保留来源映射，6类历史哈希相同本身不足。

每个状态独立克隆到A/B/C/D × U_FROZEN/U_NATIVE_UPDATE共8格。每格一次两轮原生BA；第一轮提供直接作用，第二轮提供允许U变化后的反馈，期间不调用网络更新target/weight/eta，不重选关键帧，不改图。W保持开启，目标端门控等其他参数沿用快照。

保存每轮before、native-after，以及原本单次BA返回后的clamp-after；不在两轮内部增加clamp。固定U意味着禁止更新U及其affine/temp状态，数值输入仍为真实旧U；不把U清零、不关闭DINO模型缓存。

## 真实状态缺失与最小采集

历史目标输入无完整payload。需要从RGB018 C0恢复四个新进程，分别按(D1,S1)、(D0,S1)、(D1,S0)、(D0,S0)推进到RGB401，统一重放已封存调度。原生产臂也应按已封存调度强制重放，以免重新生成S。四前缀最多1532次新帧处理；不重算RGB001—018，不执行后续402—487、Final BA或Filler。中间采集不改变状态与随机源。

这是新采集的受控前缀，并不保证复现旧四组每个连续Tensor。必须报告新输入与历史可用哈希的匹配/差异，科学结论限于新采集状态。不能把新快照写回原B1/B2/B3/B4目录。

## 原生端点核验

候选独立编译为gamecam_task005b_depth_paths；不覆盖droid_backends.so，不重编译或重装原环境中的原扩展。原始CUDA源逐字节保留，追加一个新入口，仅分离C/w两式并记录诊断。当前候选未编译，不能称已验证的GPU运行器。

每个state/U模式增加原已安装扩展的D1/D0两个两轮参照，共4次参照调用。A须对应真实mono，D须对应zeros；比较dx、dz、poses、disps、U、affine/temp。固定预设数值门槛atol=1e-6、rtol=1e-5，逐字段报告最大差异；所有输入SHA严格相等。若出现超差、非有限值或求解失败，停止，不放宽门槛、不自动重试。门槛通过也不等于跨平台确定性。

上限为12上下文×(8分项+4参照)=144次两轮原生BA调用。不是144次完整SLAM，不是统计n=144。只有完整输入证明重复时才减少次数；不增加种子或其他序列。

## 评价与解释

主评价是同状态每个目标Pose的dx/dz、固定权重重投影变化、保存系统的谱与求解残差及条件对比，不以更新较小=精度更高。需要运动误差时，固定同一个before状态的尺度/坐标映射，GT仅用于离线评分，禁止给每个格子重新独立拟合Sim3以掩盖局部更新。

Task005A的相反效果限定为位置Sim3 ATE；尺度诊断与姿态误差并无相同反转。本轮不能默认每个位置/每种指标也必然反转。S1/S0是内生历史调度，不是独立随机化的几何条件。不得声称单次局部效应已解释完整487帧总效应。

## 执行边界

当前用户确认无卡，本轮未启动实例。开启3090后先检查可信主机与原有源码、权重、扩展身份，精确计算本轮存储，再单独启动上述定向采集与原生验证。任何完整状态缺失、原生等价性失败、空间不足或CUDA错误停止并保留证据。定向补采的规模已在本包明确披露，提交用户确认后推进；不隐式扩大到全487帧。
''')
put('GPU_CAPTURE_REQUIREMENTS.md','''
# 完整BA输入与存储要求

每个native调用前捕获13个实参Tensor：poses、disps、intrinsics、selected_prior、targets、weights、uncertainties、temp_y_cdot、dino_feats_resize、affine_weights、eta、ii、jj。同时另存真实cached_mono_disps；D0的selected_prior全零并不代表真实mono不存在。保存所有17个标量：t0/t1/iterations/lm/ep/gamma_data/gamma_prior/gamma_depth/lr/weight_decay/motion_only/depth_only/enable_update_uncer/enable_udba/enable_affine_transform/enable_bidirectional_uncer/debug。

附带active_count、slot↔RGB、调度前缀SHA、native调用编号与阶段、source/config/extension pins、真实RNG状态及原始输出。每Tensor记录shape、dtype、stride、storage_offset、device、全部字节SHA以及storage alias关系。反序列化后重算；有alias时必须保留，禁止逐Tensor clone后仍声称alias一致。

原生求解器新增trace每轮22项：poses/disps/U before，C_geometry/w_geometry，C/w/Q/E/kx，A/v、Schur扣除矩阵及右端、H/rhs/L、dx/dz、poses/disps/U after。还要保留不可变full target/weight/K/图/先验，才能计算完整像素残差，不把旧observer采样当full objective。

当前磁盘只有约3.498GiB超过10GiB安全余量；本地C盘接收空间约19.66GiB，D盘约5.90GiB，均为本轮检查时快照。完整DINO resize缓冲单独为2,764,800,000 bytes；其他输入、trace、模块编译产物和临时归档也需计算。真实总量UNKNOWN。

复用已封存C0只读文件；不再次复制整套C0或模型。采集前按唯一storage精确计数，写入前检查最坏原始空间，压缩是后续优化，不拿预计压缩比准入。保存一次、传本地、SHA验证、ZIP/归档CRC验证，再决定本轮临时输出的生命周期；不删除任何旧产物。当前没有执行删除、移动或新的数据传输。

若空间不足，提交该次实际storage字节数和最小扩容/转存方案。不要为通过门槛降低buffer、精度、分辨率或丢弃必须的输入。
''')
put('U_FEEDBACK_PROTOCOL.md','''
# U反馈的时间顺序

原生循环先生成geometry→solve→pose/disparity retraction，再执行U更新。因而在相同完整初始状态下，第一轮允许/禁止U更新不应改变第一轮dx/dz；这里只可能有原生浮点非确定性，需逐项检查。

第二轮固定U组使用旧U，更新U组使用上一轮产生的新U；目标/原始weight/eta/图不重新由网络产生。两轮必须保留在同一个ba调用里；其J_linear等scratch缓冲并不是每次独立调用都相同的生命周期。把两次独立1-iteration调用等同于一次2-iteration调用没有源码依据。

记录U、affine_weights、temp_y_cdot的更新，以及实际源端乘子，不因开关相同就说权重相同。第一轮各C/G组的U_after可以不同，它通过第二轮参与反馈。固定初态的第二轮差异是本地U反馈效应，不等于网络target/eta等完整前端反馈。

残差需同时报告冻结before权重和更新后的实际权重；减小自适应加权损失不能单独证明几何更准。
''')
put('CPU_VALIDATION_REPORT.md','''
# CPU验证结果

第二次完整执行38/38通过，退出码0；NumPy合成正规方程与源码检查，没有CUDA。

检查包括A/D原生公式端点、B/C单路径隔离、无效prior掩码、Schur解与完整联合系统一致、LM放置、解析梯度传递、交互闭合、无耦合/零prior误差/alpha=eta退化情形、NaN/Inf/非正深度块拒绝、秩与下三角谱诊断、原始源码blob与全文保留、U更新体与几何调用不变、两轮保持一次原生调用。

首次37/38通过；唯一ERROR为NumPy.diag产生的只读fixture数组被测试尝试置零。修改fixture为明确copy后重跑，未修改数学公式或放宽断言。首次stdout/stderr和结构化结果完整保留。没有把CPU结果标为CUDA验证。

后续GPU必须独立通过A/D与已安装原生扩展等价性、两种U模式、完整输入SHA、输出有限性和谱/求解残差审查。
''')
put('EXECUTION_LOG.md','''
# 执行记录

1. 读取Task005A原始报告、提案、冻结CUDA源码及Task004C-B封存清单。
2. 第一次SSH使用默认known_hosts，因当前端口条目不存在失败；未接受未知密钥。随后找到历史专用pin文件，验证其ED25519指纹，使用历史HostKeyAlias完成hostname检查及一次只读资源/文件清点。没有修改known_hosts。
3. 可信目标主机与之前实例一致。nvidia-smi两项查询均返回Exec format error；用户确认当前无卡启动。未修改驱动、启停实例或初始化CUDA。
4. 只读C0 TAR目录和manifest JSON，不提取/反序列化Tensor；扫描四组observer/native trace目录和npz成员名。保存12个目标状态元数据，确认目标完整BA输入缺失。
5. 创建独立ba_paths_cuda候选与CPU数学参考，冻结原始源码blob；没有编译新模块或触碰已安装扩展。
6. 首轮38项检查中1项fixture报错，保留日志；修正fixture后38/38通过。逐项测试实录见04_tests。
7. 形成有明确资源规模的定向补采方案，整理公开评审包，验证历史封存与ZIP/文件哈希；GitHub发布另有可核验回执。

真实GPU实验0，模型推理0，完整/前缀RGB执行0，原生BA重放0，远端文件修改0。
''')
security={'gpu_requested':False,'gpu_started':False,'cuda_initialized':False,'new_GPU_replays':0,'new_RGB_prefix_runs':0,'baseline_model_runs':0,'checkpoint_deserialized':False,'original_BA_formula_modified':False,'isolated_mathematical_intervention_candidate_generated':True,'new_extension_compiled':False,'installed_extension_modified':False,'sealed_Task004CB_modified':False,'original_weights_or_config_modified':False,'remote_files_modified':False,'unknown_SSH_key_accepted':False,'SSH_pin_verified':True,'user_confirmed_no_GPU_boot':True,'TASK005C_or_TASK006_started':False,'historical_results_deleted':False,'synthetic_results_presented_as_real':False}
put('SECURITY_AUDIT.json',json.dumps(security,ensure_ascii=False,indent=2))
put('TASK005B_DECISION.json',json.dumps({'status':'CPU_PREPARATION_COMPLETE_GPU_EXPERIMENT_NOT_STARTED','real_mechanism_attribution':'INSUFFICIENT_EVIDENCE','CPU_tests_passed':38,'native_GPU_replays_executed':0,'historical_BA_target_checkpoints_complete':0,'target_contexts':12,'C0_available':True,'blocking_conditions':['User-confirmed no-GPU instance','Target complete historical BA inputs absent','Native candidate not compiled or GPU-equivalence tested','Exact live capture/trace storage budget not established'],'next_concrete_operation':'User-confirmed directed prefix capture through RGB401 on a GPU-enabled instance, then bounded 2x2/U replay; no full487 rerun'},ensure_ascii=False,indent=2))
put('DATA_AVAILABILITY.md','''
# 公开评审包范围

包含本轮报告、完整独立求解器候选源码、公式参考、状态选择、CPU测试源码和原始测试记录、完整性清单。未包含模型权重、RGB、完整GT、真实C0或连接凭据。新原生GPU输出为空，因为尚未执行。

00_intake中的连接原始日志与C0对象图保留本地，不公开。05_evidence提供去除主机/账户路径的事实摘要及来源文件SHA，原始历史证据由Task004C-B封存包与Task005A固定提交引用。用于ChatGPT审查准备工作的完整包不等于包含第三方数据的即用复现实验集。
''')
source_files=['00_intake/REMOTE_READONLY.stdout.json','00_intake/REMOTE_READONLY_RECEIPT.json','00_intake/C0_MANIFEST_INTAKE.json','00_intake/BA_EVIDENCE_INVENTORY.json','00_intake/SEALED_HISTORY_CHECK.json']
summary={'GPU_mode':'NO_GPU_BOOT_CONFIRMED_BY_USER','trusted_connection_verified':True,'remote_commands_read_only':True,'remote_disk_free_bytes':res['disk_free_bytes_at_probe'],'remote_shm_bytes':res['shm_bytes'],'nvidia_smi':'EXEC_FORMAT_ERROR','sealed_history_check':read('00_intake/SEALED_HISTORY_CHECK.json'),'raw_evidence_SHA256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_files}}
put('05_evidence/INTAKE_PUBLIC_SUMMARY.json',json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps({'reports_written':True,'CPU_tests':tests['total'],'GPU_executed':0}))

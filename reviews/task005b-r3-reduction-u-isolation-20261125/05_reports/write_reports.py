"""Write scientific decisions only from completed R3 outputs and checks."""
import sys,pathlib,json,csv,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
def read(rel):return json.loads((ROOT/rel).read_text(encoding='utf-8'))
def rows(name):
    with (ROOT/'04_analysis'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,text):(ROOT/name).write_text(text.rstrip()+'\n',encoding='utf-8')
def number(x):return f'{float(x):.8g}'
def main():
    iso=read('04_analysis/ISOLATED_SUMMARY.json');ba=read('04_analysis/BA_ANALYSIS_SUMMARY.json');math=read('04_analysis/INDEPENDENT_FEEDBACK_FORMULA_AUDIT.json');tests=read('03_tests/FULL_CPU_TEST_REPORT.json');pres=read('ORIGINAL_EVIDENCE_PRESERVATION.json')
    assert tests['PASS'] and math['all_original_tolerance_PASS'] and pres['all_protected_SHA_unchanged']
    jjj=next(r for r in iso if r['field']=='Jjj_data');linear=next(r for r in iso if r['field']=='J_linear')
    fixed=all(r['fixed_repeat_bitwise_equal'] for r in ba['feedback_variability'] if r['field'] in ['iter2_Cii_geometry','iter2_H_raw','iter2_rhs','iter2_dx','iter2_dz'])
    native=all(r['strict_all_final_pairs_PASS'] for r in ba['within'] if r['group'].endswith('native')) and all(r['all_final_pairs_PASS'] for r in ba['cross'] if r['comparison'] in ['original_vs_reference_native','original_vs_paths_native','reference_vs_paths_native'])
    gate='DIAGNOSTIC_COMPLETE_U_FEEDBACK_ISOLATED_NATIVE_GATE_NOT_PASSED' if fixed and not native else 'DIAGNOSTIC_COMPLETE_REQUIRES_REVIEW'
    endpoint_table='|比较|调用数/模式|相关配对数|七个最终字段全部通过|\n|---|---:|---:|---:|\n'
    for r in ba['within']:endpoint_table+=f"|{r['group']}|{r['calls']}|{r['within_pair_count']}|{r['seven_final_fields_PASS_pairs']}|\n"
    for r in ba['cross']:
        if 'native_vs_fixed' not in r['comparison']:endpoint_table+=f"|{r['comparison']}|4 vs 4|{r['pairs']}|{r['all_seven_final_PASS_pairs']}|\n"
    iso_table='|字段|固定输入调用数|逐位相同配对|原容差通过配对|最大绝对差|变化元素|最大ULP|\n|---|---:|---:|---:|---:|---:|---:|\n'
    for r in iso:iso_table+=f"|{r['field']}|16|{r['bitwise_equal_pairs']}/120|{r['tolerance_PASS_pairs']}/120|{number(r['max_pair_abs'])}|{r['variable_elements']}|{r['max_pair_ULP']}|\n"
    feedback='|实现|输出|Native重复RMS SD|Fixed重复RMS SD|Fixed逐位重复|\n|---|---|---:|---:|---|\n'
    for r in ba['feedback_variability']:
        if r['field'] in ['iter2_H_raw','iter2_rhs','iter2_dx','iter2_dz','affine_weights','temp_y_cdot']:feedback+=f"|{r['implementation']}|{r['field']}|{number(r['native_RMS_SD'])}|{number(r['fixed_RMS_SD'])}|{r['fixed_repeat_bitwise_equal']}|\n"
    cond=rows('BA_NORMAL_EQUATION_CONDITIONING.csv');condmin=min(float(r['condition_number']) for r in cond);condmax=max(float(r['condition_number']) for r in cond)
    write('R3_REDUCTION_ISOLATION.md',f'''# Jjj 与 J_linear 独立重复性

两个实验各16次串行调用，全部输入固定并前后SHA核验。J_linear使用封存的R2 J_total，完全不使用本轮Jjj结果。

{iso_table}

结论：两处原文未改的CUDA kernel各自存在独立的非逐位重复。Jii和kf_count全部逐位一致；Jjj散射累加与J_linear通道归约均会波动，但本轮各自120个相关配对全部满足原容差。

J_linear可能接近零且存在正负抵消，因此绝对差很小也可能产生很大的ULP距离；不能把最大ULP单独当作绝对数值严重性。逐元素变化及16次所有变化值存于04_analysis/*ELEMENTWISE_VARIATION.npz，原输出52份完整保留。

本轮定位到两个具体归约kernel，不记录每条atomic指令执行顺序，不把两者传播贡献强行分成百分比。n=16只针对同GPU、同状态；120个配对共享调用。
''')
    write('R3_U_FEEDBACK.md',f'''# U 单通道反馈隔离

同一完整状态，reference/paths各Native U和Fixed U两模式，每模式4次双迭代BA。Fixed U保留affine/temp原生更新，记录U_computed后仅恢复U到调用起点。

固定U控制验收：{ba['all_fixed_U_controls_PASS']}；affine/temp确实继续更新：{ba['all_fixed_affine_and_temp_actually_update']}；每次第一轮→第二轮状态接缝核验：{ba['all_feedback_seams_PASS']}。

{feedback}

本状态Fixed U下第二轮几何正规方程及dx/dz是否在各自4次重复中逐位一致：**{fixed}**。具体每个中间字段和全部配对见BA_GROUP_DISPERSION.csv、BA_FIRST_DIFFERENCE_TIMELINE.csv。

当Native U的第二轮存在差异而Fixed U第二轮几何和求解重复时，支持U→几何权重通道将第一轮归约波动传入第二轮。这是本受控状态的通道隔离证据，不是原模型全部误差的归因，也不证明D/S1/S0效果反转已经解释。

固定U仍保留affine/temp反馈，不能宣称整个优化状态完全确定。该干预同时移除正常U更新和噪声；Native/Fixed均值差不是纯噪声放大效应。Fixed重复标准差为0时，比例没有有限分母，CSV使用null，不能报告无限统计放大倍数。

{len(cond)}个实际记录的阻尼Pose系统采用原生LLT下三角语义分析（16次诊断BA×2轮）；全部SPD={ba['all_systems_SPD']}，条件数范围{condmin:.6g}–{condmax:.6g}。原安装4次没有内部矩阵trace，未伪造其内部系统。这些系统不是奇异矩阵，但条件数约2.6×10^5，不能把SPD解释为不存在数值敏感性。

几何权重另有显式源码公式审查：R3_GEOMETRY_WEIGHT_AUDIT.md。CPU FP64代理与真实GPU几何方程分开记录，未冒充原生逐位权重转储。
''')
    write('R3_IMPLEMENTATION_EQUIVALENCE.md',f'''# 原安装、reference 与 paths(0,0)

未改变atol=1e-6、rtol=1e-5；七字段为dx_last、dz_last、Pose、disparity、U、temp、affine。

{endpoint_table}

Native原始参考与paths的全字段严格门槛通过：**{native}**。不能只选择某个通过配对认定整体等价。Fixed U的通过只覆盖本D0状态及有意干预模式，不替代Native U准入。

原安装/reference使用零prior，paths传真实mono但C=G=0；有效D0语义相同，prior实参字节不同。其他输入以实际SHA、元数据和alias合同核验。

独立归约实验已证明原文kernel可波动，原安装自身重复也作为对照；这降低了“任何端点差异均由候选路径错误导致”的解释力。尚未独立识别编译器/布局/观测同步的贡献，不能反向宣称候选没有任何缺陷。两种诊断实现第一轮与Fixed U第二轮的语义证据，应与Native严格门槛分开评审。
''')
    decision={'task':'TASK005B-R3','status':gate,'context':'D0_S1_RGB233','isolated_jjj_calls':16,'isolated_J_linear_calls':16,'two_iteration_BA_calls':20,'internal_BA_iterations':40,'tolerance':{'atol':1e-6,'rtol':1e-5,'changed':False},'both_reductions_independently_nonbitwise_reproducible':jjj['bitwise_equal_pairs']==0 and linear['bitwise_equal_pairs']==0,'isolated_reductions_all_original_tolerance_PASS':jjj['tolerance_PASS_pairs']==120 and linear['tolerance_PASS_pairs']==120,'Fixed_U_second_round_geometry_and_solve_repeat_bitwise':fixed,'fixed_U_only_controls_validated':ba['all_fixed_U_controls_PASS'],'affine_temp_updates_preserved':ba['all_fixed_affine_and_temp_actually_update'],'native_unconditional_endpoint_gate_PASS':native,'direct_compiler_contribution_isolated':False,'atomic_instruction_order_captured':False,'individual_Jjj_vs_linear_propagation_fraction_identified':False,'S0_started':False,'remaining_S1_matrix_resumed':False,'original_CUDA_implementation_modified':False,'R1_R2_assets_modified':False,'new_diagnostic_extension_compiled':True,'model_loaded_or_forward_executed':False,'instance_shutdown':False,'next_stage_requires_review':True,'CPU_tests_PASS':tests['tests'],'independent_formula_checks_PASS':math['checks']}
    write('R3_DECISION.json',json.dumps(decision,indent=2,ensure_ascii=False))
    write('R3_CANDIDATE_READINESS.md',f'''# 是否调整 CUDA，以及能否恢复机制实验

状态：**{gate}**。

1. 两处归约独立波动已确认，U反馈通道在本状态被直接控制。可以把它作为数值诊断机制结论，不作为轨迹精度改善或D深度机制归因结果。
2. Native U严格端点门槛通过={native}。保持原门槛，不通过放宽容差将结果改为PASS。
3. Fixed U第二轮几何/求解逐位重复={fixed}。这支持D0固定状态下reference/paths计算语义的验证范围，但不授权以Fixed U替代原始研究配置。
4. 当前不修改原始CUDA实现。单次归约的波动均在原容差内，改成确定性归约会改变累加次序、性能和Baseline身份，必须是独立候选及单独审批，不能覆盖原.so。
5. 若后续必须获得严格Native端点证书，最小可评审方向是独立确定性诊断归约副本，或预先定义基于原生重复的数值评价合同。两者本轮均未执行；不得事后调整标准宣布已通过。
6. 恢复S1剩余和启动S0仍需用户评审。本轮未检查D1端点、其他时点、其他调度或GPU，不能自动扩大准入。

尚未完成：Jjj与J_linear各自对最终dz的定量因果份额、独立编译差异、跨状态稳定性、S1/S0深度路径效果反转解释。
''')
    write('FINAL_REVIEW.md',f'''# TASK005B-R3：CUDA 归约与 U 反馈隔离评审

2026-11-25（Asia/Shanghai）。状态：**{gate}**。

## 核心结果

**两个原生浮点归约在固定输入下各自可波动；仅冻结U、保留affine/temp更新后，两个诊断实现的第二轮几何方程、dx和dz在各自四次重复中逐位一致。Native U严格端点门槛仍未通过。** 这次把“归约自身波动”和“U进入下一轮BA”分开测量，没有把Jjj的波动传给独立J_linear实验。

{iso_table}

本轮实际完成16次Jjj、16次J_linear和20次双迭代BA（40轮内部迭代）。全部输出有限，没有OOM、自动GPU重试、模型运行或RGB前缀。原安装二进制4次，其余reference/paths × Native/Fixed U各4次。

## U反馈及候选差异

{feedback}

Fixed U的第二轮几何/求解在每个实现内部逐位重复：**{fixed}**；U-only干预验证通过：**{ba['all_fixed_U_controls_PASS']}**；affine/temp继续更新：**{ba['all_fixed_affine_and_temp_actually_update']}**。

Fixed U只恢复U，不关闭enable_update_uncer，不冻结affine或temp。Native模式与Fixed模式正常状态演化本来不同，均值差不能全归为浮点噪声。完整比较见R3_U_FEEDBACK.md。

{endpoint_table}

**Native U的严格端点准入通过={native}。** 不改变原容差，不把部分通过的配对、Fixed U结果或工程测试当成完整Native等价性证书。

原安装自身6个相关配对中仅2个通过七字段联合门槛；主要超差字段为dz_last，1个配对的dx_last也超差。原安装与paths的16个相关配对为9个通过，不能解释为统计通过概率。Fixed U下reference与paths为16/16通过原容差，但并非七字段全部逐位一致。分项最大误差及超差元素数见04_analysis/BA_FINAL_FIELD_COMPARISON_SUMMARY.csv。

## 归因边界及科研决策

已有直接证据：两个归约各自非逐位重复；原安装自身的重复对照；Fixed U控制及第二轮几何、正规方程和dx/dz的实际变化。源码支持的传播通道为 Jjj/J_linear → affine → U → 几何权重 → 第二轮Schur系统。

尚未证明：精确atomic执行顺序、两处归约分别占最终误差的百分比、独立编译/观测影响为零、所有候选状态均等价。仅一份D0_S1_RGB233，不解释S1/S0深度正则反转的最终根因。

建议保持原CUDA及R1/R2封存，先审查本轮通道隔离和数值合同。若要严格确定性证书，应单独评审诊断实现及标准，不覆盖Baseline，不自动恢复S1/S0。

## 验证、保护与交付

{tests['tests']}/{tests['tests']} CPU测试，{math['checks']}/{math['checks']}独立公式复算通过；{len(pres['protected_files'])}个保护文件SHA保持一致。结束数据盘可用{pres['disk']['free']/1024**3:.3f}GiB，本轮新增约{pres['r3_total_bytes']/1024**2:.2f}MiB，保留10GiB底线。GPU结束无计算进程，实例未关机。

完整ZIP包含原输入tar、固定R2中间态、52份原始输出、逐轮状态、诊断.so、源码差异、运行日志与SHA清单。GitHub展开报告与CSV便于直接审查；ZIP的CRC、所有内部SHA及匿名下载另作发布验收。
''')
    write('README_请先读.md','''# TASK005B-R3 评审入口

先读FINAL_REVIEW.md，再读R3_REDUCTION_ISOLATION.md、R3_U_FEEDBACK.md、R3_IMPLEMENTATION_EQUIVALENCE.md、R3_CANDIDATE_READINESS.md。

本轮没有进入S0或剩余S1机制矩阵。工程测试通过与Native数值准入分开记录；详细限制见METHOD_AND_LIMITATIONS.md。

04_analysis含全部误差CSV、逐元素变化NPZ和独立公式复算；05_reports/figures含两张诊断图。完整大数组、输入快照及二进制在同Release的GAMECAM_TASK005B_R3_REVIEW.zip内，见COMPLETE_RAW_ASSET_INDEX.json。
''')
    security={'gpu_requested':False,'existing_GPU_used':True,'gpu_restarted':False,'cuda_context_initialized':True,'model_loaded':False,'model_forward_executed':False,'checkpoint_snapshot_deserialized':True,'model_weights_deserialized':False,'RGB_sequence_processed':False,'training_executed':False,'S0_executed':False,'remaining_S1_executed':False,'original_extension_replaced':False,'R1_R2_modified':False,'independent_diagnostic_extension_compiled':True,'GPU_call_retries':0,'SSH_pin_verified':True,'instance_shutdown':False,'historical_files_deleted':False,'tolerance_changed':False}
    write('SECURITY_AUDIT.json',json.dumps(security,indent=2))
    source=(ROOT/'02_candidate/task005b_r3_kernels.cu').read_text(encoding='utf-8').splitlines();mapping=[]
    for name in ['projective_transform_kernel','dino_feats_projective_transform_kernel','linear_transform_kernel','uncertainty_update_kernel','ba_r3_reference_cuda','ba_r3_paths_cuda','isolated_jjj_cuda','isolated_linear_cuda']:
        line=next(i for i,t in enumerate(source,1) if ('void '+name+'(' in t or 'Tensor> '+name+'(' in t));mapping.append(f'|{name}|02_candidate/task005b_r3_kernels.cu:{line}|')
    write('SOURCE_MAP.md','# 源码映射\n\n|函数|位置|\n|---|---|\n'+'\n'.join(mapping)+'\n\nR1原函数正文位于新源码前缀，CPU合同核验一致。reference/paths相对R2差异见02_candidate/*_vs_R2.diff。原安装.so及R1/R2所有保护文件SHA见ORIGINAL_EVIDENCE_PRESERVATION.json；未以无.git目录的HEAD伪造提交核验。')
    receipts=sorted((ROOT/'00_intake').glob('*.receipt.json'));entries=[]
    for p in receipts:
        r=json.loads(p.read_text());time=datetime.datetime.fromtimestamp(r['started_unix'],datetime.timezone(datetime.timedelta(hours=8))).isoformat();entries.append(f"- {time}：{p.stem}；exit={r['exit_code']}，SSH信任核验={all(r['trust'].values())}。")
    write('EXECUTION_LOG.md','# 执行记录\n\n'+'\n'.join(entries)+'\n\n完整科学进程stdout/stderr、每调用STARTED/receipt与SHA在06_runtime_evidence及原始数据中。编译时隐藏GPU，No CUDA runtime提示来自构建探测，不是本轮GPU故障。GPU主进程一次启动且exit0。')
    print(json.dumps(decision,indent=2))
if __name__=='__main__':main()

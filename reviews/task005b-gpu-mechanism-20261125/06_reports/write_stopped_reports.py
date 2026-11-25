"""Truthful terminal review after endpoint-equivalence guard stopped GPU work."""
import pathlib,sys,json,tarfile,csv,hashlib,datetime
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
RECEIVER=pathlib.Path(r'C:\Users\Administrator\Documents\GameCam-TASK005B-GPU-20261125-R1')

def rows(name):
    with (ROOT/'05_analysis'/name).open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def write(name,value):(ROOT/name).write_text(value,encoding='utf-8')
def dump(name,value):write(name,json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def table(headers,values):return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+'\n'.join('| '+' | '.join(str(x) for x in row)+' |' for row in values)+'\n'

def main():
    failure=json.loads((ROOT/'05_analysis/ENDPOINT_FAILURE_FORENSICS.json').read_text())
    assert failure['failure_reproduced_on_CPU'] and failure['partial_total_native_calls']==10
    assert not (ROOT/'04_results/SUPERVISOR_SUCCESS.json').exists()
    metrics=rows('NATIVE_ITERATION_METRICS.csv');endpoint=rows('ORIGINAL_ENDPOINT_EQUIVALENCE.csv');contexts=rows('CONTEXT_MECHANISM_SUMMARY.csv')
    schur=rows('CPU_SCHUR_RECONSTRUCTION.csv');formulas=rows('NATIVE_FORMULA_CHECKS.csv');feedback=rows('U_FEEDBACK_CONTRASTS.csv')
    assert len(metrics)==64 and len(endpoint)==16 and all(r['PASS']=='True' for r in endpoint)
    transfer=json.loads((ROOT/'07_release/RUN_EVIDENCE_TRANSFER.json').read_text());prefix=[];events=[]
    with tarfile.open(transfer['archive'],'r:gz') as archive:
        for arm in ('D1_S1','D0_S1'):
            result=json.load(archive.extractfile('attempts/'+arm+'/SUCCESS.json'))
            receipt=json.load(archive.extractfile('attempts/'+arm+'/PROCESS_RECEIPT.json'))
            restored=json.load(archive.extractfile('attempts/'+arm+'/RESTORE_RECEIPT.json'))
            prefix.append({'arm':arm,'keyframes':result['keyframes'],'seconds':receipt['seconds'],'new_input_steps':result['new_input_steps'],
                           'C0_nodes':restored['object_nodes'],'full_C0_match':restored['all_tensor_and_object_nodes_match'],
                           'peak_cuda_bytes':result['peak_cuda_bytes'],'schedule_events':result['consumed_events'],'schedule_chain_tip':result['last_source_event_sha256']})
        audit=json.load(archive.extractfile('evidence/FROZEN_IDENTITY_AFTER_STOP.json'))
    dump('04_results/PREFIX_EXECUTION_SUMMARY.json',prefix)
    dump('00_intake/FROZEN_IDENTITY_AFTER_STOP_PUBLIC.json',audit)
    for line in (ROOT/'04_results/SUPERVISOR_EVENTS.jsonl').read_text().splitlines():events.append(json.loads(line))
    assert len([e for e in events if e['event']=='LAUNCHED' and e.get('state') is None])==1 # D1_S1 was launched before supervisor.
    first_U=max(float(r['native_minus_frozen_dx_translation_norm']) for r in feedback if r['iteration']=='1')
    second_U=[float(r['native_minus_frozen_dx_translation_norm']) for r in feedback if r['iteration']=='2']
    max_res=max(float(r['native_linear_relative_residual']) for r in metrics)
    failed_systems=json.loads((ROOT/'05_analysis/FAILED_CONTEXT_LINEAR_DIAGNOSTICS.json').read_text())
    formula_fails=[r for r in formulas if r['allclose_1e_5_1e_6']!='True']
    recon={k:max(float(r['relative_frobenius']) for r in schur if r['formula']==k) for k in ('Schur_matrix','Schur_rhs','dz_native_guard')}
    decision={'task':'TASK005B_GPU_MECHANISM_ATTRIBUTION','status':'STOPPED_ENDPOINT_EQUIVALENCE_FAILURE',
              'scientific_decision':'PARTIAL_LOCAL_EVIDENCE_NOT_FULL_MECHANISM_ATTRIBUTION',
              'prefixes_completed':2,'prefixes_planned':4,'captured_states':6,'planned_states':12,
              'complete_replay_contexts':4,'partial_replay_contexts':1,'unstarted_replay_contexts':7,
              'new_input_frame_steps':sum(p['new_input_steps'] for p in prefix),
              'original_installed_native_calls':20,'candidate_native_calls':38,'native_calls_executed':58,'native_call_budget':144,
              'endpoint_checks_passed':19,'endpoint_checks_failed':1,'endpoint_checks_not_run':28,
              'failure_state':'D0_S1_RGB233','failure_mode':'NATIVE_UPDATE_D',
              'fixed_atol':1e-6,'fixed_rtol':1e-5,'dx_violations':3,'dz_violations':2657,
              'all_final_pose_disparity_U_affine_fields_pass_tolerance':True,
              'failure_cause_established':False,'NaN_or_Inf_in_failed_saved_arrays':False,
              'failed_candidate_systems_SPD':all(r['L_SPD'] for r in failed_systems['observations']),
              'failed_candidate_system_condition_numbers':[r['L_condition_2'] for r in failed_systems['observations']],
              'installed_original_vs_itself_reproducibility_test_executed':False,
              'completed_context_damped_systems':64,'completed_context_all_damped_systems_SPD':all(r['L_SPD']=='True' for r in metrics),
              'completed_context_max_linear_relative_residual':max_res,'completed_context_CPU_Schur_relative_errors_max':recon,
              'completed_context_formula_failures':len(formula_fails),
              'first_iteration_U_mode_dx_difference_max':first_U,'second_iteration_U_affine_feedback_norm_range':[min(second_U),max(second_U)],
              'S0_prefixes_executed':0,'S1_vs_S0_reversal_explained':False,'Task005C_executed':False,'Task006_executed':False,
              'GPU_numerical_retry_executed':False,'tolerance_changed':False,'GPU_compute_processes_after_stop':audit['gpu_compute_processes'],
              'frozen_assets_after_stop_passed':audit['all_protected_asset_hashes_match'],'shutdown_performed':False}
    dump('TASK005B_DECISION.json',decision)
    failed_fields=[[r['field'],r['elements'],r['violations'],f"{r['max_absolute_difference']:.9g}",f"{r['max_error_to_allowed_tolerance']:.6g}",r['runtime_allclose_reproduced']] for r in failure['fields']]
    completed=[[r['arm'],r['rgb'],r['U_mode'],r['iteration'],f"{float(r['A_translation_dx_norm']):.6g}",f"{float(r['B_translation_dx_norm']):.6g}",f"{float(r['C_translation_dx_norm']):.6g}",f"{float(r['D_translation_dx_norm']):.6g}"] for r in contexts if r['iteration']=='2' and r['U_mode']=='NATIVE_UPDATE']
    write('FINAL_REVIEW.md',f'''# TASK005B GPU 阶段评审：原生端点超差后停止

**本轮没有完成12上下文的机制归因。** 已完成2/4条定向前缀、采到6/12个真实输入状态；4个上下文完整重放，第5个在端点等价性校验失败后停止。累计58/144次原生两轮BA调用：20次原安装扩展参照、38次独立候选调用。没有自动重试、放宽容差或启动S0前缀。

## 停止原因

状态`D0_S1_RGB233`，原生U更新模式的D格（曲率=0、梯度=0）不满足预先固定的`atol=1e−6, rtol=1e−5`。CPU从保存的两份真实输出重新执行NumPy判据，复现该失败。

{table(['字段','元素数','超差数','最大绝对差','最大差/允许误差','原判据通过'],failed_fields)}

最终Pose、Disparity、U、temp及affine均在容差内；超差发生在最后一轮dx/dz。这里不是OOM，也没有非有限输出。不能仅凭小幅差异把它归因为CUDA浮点非确定性，更不能据此宣布DROID-W或候选数学公式有错；其来源仍未建立。

CPU检查失败候选的两轮阻尼系统仍为正定，条件数约2.64×10⁵、2.67×10⁵，原生dx的线性相对残差约1.56×10⁻⁸、1.09×10⁻⁷。第一轮与同候选Frozen D完全一致；第二轮已有U反馈差异。原安装扩展没有逐轮系统trace，也没有执行原实现对自身的重复性对照，因此这些诊断不能区分原生波动与候选新增差异。完整数值见FAILED_CONTEXT_LINEAR_DIAGNOSTICS.json。

## 实际执行边界

{table(['前缀','RGB401关键帧','新增输入帧次','耗时秒','C0恢复节点'],[[p['arm'],p['keyframes'],p['new_input_steps'],f"{p['seconds']:.2f}",p['C0_nodes']] for p in prefix])}

两条前缀均从封存RGB018 C0恢复18,143个对象节点并逐Tensor核验，固定重放S1历史调度至401。没有重算RGB001—018，没有运行402—487、Final BA或Filler。S0两条前缀未启动，D0_S1_RGB401已采样但未重放。

完整状态：D1_S1_RGB019、D1_S1_RGB233、D1_S1_RGB401、D0_S1_RGB019。部分状态：D0_S1_RGB233。前4状态共16个端点检查全部通过；部分状态3个通过、1个失败，合计19/20已执行检查通过，其余28个未执行。

## 已获得的局部证据

{table(['来源','RGB','U模式','内部轮次','A平移范数','B平移范数','C平移范数','D平移范数'],completed)}

A/B/C/D为同状态的曲率/梯度四格；表中仅为原生Δx范数，不是GT精度或轨迹改善。诊断交叉C组可能不对应一致目标函数的Gauss–Newton对，极端更新不能冒充原始Baseline行为。

完整4状态的64个记录阻尼系统全部正定，原生dx最大线性相对残差{max_res:.6g}。CPU独立Schur复算最大相对误差：矩阵{recon['Schur_matrix']:.6g}、右端{recon['Schur_rhs']:.6g}、原guard深度回代{recon['dz_native_guard']:.6g}。逐公式检查{len(formulas)}项，超出所列逐元素判据{len(formula_fails)}项。

第一轮两种U模式的平移Δx最大差{first_U:.6g}，第二轮出现U/affine联合更新反馈。原生分支同时更新U、temp与affine，不能称为固定affine的纯U独立效应。逐轮affine没有保存，只有调用前/后值。

这些局部证据支持继续研究曲率—梯度耦合，但**不够回答S1与S0下的完整效果反转**。S0尚无本轮结果；不能把4个完整上下文或58次调用当成独立统计重复，也不具备进入Task006的机制结论。

## 冻结资产与故障现场

终态重新核验原R2 YAML、原安装扩展与4份模型权重：6/6 SHA一致；候选源码HEAD仍为5d357c1d3079de134dd8b41a20a00632da37f0b0，工作区干净。GPU计算进程为空，数据盘剩余{audit['disk_free_bytes']/1024**3:.3f} GiB；实例保持有卡开机，没有关闭。

6个完整输入快照与失败输出已转存本地并核验SHA；失败状态远端文件未清理。D1_S1已完成的远端副本在故障之前按归档合同回收，原日志及回收收据保留。历史Task004C-B/Task005A不修改。

## 最有价值的下一步（未执行）

先对**这个已封存的同一失败状态**做原安装扩展对自身的短重放，再与候选对照，估计原生两轮U/affine更新的数值重复性。需要独立批准新的少量原生调用；无需重跑两条401帧前缀，更不应直接放宽现有门槛后继续原144次矩阵。

该短验证应预先记录每次完整输入/布局/别名/随机状态、原生内两轮、最后dx/dz和最终状态。只有区分“原实现自身波动”与“候选新增差异”后，才能决定保留阈值、修复候选或提出新的统计等价合同。此次没有执行任何额外重放。

## 包内审查路径

FINAL_REVIEW.md → TASK005B_DECISION.json → 05_analysis/ENDPOINT_FAILURE_FORENSICS.json及超差逐元素CSV → 04_results/states/与原始小矩阵 → 源码/分析器/测试 → DATA_AVAILABILITY.md中的完整原生数组和运行日志资产。

最终状态：**STOPPED_ENDPOINT_EQUIVALENCE_FAILURE / PARTIAL_REVIEW_READY**。等待评审，不自动继续GPU、不进入Task005C/006、不关机。
''')
    write('README_请先读.md','''# TASK005B 真实GPU阶段评审包

本包是端点超差后停止的真实结果，**不是12上下文全部完成包**，也不是f292f19的CPU准备包。

请先读FINAL_REVIEW.md和TASK005B_DECISION.json。重点审阅ENDPOINT_FAILURE_FORENSICS.json、逐元素超差CSV、失败原生数组、完整调用日志及输入哈希。

轻量ZIP包含全部报告、源码、逐轮CSV、收据、小型原生Schur矩阵及图。完整逐轮数组和运行日志作为同一GitHub Release的单独资产发布，每项均有SHA。大型C0、DINO完整输入快照、RGB、权重和GT不公开打包。详见DATA_AVAILABILITY.md。报告生成器中的全完成版没有执行且不纳入交付；仅使用停止版生成器。
''')
    asset_entries=[]
    for path in sorted(list(RECEIVER.glob('result_*.tar'))+list(RECEIVER.glob('partial_*.tar'))):
        proof=json.loads((RECEIVER/(path.stem+'.VERIFIED.json')).read_text())
        asset_entries.append({'name':path.name,'bytes':proof['archive_bytes'],'sha256':proof['archive_sha256'],'kind':'partial_failed_native_trace' if path.name.startswith('partial_') else 'complete_native_numeric_trace',
                             'URL':'https://github.com/Pseven0108/GameCam-VO/releases/download/task005b-gpu-mechanism-20261125/'+path.name})
    asset_entries.append({'name':pathlib.Path(transfer['archive']).name,'bytes':transfer['bytes'],'sha256':transfer['sha256'],'kind':'current_task_complete_run_logs',
                         'URL':'https://github.com/Pseven0108/GameCam-VO/releases/download/task005b-gpu-mechanism-20261125/'+pathlib.Path(transfer['archive']).name})
    dump('07_release/RAW_ASSET_INDEX.json',{'assets':asset_entries,'light_review_ZIP_does_not_embed_these_large_assets':True,'C0_full_input_snapshots_published':False})
    write('DATA_AVAILABILITY.md','''# 原始证据的分层与位置

- **展开报告及轻量评审ZIP**：所有报告、候选源码、运行/分析脚本、CPU测试、4个完整状态的64行逐轮指标、小型原生线性系统、逐Pose更新、全部输入哈希/调用收据、超差逐元素CSV及图。
- **同一Release的4个result_*.tar**：4个完整状态的8格×两轮原生trace、4份原安装扩展参照、COMMON_INPUTS、逐次收据与SUCCESS。
- **同一Release的partial_D0_S1_RGB233.tar**：失败状态的4份原扩展对照、5个成功返回的候选格、1份失败端点完整数组及ENDPOINT_FAILURE。失败前未生成COMMON_INPUTS或SUCCESS，不能伪造补写。完整输入snapshot另存本地。
- **同一Release的task005b_run_evidence.tar.gz**：2条真实前缀、5个启动的context02重放及首次context guard故障的完整运行日志、调度链、配置、恢复/终态收据、构建记录和远端副本回收记录。逐成员SHA核验通过，发布前解压扫描凭据。
- **仅本地保留的6个snapshot_*.tar**：包含真实BA全部输入与DINO派生特征的完整存储快照；逐成员SHA均核验。封存C0继续保留。其来源/大小/SHA列于00_intake/LOCAL_IMMUTABLE_ARCHIVE_INDEX.json；不自动公开大型输入快照、RGB、GT或模型权重。

全部发布资产的大小和SHA见07_release/RAW_ASSET_INDEX.json。轻量ZIP不是全部大型数值数组的容器；完整数组均以同一Release的独立资产提供。本次失败状态远端源文件保留，未做故障后清理。
''')
    write('MINIMAL_NEXT_EXPERIMENT.md','''# 待批准的最小端点重复性验证

对象固定为D0_S1_RGB233已有完整输入快照，保持原U更新、2次内部迭代和既有容差。先做至少两次原安装扩展对自身的完全同状态重放；若自身已超差，记录真实波动，不能简单宣布候选合格。随后才按新明确预算比较候选或其逐字节保留的reference入口。

目标是区分原生浮点/U-affine更新重复性、候选编译/埋点新增差异及输入状态错误。不得通过两次独立1轮调用替换原生内部2轮，不放宽1e−6/1e−5后宣布既有验证通过，不重跑401帧前缀，不自动继续S0。

本方案未执行，新增GPU调用0。需要用户单独批准具体调用预算后实施。
''')
    write('EXECUTION_LOG.md','''# 执行与故障记录

1. 沿用可信SSH主机密钥连接新30601实例，核验3090、封存C0、源码、权重、R2配置与原CUDA扩展。独立候选第二构建目录成功；首次仅nvcc定位失败，未覆盖原扩展。
2. 首次重放入口被grad_enabled上下文检查拒绝，BA调用0次。CPU probe确认原状态no_grad，context02仅恢复该上下文；保留原失败目录，未放宽数值容差。
3. D1_S1前缀与019/233/401重放成功。工具托管的本地监督进程丢失后，按远端终态续接，未重复GPU。归档回收又在Python3.10缺少hashlib.file_digest时、尚未删除前停止；改为同一SHA的分块读取后续接归档，未重跑数值实验。
4. D0_S1前缀成功到401；019重放成功；233完成4次原对照、Frozen A/D/B/C和Native A，第6个候选格Native D在端点校验失败。该调用输出已保存为NATIVE_UPDATE_D_FAILED_ENDPOINT.npz，未写成功收据。
5. 原生进程退出码1；整个监督器按合同停止，没有执行Native B/C、D0_S1_RGB401或任何S0实验。数值调用累计58，无重试。
6. GPU退出后只做CPU逐元素复核、哈希保护核验和故障证据下载。保留全部失败状态及历史结果，不关闭或释放GPU。

时间、PID、退出码、策略/输入SHA、精确顺序见SUPERVISOR_EVENTS和运行日志资产。两次入口/调度修正与一次真正的数值等价性失败分别记录，不称全过程无故障。
''')
    dump('SECURITY_AUDIT.json',{'GPU_used':True,'CUDA_initialized':True,'models_loaded_for_prefixes':2,'training_performed':False,'full487_runs':0,'Final_BA_or_Filler_executed':False,
        'frozen_asset_hashes_after_stop':audit['all_protected_asset_hashes_match'],'original_extension_overwritten':False,'production_sources_modified':False,'original_R2_modified':False,
        'historical_results_modified':False,'SSH_pin_verified':True,'StrictHostKeyChecking_disabled':False,'GPU_rebooted_or_reallocated':False,'GPU_numerical_retry':False,
        'endpoint_tolerance_changed':False,'new_datasets_downloaded':False,'Task005C_or_Task006_executed':False,'shutdown_performed':False,'GPU_compute_processes_after_stop':audit['gpu_compute_processes']})
    dump('REPRODUCIBILITY_MANIFEST.json',{'baseline_commit':'c3414af6047d06bafc1a6645d09f23247f3b2cdc','sealed_candidate_commit':audit['source_HEAD'],
        'independent_extension_SHA256':'1edb9685e1569f2513a4dc895b2eddbe699e15d2d684079e4d9c2f77e9a4ad44','C0_digest':'18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92',
        'seed':43,'buffer':500,'resolution':[640,360],'stride':1,'prefix_max_RGB':401,'native_internal_iterations':2,'atol':1e-6,'rtol':1e-5,
        'CPU_numerical_analysis_tests':10,'CPU_native_algebra_tests':6,'CPU_static_contract_checks':9,'prior_CPU_preparation_tests_not_new':38,
        'executed_native_calls':58,'planned_native_calls':144,'postcall_clamp_executed_in_replays':False,'prior_effective_argument_exception':'05_analysis/EFFECTIVE_ARGUMENT_AUDIT.json',
        'no_full_completion_claim':True})
    print(json.dumps(decision))

if __name__=='__main__':main()

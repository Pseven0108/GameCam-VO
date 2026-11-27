"""Finalize only a real 140-outcome batch; never synthesize missing results."""
import csv,json,shutil
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
from common import ROOT,TASK,dump,sha

REVIEW=ROOT/'reviews/task011b-validity-aware-cadp-dr-20261127'


def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf-8')


def table(rows,columns):
    def value(x):
        if x in ('',None):return 'NA'
        if isinstance(x,(float,np.floating)):return f'{x:.6g}'
        return str(x)
    return '| '+' | '.join(columns)+' |\n|'+ '|'.join(['---']*len(columns))+'|\n'+ '\n'.join(
        '| '+' | '.join(value(r.get(k)) for k in columns)+' |' for r in rows)


def number(row,key):
    return float(row[key]) if row.get(key) not in (None,'') else None


def main():
    batch=TASK/'gpu_results/BATCH_COMPLETE.json'
    if not batch.exists():raise RuntimeError('Formal batch incomplete; no final report')
    state=json.loads((TASK/'evaluation/EVALUATION_STATE.json').read_text())
    if state['terminal']!=140 or not state['complete_batch']:
        raise RuntimeError('Missing real outcomes')
    rows=read(TASK/'evaluation/VIPER_TRAJECTORY_METRICS.csv')
    if len(rows)!=140 or len({(r['window'],r['arm']) for r in rows})!=140:
        raise RuntimeError('Formal outcome matrix is not complete and unique')
    from analyze_failure_contexts import main as summarize_failure_contexts
    summarize_failure_contexts()
    failure_context=json.loads((TASK/'evaluation/FAILURE_CONTEXT_STATUS.json').read_text())
    from analyze_metric_tradeoffs import main as summarize_tradeoffs
    summarize_tradeoffs()
    tradeoffs=read(TASK/'evaluation/VIPER_MULTIMETRIC_TRADEOFF_SUMMARY.csv')
    tradeoff_display=[r for r in tradeoffs if r['arm']=='A6' and r['population']=='TRANSLATING_EXPLORATORY']
    summaries=read(TASK/'evaluation/VIPER_ENVIRONMENT_METRICS.csv')
    pairs=read(TASK/'evaluation/VIPER_METHOD_COMPARISON.csv')
    all_rows={r['arm']:r for r in summaries if r['environment']=='ALL'}
    runtime_rows=read(TASK/'evaluation/VIPER_RUNTIME_METHOD_SUMMARY.csv')
    complete_runtime={r['arm']:r for r in runtime_rows if r['population']=='COMPLETE_TRAJECTORIES_ONLY'}
    runtime_pairs=read(TASK/'evaluation/VIPER_RUNTIME_PAIRED_SERVICE_COSTS.csv')
    runtime_display=[]
    for arm in ('A0','A1','A2','A3','A4','A5','A6'):
        r=complete_runtime[arm]
        runtime_display.append(dict(Arm=arm,Completed_N=r['outcomes'],
            Whole_window_process_seconds=number(r,'service_seconds_mean'),
            Model_run_seconds=number(r,'model_run_seconds_mean'),
            Tracking_stage_seconds=number(r,'tracking_child_seconds_mean')))
    valid=sum(r['success']=='True' for r in rows)
    scorable=sum(r.get('ate_sim3_rmse') not in ('',None) for r in rows)
    failures=[r for r in rows if r['success']!='True']
    date=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M %Z')
    display=[]
    for arm in ('A0','A1','A2','A3','A4','A5','A6'):
        r=all_rows[arm]
        display.append(dict(Arm=arm,Complete=f"{r['completed']}/20",
            Sim3_ATE_path_pct=number(r,'ate_sim3_path_pct_mean'),
            SE3_ATE=number(r,'ate_se3_rmse_mean'),
            Sim3_RPE_t=number(r,'single_global_sim3_RPE_translation_mean'),
            RPE_rot_deg=number(r,'single_global_sim3_RPE_rotation_deg_mean'),
            Raw_scale_abs_error=number(r,'raw_path_ratio_abs_error_mean'),
            Tracking_seconds=number(r,'runtime_tracking_child_seconds_mean'),
            Child_peak_GiB=(number(r,'peak_allocated_bytes_mean') or 0)/1024**3))
    ate_pairs=[]
    for r in pairs:
        if r['metric']=='ate_sim3_path_pct':
            ate_pairs.append(dict(Arm=r['arm'],Reference=r['reference'],N=int(r['paired_sequences']),
                Mean_delta=float(r['mean_difference']),Median_delta=float(r['median_difference']),
                CI_low=number(r,'lower95'),CI_high=number(r,'upper95'),
                Wins=r['wins'],Losses=r['losses'],Ties=r['ties']))
    candidates=[r for r in summaries if r['environment']=='ALL' and r['arm'] not in ('A0','A1')
                and r.get('ate_sim3_path_pct_mean') not in ('',None)]
    best=min(candidates,key=lambda r:float(r['ate_sim3_path_pct_mean']))['arm'] if candidates else None
    a6_original_pair=next(r for r in ate_pairs if r['Arm']=='A6' and r['Reference']=='A0')
    # This describes observed completion and paired intervals; it is not a
    # test-selected hyperparameter nor a calibrated cross-domain certificate.
    a6pairs=[r for r in ate_pairs if r['Arm']=='A6']
    a6_lower_in_both=all(r['Mean_delta']<0 for r in a6pairs) and len(a6pairs)==2
    a6_intervals_below_zero=all(r['CI_high'] is not None and r['CI_high']<0 for r in a6pairs) and len(a6pairs)==2
    mechanism=json.loads((TASK/'evaluation/MECHANISM_ANALYSIS_STATUS.json').read_text())
    if mechanism['native_live_cache_checks']!=20 or not mechanism['all_observed_live_cache_checks_pass']:
        raise RuntimeError('Missing native live cache identity checks')
    mechanism_rows=read(TASK/'evaluation/VIPER_PRIOR_U_GEOMETRY_SUMMARY.csv')
    geometry_display=[]
    for r in mechanism_rows:
        if r['arm']!='A6' or r.get('geometry_g_mean_n') in ('',None,'0'):continue
        geometry_display.append(dict(Window=r['window'],Controlled_BA_calls=r['controlled_calls'],
            g_call_mean_average=number(r,'geometry_g_mean_mean'),
            g_observed_min=number(r,'geometry_g_min_min'),g_observed_max=number(r,'geometry_g_max_max'),
            reliability_call_mean_average=number(r,'relative_reliability_mean_mean'),
            effective_prior_mean=number(r,'local_effective_prior_mean_mean')))
    regression=json.loads((TASK/'diagnostics/native_001/formal_native_regression/real_first_local_001/NATIVE_REGRESSION.json').read_text())
    if regression['status']!='PASS':raise RuntimeError('Native endpoint gate not passed')
    endpoint_rows=read(TASK/'evaluation/VIPER_A0_A1_CONTROL_VARIABILITY.csv')
    endpoint_display=[]
    for key in ('ate_sim3_path_pct','single_global_sim3_RPE_translation',
                'single_global_sim3_RPE_rotation_deg','raw_path_ratio_abs_error','keyframes'):
        differences=[float(r['absolute_difference']) for r in endpoint_rows if r['metric']==key]
        if differences:endpoint_display.append(dict(Metric=key,N=len(differences),
            Median_absolute_A1_minus_A0=float(np.median(differences)),Max_absolute_A1_minus_A0=max(differences)))
    increment=read(TASK/'evaluation/VIPER_A6_VS_A4_GEOMETRY_INCREMENT.csv')
    increment_display=[r for r in increment if r['environment']=='ALL' and r['metric'] in
        ('ate_sim3_path_pct','raw_path_ratio_abs_error','single_global_sim3_RPE_rotation_deg')]
    for r in increment_display:
        for key in ('mean_difference','lower95','upper95'):
            r[key]=number(r,key)
    weather_display=[]
    for env in ('Day','Sunset','Rain','Snow','Night'):
        chosen={r['arm']:r for r in summaries if r['environment']==env}
        weather_display.append(dict(Environment=env,**{a:number(chosen[a],'ate_sim3_path_pct_mean') for a in ('A0','A1','A4','A6')}))
    motion_state=json.loads((TASK/'evaluation/MOTION_SENSITIVITY_STATUS.json').read_text())
    stratified_rows=read(TASK/'evaluation/VIPER_MOTION_STRATIFIED_RUNS.csv')
    nearzero_ate=sum(r['motion_stratum']=='NEAR_ZERO_TRANSLATION' and r.get('ate_sim3_rmse') not in ('',None) for r in stratified_rows)
    motion_pairs=read(TASK/'evaluation/VIPER_MOTION_STRATIFIED_PAIRED.csv')
    motion_ate=[]
    for r in motion_pairs:
        if r['motion_stratum']=='TRANSLATING' and r['metric']=='ate_sim3_path_pct':
            own=dict(r)
            for key in ('mean_difference','lower95','upper95'):own[key]=number(r,key)
            motion_ate.append(own)
    moving_summary=read(TASK/'evaluation/VIPER_MOTION_STRATIFIED_SUMMARY.csv')
    moving_candidates=[r for r in moving_summary if r['motion_stratum']=='TRANSLATING' and r['arm'] in ('A2','A3','A4','A5','A6')
                       and r.get('ate_sim3_path_pct_mean') not in ('',None)]
    moving_best=min(moving_candidates,key=lambda r:float(r['ate_sim3_path_pct_mean']))['arm'] if moving_candidates else None
    moving_A6=[r for r in motion_ate if r['arm']=='A6' and r['reference'] in ('A0','A1')]
    moving_A6_lower=len(moving_A6)==2 and all(r['mean_difference']<0 for r in moving_A6)
    moving_A6_CI=len(moving_A6)==2 and all(r['upper95'] is not None and r['upper95']<0 for r in moving_A6)
    copy_dirs=[('evaluation','04_R3_VIPER_EVALUATION'),('figures/vo','06_FIGURES/vo')]
    for source,dest in copy_dirs:
        shutil.copytree(TASK/source,REVIEW/dest,dirs_exist_ok=True)
    for p in (TASK/'evaluation').glob('*.csv'):
        shutil.copy2(p,REVIEW/'05_METRICS'/p.name)
    for name in ('VIPER_WINDOW_MANIFEST.csv','VIPER_SELECTION_FROZEN.json','GPU_RUN_ORDER_FROZEN.json','GPU_RGB_INPUTS.json','frozen_r2.yaml'):
        shutil.copy2(TASK/'configs'/name,REVIEW/'07_CONFIGS'/name)
    decision=dict(task='TASK011B',status='COMPLETED_ACTUAL_140_TERMINAL_OUTCOMES',
        R0='COMPLETE_ACTUAL_CACHE_VALIDITY_AUDIT',R1='COMPLETE_REUSED_AUXILIARY_CACHE_EXPERIMENT',
        R2='ISOLATED_CUDA_COMPILED_REAL_NATIVE_CONTEXT_REGRESSION_PASS',R3='COMPLETE_20_WINDOWS_SEVEN_ARMS',
        formal_window_runs=140,complete_64_frame_trajectories=valid,algorithm_failures=len(failures),
        ATE_scorable_trajectories=scorable,complete_but_alignment_unscorable=valid-scorable,
        near_zero_translation_ATE_scorable=nearzero_ate,
        failures_before_any_controlled_BA=failure_context['failures_before_any_controlled_BA'],
        all_seven_initialization_failure_windows=failure_context['all_seven_initialization_failure_windows'],
        FP32_engineering_pilots_excluded=10,formal_precision='NATIVE_MOTION_FILTER_AUTOCAST_V2',
        windows=20,distinct_source_sequences=20,environments=5,seeds=[43],
        best_observed_controlled_arm_by_mean_Sim3_ATE_path_pct=best,
        A6_paired_mean_lower_than_both_references=a6_lower_in_both,
        A6_paired_bootstrap_upper_below_zero_for_both_references=a6_intervals_below_zero,
        confirmatory_generalization_proven=False,probability_calibration_claim=False,
        research_decision='PILOT_COMPLETE_REVIEW_REQUIRED_NO_CONFIRMATORY_GAIN_CLAIM',
        algorithm_selection_certificate=False,
        original_baseline_modified=False,uniform_attenuation_control_run=False,
        near_zero_translation_windows=motion_state['near_zero_translation_windows'],
        descriptive_motion_sensitivity_is_post_selection=True,
        exploratory_translating_stratum_best_controlled_arm=moving_best,
        exploratory_translating_A6_mean_lower_than_A0_A1=moving_A6_lower,
        exploratory_translating_A6_CI_upper_below_zero_for_both=moving_A6_CI,
        all_window_path_normalized_ranking_not_a_method_selection_certificate=True,
        next_stage_started=False,instance_shutdown=False,
        CPU_test_evidence='08_TESTS/CPU_TEST_REPORT.md',published_date=date)
    dump(REVIEW/'10_FINAL_REPORT/TASK011B_DECISION.json',decision)
    failtext=table(failures,['window','arm','status']) if failures else '全部140个计划组均输出64帧有限位姿；没有以跳过失败组提高分母。'
    scope='''# R2 integration: actual isolated native execution

A0 uses the original installed DROID-W extension. The official baseline already
contains Metric3D depth regularization. A1 is the independent candidate s=1 D1
endpoint. It is an implementation/trajectory variability control, not a separate
depth-enabled method or an invented D0 baseline.

Only frontend main-loop joint local BA is controlled. Initialization, second
initialization, native U/UBA, target weights, post-Schur damping, solve,
retraction, final BA and filler retain the frozen original implementation and
parameters. No pose-only or frozen-disparity experiment replaces the main design.

The unique candidate module is compiled separately; original droid_backends is
not overwritten. D0/D1 original repeats and cross-implementation pairs passed
the predeclared rtol1e-4/atol1e-5 in a real first-local-BA context, with two native
internal iterations and U updates retained. This local certificate does not
prove global bitwise determinism or supersede the historical R3 U-feedback
non-repeatability evidence. A0/A1 full-window differences must be reported.

Native CPU preprocessing plus CUDA float16 autocast is preserved. All20 A0
windows require a live first-frame Metric3D/cache bitwise identity and unchanged
CPU/CUDA RNG. Model construction and initialization remain native in every arm.
The shared prior cache eliminates repeated model forwards across methods; cold
end-to-end deployment runtime cannot be inferred from these cache-assisted times.

The native predictor's original cfg.cam.fx focal is retained, while tracker K
is the scaled calibration. This preexisting behavior is disclosed, not repaired
selectively for a method. Risk ranks and g are ordinal/inverse-normal proxies,
not calibrated probabilities or independently measured physical covariance.
'''
    write(REVIEW/'03_R2_CADP_DR_INTEGRATION/CADP_DR_INTEGRATION_REPORT.md',scope)
    write(REVIEW/'04_R3_VIPER_EVALUATION/VIPER_FAILURE_ANALYSIS.md','# Actual complete outcome denominator\n\n'+failtext+'''

Completion and metric scorable status are separate. All planned sequences stay
in the denominator. Alignment-degenerate trajectories retain the completion
record and missing alignment scores. Paired accuracy tables condition on
available pairs, with N shown and no failure score imputation. Do not interpret
success-conditional accuracy as a risk-adjusted population performance score.

Read VIPER_FAILURE_STAGE_ANALYSIS.md and VIPER_FAILURE_CONTEXT_ALL_140.csv for
accepted-keyframe counts and actual controlled-BA exposure. Whole seven-arm
sets that fail initialization before controlled BA cannot identify a benefit
or harm of the reliability intervention. No replacement windows were run.
''')
    report=f'''# TASK011B：真实七组 VIPER 下游验证完整评审

完成时间：{date}。**20个固定窗口 × 7组 = 140个正式终态；{valid}个完整64帧轨迹，{len(failures)}个算法失败。**

其中**{scorable}条轨迹可计算ATE，另有{valid-scorable}条完整轨迹因平移对齐退化而不评分**；每组ATE实际N=13，完成率分母仍是每组20，不把缺失分数补成0。

本轮完成R0–R3，不再是GPU阻断准备包。主数据集仅VIPER；全部使用现有数据，无新增训练或第三人称数据分支。

失败中有{failure_context['failures_before_any_controlled_BA']}次尚未执行任何受控BA，{failure_context['all_seven_initialization_failure_windows']}个窗口的七组全部初始化失败。这类结果计入完成率，但不提供可靠性干预改善/损害跟踪的证据；逐组关键帧数量和阶段见VIPER_FAILURE_STAGE_ANALYSIS.md。

**主要观察：** 原始A0的平均Sim3 ATE/path为{float(all_rows['A0']['ate_sim3_path_pct_mean']):.3f}%，本批形状均值最低的受控组{best}为{float(all_rows[best]['ate_sim3_path_pct_mean']):.3f}%，完整CADP-DR A6为{float(all_rows['A6']['ate_sim3_path_pct_mean']):.3f}%。A6−A0的探索性95%配对区间为[{a6_original_pair['CI_low']:.3f}, {a6_original_pair['CI_high']:.3f}]个百分点，仍跨零。{best}的旋转RPE均值为{float(all_rows[best]['single_global_sim3_RPE_rotation_deg_mean']):.4f}°，A0为{float(all_rows['A0']['single_global_sim3_RPE_rotation_deg_mean']):.4f}°；形状均值较低不等于所有指标全面获益。七组完成率均为14/20，未观察到完成率提升。这些结果支持继续审查简单可靠性控制，尚不证明复杂A6架构稳定优于原始模型。

## 1. 直接可核对的结果

以下为逐窗口均值。位移和SE3/平移RPE沿用Camera原生参考单位，不新增米制认证。Sim3只拟合一次全局尺度，不能单独证明尺度恢复改善。

**数据适用性限制：预选20窗口含{motion_state['near_zero_translation_windows']}个近零平移窗口，相关误差/path%和原尺度比可能退化。本批这些窗口实际有{nearzero_ate}条可用ATE；未通过对齐者保留状态且不评分，不给近零分母强算精度。另列平移分层的事后敏感性分析，不将可用病例排名当作算法选择证书。**

{table(display,['Arm','Complete','Sim3_ATE_path_pct','SE3_ATE','Sim3_RPE_t','RPE_rot_deg','Raw_scale_abs_error','Tracking_seconds','Child_peak_GiB'])}

ATE/path%为ATE RMSE除以该窗口GT路径长再乘100。各项评分分母见原CSV；完整结果同时提供均值、中位数、五环境、每窗口和失败情况。

### 相对两个原生对照的配对 ATE/path% 差值

负值有利于该方法。Bootstrap以来源序列为单位，3000次，未将像素或BA事件当作独立样本。每条来源序列只取一个预选窗口，seed43；区间为探索性，不是多种比较后的确认性检验。

{table(ate_pairs,['Arm','Reference','N','Mean_delta','Median_delta','CI_low','CI_high','Wins','Losses','Ties'])}

**解释限制：原计划分母包含近零平移窗口，但本批这些窗口均未得到可用ATE。ATE可用病例均值实际来自13个平移窗口；没有把近零路径上的巨大数值混入该均值，也没有用0补缺。以下为成功且可评分条件下的比较，不能替代全部20窗口的完成率。**

本批按平均Sim3 ATE/path%观察到的受控组最低者为 **{best}**。A6相对A0和A1配对均值均降低：**{a6_lower_in_both}**；两个95%区间上界均低于0：**{a6_intervals_below_zero}**。这是预选窗口的一次种子结果，不能据此宣称跨场景普遍有效。

### 运动条件的事后描述性敏感性分析

不使用GT运动选窗的算术中点策略实际选入{motion_state['near_zero_translation_windows']}个近零平移窗口，另有{motion_state['translating_windows']}个平移窗口。对前者，轨迹误差除以极小GT路径、Sim3尺度与平移尺度比缺少可靠的运动几何解释；静止/纯旋转下初始化失败也不等同于有平移场景中的跟踪丢失。

在发现这一问题时固定了单独敏感性规则：GT路径≤1e-4相机原生单位归为近零平移；不是米制物理阈值，也不是原先预注册指标。阈值只基于GT运动描述、对所有组相同，不修改原评价程序/分数、不换窗、不增加GPU运行。全部20窗口仍计入完成率。原规则及冻结时进度保留在POST_SELECTION_MOTION_SENSITIVITY_AMENDMENT.json中。

以下仅为平移分层中的Sim3 ATE/path%配对差值；结果为探索性敏感性分析，不能冒充确认性主终点。近零平移组及全部原始分数仍独立完整报告。

本批该分层的ATE可用病例与原计划可用病例恰好都是相同的13个窗口，因此相同ATE结果不是额外一次独立验证。平移分层仍有1个窗口初始化失败，保留在其14窗口完成率分母中。

{table(motion_ate,['arm','reference','paired_sequences','mean_difference','lower95','upper95'])}

该描述性分层中，受控方法的平均形状指标最低者为{moving_best}；A6对A0/A1配对均值均下降：{moving_A6_lower}；两个探索性区间上界均低于零：{moving_A6_CI}。这一分层仍只有一个seed，且不是盲测或预注册确认性检验。

### A6 相对 A4：加入几何需求 g 后的总效应

{table(increment_display,['metric','paired_sequences','mean_difference','lower95','upper95','wins','losses'])}

A4/A6使用同一可靠性规则，差别为几何g。这里估计的是跟踪反馈下加入g的总效应，不是固定BA状态的直接效应；由于没有geometry-only组，不能由此识别严格的g×r交互或宣称协同机制已经证实。

### A6 的形状、尺度与旋转取舍

{table(tradeoff_display,['reference','paired_three_metric_windows','shape_lower_windows','raw_scale_error_lower_windows','rotation_error_lower_windows','shape_lower_but_scale_error_higher_windows','all_three_lower_windows'])}

此表只描述事后平移分层内的配对差值符号，没有新建综合分数或显著性检验。形状降低但原始尺度误差升高的窗口也完整保留，不能用Sim3对齐隐藏这类取舍。全部方法/窗口原值和符号在VIPER_MULTIMETRIC_TRADEOFF_WINDOWS.csv。

### 分环境形状误差均值（Sim3 ATE / path %，每环境4个固定序列）

{table(weather_display,['Environment','A0','A1','A4','A6'])}

分环境样本量小，全部七组、旋转、原尺度与完成率均在原CSV中保留；不只挑选有利天气。

## 2. 七组的真实含义

- A0：已安装的原始DROID-W，原本已经包含Metric3D深度先验。
- A1：独立候选s=1，复现原D1端点；用于实现与数值反馈对照。
- A2：Native-only风险排序控制。
- A3：有效性门控Flip，Native有效而TTA无效时回退Native。
- A4：有效性门控等权Rank融合及Native回退。
- A5：有效性门控Max融合及Native回退。
- A6：与A4相同的可靠性r，乘以真正无先验几何逆正规方程得到的g。

A0不是D=0；A0/A1不是两个独立新算法。所有组保留原始初始化、R2参数、U/UBA、Final BA和Filler。只干预Frontend主循环Local BA。U/UBA保留的是公式和更新机制，其实际数值可以随不同轨迹状态产生反馈变化，并非强制固定所有组的U张量。

## 3. R0/R1 数值与辅助排序结论

16份历史缓存保持不变。历史未门控T1最大约81369773.8647461；Native/Flip/Pair分别检查，T2只在有效配对上计算且有界。A2–A6受控先验对无效Native赋权0，Native有效/TTA无效回退Native-only；A0/A1保留原生端点行为。NaN与拒绝策略风险1分开保存。

下游A4是带有效性门控和Native回退的Rank；未额外运行旧的未门控Rank作为VO对照。因此只能在R1缓存评价中直接比较有效性感知与历史Rank的排序，不能声称下游已经单独识别“仅修复TTA有效性”的因果收益。

十张旧VIPER缓存有94个Native无效像素、86个Native有效/TTA无效像素。数值有效性不等于深度精度提升。

在已观察过的MVS0001三帧诊断中，Native AUROC/AP更强，Max AUSE更低，Validity-Aware没有全面胜过旧Rank。原7个零预测保留为AbsRel1；严格GT准入失败记录不变。它不是VIPER稠密GT、米制校准或独立盲测证据。R1完整CSV和528数组/3360标量精确复算均在包内。

## 4. 原生等价性、精度修正与全部尝试

远端运行源码目录是导出副本，没有Git元数据，不能将预检中的git报错当作版本身份证明。已独立核对208个跟踪文件：30个Git blob逐字节一致，178个仅有CRLF换行差异；仅归一换行后全部匹配冻结提交c3414af6，没有其他内容差异。本轮没有改写这些运行文件；包内保留原始字节核对和换行专项核对，最终保护检查再核验实际导出文件身份。

真实首个Local BA的D0/D1原始重复与候选配对均通过rtol1e-4、atol1e-5；14个状态字段比较，保留原生双迭代和U更新。最大Pose配对差约9.54e-7。该证书只覆盖实际测试输入，不把原生CUDA浮点累加说成全局确定性。

早期10个完整窗口工程试跑遗漏MotionFilter的autocast，已保留并**全部排除正式估计**。同帧原生AMP与FP32最大差12.228088，206138/230400像素不同；修正同时恢复原生CPU图像预处理。之后重新开始固定140组，窗口/方法/顺序/算法参数不变，未依据GT或分数选择修正。

正式20个A0窗口均现场重算首帧，缓存与原生深度逐位一致，CPU/CUDA RNG均不变。此前HF路径和spawn/Printer上下文故障以及存储准入停止保留在工程日志中，不伪装为独立重复或删除失败现场。

### 整窗口 A0/A1 端点对照的实际差异

{table(endpoint_display,['Metric','N','Median_absolute_A1_minus_A0','Max_absolute_A1_minus_A0'])}

以上是一对原安装扩展/独立候选的实际全窗口结果差异，不能直接称为同一二进制的重复噪声估计。单个真实BA状态通过数值等价门槛，不代表整条反馈轨迹逐位相同；方法差值必须同时对照A0/A1的变异范围。本轮没有据此追加未授权重复。

## 5. Geometry Need 和统计边界

g来自prior-free的Q0、E、原生后Schur阻尼Hd与逆正规方程对角，u为正视差上的相对标准差中位数，g=u/(1+u)。参数在结果之前固定，不由Confidence、U或GT替代，不对GT拟合。它仍是逆正规方程代理，不是独立校准的物理协方差。

{table(geometry_display,['Window','Controlled_BA_calls','g_call_mean_average','g_observed_min','g_observed_max','reliability_call_mean_average','effective_prior_mean'])}

这些是各运行内部的描述性调用统计，BA次数不充当独立实验样本。g接近1表示本映射对r只作较小的额外衰减；不能因g名称含“几何”便认定其已校准或带来协同收益。有效系数同时受原生先验掩码及各迭代状态影响，不能简单用表中几个均值相乘代替逐像素实值。

这里prior-free指从当前线性化状态移除本轮Metric3D先验项；当前Pose/Depth及原生U加权仍带有此前运行历史，不是另外一条完全无先验轨迹，也不构成历史反馈独立性的证明。原生focal与trackerK的尺度差异同样是本轮未干预的实现属性，不能把所有观察到的尺度变化唯一归因于r或g。

排名系数会改变平均先验强度。本轮未运行额外均匀衰减对照，因此即使某组提升，也不能证明收益必然来自空间选择能力而不是整体减弱先验。跨种子、多窗口/整序列泛化和这一机制分离留待单独授权。

## 6. 时间、显存、阶段记录的实际范围

运行时间来自实际收据，不是模拟。公共Metric3D/Flip预计算耗时另列；每组缓存读取、模型原生构造、跟踪/Final BA/Filler保留。A0有额外首帧验证，首窗口A0另有8次端点BA和1次几何探针；其原始总时间不能直接当作干净的推理基准。

{table(runtime_display,['Arm','Completed_N','Whole_window_process_seconds','Model_run_seconds','Tracking_stage_seconds'])}

整窗口进程计时包括启动、模型构造、风险图准备、跟踪、Final BA及Filler，不含共享缓存预计算、压缩和传输；Model_run从父进程SLAM构造之后开始；Tracking_stage从子进程系数准备和候选导入之后开始。故Tracking_stage不能独自代表全部新增开销。另有完整的逐组失败耗时，以及相同成功序列上的整窗口配对差值与区间：VIPER_RUNTIME_PAIRED_SERVICE_COSTS.csv。所有这些都是缓存辅助运行，尚未测量真实部署的全冷启动代价。

GPU内存表为tracking子进程的PyTorch峰值，设备采样峰值为20秒采样下限，并包含运行前驱动报告的约5316MiB分配，不能相减后冒称精确独占峰值。没有为释放这部分显存重启GPU或终止其他进程。

BA日志记录真实更新范数、U、有效先验比例、g及负视差计数。未导出目标函数残差，不能将dx/dz范数直接叫收敛证明；负视差计数只是完整clamp数量的下限。未保留所有拒绝原因，最终关键帧保留不区分Motion Filter和Local BA拒绝。

## 7. 对任务十问的结论

1. 数值问题：门控、边界与回退已实现并实际验证；原深度数值未被改写。
2. Validity-Aware是否优于原Rank：辅助排序不支持全面优胜；下游按本包配对表判断，不能混为一个指标。
3. 最佳方法：全样本原表最低者{best}、事后平移分层最低者{moving_best}；两者都是探索性排名，同时必须查看原尺度、旋转、失败与环境差异，暂不认定通用胜者。
4. CADP-DR实际改善：已真实运行；A6配对均值均低于两个参考为{a6_lower_in_both}，探索性区间均低于零为{a6_intervals_below_zero}。
5. ATE/RPE：全部逐窗口、偏移1/15/60和两个参考配对CSV均提供，负面结果保留；近零平移窗口不用于支持尺度/形状改进的结论。
6. Night/Rain/Snow：每种4个序列的实际分组表和图在04_R3与06_FIGURES，不用风险图代替VO结果。
7. 平移压缩：单列raw path ratio、拟合尺度及统一全局尺度下早/中/后段比例；Sim3 ATE降低本身不算缓解证据。
8. 旋转与失败：旋转RPE和全部140分母保留，失败不会从总体完成率消失。
9. 额外开销：给出真实缓存、子进程、设备采样与模型运行时间；未声称包含未测量的全冷启动代价。
10. 下一步：先审查A0/A1变异、跨指标收益和负面环境。信息增益最高的后续对照是保持相同Native有效掩码、以每帧r均值作均匀先验衰减，分离空间可靠性选择与先验总量减弱；随后才考虑更多种子和独立窗口确认。本阶段不执行这些新增对照，也不自动开发新算法。

## 8. 交付与复现边界

包含全部新代码/候选源码/配置、CPU原始数值图、实际指标、图表、逐组日志、最终轨迹、原生BA网格视差/U、精确控制系数、回归输入输出与SHA清单。原始RGB、完整带RGB的video.npz、全分辨率重复预测、权重和环境二进制不公开；完整原始运行归档保留本地D盘，每个网格证据记录其源SHA和精确采样规则。

完整Review ZIP与展开文件同时发布到原Public仓库；Release绑定固定Commit。原R2、TASK011A、旧结果、模型权重与安装扩展均保护。运行结束不关机、不进入下一阶段。
'''
    write(REVIEW/'FINAL_REVIEW.md',report)
    write(REVIEW/'10_FINAL_REPORT/FINAL_REVIEW.md',report)
    write(REVIEW/'README.md','''# TASK011B complete actual review

Read FINAL_REVIEW.md, then10_FINAL_REPORT/TASK011B_DECISION.json. All140 planned
formal outcomes are real. R0/R1 cached auxiliary results and R3 VIPER camera
trajectory results are different evidence populations and are not pooled.

04_R3_VIPER_EVALUATION/evidence contains original logs, complete trajectories,
native BA-grid final states and exact full-image-ranked per-pixel coefficients.
Every derived grid is linked to the local full original archive and original
file SHA. Raw RGB, embedded-RGB fullvideo files, weights and environment
binaries are deliberately excluded. No claim is made that those inputs can be
recovered from SHA values. Complete source archives remain on the user's D:.

To replay the real R0/R1 numerical evidence without GPU/RGB/GT/model:

```text
python reproducibility/experiments/TASK011B/scripts/replay_saved_arrays.py --run 01_R0_TTA_VALIDITY/cpu_003 --output replay-outside-review.json
```

Use an output outside the sealed review. Native GPU reproduction additionally
requires the exact existing source/weights/environment and permitted original
VIPER inputs; it is not a synthetic or simulated replacement experiment.
''')
    write(REVIEW/'10_FINAL_REPORT/NEXT_STAGE_RECOMMENDATION.md',f'''# Next research decision, not an execution authorization

The actual batch is complete: {valid}/140 complete trajectories and {len(failures)} retained failures. Completion retains all20 windows, including near-zero GT translation. All actual ATE scores come from the same13 translating windows in both the original available-case table and the exploratory motion stratum; their agreement is not independent replication. The observed best controlled arm is {moving_best}; its shape, rawscale, rotation, completion, runtime and both endpoint controls must be considered jointly. This is not a blind-test algorithm-selection certificate.

The most informative next control would retain the same Native-valid pixel mask and replace spatial r by its per-frame mean, frozen without consulting GT outcomes. Comparing that uniform attenuation with the spatial controller would distinguish average prior weakening from actual pixel-selection utility. A6 versus A4 in the present batch describes the total addition of geometry gating under feedback; it does not establish a geometry-by-reliability interaction. Geometry often yields g near1, so actual coefficient values and runtime costs matter.

Before a wider claim, assess endpoint implementation/trajectory variability and repeat a frozen design across seeds and independently selected translating windows. Pre-control initialization failures remain failures but cannot measure an intervention that never executed. Depth confidence remains an ordinal risk signal, and inverse-normal geometry remains a proxy, with no new physical-depth calibration certificate.

No extra control, new seed, new dataset, integration stage or GPU run is started by this recommendation. Stop for review of the complete evidence package.
''')
    # These are current pointers, not edits of any sealed old research report.
    current=dict(date=date,active_dataset='VIPER',current_task='TASK011B',
        current_status='COMPLETED_WAITING_FOR_REVIEW',latest_completed_task='TASK011B',
        current_experiment_running=False,formal_window_runs=140,complete_trajectories=valid,
        no_automatic_third_person_resume=True,next_stage_started=False)
    for name in ('CURRENT_RESEARCH_SCOPE.json','RESEARCH_DIRECTION_CURRENT.json'):dump(ROOT/name,current)
    status=f'''# GameCam-VO — TASK011B completed

{date}. VIPER is the sole active dataset. Real R0/R1 validity/reliability audit,
isolated native CUDA integration and20-window ×7-arm GPU comparison completed:
140 planned formal outcomes, {valid} complete trajectories, {len(failures)} algorithm failures.
No production baseline, original weights or frozen history was changed.

[Complete current review](reviews/task011b-validity-aware-cadp-dr-20261127/FINAL_REVIEW.md).
Observed results and limits are in the paired tables; no universal algorithm
gain or probability calibration is presumed. Stopped for review, no next stage.
'''
    for name in ('CURRENT_RESEARCH_STATUS.md','PROJECT_STATUS.md','README.md'):write(ROOT/name,status)
    write(ROOT/'REVIEW_INDEX.md','''# Current reviews

- [TASK011B complete actual140-outcome review](reviews/task011b-validity-aware-cadp-dr-20261127/FINAL_REVIEW.md)
- [TASK011A sealed predecessor](https://github.com/Pseven0108/GameCam-VO/blob/e2744c21d9d597fa253d552caec8c0b9540f5484/reviews/task011a-depth-reliability-fusion-20261127/FINAL_REVIEW.md)
''')
    dump(TASK/'private/TASK011B_STATE.json',decision)
    write(TASK/'EXECUTION_STATE.md',status)
    print('FINAL_ACTUAL_REVIEW_WRITTEN',valid,len(failures),best,flush=True)


if __name__=='__main__':main()

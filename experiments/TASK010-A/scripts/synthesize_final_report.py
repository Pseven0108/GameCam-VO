"""Generate the research decision from the complete, frozen paired matrix."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'experiments/TASK010-A'


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def main():
    subprocess.run([sys.executable,'-B',str(TASK/'scripts/validate_frozen_runtime.py')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'-B',str(TASK/'scripts/verify_depth_candidate_inputs.py')],cwd=ROOT,check=True)
    state=json.loads((TASK/'private/forkserver_holdout_STATE.json').read_text())
    if state['status']!='COMPLETE':raise RuntimeError('Frozen transfer matrix has not finished')
    selection=json.loads((TASK/'09_reproducibility/TRANSFER_SELECTION_FROZEN.json').read_text())
    for relative,expected in selection['source_sha256'].items():
        if hashlib.sha256((ROOT/relative.replace(chr(92),'/')).read_bytes()).hexdigest()!=expected:raise RuntimeError('Frozen source changed')
    all_rows=json.loads((TASK/'07_cross_scene_evaluation/ALL_RUN_METRICS.json').read_text())
    roster={d['name']:d for d in json.loads((TASK/'private/DATA_MANIFEST.json').read_text())}
    valid=[r for r in all_rows if r.get('status')=='COMPLETE' and 'sim3_ate_native_reference_units' in r]
    windows=selection['heldout_windows'];methods=selection['heldout_primary_methods'];table=[];grouped={}
    for name in windows:
        for method in methods:
            attempts=[r for r in all_rows if r.get('dataset')==name and r.get('method')==method]
            rr=[r for r in valid if r['dataset']==name and r['method']==method]
            if len(attempts)!=3 or {r['seed'] for r in attempts}!={43,44,45}:raise RuntimeError('Incomplete paired denominator')
            if len(rr)!=3:raise RuntimeError('Unscorable trajectory: preserve all rows and issue a failure-specific report, never drop it')
            row={'dataset':name,'domain':roster[name]['domain'],'method':method,'seeds':'43;44;45','n':len(rr),
                'reference_unit':roster[name]['pose_unit']}
            for key in ['sim3_ate_native_reference_units','se3_ate_native_reference_units','normalized_sim3_ate',
                'rpe_translation_offset1_native_reference_units','rpe_rotation_offset1_deg','sim3_scale']:
                values=np.array([r[key] for r in rr]);row[key+'_mean']=float(values.mean());row[key+'_sd']=float(values.std(ddof=1))
            row['pose_coverage']=min(r['coverage'] for r in rr);grouped[(name,method)]=rr;table.append(row)
    summary={(r['dataset'],r['method']):r for r in table};paired=[];decisions=[]
    for method in methods:
        if method=='baseline':continue
        ate_wins=[]
        for name in windows:
            b={r['seed']:r for r in grouped[(name,'baseline')]};m=grouped[(name,method)]
            for r in m:
                paired.append({'dataset':name,'domain':roster[name]['domain'],'method':method,'seed':r['seed'],
                    'ATE_difference':r['sim3_ate_native_reference_units']-b[r['seed']]['sim3_ate_native_reference_units'],
                    'normalized_ATE_difference':r['normalized_sim3_ate']-b[r['seed']]['normalized_sim3_ate'],
                    'RPE1_translation_difference':r['rpe_translation_offset1_native_reference_units']-b[r['seed']]['rpe_translation_offset1_native_reference_units'],
                    'RPE1_rotation_deg_difference':r['rpe_rotation_offset1_deg']-b[r['seed']]['rpe_rotation_offset1_deg'],
                    'reference_unit':roster[name]['pose_unit']})
            key='sim3_ate_native_reference_units_mean'
            ate_wins.append(summary[name,method][key]<summary[name,'baseline'][key])
        domains=[]
        for domain in ['VIPER_GAME','REAL_DROIDW_DOWNTOWN']:
            names=[n for n in windows if roster[n]['domain']==domain]
            d={'domain':domain,'windows':len(names),'ATE_window_wins':sum(ate_wins[windows.index(n)] for n in names)}
            for key in ['normalized_sim3_ate','rpe_translation_offset1_native_reference_units','rpe_rotation_offset1_deg']:
                d[key+'_difference_mean']=float(np.mean([summary[n,method][key+'_mean']-summary[n,'baseline'][key+'_mean'] for n in names]))
            domains.append(d)
        go=all(ate_wins) and all(d['rpe_translation_offset1_native_reference_units_difference_mean']<=1e-12 and d['rpe_rotation_offset1_deg_difference_mean']<=1e-12 for d in domains)
        decisions.append({'method':method,'preselected_primary':method==selection['main_confirmatory_candidate'],
            'decision':'GO_FOR_SEPARATE_FORMAL_VALIDATION_ONLY' if go else 'NO_GO_FOR_GENERALIZED_IMPROVEMENT',
            'ATE_window_wins':sum(ate_wins),'windows':len(windows),'domain_results':domains,
            'production_acceptance':False,'new_test_tuning_allowed':False})
    main_decision=next(d for d in decisions if d['preselected_primary'])
    decision={'primary':main_decision,'all_methods':decisions,'selection':selection,
        'completed_matched_development_runs':42,'completed_matched_transfer_runs':selection['planned_native_runs'],
        'preliminary_baseline_runs':1,'native_complete_receipts':len(valid),'no_motion_GT_accuracy_claim':True,
        'no_metric_depth_accuracy_claim':True,'formal_R2_or_full_sequence_reproduction':False}
    out=TASK/'07_cross_scene_evaluation';write_csv(out/'FROZEN_TRANSFER_WINDOW_TABLE.csv',table)
    write_csv(out/'FROZEN_TRANSFER_SEED_PAIRS.csv',paired)
    (TASK/'08_reports/RESEARCH_DECISION.json').write_text(json.dumps(decision,indent=2))
    dev=json.loads((out/'METHOD_WINDOW_SUMMARY.json').read_text())
    dev=[r for r in dev if r['dataset']=='night007_dev']
    lines=['# TASK010-A 最终研究评审','',f'日期：2026-11-27（Asia/Shanghai）。主候选：`{selection["main_confirmatory_candidate"]}`。最终判断：**{main_decision["decision"]}**。','',
        '本轮完成动态模型独立推理、几何与深度融合实现，以及冻结后的跨场景 VO 比较。结论来自实际轨迹；没有把视觉上合理的 Mask、合成测试或成功启动模型当成算法精度证明。原始生产 Baseline、权重、数据和历史结果保持独立。','',
        '## 1. 范围与实际执行','',
        f'- 开发：Night007 RGB301–332，14种方法×3种子＝42次匹配运行；另保留1次早期 Baseline。',
        f'- 固定评价：7个窗口×{len(methods)}种方法×3种子＝{selection["planned_native_runs"]}次。所有窗口、方法和种子均保留，不挑选最佳种子。',
        '- 模型：π³MOS、GMOS-S、GeoMotion CVPR、Full GeoMotion，各9个32帧窗口，共1152份主要浮点输出。Night007的32份π³MOS结果复用封存缓存；其他主要输出为本轮推理。另保留小规模探针及失败记录。',
        '- 数据：VIPER五种天气；真实 Downtown1/2；额外 WildWorld第三人称游戏窗口只作定性观察，未伪造相机GT、K或SLAM成绩。',
        '- 全部使用本地RTX5060。没有连接、重启或申请远端实例，没有训练、修改生产CUDA扩展或覆盖历史实验。','',
        '## 2. 可比性与数据边界','',
        '这是TASK009衍生的32帧本地工程协议：VIPER384×216、真实场景288×216、buffer64、warmup6、stride1、每2帧强制关键帧、gamma_depth=0.01、原生U/UBA、Final BA7+12及Filler。它不是正式R2的487帧/640×360/buffer500复现，不能与旧正式成绩合并。强制关键帧策略也不能证明自然关键帧选择得到改善。',
        '每条完整轨迹只进行一次全局Sim3对齐，同时保留SE3 ATE和offset1/5/15 RPE。各路段不另拟尺度。VIPER为游戏原生单位，Downtown为作者发布的FAST-LIVO2米制参考；不混合两种原始误差。参考插值、标定及数据历史见REAL_REFERENCE_ADMISSION.md。',
        '跨场景方法选择仅使用开发窗口。冻结时间、源码/输入身份及全部调度见TRANSFER_SELECTION_FROZEN.json和执行计划；之后没有根据评价GT调整参数。这里的“heldout”指从本任务方法选择中保留，并不表示这些序列从未在项目或模型训练历史中出现。','',
        '## 3. 开发结果：每个点对应一次独立种子运行','',
        '| 方法 | Sim3 ATE均值±SD（游戏单位） | 相对匹配Baseline的种子获胜数 |','|---|---:|---:|']
    for r in sorted(dev,key=lambda x:(x['method']!='baseline',x['sim3_ate_native_reference_units_mean'])):
        lines.append(f"| {r['method']} | {r['sim3_ate_native_reference_units_mean']:.5f} ± {r['sim3_ate_native_reference_units_sd']:.5f} | {r.get('paired_ate_wins','—')}/3 |")
    lines += ['',
        '均值最优不代表统计上显著优于其他候选；三种子的波动明确可见。候选排名没有使用评价窗口成绩。',
        '', '## 4. 冻结后的跨场景结果','',
        '| 窗口 | 单位 | '+' | '.join(methods)+' |','|---|---|'+'---:|'*len(methods)]
    for name in windows:
        unit='game' if roster[name]['domain']=='VIPER_GAME' else 'm(ref)'
        values=[f"{summary[name,m]['sim3_ate_native_reference_units_mean']:.5f}±{summary[name,m]['sim3_ate_native_reference_units_sd']:.5f}" for m in methods]
        lines.append('| '+name+' | '+unit+' | '+' | '.join(values)+' |')
    lines += ['', '| 方法 | ATE均值降低的窗口数 | 预先规定准入判断 |','|---|---:|---|']
    for d in decisions:lines.append(f"| {d['method']} | {d['ATE_window_wins']}/7 | {d['decision']} |")
    lines += ['',
        'GO仅表示值得另行开展更长序列正式验证，不是生产接入批准。判据在评价前冻结：五个游戏窗口和两个真实窗口均降低ATE，且两个域各自的平均平移/旋转RPE不恶化。达不到就保留局部收益与退化，不能包装成普遍改进。完整逐种子、SE3、RPE、尺度和阶段表均随包提供；像素和BA事件不作为独立实验样本。','',
        '## 5. TASK009失效机制：哪些已证实','',
        '已从原始实际对应点重算：首轮门控均值0.94646233，117次调用的边数加权均值0.93998544，几乎全部观测受到衰减。原实现只改观测W，未把π³深度或Confidence用于BA，也未覆写原生U。source/target取样和原始帧身份没有发现直接错配。',
        '数学上，几何项缩放而深度先验/eta/绝对阻尼不同比缩放，会改变Schur系统。float64合成例验证了这个机制及无固定先验/绝对阻尼时的缩放不变性；它不是历史BA重放。均值降权控制与结构化Mask的开发结果不同，因此不能将所有失败归咎于平均降权量。',
        '外部门控确实乘在原生UBA之外，但保存的source-U大多没有触发原生降权，不能认定广泛重复UBA抑制是唯一根因。新source-U/模型重叠表是Final BA后保留关键帧的描述统计，未重建全部target-U及原生每轮联合权重。','',
        '## 6. 哪个动态先验可用，几何残差有何价值','',
        '四种模型都获得了真实连续分数和可视化；没有运动GT，无法给出Precision、Recall、F1、静态误报率或声称某模型检测最准确。图中可见车辆/行人支持，也可见建筑/路边覆盖及时间变化。相机车身运动不能简单当作静态背景误报。Full与CVPR不是同一模型，且Full未使用可选SAM2后细化。',
        '新门控有精确中性区；几何方案使用独立RAFT前后向检查和MAGSAC对极残差。融合要求模型与几何共同支持，并用由U计算的source系数作保守调制。实现没有按每次调用的enable_udba开关切换该系数，因此不是逐阶段实际UBA权重的精确去重；也不假设两类分数统计独立或已经校准。U的生成与更新不变。它不是完整RoMo/DynOSeg复现。',
        '对极残差无法辨别沿对极线运动；纯旋转、平面和主导动态物体也会造成退化。另行保存的原生Pose/Depth相机流残差只用于诊断，没有偷偷作为当前门控输入；它同时混合位姿、深度、光流、遮挡及物体运动误差，不能直接充当动态GT。','',
        '## 7. 深度与Confidence：已经做到和没有做到','',
        '深度方案用整段窗口的一个鲁棒尺度，把π³局部z对齐到Metric3D预测单位，在有效静态支持、比例0.5–2范围内做25%逆深度混合，其余像素保持原值。每窗口尺度P95/P05≤2才准入。对齐没有使用GT；FiT3D特征保持不变。该方案含静态Mask支持，并不是纯粹无Mask的深度因果分解。',
        '独立字节检查还验证了256帧的FiT3D特征和输入正深度掩码一致。公式层面，在相同BA状态且原生m不变的条件下，先验目标改变直接影响梯度右端项，alpha·m的先验曲率不因目标深度值本身改变。未逐次捕获原生mono_disps掩码，因此这仍是带条件的源码推导；初始化、几何与U反馈也未固定，不能宣称真实轨迹只是梯度的直接效应。',
        '没有建立逐像素物理深度GT，因此不能声称深度误差变小、获得真实米制尺度或完成Confidence校准。GeoMotion的conf实际是motion logit，不是深度可信概率；π³几何Confidence也不能与DROID U混用。没有为缺少可靠监督的数据训练预测头。','',
        '## 8. 资源、工程问题和完整性','',
        '本轮保留全部失败：GMOS早期环境/构造尝试；Full常驻FP32参数搬入GPU时OOM；观测器启动器预加载与兼容层冲突；runpy相对__file__收据错误；静态缓存文件名检查错误。后面三类发生在模型/原生BA启动前；没有把它们当成算法失败或伪造结果。修复使用新编号，保留现场。',
        'Full使用独立逐模块FP32权重搬运，保持BF16运算和官方权重严格加载；原始CPU权重对象恢复。合成网络常驻/搬运输出逐位一致，真实完整模型的常驻路径数值等价性仍未能验证。原生DROID扩展未替换。投影探针证实Pose/Depth/K与CPU/CUDA RNG不被观察调用修改，但不能消除CUDA原子归约的时序波动。',
        '计时分别报告模型加载/前向/保存、跟踪+Final BA+Filler、子进程总墙钟与资源记录。缓存VO的FPS不含辅助模型、Python导入和模型初始化，不能宣称端到端实时。GMOS使用未来上下文、静态轨迹和深度对齐使用整窗口，这些仍是离线原型。',
        '完整浮点模型/光流/先验数组作为六份独立ZIP附件发布，主评审包含全部代码、原始原生日志、配置、轨迹、指标和代表性未改写数组。原图数据集、GT、权重、外部环境及凭据不提交。历史保护和SHA/CRC核验有独立记录。','',
        '## 9. 最终研究判断与下一步','',
        f'预选主候选 `{selection["main_confirmatory_candidate"]}` 的判定为 **{main_decision["decision"]}**。其他方法的局部收益与退化完整列出，不根据评价集重新选阈值或只挑有利路段。',
        '本任务已具备回答“Mask更好看是否能改善VO”的实际证据，但尚未完成第三人称游戏的定量相机评价、完整长序列验证或独立运动GT准确率。任何正式改进主张都应保留这些范围。',
        '下一步优先对已冻结、有跨域支持的机制做更长序列验证，并分开限制初始化/局部BA/Final BA/Filler的作用范围。若本轮没有普遍收益，就先保留原Baseline；通过有标签的少量动态片段核查几何支持与误删静态约束，而不是继续无界堆模型或在这七个评价窗口上调参。不得自动进入新任务或生产接入。','',
        '详见逐项代码/来源审计、QUALITATIVE_REVIEW、GEOMETRY_INTERPRETATION、RESEARCH_DECISION.json、冻结协议和完整原始日志。']
    report='\n'.join(lines)+'\n';(TASK/'08_reports/FINAL_REPORT.md').write_text(report,encoding='utf-8')
    (TASK/'08_reports/NEXT_RESEARCH_DIRECTION.md').write_text('\n'.join(lines[-9:])+'\n',encoding='utf-8')
    body=f'''TASK010-A completed: 42 matched development runs and {selection['planned_native_runs']} frozen paired transfer runs, plus one preserved preliminary baseline.

Primary candidate: `{selection['main_confirmatory_candidate']}`. Decision: **{main_decision['decision']}**.

This is a bounded local32-frame protocol, not full-sequence R2 reproduction. Main review ZIP contains expanded reports/code/tests, all native trajectories/configs/logs and representative original float arrays. Six RAW assets contain full original model, optical-flow and depth/static-prior outputs. SHA-256 and CRC identities are supplied. No pretrained weights, raw RGB dataset, GT or credentials are redistributed.

Full report and fixed-commit links are added at publication. No production baseline or historical release is changed.
'''
    (TASK/'08_reports/RELEASE_BODY.md').write_text(body,encoding='utf-8')
    print(json.dumps({'primary':main_decision,'matched_transfer_runs':selection['planned_native_runs']},indent=2))


if __name__=='__main__':main()

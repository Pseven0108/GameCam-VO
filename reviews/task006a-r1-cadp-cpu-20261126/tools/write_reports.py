"""Generate review text from the final real CPU receipts. No experiment execution."""
import json
import hashlib
from pathlib import Path
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'results/research_003'


def dump(name,data):
    (ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def put(name,text):
    (ROOT/name).write_text(text.strip()+'\n',encoding='utf-8')


def main():
    if (ROOT/'FINAL_REVIEW.md').exists():
        raise RuntimeError('Reports already sealed; do not overwrite')
    r=json.loads((RUN/'RESEARCH_RESULTS.json').read_text(encoding='utf-8'))
    assert r['success'] and r['unit_tests']['success'] and not r['torch_imported']
    tests=r['unit_tests']['tests_run']
    cov=r['covariance']; ep=r['endpoints']; large=r['dimension_matched_blocks']; bad=r['inaccurate_prior_counterexample']
    decision={
      'project':'GameCam-VO','task':'TASK006A-R1','date':'2026-11-26','timezone':'Asia/Shanghai',
      'status':'TASK006A_R1_COMPLETE_WAITING_FOR_HUMAN_REVIEW',
      'technical_assessment':'PASS_CPU_MATHEMATICS_WITH_RECORDED_LIMITATIONS',
      'R0_human_approval':'Confirmed by user in R1 authorization; sealed R0 decision not edited',
      'R1_executed':True,'R1_human_review_passed':False,'R2_authorized':False,'R2_executed':False,
      'effective_gamma_depth':0.01,'unit_tests':r['unit_tests'],
      'covariance_formula':'Verified against joint precision inverse on synthetic SPD systems',
      'full_covariance_real_BA_computed':False,'historical_R3_E_recovered':False,
      'blocked_diagonal_exact_up_to_float64_roundoff':True,
      'D0_D1_CPU_mathematical_endpoints':'PASS_18_CONFIGURATIONS',
      'CUDA_endpoint_equivalence':'NOT_TESTED_IN_R1',
      'native_U_endpoint_gate':'Historical TASK005B-R3 unresolved; not waived',
      'native_backsub_guard':'Algebraically modeled separately; not identical to ideal joint estimator',
      'rho_calibrated_on_real_data':False,'prior_accuracy_established':False,
      'universal_prior_benefit':'Not supported; explicit synthetic counterexample retained',
      'next_recommended_scope':'R2 engineering feasibility review only after separate approval',
      'GPU_runs_consumed':0,'github_push_performed':False}
    dump('AUDIT_DECISION.json',decision)
    put('FINAL_REVIEW.md',f'''
# TASK006A-R1 最终评审

2026-11-26（Asia/Shanghai）。**CPU float64 数学原型已完成，结论为 PASS_CPU_MATHEMATICS_WITH_RECORDED_LIMITATIONS。**

核心判断：CADP 的 prior-off 正则化边缘协方差与 eta/alpha 插值端点在指定数学体系中成立；分块对角方案值得进一步工程验证。尚无证据证明其改善真实DROID-W轨迹，也没有完成原生GPU等价性或概率校准。

## 验收结果

|项目|实际结果|证据范围|
|---|---|---|
|最终自动化测试|{tests}/{tests} PASS|CPU、合成矩阵与合同|
|协方差独立验证|{cov['systems']}个系统、{cov['block_comparisons']}次分块对照PASS|联合precision直接求逆及SciPy sparse solve|
|完整/分块与联合逆最大绝对差|{cov['max_abs_block_vs_joint_inverse']:.3e}|float64合成小系统|
|D0/D1端点|{ep['endpoint_configurations']}组全部CPU精确一致|C、b、dx、理想及原生guarded回代|
|连续rho|{ep['rho_configurations']}组联合求解验证PASS|固定alpha=0.01，含eta小于/大于alpha|
|自适应完整CPU链|9组PASS|几何→Sigma对角→u→rho→深度项→联合增量|
|信息强弱排序|9组帧级顺序验证PASS|3种子×3帧组，仅限合成|
|稳定性|17个预设结果全部符合|含应当拒绝的病态、NaN/Inf、零曲率|
|72×54,000合成系统|4种分块全部PASS，最大差{large['max_abs_error']:.3e}|没有分配54,000²完整矩阵|
|真实VIPER、C0、模型与GPU|均未运行/读取|本轮授权边界保持|

最终科学结果固定为 `results/research_003/RESEARCH_RESULTS.json`。前两个开发验证目录完整保留，不叠加计数为更多独立实验。

## 三个必须保留的限制

**1. 几何弱不等于先验准。** 相同u对准确和错误Metric3D先验产生相同rho。本轮反例中，错误prior使合成位姿增量误差由{bad['adverse_prior_pose_error_D0']:.2f}增加至{bad['adverse_prior_pose_error_adaptive_demo']:.5f}。该例反驳无条件收益，不能据此推断真实VIPER上的CADP胜负。

**2. 协方差有明确的估计器边界。** 公式对应固定W/U、eta和gauge下的正则化联合precision逆。原生depth backsub的ix<=0分支与理想联合估计器不同，已另行转录并测试，未改动源码。未认证原生估计器的误差传播协方差。

**3. 原生工程与校准尚未完成。** R3缺少完整E，本轮没有从Schur反推或读取C0；k/tau、真实Vf、最低支持率、双轮rho冻结、Native-U数值门槛、在线耗时和显存均未完成生产验证。

## 建议决策

值得提交R1人工评审，并以明确上述局限为前提考虑R2工程可行性。R2须先明确真实E的合法取得方式、原生guard/gauge合同、分解复用与多RHS方案、mask与校准协议；不得用本次数学PASS替代这些关卡。

**本轮未启动R2、未修改生产源码/配置/权重、未编译CUDA、未发布GitHub。** 本包保留来源、全部代码、合成输入、逐项日志、对照CSV、执行收据、保护哈希和SHA清单。归档最终验收以外置 `deliveries/ZIP_VALIDATION.json` 为准。

最终状态：**TASK006A_R1_COMPLETE_WAITING_FOR_HUMAN_REVIEW**。
''')
    put('CPU_TEST_AND_EXPERIMENT_REPORT.md',f'''
# CPU 测试与研究结果

最终执行命令、退出码0与输出SHA见 `logs/RESEARCH_EXECUTION_RECEIPT_003.json`；全部明细位于 `results/research_003`。

- 自动化测试：{tests}/{tests}，无失败、错误或跳过。
- 独立合成种子：43、44、45、1729、2026、20261126。它们不是模型训练重复或统计推广证据。
- oracle固定混合容差：atol=rtol=2e-11；未事后放宽。
- covariance：24系统×4分块=96对照。完整块逆和分块对角相对联合逆的最大绝对差均为{cov['max_abs_full_vs_joint_inverse']:.6g}；SciPy稀疏路径最大绝对差{cov['max_abs_sparse_vs_joint_inverse']:.6g}。
- endpoint：3种子×3eta尺度×2端点=18组，C/RHS/CPU增量与独立原生公式转录精确一致；含rho=0.1、0.5、0.9后总计45组。
- adaptive pipeline：9组从prior-off covariance到rho再到联合增量完整运行，逐一与直接联合求解对照。
- uncertainty：45帧记录，9条信息增强序列的u严格下降；36条k/tau敏感性记录，不作校准结论。
- stability：12个预先指定接受/拒绝案例，加5个零几何eta敏感性案例，共17个结果全部符合。拒绝是正确行为，不计为求解通过。
- inaccurate prior：6条独立反例记录，保留不利结果。
- scale：72×54,000合成Gram系统，4种分块与独立Hd求解列二次型对照，最大差{large['max_abs_error']:.6g}。

## 分块内存与时间口径

一份float64 E为31,104,000 bytes；完整Sigma为23,328,000,000 bytes（约21.73GiB），未分配。block=256时两块72×256的float64缓冲区合计294,912 bytes，输出对角432,000 bytes；另有原始E及其副本、分解、验证临时数组等。这些是数组与workspace算术，不是实测进程峰值或GPU显存。

本机单线程BLAS一次分块计时：`{json.dumps(large['CPU_seconds_by_block'])}` 秒。它排除真实模型、E采集、native转换与在线集成，不证明满足在线20%开销或任何GPU内存预算。

## 保留的运行记录

1. `cpu_validation_001`：原型基础87项测试。
2. `research_001`：基础全研究，87项测试。
3. `research_002`：增加反例与索引验证，93项测试。
4. `research_003`：加入只读自适应plan与完整链验证，最终97项测试。

新增代码后才重新测试；未重复GPU、SLAM或历史研究。保留中间目录用于核对开发过程，不把执行次数当作科学样本量。
''')
    put('NEXT_STAGE_OPEN_ITEMS.md','''
# R1之后的明确待办（设计建议，未授权执行）

|问题|本轮结论|下一阶段需要的证据|
|---|---|---|
|正规系统协方差定义|CPU数学成立|确认真实E装配、固定窗口、gauge及原生guarded estimator用途|
|完整与分块对角|合成float64一致|原生数据类型/索引/多RHS接口下的等价性|
|端点|有限CPU数学两端精确恢复|原扩展float32、原子归约和Native-U两轮数值门槛|
|E来源|历史Schur不足以唯一确定|另获授权后显式采集E或从原始几何核验重建；不能伪造|
|rho冻结|只读CPUplan通过|首轮prior-off、同一次BA两轮固定rho的原生调用合同|
|Vf|无prior-mask依赖、保留弱Cg|真实投影/权重有效性、覆盖率、遮挡与空帧处理|
|k/tau/epsilon|只做合成敏感性|独立数据与尺度校准方案；不得据此默认采用Pi3MOS阈值|
|先验错误|高rho可放大错误prior|先验可靠性与几何退化分离的对照设计，不预设新增模块|
|性能|大shape合成分块可计算|实际窗口上分解复用、内存峰值、成本预算|
|算法收益|未知|后续单独获批的固定rho/D0/D1/CADP及跨场景比较|

本阶段完成后停在R1。R2、CUDA修改、GPU诊断、真实视频、真实C0、TASK006算法工程以及GitHub发布均未自动获批。
''')
    put('README_请先读.md','''
# TASK006A-R1 CADP CPU数学原型评审包

先读 `FINAL_REVIEW.md` 与 `AUDIT_DECISION.json`。科学结论：局部正则化协方差与D0/D1代数端点成立，值得继续工程验证；不代表真实轨迹改善。

建议评审顺序：

1. `MATHEMATICAL_DERIVATION.md`：精确协方差对象、原生阻尼和backsub guard局限。
2. `CPU_TEST_AND_EXPERIMENT_REPORT.md` 与 `results/research_003/RESEARCH_RESULTS.json`。
3. `NUMERICAL_STABILITY_AND_LIMITATIONS.md`：空帧/病态处理与错误prior反例。
4. `src/`、`tests/`、`IMPLEMENTATION_AND_REPRODUCIBILITY.md`：完整可运行实现及复核命令。
5. `NEXT_STAGE_OPEN_ITEMS.md`、`SECURITY_AUDIT.json`、保护记录和SHA清单。

全部研究为CPU、合成数据、float64。没有读取C0、真实视频或模型权重，没有运行GPU、CUDA或SLAM。R2未执行。所有原有R0/R3及Baseline资产保持原位；唯一项目级文字更新是正式流程进度文档，并保留前像。

评审无需解压大数据或加载任何模型。ZIP内携带完整源码和数值表；SHA清单排除自身以避免自引用，ZIP外的验收收据及最终整包SHA单独提供。本轮按授权没有上传GitHub。
''')
    put('EXECUTION_LOG.md','''
# R1执行记录

日期：2026-11-26，Asia/Shanghai。

1. 读取用户R1授权和现有正式流程，核对R0数学/配置/来源；没有重跑R0静态审计。
2. 使用GitHub只读连接器重查Pi3MOS官方固定提交及协方差相关源码，未发布任何内容。
3. 新建独立R1目录；只读保护148项R0/源文本/配置/流程文件，复制14份文字证据；重验R0小包CRC。没有读取R3数组/C0/权重。
4. 默认解释器未装NumPy，改用现有Python3.9、NumPy2.0.2、SciPy1.13.1；无安装、无环境改写。所有Python研究子进程CUDA_VISIBLE_DEVICES为空。
5. 实现独立prior-off协方差、分块对角、CADP端点、有效集、数值拒绝政策和合成生成器。基础87项测试通过。
6. 完成第一批CPU研究；增加E不可识别、6DOF索引、错误prior反例等验证后完成第二批93项测试。
7. 增加只读rho plan和完整自适应链后，最终批次research_003为97/97通过。原始中间目录保留，没有覆盖。
8. 生成数学、稳定性、实现、研究决策与最终评审；更新正式流程文字，记录前像。
9. 最终发行验证检查源码AST、保护文件、payload SHA及ZIP CRC；实际结果以相关收据为准。

R1未连接SSH、未启动/关闭/重启租赁实例；未运行模型、CUDA或真实视频；未触及生产源码和冻结YAML。R2尚未执行，完成后等待人工评审。
''')
    dump('SECURITY_AUDIT.json',{
      'scope':'Actions of this TASK006A-R1 execution only; not an audit of other local projects',
      'cpu_only':True,'CUDA_VISIBLE_DEVICES':'','torch_imported_in_research':r['torch_imported'],
      'gpu_requested':False,'gpu_used':False,'cuda_context_initialized':False,'cuda_compiled':False,
      'model_loaded':False,'weights_deserialized':False,'sealed_C0_read':False,'sealed_C0_deserialized':False,
      'real_VIPER_read':False,'SLAM_executed':False,'R3_arrays_loaded':False,'historical_E_fabricated':False,
      'baseline_production_sources_modified':False,'original_R2_YAML_modified':False,
      'model_weights_modified':False,'U_W_Frontend_Backend_modified':False,'scientific_history_overwritten':False,
      'remote_SSH_used':False,'GPU_server_rebooted':False,'dependencies_installed':False,
      'github_read_only_source_lookup':True,'github_push_performed':False,
      'R2_started':False,'project_tracking_document_updated':True,
      'synthetic_npz_created':True,'synthetic_npz_contains_models_or_C0':False})

    # Updating the formal progress record is metadata only; preserve its entire preimage.
    before=json.loads((ROOT/'evidence/PRESERVATION_BEFORE.json').read_text(encoding='utf-8'))
    progress=ROOT.parents[1]/'docs/TASK006A_PROGRESS.md'
    old=progress.read_bytes()
    entry=next(x for x in before['files'] if Path(x['path'])==progress)
    if hashlib.sha256(old).hexdigest()!=entry['sha256']:
        raise RuntimeError('Formal progress changed concurrently; do not overwrite')
    (ROOT/'evidence/FORMAL_PROGRESS_BEFORE.md').write_bytes(old)
    update=f'''# TASK006A 正式流程进度

最新更新：2026-11-26（Asia/Shanghai）。

- R0：用户已在R1指令中明确批准，历史R0封存报告保持不变。
- R1：CPU float64 CADP原型完成，最终{tests}/{tests}测试通过。
- 当前状态：`TASK006A_R1_COMPLETE_WAITING_FOR_HUMAN_REVIEW`。
- 结论：局部正则化数学结构成立；错误prior、原生backsub与Native-U等价性等局限保留。
- R2：未授权、未启动；CUDA/GPU/真实C0/真实视频均未执行。
- GitHub：本轮未发布。

最新评审：[FINAL_REVIEW.md](../experiments/{ROOT.name}/FINAL_REVIEW.md)。
完整包：[GAMECAM_TASK006A_R1_CADP_CPU_REVIEW.zip](../experiments/{ROOT.name}/deliveries/GAMECAM_TASK006A_R1_CADP_CPU_REVIEW.zip)。

---

以下保留先前流程登记原文，供追溯；当前状态以上述更新为准。

'''
    progress.write_text(update+old.decode('utf-8'),encoding='utf-8')
    (ROOT/'PROJECT_PROGRESS_UPDATE.md').write_text(update,encoding='utf-8')
    (ROOT/'evidence/FORMAL_PROGRESS_AFTER.md').write_bytes(progress.read_bytes())
    dump('REPRODUCIBILITY_MANIFEST.json',{
      'final_result_directory':'results/research_003','final_test_count':tests,
      'alpha':0.01,'lm':1e-4,'ep':0.1,'condition_limit_policy':1e12,'oracle_atol':2e-11,'oracle_rtol':2e-11,
      'demo_k':2.0,'demo_tau':2.0,'demo_epsilon':1e-6,'min_valid_demo':1,
      'median':'NumPy midpoint on even counts','rng':'NumPy default_rng PCG64',
      'synth_seeds':[43,44,45,1729,2026,20261126],
      'unit_test_report':'results/research_003/UNIT_TEST_REPORT.json',
      'execution_receipt':'logs/RESEARCH_EXECUTION_RECEIPT_003.json',
      'large_input_recipe':'src/synthetic.py::large_fixture(seed=20261126,npose=72,ndepth=54000)',
      'large_array_hashes':'results/research_003/DIMENSION_MATCHED_INPUT_RECEIPT.json',
      'real_data_used':False,'all_new_research_artifacts_independent':True,
      'metadata_exception':'docs/TASK006A_PROGRESS.md only; entire preimage and postimage included'})
    print(json.dumps({'reports_generated':True,'tests':tests,'R2_executed':False}))


if __name__=='__main__':
    main()

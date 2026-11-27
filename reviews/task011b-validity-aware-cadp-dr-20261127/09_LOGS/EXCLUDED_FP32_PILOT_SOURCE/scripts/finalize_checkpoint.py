"""Honest CPU checkpoint, explicitly incomplete Task011B while no GPU exists."""
import csv
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np

from common import ROOT,TASK,PREV,PREV_TASK,PROTOCOL,sha,dump,csvwrite,records

REVIEW=ROOT/'reviews/task011b-validity-aware-cadp-dr-20261127'
RUN=TASK/'runs/cpu_003'


def read(name):return list(csv.DictReader((RUN/name).open(encoding='utf-8-sig')))


def write(path,text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text.strip()+'\n',encoding='utf-8')


def copy(src,dst):
    dst=Path(dst);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)


def table(rows,cols):
    output=['| '+' | '.join(cols)+' |','|'+'---|'*len(cols)]
    for r in rows:
        values=[]
        for c in cols:
            x=r.get(c,'')
            try:x=f'{float(x):.6f}' if x!='' else ''
            except (ValueError,TypeError):pass
            values.append(str(x))
        output.append('| '+' | '.join(values)+' |')
    return '\n'.join(output)


def main():
    gpu=json.loads((TASK/'intake/TORCH_GPU_AVAILABILITY.json').read_text())
    if gpu['cuda_available'] or gpu['visible_device_count']:
        raise RuntimeError('GPU state differs; continue authorized GPU work instead of sealing a blocked checkpoint')
    proof=json.loads((RUN/'ARTIFACT_REPLAY_VERIFICATION.json').read_text())
    if proof['status']!='PASS' or proof['scalar_comparisons']!=3360:raise RuntimeError('Artifact proof missing')
    tests=(TASK/'private/CPU_TESTS_004.log').read_text(encoding='utf-8-sig')
    if 'Ran 63 tests' not in tests or not tests.rstrip().endswith('OK'):raise RuntimeError('CPU tests not verified')
    for name in ('01_R0_TTA_VALIDITY','02_R1_DEPTH_RELIABILITY','03_R2_CADP_DR_INTEGRATION','04_R3_VIPER_EVALUATION',
                 '05_METRICS','06_FIGURES','07_CONFIGS','08_TESTS','09_LOGS','10_FINAL_REPORT'):
        (REVIEW/name).mkdir(parents=True,exist_ok=True)
    # All original source cache hashes, previous review sources and source GTs are checked.
    protected=[]
    for r in records():
        path=Path(r['local_npz']);assert sha(path)==r['sha256']
        protected.append(dict(kind='ORIGINAL_R2_1_CACHE',path=str(path),sha256=r['sha256'],unchanged=True))
    previous=json.loads((PREV_TASK/'private/publication/allowlist.json').read_text())
    for row in previous['entries']:
        assert sha(row['source'])==row['sha256']
        protected.append(dict(kind='SEALED_TASK011A_PUBLICATION_SOURCE',path=row['source'],sha256=row['sha256'],unchanged=True))
    admission=list(csv.DictReader((TASK/'private/viper_inputs/CAMERA_ADMISSION.csv').open()))
    for row in admission:
        assert sha(row['source_path'])==row['source_sha256']
        protected.append(dict(kind='ORIGINAL_CAMERA_GT',path=row['source_path'],sha256=row['source_sha256'],unchanged=True))
    dump(REVIEW/'10_FINAL_REPORT/ORIGINAL_ASSET_PROTECTION.json',dict(status='PASS',files=protected,
        checked_paths=len(protected),GPU_or_model_runs=0,model_weights_written=False,production_source_written=False))
    for p in RUN.rglob('*'):
        if p.is_file():copy(p,REVIEW/'01_R0_TTA_VALIDITY/cpu_003'/p.relative_to(RUN))
    for p in RUN.glob('*.csv'):copy(p,REVIEW/'05_METRICS'/p.name)
    for p in (TASK/'figures').rglob('*'):
        if p.is_file():copy(p,REVIEW/'06_FIGURES'/p.relative_to(TASK/'figures'))
    for p in (TASK/'configs').glob('*'):
        if p.is_file():copy(p,REVIEW/'07_CONFIGS'/p.name)
    for p in (TASK/'CADP_DR_CONFIGS').glob('*.json'):copy(p,REVIEW/'07_CONFIGS/arms'/p.name)
    for p in (TASK/'CADP_DR_EXPERIMENTAL_BRANCH').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:copy(p,REVIEW/'03_R2_CADP_DR_INTEGRATION/CADP_DR_EXPERIMENTAL_BRANCH'/p.relative_to(TASK/'CADP_DR_EXPERIMENTAL_BRANCH'))
    # A source-layout copy lets external reviewers run the CPU replay without raw GT.
    for part in ('scripts','tests','configs','intake'):
        for p in (TASK/part).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:copy(p,REVIEW/'reproducibility/experiments/TASK011B'/p.relative_to(TASK))
    for p in (TASK/'tests').glob('*.py'):copy(p,REVIEW/'08_TESTS'/p.name)
    for p in (TASK/'private').glob('*.log'):copy(p,REVIEW/'09_LOGS'/p.name)
    for p in (TASK/'runs/cpu_001').rglob('RUN_CONFIGURATION.json'):copy(p,REVIEW/'09_LOGS/engineering_attempts/cpu_001'/p.name)
    for p in (TASK/'runs/cpu_002').glob('*.json'):copy(p,REVIEW/'09_LOGS/engineering_attempts/cpu_002'/p.name)
    for name in ('REMOTE_RESOURCE_STATUS.json','TORCH_GPU_AVAILABILITY.json'):
        copy(TASK/'intake'/name,REVIEW/'09_LOGS'/name)
    for name in ('VIPER_SELECTION_FROZEN.json','VIPER_WINDOW_MANIFEST.csv'):
        copy(TASK/'configs'/name,REVIEW/'04_R3_VIPER_EVALUATION'/name)
    for name in ('RGB_INTEGRITY.csv','CAMERA_ADMISSION.csv','SOURCE_ARCHIVES.json'):
        copy(TASK/'private/viper_inputs'/name,REVIEW/'04_R3_VIPER_EVALUATION'/name)
    manifest=list(csv.DictReader((TASK/'configs/VIPER_WINDOW_MANIFEST.csv').open()))
    ledger=[dict(window=r['window_id'],environment=r['environment'],arm='A'+str(a),status='PLANNED_NOT_STARTED_NO_GPU',
        frames_expected=64,attempt_id='',ATE='',RPE_translation='',RPE_rotation='') for r in manifest for a in range(7)]
    csvwrite(REVIEW/'04_R3_VIPER_EVALUATION/R3_EXECUTION_LEDGER.csv',ledger)
    for name in ('VIPER_TRAJECTORY_METRICS.csv','VIPER_ENVIRONMENT_METRICS.csv','VIPER_METHOD_COMPARISON.csv'):
        write(REVIEW/'04_R3_VIPER_EVALUATION'/name,'window_id,environment,arm,status,ATE_SE3,ATE_Sim3,RPE_translation,RPE_rotation,scale_est_to_GT,raw_path_ratio')
    fields='''| Field | Actual source / coordinates / meaning |
|---|---|
| native_depth | Official model canonical depth, unpad, bicubic to input grid, fx/1000, clamp0..300. Frozen output units are not independently certified physical metres. |
| flip_depth | Same restoration in horizontally flipped input coordinates; reverse the width axis exactly once before comparison. |
| native_confidence | Final raw model confidence, unpad then bilinear to native input grid; unbounded score, not a probability. |
| flip_confidence | Raw confidence in flipped coordinates; reverse width once for comparison; no depth scale factor. |
| flip_relative_disagreement | Original saved native-aligned T1 float32. Original invalid pairs remain NaN; raw historical zero extension is separate. |
| flip_log_disagreement | Original saved native-aligned log disagreement float32, invalid pairs remain NaN. |
| tta_valid | Exact original finite(native)&finite(unflipped flip)&native>0&flip>0, boolean on native pixel grid; all16 checked against original code and arrays. |
| native_bin_entropy | Initial 256-bin logits softmax entropy on154x266 bin grid; not final-depth calibrated uncertainty. |
| native_bin_variance | Variance of actual depth anchors under initial softmax; not final metric-depth error variance. |
| native_bin_max_probability | Initial largest softmax-bin mass; not probability that final depth is correct. |
| native_effective_bins | exp(initial entropy); bin-grid quantity, not 360x640 pixel depth reliability. |
'''
    write(REVIEW/'01_R0_TTA_VALIDITY/SOURCE_FIELD_PROVENANCE.md',fields)
    audit=read('TTA_VALIDITY_AUDIT.csv');vip=[r for r in audit if r['dataset']=='VIPER']
    max_legacy=max(float(r['ungated_relative_max']) for r in audit)
    native_invalid=sum(int(r['native_invalid']) for r in vip)
    fallback=sum(int(r['native_valid_pair_invalid']) for r in vip)
    comparison=[r for r in read('MVS_OBSERVED_SEQUENCE_MACRO.csv') if r['disagreement']=='SymmetricRelative' and r['domain'].startswith('FULL')]
    metric_cols=['method','AUROC_gt_0.2_mean','AP_gt_0.2_mean','AUSE_mean','AURG_mean','Spearman_mean']
    write(REVIEW/'01_R0_TTA_VALIDITY/R0_REPORT.md',f'''# R0: actual TTA validity audit

16 unchanged original NPZ caches: VIPER10 images/five weather groups plus six historical auxiliary MVS images. No model forward.

The historical ungated relative maximum is **{max_legacy:.8f}**. This is a diagnostic over finite raw depths including zeros, not an input to the new controller. Even valid positive pairs can have a large asymmetric T1; T2=abs(a-b)/(abs(a)+abs(b)+1e-6) is bounded below1 for positive pairs. T3=abs(log(a+1e-6)-log(b+1e-6)) is a log-scale quantity, not a bounded relative quantity. T4 retains native depth units.

The preregistered numerical lower bound1e-6 is in output units, not1micrometre or an independently measured distance. Native/Flip validity require finite values above that bound. Pair validity also requires the original boolean tta_valid. On10 VIPER images there are **{native_invalid} invalid Native pixels** and **{fallback} Native-valid/TTA-invalid pixels**.

Every undefined disagreement remains NaN with an explicit mask. No invalid pair is replaced by a zero disagreement. Invalid Native never receives a nonzero prior coefficient in controlled arms. Native-valid/TTA-invalid pixels use Native-only fallback in runtime TTA controls. The original depth arrays, original saved NaNs, restoration method and all original NPZ files remain unchanged.

The strict historical GT gate still fails. The seven zero Native predictions on validGT in MVS0001/0099 are included with AbsRel1 in the full-GT secondary diagnostic; they are not deleted to improve a score.

See TTA_VALIDITY_AUDIT.csv, TTA_DISAGREEMENT_COMPARISON.csv, TTA_NUMERICAL_STATISTICS.csv and SOURCE_FIELD_PROVENANCE.md. Bin-grid entropy/statistics are audited, not silently resized into or substituted for final-depth reliability.
''')
    write(REVIEW/'02_R1_DEPTH_RELIABILITY/R1_REPORT.md',f'''# R1: actual validity-aware relative-risk comparison

Raw Native risk is -Confidence. Percentile=(average rank-.5)/N on the declared finite prediction domain, without GT or error. Flip ranks use only pair-valid pixels. Native ranks use Native-depth-valid/finite-confidence pixels. Equal Rank uses0.5/0.5, Max takes the larger rank. Parameters were fixed before this batch; no tuning on0001.

Pure Flip/Rank/Max diagnostic fields remain undefined outside their allowed domains. ValidityAwareFusion uses equal Rank on valid pairs and Native-only fallback otherwise. Invalid Native is always forbidden as a prior. For the full-GT *policy* diagnostic only, rejection is a separate maximum-risk sentinel1; this is not an inferred confidence or a zero disagreement. All five methods retain the same GT population and seven zero predictions. A second common-pair diagnostic explicitly excludes invalid pairs for mathematical comparison and is not a replacement for the failed strict gate.

## Previously observed MVS0001, three frame macro means

{table(comparison,metric_cols)}

ValidityAwareFusion does not universally improve on either the historical Rank Fusion or the new pair-only Rank Fusion. Its small full-domain difference from pair-only Rank is solely fallback/rejection behavior; the two fields are exactly equal on common valid pairs. Symmetric TTA has a bounded numerical domain, but boundedness does not establish better ranking, calibration or VO utility.

All four disagreement definitions are saved and evaluated; SymmetricRelative was not replaced by a test-selected winner. AbsRel event thresholds0.1/0.2/0.5, raw-AbsRel AUSE/AURG, Spearman/Pearson, risk/error bins and20/40/60/80% retained coverage are in the CSVs. Native-only retains the stronger AUROC/AP here; Max has the lower AUSE. No method is a universal winner.

There is one reused evaluation sequence, not a new blind test or independent-domain generalization certificate. No VIPER dense-GT accuracy, probability calibration or temporal continuity is measured from the10 nonconsecutive images. Reliability=1-Risk is an ordinal control coefficient, not correctness probability.
''')
    write(REVIEW/'03_R2_CADP_DR_INTEGRATION/CADP_DR_INTEGRATION_REPORT.md','''# R2: isolated native candidate, GPU validation not run

**STATUS: IMPLEMENTED_CANDIDATE_CPU_CONTRACTS_ONLY. No compilation or native GPU regression has occurred. R2 is not complete.**

The project branch starts from official repository main7a4d93a8ace18ca37f97949622953ade5b129d86. The nested algorithm is separately pinned to DROID-W c3414af6047d06bafc1a6645d09f23247f3b2cdc. Native files are exported from exact Git objects, rather than copying local compatibility edits. The original worktree and installed droid_backends.so are not overwritten.

The candidate adds an isolated prior_strength tensor and explicit control/geometry booleans to its own BA binding. Original projective/retraction kernels, original Schur solve and its damping body, and the entire original U update body are preserved. The native two internal iterations are not split into separate calls. Existing U, affine, temp and UBA inputs/flags are forwarded unchanged. Disabled control takes the unchanged native formula.

Native variables: Cg=accum(Cii,ii,kx), bg=accum(wi,ii,kx), m=(mono_disparity>0), alpha=gamma_depth=.01. Candidate equations are C=Cg+m*s*alpha+(1-m*s)*eta, b=bg-m*s*alpha*(d-dm). The sign is native update RHS, not a copied residual-gradient convention. s0 gives D0, s1 gives D1; missing prior m0 retains eta. CPU tests verify the endpoint formulas, fractional interpolation and gradient sign.

The geometry-only path uses the same current native linearization: Q0=1/(Cg+eta), H0=A-EQ0Et, Hd=H0+diag(ep+lm*diag(H0)). Full pose-depth coupling E is assembled from current native Eii/Eij with source/target indices. Blocked Cholesky column solves evaluate diagSigma=Q0+diag(Q0Et Hd^-1 E Q0). This is a regularized inverse-normal proxy under native weights, not an independently calibrated physical covariance. g=u/(1+u), u=median(sqrt(diagSigma)/(abs(d)+1e-6)) over finite positive current disparities. No Metric3D prior, Confidence or external reliability is an input to the geometry helper. Current state can carry prior history; functional separation does not imply causal independence of entire optimization histories.

The geometry helper never replaces the optimizer's original sparse solve. Its full native cross-block assembly, float reduction behavior, cost and GPU correctness still require real captured-state verification. No diagonal-only substitute or Confidence/U proxy is used. Failure of SPD/finite checks stops the candidate rather than adding unregistered jitter.

Control scope is frontend main-loop local BA, including predecision and retained updates. Initialization, second initialization, online/final backend and filler use original paths; motion-only never receives this intervention. Unknown/missing eligible stage markers stop. A4 and A6 share the identical validity-aware rank reliability; only A6 adds g. Runtime A3/A4/A5 all fall back to Native-only on invalid TTA, whereas pair-only risk baselines are separately documented in R1.

Original DROID-W already has Metric3D regularization. Therefore A0 is the installed native path and A1 is the independent candidate's s1 endpoint. They are equivalent intended algorithms, not a fabricated D0 baseline or two independent depth-enabled methods. R2 native equivalence must be checked before R3. Historical U-feedback reduction variability requires original-repeat controls; CPU endpoint tests are not a native numerical certificate.

Original R2 buffer500, warmup12, gamma_depth.01, seed43 and the remaining YAML stay frozen. The actual native predictor uses cfg.cam.fx. Do not transplant R0's resized-focal output into the tracker under another focal convention. Preserve native restoration and log both actual trackerK and actual Metric3D focal; no hidden focal/scale repair is authorized in this task.

Seven arm JSON files, candidate source/diff/provenance, CPU reference and tests are included. build_extension.py compiles a unique module in a new directory when the approved GPU is present; it never installs over droid_backends. Native compilation, captured-input regression, real cache-provider wiring and the batch runner remain to be validated/completed when the GPU blocker is removed.
''')
    write(REVIEW/'04_R3_VIPER_EVALUATION/R3_INPUT_ADMISSION.md','''# R3: data admitted, trajectory experiment not started

**20 windows, four per environment,20 sequences,64 contiguous frames each,1280 original JPEGs. Planned140 arm/window runs; actual0.**

Selection was frozen before any new model result: first four eligible constant-K complete Validation sequence IDs per environment, arithmetic temporal midpoint. No algorithm score, depth error or GT motion was used to choose them. Camera motion descriptors were calculated only afterward. This balances weather and sequence identity, but does not prove that all requested scene challenges (especially dynamic-object density) are covered; those still require visual descriptors or manual review. These are previously available Validation sequences, not a new official Test or blind holdout.

Only the1280 exact existing ZIP members were extracted. All member CRC and complete JPEG decode checks pass, original1920x1080 RGB is retained. Camera rows exist64/64 per window and CameraID=RGBID-1 holds. K deviations are below.001px. Known variable-K val042/043 are excluded before comparison. No dataset downloads or retired third-person assets are used.

Candidate common input:640x360, OpenCV INTER_LINEAR, no crop, half-pixel calibration as in the existing full-sequence input protocol. Native loader calibration must be compensated exactly as in the original input adapter. Pose labels stay in an offline scoring file; inference must receive only images, IDs andK.

ATE/RPE, success/failure, raw scale, Sim3 scale and drift are **unmeasured**. The three metric CSVs currently contain schemas only, with no score rows or invented zero results. R3_EXECUTION_LEDGER is explicitly140 planned/not-started entries, not a run log. CAMERA_ADMISSION motion numbers are GT-only input descriptors, not predicted performance.

After GPU readiness and native regression, finish the common cached native-depth/Confidence/flip provider with identity, preprocessing/focal and RNG checks. Then serially run all seven arms on this fixed list, retain every failure and original output, score full valid trajectories with the same existing SE3/Sim3 tools, and report scale separately. Do not use Sim3 alone as scale-improvement evidence. Group bootstrap by source sequence, not pixels or BA events. A possible outcome is no improvement; do not terminate merely because an auxiliary ranking is poor.

Uniform attenuation is not an eighth authorized arm. Since per-image ranks attenuate mean prior strength, any eventual utility gain must be interpreted with this limitation; selective-reliability superiority over uniform attenuation cannot be claimed without an additional controlled experiment.
''')
    write(REVIEW/'04_R3_VIPER_EVALUATION/VIPER_FAILURE_ANALYSIS.md','''# Failure analysis status

No window inference was attempted. There are no tracking failures, successes, ATE/RPE scores or memory peaks to analyze. The current failure is environmental admission: the connected container exposes zero CUDA devices. Do not label planned windows as algorithm failures or fabricate zero errors.
''')
    write(REVIEW/'10_FINAL_REPORT/GPU_RESOURCE_BLOCKER.md',f'''# Actual environment blocker, not a new approval request

Current trusted endpoint is sc01-ssh.gpuhome.cc:31454, ED25519 pin SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA. Strict checking remained on.

nvidia-smi returned Exec format error. A second read-only check found no /dev/nvidia* nodes. The original DROID-W Python environment reports PyTorch **{gpu['torch']}**, CUDA build **{gpu['cuda_build']}**, **cuda_available=False**, **visible_device_count=0**. Merely seeing host driver files is not evidence that this container has a GPU.

/dev/shm is2GiB; data disk available11946180608bytes at this check. The original installed extension was found and SHA256 is **{gpu['extension_sha256']}**. No model was loaded, no CUDA kernel or SLAM experiment was launched, no extension was rebuilt/replaced. Only read-only resource/identity queries were made remotely.

The existing Task011B GPU authorization remains approved. No new per-arm approval is requested. The missing input is a reachable *GPU-enabled* instance/SSH command, already requested asynchronously. Do not reboot, remount devices, alter drivers, allocate another GPU or delete history to bypass this blocker. Recheck resources/identities on the actual card-enabled instance, then continue the already approved R2/R3 scope.
''')
    write(REVIEW/'10_FINAL_REPORT/STORAGE_AND_RESUMPTION.md','''# Storage and resumption

The20-window input list is already frozen and1280 originals are locally admitted. All archives and historical experiments remain intact. Current remote data free space is about11.13GiB; this is a measured checkpoint, not a future capacity guarantee.

Do not stage all20 windows' full priors and all140 outputs at once. Before actual GPU work measure the isolated extension build size, one-window native/flip/feature cache and one-group output. Preserve a10GiB remote reserve; calculate actual temporary compression and artifact overhead. If space is insufficient, stop with an explicit budget. Transfer newly generated task outputs to local D:, compare complete SHA/CRC and file identity, verify the owning process has exited, and only then remove that task's own temporary staged files under a documented lifecycle. Never automatically delete historical assets, weights, installed environments or frozen data.

GPU continuation order: current host/device/VRAM/process/SHM/disk identity → isolated compile → real native D0/D1 endpoint regression with original-repeat controls → common native-configuration prior cache/provider validation → all seven arms on the frozen20 windows → paired offline SE3/Sim3/RPE/scale analysis → complete final review. No automatic retries or protocol changes after OOM/native faults. No DROID-SLAM rerun or extra algorithm/data branch is part of this task.

The original buffer500 video logical storage alone is about6.955GiB before networks and workspaces. Therefore no assumption is made that the unchanged formal protocol fits the local8GB GPU, and no silent resolution/buffer/precision substitution is used. Keep the hardware division: local CPU work here; approved native/formal work on the available3090.
''')
    write(REVIEW/'08_TESTS/CPU_TEST_REPORT.md',f'''# Actual CPU verification

63/63 tests passed in CPU_TESTS_004.log. They cover validity classes, undefined scores, TTA boundedness/symmetry, ties, fallback, Native invalid rejection, all five risk controls, native D0/D1/fractional prior algebra, gradient sign, full joint inverse versus block covariance, chunk invariance, geometry-input separation, stage guards and unchanged original kernel/U bodies.

The actual cached-array replay verifies {proof['array_comparisons']} arrays, {proof['metric_rows']} metric rows and {proof['scalar_comparisons']} scalar values with maximum absolute difference0 (atol1e-12). No raw GT/model/GPU is required by this replay. The original seven zero predictions remain included.

These are CPU mathematical/source/data contracts. CUDA compilation, original-extension numerical regression, tracker/filler/native-GPU output behavior and any downstream ATE/RPE improvement remain UNVERIFIED.
''')
    write(REVIEW/'09_LOGS/ISSUES_AND_CORRECTIONS.md','''# Preserved engineering corrections

1. cpu001 stopped on metadata quantiles of a boolean validity field (NumPy disallows boolean interpolation subtraction). Quantile input was cast to float64 without changing the original dtype or any mask. A regression test was added. Original log retained.
2. cpu002 used the slow frozen Python per-tie loop. Only that owned CPU process was stopped after identity verification; partial arrays and receipt remain. Equivalent vectorized within-tie prefix accumulation was checked against the frozen reference on multiple sample sizes. No score/mask/threshold changed.
3. cpu003 is the completed actual batch (158.53s). It produced240 real metric rows. The stopped/failed CPU passes are engineering attempts, not independent scientific repeats or GPU retries.
4. The execution-config helper initially duplicated its arm dictionary key; corrected before sealing the seven configurations, with no model execution or change to numerical outputs.
5. Initial figure QA caught automatic color cycling changing weather colors across groups. A fixed weather palette and categorical mask ticks were applied, and the actual figures were regenerated. Numerical data did not change.

The existing main worktrees were not reset/cleaned/stashed. The new shallow sparse repository's initially unpopulated index was initialized from its own HEAD; no main-tree deletion was committed. Main and all historical public Releases remain unchanged.
''')
    write(REVIEW/'06_FIGURES/FIGURE_QA.md','''# Figure QA

20 actual PNGs: four quantitative figures and16 per-image validity/reliability plates. The four quantitative figures also have editable SVG/PDF. Plotting and all exports use the inherited Python/matplotlib workflow. No synthetic VO result is drawn.

Visual inspection covered the full-GT ranking plot, numerical-extremes/validity plot and the Night007/00244 plate. The fixed-palette numerical plot was inspected again after correction. All figures share stable method/weather colors, score ranges and explicit undefined-pixel display. Raw RGB is neither retouched nor relabelled as GT; depth/error accuracy is not claimed on VIPER. Display clipping is labelled, and arrays retain original values. Dots are three reused MVS frame values, horizontal bars are means; there are no pixel-IID significance marks or blind-test confidence intervals.

These are research-report figures, not a claim of final journal-specific submission formatting.
''')
    decision=dict(task='TASK011B',status='INCOMPLETE_WAITING_FOR_GPU_DEVICE',R0='COMPLETE_ACTUAL_CPU_CACHE_AUDIT',
        R1='COMPLETE_ACTUAL_CPU_CACHE_EXPERIMENT',R2='ISOLATED_CANDIDATE_IMPLEMENTED_GPU_UNVERIFIED',R3='NOT_STARTED_NO_GPU',
        approved_window_runs=140,actual_window_runs=0,actual_GPU_model_forwards=0,
        CUDA_compilation=False,windows_admitted=20,input_images_admitted=1280,CPU_tests_passed=63,
        arrays_replayed=proof['array_comparisons'],scalars_replayed=proof['scalar_comparisons'],
        validity_aware_fusion_universally_improves_ranking=False,downstream_VO_improvement='NOT_MEASURED',
        original_Baseline_modified=False,original_NPZ_modified=False,retired_datasets_used=False,
        current_gpu_authorization='APPROVED_REMAINS_VALID_PENDING_DEVICE_AND_REGRESSION',
        needs_new_stage_approval=False,needs_current_GPU_SSH=True,next_stage_automatically_launched=False)
    dump(REVIEW/'10_FINAL_REPORT/TASK011B_DECISION.json',decision)
    final=f'''# TASK011B 阶段评审：R0/R1已完成，真实GPU阶段阻断

2026-11-27（Asia/Shanghai）。**TASK011B 尚未完成。本包是完整的当前CPU阶段与阻断证据，不是140次VO结果包。**

| 阶段 | 实际状态 |
|---|---|
| R0 数值有效性 | 16份真实历史缓存完整检查，T1/T2/T3/T4与三个有效性标记已实现并实际计算 |
| R1 可靠性融合 | 五组风险对照、240条逐帧/分歧/域指标、阈值0.1/0.2/0.5与覆盖率20/40/60/80%已计算 |
| R2 独立接入 | 原生候选代码/七组配置/CPU合同已实现；未编译、未做真实CUDA端点和完整运行器验证 |
| R3 VO验证 | 20窗口/1280张原图及Camera映射准入；0/140窗口运行，ATE/RPE未测量 |

## 1. 已得到什么证据

旧未门控相对分歧最大约 **{max_legacy:.2f}**。新实现保留原始NPZ和NaN，Native/Flip/Pair Validity分开，T2仅在有效配对上计算且有界；无效Native的受控先验权重为0，Native有效而TTA无效时使用Native-only回退。十张VIPER缓存有{native_invalid}个Native无效像素、{fallback}个Native有效/TTA无效像素。数值安全不等于深度预测精度改善。

三张已观察MVS0001图像的全GT零扩展/拒绝策略诊断：

{table(comparison,metric_cols)}

**Validity-Aware Fusion 没有全面胜过原融合。** 对称分歧的数值界更好，但现有样本不支持普遍排序提升。相同有效配对区域中它与等权Rank相同；全域微小差异来自回退/拒绝策略。保留所有负面结果，不据此取消已批准的下游效用实验。

严格GT门禁仍是历史失败状态。原七个零预测在全GT诊断中仍保留，AbsRel为1；共同有效配对是另列的受限诊断，不能伪装成严格GT通过。MVS0001不是新盲测。没有将这些结果写成VIPER准确率，也没有把Risk/1-Risk称作概率或校准方差。

## 2. 接入边界与关键审查项

项目从main `7a4d93a8ace18ca37f97949622953ade5b129d86` 建立独立 `task011b/validity-aware-cadp-dr` 分支。算法源码独立固定为DROID-W `c3414af6047d06bafc1a6645d09f23247f3b2cdc`。TASK011A固定提交 `e2744c21d9d597fa253d552caec8c0b9540f5484` 的194项发布源保持一致。

候选只控制深度先验曲率和RHS梯度，保留eta路径、原生Schur/阻尼、U/UBA及原生双迭代。Geometry Need来自当前无先验几何逆正规方程，而非Confidence或U替身；其真实原生跨块与数值路径仍需GPU验证。关闭/端点只获CPU数学和源码支持，尚无GPU数值证书。

A0与A1原任务文字有重叠：原始DROID-W已含先验。本实现明确A0=原装路径，A1=候选s1原始端点，不擅自把A0改成D0。A4/A6共用同一有效性感知Rank，仅A6加入g。所有组初始化、FinalBA和Filler保持原路径。尚未把候选部署到生产。

## 3. 为什么没有启动GPU

可信连接 sc01-ssh.gpuhome.cc:31454 后，nvidia-smi为Exec format error；独立检查没有NVIDIA设备节点。原DROID-W环境实测 **CUDA available=False、device count=0**。这是真实设备准入问题，不是辅助指标差导致停止。

已经请求当前有卡实例的SSH信息。现有GPU运行授权保持有效；不要求每组重新批准。没有自行重启、改驱动、分配新GPU或以8GB本地显卡的缩小参数替代正式协议。详见GPU_RESOURCE_BLOCKER.md。真实模型推理和SLAM执行均为0。

## 4. 原始资产、测试与复现

63项CPU测试真实通过。完整重放核对528项数组和3360项标量，最大绝对差0（atol1e-12），历史七个零值未丢失。{len(protected)}个受保护路径哈希一致。1280张选定原图成员CRC、JPEG完整解码、64帧Camera映射全部通过。保留原生产源码、权重、旧NPZ、旧报告和Release。

包含全部当前浮点风险/有效性数组、实际CSV、20PNG/4SVG/4PDF、可运行CPU代码、候选完整源码/补丁、七组配置、测试和日志。原始RGB/GT、模型权重、环境二进制和凭证不重新分发。所有新连续数组都在完整展开目录与完整ZIP中，没有以核心包冒充全包。

## 5. 对任务十问的当前回答

| 问题 | 当前证据 |
|---|---|
| 数值问题解决？ | 有效性、回退和有界T2在CPU真实缓存上验证；未改变原始深度 |
| Validity-Aware优于原Rank？ | 当前样本不支持全面优势 |
| 哪个方法最好？ | 指标有取舍；Native事件AUROC/AP强，Max的AUSE低，无通用优胜者 |
| CADP-DR改善DROID-W？ | 未测量，GPU不可用 |
| ATE/RPE改善？ | 未测量，0/140运行 |
| Night/Rain/Snow改善？ | 未测量，不能用风险图代替VO |
| 平移压缩缓解？ | 未测量 |
| 新旋转误差/失跟？ | 未运行，不能称为0失败率 |
| 时间/显存开销？ | 只有CPU批处理158.53秒；正式GPU/算法开销未知 |
| 下一步？ | 恢复当前有卡实例准入，完成原生回归与共同缓存/运行器验证后执行已批准20窗口七组对照 |

当前不发布“算法改进成功”结论，不进入新方法/新数据集，也不消耗本任务正式运行预算。GPU可用后应无缝继续本任务，保留本CPU阶段封存证据。
'''
    write(REVIEW/'FINAL_REVIEW.md',final);write(REVIEW/'10_FINAL_REPORT/FINAL_REVIEW.md',final)
    write(REVIEW/'README.md','''# TASK011B current complete checkpoint, not completed VO research

Start with FINAL_REVIEW.md and10_FINAL_REPORT/TASK011B_DECISION.json. R0/R1 are actual completed cache experiments; R2 is an isolated uncompiled candidate; R3 has20 admitted windows and zero runs because the current container has no visible CUDA device. No VO improvement is claimed.

Full float evidence lives in01_R0_TTA_VALIDITY/cpu_003/derived_maps. CSVs, code, tests, configs, source patch and actual logs are included. To reproduce the full528-array/3360-scalar check from this extracted review without RGB/GT/model/GPU:

```powershell
python reproducibility/experiments/TASK011B/scripts/replay_saved_arrays.py --run 01_R0_TTA_VALIDITY/cpu_003 --output replay_outside_sealed_review.json
```

Use a separate output location to keep sealed files unchanged. NumPy/SciPy are required. Original physical GT and VIPER dense-GT accuracy are not certified. CUDA compilation and native regression must occur on the approved device before model inference.

The public GitHub Release binds the final publication Commit; this archive binds every file by SHA256. A commit cannot contain its own hash, so the final delivery receipt/Release records the fixed publication identity externally.
''')
    scope=dict(date='2026-11-27 Asia/Shanghai',active_dataset='VIPER',current_task='TASK011B',
        current_status='WAITING_FOR_GPU_DEVICE',latest_completed_task='TASK011A',current_experiment_running=False,
        authorization='TASK011B_R0_R3_APPROVED',planned_window_runs=140,actual_window_runs=0,
        no_automatic_third_person_resume=True,local_review=str(REVIEW),needs_current_GPU_SSH=True)
    dump(ROOT/'CURRENT_RESEARCH_SCOPE.json',scope);dump(ROOT/'RESEARCH_DIRECTION_CURRENT.json',scope)
    status='''# TASK011B — R0/R1 complete, GPU unavailable

2026-11-27. VIPER remains the only main experimental dataset. Task011B is approved but **not complete**: actual CPU/cache reliability experiments and native-candidate contracts passed; CUDA/R3 have not run because the connected container reports zero CUDA devices. The20-window/140-run protocol is preserved. No production baseline change or retired-dataset restart.

[Current review](reviews/task011b-validity-aware-cadp-dr-20261127/FINAL_REVIEW.md). The last fully completed task remains TASK011A. Current GPU authorization remains valid; resume this same task after device/identity readiness and native regression, without asking per-arm approval again.
'''
    write(ROOT/'CURRENT_RESEARCH_STATUS.md',status);write(ROOT/'PROJECT_STATUS.md',status)
    write(ROOT/'README.md',status+'\nSource branch starts from project main7a4d93a8; nested DROID-W is separately pinned c3414af6. All new work is under experiments/TASK011B. Production main, baseline source/weights and historical releases are untouched.\n')
    write(ROOT/'REVIEW_INDEX.md','''# Current reviews

- [TASK011B R0/R1 checkpoint; R2/R3 blocked by no GPU](reviews/task011b-validity-aware-cadp-dr-20261127/FINAL_REVIEW.md)
- [TASK011A fixed completed evidence](https://github.com/Pseven0108/GameCam-VO/blob/e2744c21d9d597fa253d552caec8c0b9540f5484/reviews/task011a-depth-reliability-fusion-20261127/FINAL_REVIEW.md)
''')
    dump(TASK/'private/TASK011B_STATE.json',decision)
    write(TASK/'EXECUTION_STATE.md','''# TASK011B execution state

R0/R1 complete from real cached data; CPU contracts63/63; independent replay528 arrays and3360 scalars exact. Original assets preserved. R2 candidate uncompiled/GPU unverified; R3 dataset20 windows/1280 images admitted, actual0/140 runs. Connected sc01:31454 PyTorch cuda_available=False, device_count0.

Authorization for this same Task011B R2/R3 remains approved. Need a currently GPU-enabled SSH endpoint, already asked asynchronously. No model/GPU/SLAM run has been launched. Do not fabricate success or restart another stage, driver or instance.
''')
    print('COMPLETE_CURRENT_CHECKPOINT_STAGED_TASK_INCOMPLETE_GPU_BLOCKED',flush=True)


if __name__=='__main__':main()

"""Assemble the complete CPU-stage review; no publication or experiment launch."""
import csv
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from common import BASE,PARENT,REVIEW,REVIEW_REL,ROOT,TASK,csvwrite,dump,sha


def write(name,text):
    path = REVIEW/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.strip()+'\n',encoding='utf-8')


def copy(source,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,dest)


def main():
    tests = json.loads((TASK/'tests/results_002/CPU_TEST_SUMMARY.json').read_text())
    data = json.loads((TASK/'data_audit_final/DATA_ADMISSION_DECISION.json').read_text())
    probe = json.loads((TASK/'cpu_probe_001/SUMMARY.json').read_text())
    if tests['status'] != 'PASS' or probe['status'] != 'PASS' or data['eligible_sequences'] != 0:
        raise RuntimeError('Unexpected result; review must be regenerated from actual evidence')
    REVIEW.mkdir(parents=True,exist_ok=False)
    snapshot = json.loads((TASK/'intake/INITIAL_ASSET_PROTECTION.json').read_text())
    verified,changed = [],[]
    for record in snapshot['inherited']:
        p = ROOT/record['path']
        result = dict(**record,unchanged=p.is_file() and sha(p)==record['sha256'])
        verified.append(result)
        if not result['unchanged']: changed.append(record['path'])
    original_verified = []
    for record in snapshot['original_baseline_files']:
        p = Path(record['path'])
        result = dict(**record,unchanged=p.is_file() and sha(p)==record['sha256'])
        original_verified.append(result)
        if not result['unchanged']: changed.append(record['path'])
    if changed:
        raise RuntimeError('Protected asset changed; do not publish an intact-baseline claim')
    protection = dict(status='PASS',inherited_files=len(verified),original_source_files=len(original_verified),
        changed_paths=changed,inherited=verified,original_baseline=original_verified,
        CUDA_compilation=False,production_extension_replaced=False,
        weights_loaded=False,weight_fresh_hash_check='NOT_PERFORMED_NO_WEIGHT_ACCESS',
        remote_extension_fresh_check='NOT_PERFORMED_NO_REMOTE_EXPERIMENT',
        original_TASK011B_worktree_edited=False,Task011C_independent_worktree=str(ROOT))
    dump(TASK/'FINAL_ASSET_PROTECTION.json',protection)
    dump(REVIEW/'05_PROTECTION/FINAL_ASSET_PROTECTION.json',protection)
    dump(REVIEW/'TASK011C_DECISION.json',dict(
        research_decision='INCONCLUSIVE',execution_status='STOPPED_AT_DATA_ADMISSION_AFTER_CPU_PREPARATION',
        A7_CPU_status='PASS',data_status=data['status'],eligible_sequences=0,selected_windows=0,
        formal_manifest_frozen=False,GPU_runs=0,GPU_pilots=0,new_model_forwards=0,
        CUDA_initializations=0,CPU_tests_passed=tests['tests_run'],CPU_tests_total=tests['tests_run'],
        synthetic_BA_calls=probe['synthetic_calls'],synthetic_source_rows=probe['synthetic_source_rows'],
        maximum_FP32_mean_error=probe['maximum_FP32_mean_error'],tolerance=1e-6,
        source_parent=PARENT,claim_A5_better_than_A7=False,
        claim_uniform_attenuation_sufficient=False,A7_GPU_numeric_equivalence='UNVERIFIED',
        next_action='USER_REVIEW_AND_DATA_PROTOCOL_DECISION',automatically_enter_next_stage=False))
    write('FINAL_REVIEW.md',f'''# TASK011C：A7 空间效用对照——数据审计与 CPU 准入评审

日期：2026-11-28（Asia/Shanghai）。前置提交：`{PARENT}`。

**结论：CPU 实现通过，数据准入阻断；研究决策为 `INCONCLUSIVE`。本轮 GPU 运行 0 次。**

按任务书最后一段，本轮只完成数据审计、A7 实现和 CPU 测试，停在正式 GPU 准入前。
这不是 300 次实验结果，也不是 A5、A7 优劣的验证。

## 1. 数据阻断有直接历史记录

VIPER Validation 共 47 条源序列。历史 3090 双 Baseline 全序列运行终态清单已覆盖
全部 47 条：94 条模型终态，92 次 COMPLETE、1 次 GPU_OOM、1 次 BUFFER_CAPACITY。
本轮逐条对照 94 份独立 `attempt.json`，身份与状态均匹配。失败且已处理输入的源序列
同样参与过对照，不能包装为未使用数据。历史 stride=4 不是当前协议，但仍构成源序列暴露。

扫描了 {data['further_manifest_census_files']} 份历史 Manifest/执行索引候选文件。
扫描中的普通文本引用只记为引用，不单独当作运行证据；排除依据是完整终态和独立运行收据。
全部规则下可用新源序列为 **0**，没有冻结正式窗口，没有创建可执行 GPU 顺序表。

| 天气 | Validation 总数 | TASK011B 用过 | 只排除 TASK011B 后剩余 | 排除全部历史对照后 | 要求 |
|---|---:|---:|---:|---:|---:|
| Day |12|4|8|0|4|
| Sunset |10|4|6|0|4|
| Rain |7|4|3|0|4|
| Snow |8|4|4|0|4|
| Night |10|4|6|0|4|

即使忽略更早的实验，Rain 也只有 3 条，不能满足每天气 4 条。本轮没有自行改成 Train、
缩减天气配额、复用旧窗口或下载新数据。47 个中点的 K/相机映射/GT path 和 ZIP 目录存在性
只是候选普查，不是算法表现筛选；没有解压或解码新 RGB。

证据：[数据准入表](01_DATA_ADMISSION/VALIDATION_SEQUENCE_ADMISSION.csv)、
[历史逐次执行证据](01_DATA_ADMISSION/HISTORICAL_EXECUTION_EVIDENCE.csv)、
[最终数据决策](01_DATA_ADMISSION/DATA_ADMISSION_DECISION.json)。

## 2. A7 实现了什么

A0/A1/A4/A5 原样调用父提交锁定实现。A7 缓存保留完全相同的 A5 像素可靠性，直到
实际 BA 调用才在原生 disparity 网格、真实 `kx=unique(arange(t0,t1)∪ii)` 和
`M=(mono_disparity>0)∩Native-valid` 内逐源帧求均值；M 外为零。没有使用整张 640×360 均值。

每次调用验证有效/正支持集、逐帧均值、整次调用有效域与稠密域均值、A7 常数性。
alpha 保持 0.01；原始 30 个 BA 实参、U/UBA、Schur、retraction、迭代次数未改。
非局部 BA、初始化、Final BA、Filler 与 motion-only 均保持原安装路径。

**匹配边界：** 这里保证 A7 对“同一个当前状态的反事实 A5”均值相同。
两条独立运行的关键帧和调用历史可能分叉，不能声称两条轨迹第 k 次 BA 的均值也必然相同。
若评审要求后一种严格固定状态匹配，需要另行批准实验设计，本轮未擅自固定关键帧。

**支持集边界：** 若非有限 Confidence 导致 A5 在 M 内为零，均匀化可能重新启用该像素。
实现会 STOP，而不修改 M 或悄悄恢复先验。Pair-invalid 的 Native-only fallback
先由原 A5 计算，然后参与均值；A7 不保留像素间不同的 fallback 系数。

见 [数学定义](02_A7_IMPLEMENTATION/A7_MATHEMATICAL_DEFINITION.md) 和
[源码](reproducibility/experiments/TASK011C/uniform_control.py)。

## 3. 真实执行的 CPU 验证

- 新增 A7 合同与 CPU Tensor 接入测试：56/56。
- 原 TASK011B 回归：66/66；合计 **122/122**，无跳过。
- 独立数值探针：12 次合成 BA 调用、119 个源帧记录，网格 45×80，CPU 种子 43/44/45。
- 逐源帧最大 FP32 均值误差 **{probe['maximum_FP32_mean_error']:.12g}**，低于原定 1e-6；没有放宽容差。
- 输入数组保护通过；PyTorch CPU 测试没有初始化 CUDA，没有导入或加载研究模型。

这些是合成数学和接入合同证据，不是原生 CUDA 等价性或 VIPER 轨迹实验。
首次回归因父提交顶层没有物化一份历史 JSON 夹具而报错；随后从同一固定提交展开评审中
恢复逐字节相同夹具，通过完整回归。保留第一次日志，没有删除失败测试或修改其断言。
首次目录检查将跨分卷公共目录误当作重复文件，已改为只比较 JPEG 文件成员，保留开发记录。

见 [完整测试结果](03_CPU_VERIFICATION/results_002/CPU_TEST_SUMMARY.json) 和
[合成均值审计](03_CPU_VERIFICATION/cpu_probe_001/SYNTHETIC_PER_SOURCE_MEAN_AUDIT.csv)。

## 4. 保护与局限

父提交实验代码/配置等 {len(verified)} 份与本地原始 DROID-W 源码 {len(original_verified)} 份，
执行前后 SHA-256 全部一致。没有编译 CUDA、替换生产扩展、读取权重、运行模型或接触远端实验。
远端 GitHub 发布（如已完成）仅用于交付，不属于研究计算。权重及远端扩展没有在本轮重新
做现场 SHA 核验，不能将“未访问/未修改”写成新的远端运行证书。

没有 A5/A7 真实轨迹、GPU 时间/显存、三 seed 稳定性、天气效果、bootstrap CI 或空间效用结果。
不以 TASK011B 的已有 ATE 填充本轮表格；不将合成 Probe 种子当成正式三 seed 重复。
没有动态/深度概率校准结论，也没有证明均匀衰减足够。

## 5. 下一步审查点

首先决定是否以及如何修订数据排除规则和天气配额；任何修订必须在看新算法结果前冻结。
同时明确同状态均值匹配的估计对象，以及 RPE、raw-scale 和成本的数值退化边界。
当前任务书没有给这些次指标“不可接受退化”的数值界限，不能事后按结果选择。

在这些问题解决并获得后续 GPU 准入之前，**不启动 Pilot、不运行 300 组、不开发新 Geometry Need**。

[完整协议](00_PROTOCOL/PROTOCOL.md) · [下一阶段边界](06_DECISION/NEXT_STAGE_BOUNDARY.md) ·
[机器可读决策](TASK011C_DECISION.json)
''')
    write('01_DATA_ADMISSION/DATA_AUDIT_REPORT.md','''# Validation 源序列资格审计

准入规则未降低。全部 47 条 Validation 源序列已经有历史双 Baseline 执行记录，
严格排除后为 0；只排除 TASK011B 后，Rain 也仅有 3 条。

所有 94 个 aggregate 记录与各自独立 attempt.json 的 case/model/status 一致。
val_043 的两次失败已经分别处理了真实输入，仍属于参与过对照的源序列。
退役的 stride4 研究分支并未恢复；其历史暴露记录不能因此消失。

GT path >0.0001 native camera units 与 K <0.001 px 在任务开始前写入 STAGE_CONTRACT。
审计只读取已有 offline_gt 缓存，不向算法提供 GT。原始 ZIP 只读取中央目录；
成员存在不代表本轮 CRC 或 JPEG 解码通过，未作这类虚假声明。

REPOSITORY_MANIFEST_CENSUS 是有界的名称/文本引用普查，并非所有本地资料的穷尽证明。
它既不把计划表当执行证据，也不把 Train 001 和 Validation 001 合并。
证明本轮无可用源序列只需已独立核验的完整 Validation 终态证据。

GPU_EXECUTION_MANIFEST.csv 只有列名、0 行，明确表示没有正式运行计划。
VALIDATION_SEQUENCE_ADMISSION 的 47 个中点是普查记录，不是被冻结的 20 个正式窗口。
''')
    write('03_CPU_VERIFICATION/CPU_TEST_REPORT.md',f'''# CPU 验证

最后一次完整运行：122/122，无失败、错误或跳过。

| 组 | 测试数 | 结果 | 设备 |
|---|---:|---|---|
| 新增 A7 数学、映射、失败关闭与接入 |56|PASS|CPU|
| 原 TASK011B 精确回归 |66|PASS|CPU|

实际接入测试使用 PyTorch CPU Tensor 与求解器 Stub，检查原生 30 个实参对象身份、
U/UBA 与迭代参数、时间戳映射、源帧集合、原生网格采样、逐次 mask 变化、阶段直通及故障后恢复。
Stub 返回值不是原生 BA 输出。原测试单独进程运行，保持其“不导入 torch”的测试合同。

独立数学 Probe：12 次合成调用、119 个源帧，最大均值差 {probe['maximum_FP32_mean_error']:.12g}。
不改变 1e-6 容差。均值相同并不要求 residual 加权梯度相同，后者正是空间干预可能影响的量。

results_001 保留 1 项缺失历史测试夹具错误；results_002 从父提交取回原始夹具后完整通过。
没有修改历史测试代码或删除断言。测试报告不宣称 CUDA 数值等价。
''')
    write('04_GPU_ADMISSION/GPU_ADMISSION_STATUS.md','''# GPU 准入：BLOCKED / 未执行

| 条件 | 状态 |
|---|---|
| 独立工作分支、冻结父提交 |PASS|
| A0/A1/A4/A5 与候选原生源码未改 |PASS_CPU_SHA|
| A7 CPU 有效支持/逐源帧/调用均值 |PASS_SYNTHETIC_CPU|
| 原生 U/UBA 实参传递、阶段合同 |PASS_CPU_STUB_AND_STATIC|
| 五天气各 4 条未暴露 Validation 源序列 |FAIL：全部 0|
| 正式数据及执行顺序 Manifest |NOT_FROZEN|
| A7 CUDA reduction / 原生端点回归 |NOT_RUN|
| GPU Pilot / 正式运行 |0 / 0|

本轮交付不含可执行 GPU 调度器。历史 TASK011B launchers 是只读前置代码，
其旧授权、旧进度 JSON 和旧 GPU 证书都不能作为当前 TASK011C 准入。
''')
    write('06_DECISION/RESEARCH_QUESTIONS.md','''# 九个研究问题的当前回答

1. A5 是否优于 A7？未知，没有新的轨迹结果。
2. 收益是否来自空间分配？未知，不能从 CPU 均值证书推断。
3. A5 是否比 Rank Fusion 更有价值？TASK011B 的单 seed 探索保留，本轮未验证。
4. A5 是否比原 DROID-W 更稳定？没有新的跨 seed 证据。
5. 三个 seed 波动？没有正式重复实验；合成 Probe 不是算法重复。
6. 天气差异？没有新实验。
7. 空间分配值得保留？值得做严格对照，但尚未获得保留/放弃的确认性证据。
8. 是否继续 CADP-DR？先解决采样协议与准入，不通过新增模块绕过对照。
9. A5 能否作为下一阶段候选？可保留为候选，不能宣称已被本轮 PROMOTE。

最终决策 INCONCLUSIVE 是数据/证据不足，并非证明 A5 与 A7 等价。
''')
    for name in ('PROTOCOL.md','A7_MATHEMATICAL_DEFINITION.md','NEXT_STAGE_BOUNDARY.md'):
        folder = {'PROTOCOL.md':'00_PROTOCOL','A7_MATHEMATICAL_DEFINITION.md':'02_A7_IMPLEMENTATION','NEXT_STAGE_BOUNDARY.md':'06_DECISION'}[name]
        copy(TASK/name,REVIEW/folder/name)
    for p in (TASK/'data_audit_final').iterdir():
        if p.is_file():copy(p,REVIEW/'01_DATA_ADMISSION'/p.name)
    for folder in ('results_001','results_002'):
        for p in (TASK/'tests'/folder).iterdir():
            if p.is_file():copy(p,REVIEW/'03_CPU_VERIFICATION'/folder/p.name)
    for p in (TASK/'cpu_probe_001').iterdir():
        if p.is_file():copy(p,REVIEW/'03_CPU_VERIFICATION/cpu_probe_001'/p.name)
    # The independently runnable A7 source/test tree, exact inherited sources
    # and minimal frozen fixtures. No raw RGB/GT arrays, weights or binaries.
    for p in TASK.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ('private','__pycache__')):
            continue
        rel = p.relative_to(TASK)
        if rel.parts[0] in ('data_audit','data_audit_final','cpu_probe_001') or 'results_001' in rel.parts or 'results_002' in rel.parts:
            continue
        copy(p,REVIEW/'reproducibility/experiments/TASK011C'/rel)
    for record in snapshot['inherited']:
        copy(ROOT/record['path'],REVIEW/'reproducibility'/record['path'])
    for name in ('reliability_metrics_frozen.py','NATIVE_REGRESSION_FORMAL_REAL_FIRST_LOCAL.json'):
        p = ROOT/'experiments/TASK011B/intake'/name
        copy(p,REVIEW/'reproducibility/experiments/TASK011B/intake'/name)
    old = 'reviews/task011b-validity-aware-cadp-dr-20261127/reproducibility/'
    for rel in ('UPSTREAM_LICENSES/DROID-W-LICENSE.txt','UPSTREAM_LICENSES/ATTRIBUTION.md',
                'frozen_viper_metrics/offline_eval.py','frozen_viper_metrics/fullseq_common.py'):
        content = subprocess.check_output(['git','show',PARENT+':'+old+rel],cwd=ROOT)
        p = REVIEW/'reproducibility'/rel
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(content)
    dump(REVIEW/'03_CPU_VERIFICATION/ENVIRONMENT.json',dict(
        python=sys.version,executable=sys.executable,platform=platform.platform(),
        packages={p:importlib.metadata.version(p) for p in ('numpy','scipy','torch','pillow')},
        execution_device='CPU',CUDA_visible_devices='-1',CUDA_initialized=False,
        dependencies_installed_or_changed=False))
    write('03_CPU_VERIFICATION/DEVELOPMENT_HISTORY.md','''# 保留的工程失败与修复

1. 首轮 ZIP 中央目录去重将公共 directory entries 算作重复图像。修正为仅比较
   非目录、扩展名为 .jpg 的文件成员。首轮未完成输出仍保留在本地 data_audit；
   最终 data_audit_final 为新目录，没有覆盖历史源数据。
2. 首轮完整回归中，原测试读取的历史 NATIVE_REGRESSION_FORMAL_REAL_FIRST_LOCAL.json
   不在父提交顶层 task 目录，只在同提交展开评审里。恢复原始字节，不改测试，
   第二轮 122 项全部通过。results_001 的 stdout/stderr 与 JSON 均包含于本包。

这些修复不改变 A5、BA 或数据选择规则。
''')
    write('DELIVERY_SCOPE.md','''# 本包范围

这是 TASK011C 第一阶段完整评审包，不是完整 GPU 研究结果包。包含数据排除证据、
全部当前源码/测试/配置、完整 CPU 日志、合成 Probe 数据、原生源码指纹和保护记录。

尚不存在：正式五组轨迹、失败轨迹分析、三 seed 运行结果、天气算法对比、bootstrap、
GPU 成本表与真实 A5/A7 轨迹/可靠性空间图。未生成这些文件，没有伪造空成绩表。

不含原始 RGB、原始相机矩阵/GT、权重、Conda 环境、生产 .so、凭据。
元数据中的 GT path/K 摘要、历史执行状态和文件哈希是准入证据，不是原始数据再发布。
历史 1 GiB TASK011B ZIP 不重复打入本包，原有 Release 保持完整。
''')
    write('README.md','''# 从这里审查 TASK011C

1. FINAL_REVIEW.md：结论、证据与边界。
2. TASK011C_DECISION.json：CPU_PASS / DATA_BLOCKED / INCONCLUSIVE，GPU=0。
3. 01_DATA_ADMISSION：47 条源序列逐项准入与历史 94 次终态证明。
4. 02_A7_IMPLEMENTATION 和 reproducibility：数学定义、独立源码与测试。
5. 03_CPU_VERIFICATION：122 项最终测试、首轮日志、12 次合成数值 Probe。
6. 05_PROTECTION：79 份继承代码与 110 份原始源码的执行前后 SHA。
7. 06_DECISION：下一步需先解决的协议问题。

所有 SHA-256 均列于 SHA256_MANIFEST.csv。包内不含模型权重或数据集。
''')
    print(json.dumps(dict(status='EXPANDED_REVIEW_READY',review=str(REVIEW),
                         protected=len(verified)+len(original_verified),GPU_runs=0)))


if __name__ == '__main__':
    main()

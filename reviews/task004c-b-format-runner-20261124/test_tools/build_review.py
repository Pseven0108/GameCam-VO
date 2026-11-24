"""Build evidence-grounded stopped-stage reports; does not launch or repair models."""
import csv,hashlib,io,json,pathlib,shutil,subprocess
from datetime import datetime,timezone,timedelta
ROOT=pathlib.Path(__file__).resolve().parents[1]
RAW=ROOT/'remote_evidence';OUT=ROOT/'review_original_v2'
assert not OUT.exists();OUT.mkdir()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def put(name,text):
 p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text.rstrip()+'\n',encoding='utf-8')
def dump(name,obj):put(name,json.dumps(obj,ensure_ascii=False,indent=2))
def table(name,columns,rows):
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=columns);w.writeheader();w.writerows(rows);put(name,s.getvalue())
cp=read(RAW/'evidence/CPU_FINAL_ACCEPTANCE.json');fresh=read(RAW/'cpu_tests/REAL_MODEL_FINAL_SOURCE_ROUNDTRIP_R1/FRESH_PROCESS_RECEIPT.json')
cap=read(RAW/'attempts/capture/C0_RECEIPT.json');capproc=read(RAW/'attempts/capture/PROCESS_RECEIPT.json')
rproc=read(RAW/'attempts/restore_check/PROCESS_RECEIPT.json');restored=read(RAW/'attempts/restore_check/RESTORE_RECEIPT.json')
post=read(ROOT/'evidence/POST_FAILURE_PRESERVATION_SUMMARY.json');integrity=read(ROOT/'evidence/C0_POST_CAPTURE_INTEGRITY_SUMMARY.json')
budget=read(RAW/'C0_EXACT_BUDGET_BEFORE_SAVE.json');release=read(RAW/'evidence/CPU_STAGE_RELEASE.json')
manifest=read(RAW/'C0/manifest.json');rstate=read(ROOT/'evidence/FINAL_RUNTIME_STATE_SUMMARY.json')
assert cp['total']==cp['passed']==217 and capproc['exit_code']==0 and rproc['exit_code']==1
assert cap['state_sha256']==restored['c0_sha256']==manifest['state_sha256']
assert len(manifest['nodes'])==18143 and integrity['storage_files_verified']==852
commit=release['candidate_commit'];tree=release['candidate_tree'];now=datetime.now(timezone(timedelta(hours=8))).isoformat()
ledger={'task':'TASK004C-B-TIMM-FORMAT-CLOSURE-AND-RUNNER-READY','status':'STOPPED_RGB019_OUTPUT_DIRECTORY_COLLISION',
 'updated_Asia_Shanghai':now,'source_commit':commit,'source_tree':tree,'Format_repair':{'authorized':1,'consumed':1,'status':'PASS'},
 'CPU_release_tests':{'passed':217,'total':217,'scope':'CPU_CONTRACTS_AND_REGRESSION'},
 'CPU_real_models_new_process_restore':'PASS','GPU_C0':{'authorized':2,'consumed':1,'successful':1},
 'GPU_fresh_restore_check':{'consumed':1,'full_state_restored':True,'RGB019_processed':False,'exit_code':1},
 'short80':{'authorized':4,'consumed':0,'successful':0},'formal487':{'authorized':4,'consumed':0,'successful':0},
 'new_GPU_stage_launches':2,'automatic_retries':0,'next_stage_allowed':False,'C0_state_sha256':cap['state_sha256'],
 'stopped_reason':'FileExistsError from SummaryWriter precreating the same native output directory',
 'source_changed_after_C0':False,'instance_shutdown':False,'instance_rebooted':False,'failure_Arena_retained':True,
 'no_new_trajectory_or_causal_effect_results':True}
dump('state/STAGE_LEDGER.json',ledger)
dump('TASK004C_B_AUTONOMOUS_RUN_STATE.json',ledger)
final=f'''# Task004C-B Format 闭合与运行器验收：最终评审

更新时间：{now}（北京时间）。最终状态：**PARTIAL — STOPPED_RGB019_OUTPUT_DIRECTORY_COLLISION**。

**本轮已完成 Format 修复、真实模型 CPU 新进程恢复、真实 GPU C0 采集，以及真实 C0 的新 GPU 进程状态恢复；RGB019 尚未处理，Short80 和正式 B1～B4 均未启动。**

| 证据层次 | 实际结果 | 证据入口 |
|---|---|---|
| Format 专项 | 22/22；保留 timm 0.9.10 原枚举单例身份 | raw_evidence/cpu_tests/FORMAT_UNIT_R1/ |
| ConfigDict 回归 | 14/14；原 Adapter 保持 | raw_evidence/cpu_tests/CONFIGDICT_REGRESSION_R1/ |
| 历史回归 | 152/152；最终候选重新运行 | raw_evidence/evidence/CPU_LEGACY152_STAGE_R1_RECEIPT.json |
| Stage / driver / guard | 20 + 3 + 6 项 CPU Mock 通过 | raw_evidence/cpu_tests/ |
| CPU 发布验收总数 | 217/217 | raw_evidence/evidence/CPU_FINAL_ACCEPTANCE.json |
| 真实带权模型 CPU 往返 | 最终源码版本通过；47 状态族、849 Storage、18,062 节点、71 callable；输出/梯度 SHA 精确一致 | raw_evidence/cpu_tests/REAL_MODEL_FINAL_SOURCE_ROUNDTRIP_R1/FRESH_PROCESS_RECEIPT.json |
| 真实 GPU C0 | RGB001～018；24 次初始化 BA；RGB019 未读取；退出码 0 | raw_evidence/attempts/capture/ |
| C0 文件核验 | 852 Storage 文件 + 2 元数据，共 854/854；{integrity['actual_bytes']:,} bytes | evidence/C0_POST_CAPTURE_INTEGRITY_SUMMARY.json |
| 新 GPU 进程恢复 | 18,143 对象节点及 Tensor/alias/对象图重编码一致；下一输入身份匹配；RNG 最后恢复 | raw_evidence/attempts/restore_check/RESTORE_RECEIPT.json |
| RGB019 续跑 | **FAIL，退出码 1**；进入 Tracker 前发生目录冲突，0 个 frame event | raw_evidence/attempts/restore_check/process.stderr.txt |
| Short80 / 正式487 | NOT STARTED：0/4、0/4 | state/STAGE_LEDGER.json |

## 本轮两个可确认的工程进展

`timm.layers.format:Format` 通过精确类、版本、源码 SHA、枚举成员 name/value 白名单恢复为安装包原单例，未降格为字符串，未知枚举继续失败关闭。保留已接受的 ConfigDict 和 Metric3D identity Adapter。

真实 GPU 初始化边界首次封存为本轮的不可变 C0：state SHA `{cap['state_sha256']}`。这与 CPU fixture 是两种不同的证据；真实 C0 含 18,143 个对象节点、852 个唯一 Storage，未压缩 Storage 合计 {integrity['uncompressed_storage_bytes']:,} bytes，完整归档 {integrity['actual_bytes']:,} bytes（{integrity['actual_bytes']/1024**3:.6f} GiB）。下一输入明确是 RGB019，counter={cap['counter']}。

## 为什么停止

`native_control/native_driver.py:115` 首先创建 `SummaryWriter(out/'native')`，实际 TensorBoard Writer 会建立该目录。C0 恢复和 `rebind_output()` 后，`native_driver.py:146` 又对同一 `tracker.output` 执行 `mkdir(parents=True, exist_ok=False)`，因此抛出 `FileExistsError`。

这次异常发生在 `tracker.run(stream)`、续跑 Rerun 子进程、Short80 和正式四组实验之前。`RESTORE_RECEIPT.json` 已写入，`native_trace.jsonl` 为 0 bytes；不能把状态恢复成功写成 RGB019 已运行。对真实 SummaryWriter 的独立 CPU 诊断复现了相同错误，未加载模型、未初始化 CUDA。

CPU Mock 将 Writer 换成不创建目录的空 Sink，而且 fake scene 使用 synthetic，未覆盖真实 scene=native 的输出目录生命周期。这解释了 217 项通过仍会遇到运行器故障；这些测试没有证明完整原生续跑。

遵守停止条件：没有修补运行中的源码、没有自动重试、没有运行后续阶段。失败 Arena、C0、日志和原始证据均保留。Format 专项 1/1；本轮 C0 1/2，独立 GPU 恢复检查 1 次；Short80 0/4，Formal487 0/4。不能将剩余 C0 额度解释为可自动重试当前失败阶段。

## 源码与科学含义

- 原始研究 Baseline：DROID-W `{manifest['provenance']['baseline_commit']}`。
- 接受的起点：`aa0cca3ed0d6e5d381422d8219234b8c0c6ad065`。
- Format 专项 commit：`0184690a51877223de32c78ada65002afa91103d`。
- 最终实验候选：`{commit}`；tree `{tree}`。
- 本轮 diff 分为 Format 与 stage runner 两份；Source commit 与 GitHub 发布 commit 分别记录。
- 原始 R2 YAML、模型权重、CUDA 扩展及发布源码保护共 3,759 项再次核验一致。未重编译 CUDA、未修改 BA 数学或 Metric3D 的生产前向计算。

没有新全序列轨迹、ATE/RPE、D 的直接效应或四组交叉实验结果；不能据此宣称算法改善。Formal487 的阶段接口与原生 Final BA/Filler 保存路径仅完成静态/CPU Mock，尚未通过真实 GPU 验收；统一离线指标也未执行。

## 资源与下一步

结束时数据盘 {rstate['data_disk_free_bytes']/1024**3:.6f} GiB 可用，仍超过 10 GiB；3090 保持在线、GPU compute apps 为空。未关机、重启或释放 GPU，未删除历史文件或此次失败 Arena。C0 采集的原生 Rerun recording 已生成（3,495,924 bytes）；未验证浏览器实时画面。恢复阶段尚未启动 Viewer。

最小后续工作是修复新运行目录的创建顺序/所有权校验，并增加使用真实 SummaryWriter、scene=native 的 CPU 生命周期测试。只建议方案，本轮没有实施。当前 C0 固定了旧 candidate commit；任何新源码修复后，必须明确处理兼容性授权或另行采集 C0，不能伪造 commit 或绕过 source pin 后重放。详见 `NEXT_MINIMAL_RUNNER_FIX_PROPOSAL.md`。

公开包含真实日志、退出收据、源码 diff、CPU 测试与 C0 结构元数据，省略模型权重、RGB/GT、Tensor payload、Arena 和 Rerun 二进制。公开 SHA 对脱敏字节计算；原始→公开映射另附，不能把脱敏后的结构文件当作可直接加载的原始 C0。
'''
put('FINAL_REVIEW.md',final);put('TASK004C_B_AUTONOMOUS_FINAL_REVIEW.md',final)
put('README_请先读.md',f'''# 请先读

本轮结论：**Format 修复和真实 C0 跨进程状态恢复通过；RGB019 续跑因输出目录冲突失败。**

先读 `FINAL_REVIEW.md`，再读 `TASK004C_B_RESTORE_FINAL_REPORT.md` 和 `TASK004C_B_FORMAT_CLOSURE_REPORT.md`。

实际 GPU 阶段：1 次初始化 C0 采集成功，1 次新进程恢复检查在续跑前失败；Short80 和 B1～B4 均为 0。真实 C0 存在且哈希完整，不需要通过 CPU fixture 假称成功。没有新轨迹评价结果。

候选源码 `{commit}`。C0 state SHA `{cap['state_sha256']}`。

`raw_evidence` 是原始执行文件的脱敏公开副本。`source_diff` 给出两个本轮 commit 的完整差异；`candidate_source` 是最终候选的 SHA 核验源码子集，完整源码对应仓库 `source/DROID-W` 导出树。`test_tools` 是实际执行的测试/调度工具，依赖既有环境和私有资产，不能视为自包含环境。

公开清单覆盖除清单自身外的全部交付文件。ZIP CRC、内部哈希和 GitHub 匿名读取在发布收据记录。C0 Tensor/权重/RGB/GT/Arena/Rerun 二进制仅保存在原研究存储。
''')
put('TASK004C_B_FORMAT_CLOSURE_REPORT.md',f'''# Format 专项闭合

状态：PASS；专项修复额度 1/1。仅精确接受 `timm.layers.format:Format` / timm 0.9.10 / source SHA `8b4d8d2d76d65cfbf8589092505e0c9d28d0a7af7df941abe59deb9cc664dfae`。

成员白名单 NCHW、NHWC、NCL、NLC。保存类身份、name、value、pin；恢复通过原安装枚举 `__members__` 查找，保持 `restored is Format.NHWC`。未调用通用 object.__new__ 恢复 Enum，未将其降为字符串，未知 Enum/str 子类失败关闭。读取快照时先验证这类节点，再反序列化 Tensor-only Storage。

代码：`candidate_source/native_control/timm_format_adapter.py`、`snapshot.py`；完整 diff：`source_diff/FORMAT_ONLY.patch`。ConfigDict 及 Metric3D identity Adapter SHA 保持不变。

22/22 真实安装枚举专项、14/14 ConfigDict、152/152 历史回归通过。真实带权模型 CPU 完整往返及真实 GPU C0 对象恢复也通过；RGB019 的新失败属于目录生命周期，与 Format 单例恢复不同。
''')
put('TASK004C_B_FULL_MODEL_RESTORE.md',f'''# 完整真实模型 CPU 恢复

最终候选 `{commit}`：全新 CPU 进程通过，退出码0，{read(RAW/'cpu_tests/REAL_MODEL_FINAL_SOURCE_ROUNDTRIP_R1/PROCESS_RECEIPT.json')['runtime_seconds']:.6f}s。此前仅 Format commit 也通过一次；最终源码版本是本轮 CPU 总门槛的依据。

源/恢复进程 PID {fresh['source_pid']} / {fresh['fresh_pid']} 不同。18,062 节点、849 Storage、6 ConfigDict、47 必需状态族、71 identity callable；完整图重编码、原始Storage内容、Tensor alias/shape/stride/offset、RNG 和 buffer 对比通过。加载过程不改变 RNG，捕获的 RNG 另行恢复。

恢复后重新执行 Metric3D 固定输入、FiT3D 特征、DroidNet fnet/cnet、带权 LoRALinear 输出和输入梯度，全部历史 SHA 精确一致；未放宽数值标准。

边界：该 CPU_NATIVE_INTERFACE_FIXTURE 具有真实预训练权重，但 Tracker/cache/cursor 为 CPU 合成状态；使用上游无 xformers attention fallback 和同公式 CPU 常量适配。CUDA未初始化。它不是原生 RGB C0，也不证明 GPU kernel 等价；GPU C0 的独立证据见对应报告。

原始 stdout/stderr/退出码及固定输入输出摘要：`raw_evidence/cpu_tests/REAL_MODEL_FINAL_SOURCE_ROUNDTRIP_R1/`。
''')
put('TASK004C_B_CHECKPOINT_CPU_ROUNDTRIP.md',(OUT/'TASK004C_B_FULL_MODEL_RESTORE.md').read_text(encoding='utf-8'))
put('TASK004C_B_RGB019_STAGE_RUNNER.md','''# RGB019 阶段化续跑

实现并测试 capture / restore19 / short80 / formal487 模式；每个模式独立准入、独立 attempt、固定 source commit，前序阶段必须成功。实际 C0 捕获停在 RGB018 frame-end，next index18、next RGB019。

CPU 模拟验证了 next-input/cursor/graph/stage 合同。真实 GPU 恢复成功后，目录创建在进入 Tracker 之前失败。没有 STAGE_RESUME_INPUT.json、没有 RGB019 frame event、没有 SUCCESS.json。不能用修改 index 或伪造日志补足。

真实状态：RESTORE_STATE_PASS / ACTUAL_RGB019_NOT_REACHED。详见 `TASK004C_B_RESTORE_FINAL_REPORT.md`。
''')
put('TASK004C_B_SHORT80_SCHEDULE_REPORT.md','''# Short80 调度

状态：CPU_CONTRACTS_PASS / NATIVE_GPU_NOT_STARTED。

固定顺序：record_S1 → replay_D0_S1 → record_S0 → replay_D1_S0，均从同一 C0 进入，真实上限 RGB080。

实现哈希链离散事件日记：Motion Filter、关键帧取舍、图边、BA事件、稳定RGB ID、图拓扑以及终止标记。仅重放离散调度，不复制连续 Pose、深度、U 或求解结果。未知/未配对/拓扑差异失败关闭。

20项 stage 模拟中包含 S0/S1 相关范围与日志读写合同，152项历史测试也保留；这不是实际80帧验证。由于 RGB019 阶段停止，四个Short80目录均不存在，运行额度0/4。没有真实 S0/S1 schedule，不生成伪造的真实 schedule CSV。
''')
put('TASK004C_B_FORMAL487_RUNNER_AUDIT.md','''# Formal487 运行器能力

状态：IMPLEMENTED_AND_CPU_MOCKED / NATIVE_GPU_UNVERIFIED。

矩阵与顺序：B1(D1自然S1) → B2(D0重放S1) → B4(D0自然S0) → B3(D1重放S0)。W=U=1；INIT_D=0；原始R2模型、seed43、buffer500、640×360、stride1。D只作用于规定前端Local BA；Final BA/Filler保留原生作用范围。

候选代码将真实 Tracker 状态恢复后运行至RGB487，记录前端关键帧快照，调用原生 SLAM.backend() 与 SLAM.terminate()，保存最终BA关键帧及Filler全487帧。Final BA原生外层7/12迭代；Filler独立seen计数。CPU AST driver mocks模拟这些调用及输出路径。

CPU Mock并未执行原生CUDA、真实Final BA或Filler。实际RGB019续跑已在目录生命周期失败；正式四组为0/4。完整487导出、原生Filler、真实调度兼容性和统一离线指标尚未验收。不得称正式runner已通过GPU验证。

已知文档问题：native_driver.py开头旧bounded-only说明未同步到新增formal模式；以函数实现和实测状态为准，本轮停止后未修改源码。
''')
put('TASK004C_B_GPU_C0_FINAL_REPORT.md',f'''# 真实GPU C0采集

PASS。GPU仅一次采集；退出码0；{capproc['runtime_seconds']:.6f}s（模型子进程计时，含完整序列化/核验）。

RGB001～018真实输入；INIT_D=0；12个初始化关键帧；8+8+8=24次原生BA；RGB018 frame-end停点；RGB019尚未读取。原始R2配置、K、buffer500、seed43、模块和权重保持。

state SHA `{cap['state_sha256']}`；manifest原始SHA `{integrity['manifest_sha256']}`。完整C0 854个文件（852 Storage、manifest及COMPLETE）共{integrity['actual_bytes']:,} bytes，全部SHA核验。

47状态族、18,143对象节点，Storage未压缩{integrity['uncompressed_storage_bytes']:,} bytes。保存前精确压缩预算：{budget['exact_checkpoint_logical_bytes']:,} bytes；最低free要求{budget['minimum_free_before_save_bytes']:,} bytes，含10GiB底线及预留。实际文件数与预算匹配。

源commit `{commit}`，tree `{tree}`；其后未改源码。C0是不可变真实快照，后续恢复检查亦核验所有载荷；没有把CPU fixture改名为C0。

原生Rerun recording生成，3495924bytes，SHA `04b87c29dcebcc7a7215469fade2e5817badbc1cf6c7adaad1076b0b0bb8f5bb`。仅确认文件与退出状态，浏览器实时画面未验证。
''')
put('TASK004C_B_RESTORE_FINAL_REPORT.md',f'''# 新进程恢复与RGB019失败

状态：**真实状态恢复PASS / 阶段续跑FAIL**。

源PID {restored['source_pid']}；新PID {restored['new_process_pid']}。18,143节点、全部Tensor/对象/alias/属性重编码匹配；下一输入身份匹配；RNG最后恢复。C0 hash `{restored['c0_sha256']}`。

下一输入=RGB019，index18；RGB/SHA/K由不可变C0记录。此报告没有宣称已经重新执行恢复后Metric3D GPU forward；新的RGB019推理未开始。

真实原生阶段退出码{rproc['exit_code']}，耗时{rproc['runtime_seconds']:.6f}s。错误为 `FileExistsError`：实际SummaryWriter先创建out/native，rebind后tracker.output相同，随后mkdir(exist_ok=False)拒绝重复创建。错误发生在viewer.start()及tracker.run()之前。native_trace和observer均为空，SUCCESS不存在。

CPU独立诊断使用实际安装SummaryWriter，精确重现相同路径行为；它的退出码0表示“预期故障被复现”，并不表示续跑修复成功。没有应用修复、没有自动重试、没有修改C0或源码。

原始traceback：`raw_evidence/attempts/restore_check/process.stderr.txt`；对象恢复收据：同目录RESTORE_RECEIPT.json；CPU诊断：`raw_evidence/cpu_tests/DIRECTORY_LIFECYCLE_DIAGNOSTIC_R1/`。
''')
dump('TASK004C_B_RESTORE_RECEIPTS.json',{'native_C0':cap,'fresh_state_restore':restored,'stage_process':rproc,'actual_RGB019_consumed':False})
dump('TASK004C_B_C0_MANIFEST.json',{'scope':'STRUCTURAL_METADATA_ONLY_NO_TENSOR_PAYLOADS','original_C0_state_sha256':cap['state_sha256'],'original_manifest_sha256':integrity['manifest_sha256'],'files_verified':854,'storage_files':852,'actual_bytes':integrity['actual_bytes'],'uncompressed_storage_bytes':integrity['uncompressed_storage_bytes'],'nodes':18143,'required_families':47,'next_input':integrity['next_input'],'immutable':True,'raw_manifest_public_copy':'raw_evidence/C0/manifest.json','public_copy_not_loadable_original_C0':True})
put('TASK004C_B_CROSS_D_REPLAY_REPORT.md','''# 跨D重放

NOT_STARTED。RGB019续跑门槛失败，S0/S1真实调度未生成，不运行跨D，也不计算跨D因果结论。CPU日记测试只验证接口/合同与错误关闭。
''')
put('TASK004C_B_FORMAL_B1_B2_B3_B4_REPORT.md','''# 四组正式实验

B1/B2/B4/B3全部NOT_STARTED，0/4。没有487帧新轨迹、Final BA快照、Filler输出或ATE/RPE。所有指标用空值与NOT_STARTED状态呈现，不能填0当作结果。
''')
put('NEXT_MINIMAL_RUNNER_FIX_PROPOSAL.md','''# 最小后续方案（未实施）

已确定故障：native_driver.py先用真实SummaryWriter创建native目录，后又用exist_ok=False创建相同目录。无需改BA、预处理、模型或权重。

建议先决定单一目录所有者：attempt目录仍使用排他创建；在新attempt内明确创建并校验native目录（拒绝链接、外部路径、旧结果），然后再初始化SummaryWriter。不能泛化为吞掉所有FileExistsError，也不能复用旧失败attempt覆盖日志。

CPU回归必须使用实际SummaryWriter、R2 scene=native、实际rebind_output及真实文件系统；覆盖新目录成功、既有合法空目录/服务子目录、旧实验目录拒绝、链接/逃逸拒绝。补齐Mock中Writer无副作用及fake scene带来的盲区。该建议本轮未应用，也没有因此增加GPU运行。

C0源身份不可规避：当前C0 pin为5d357c1d3079de134dd8b41a20a00632da37f0b0。任何新候选commit都不应冒用此pin。后续需要单独审查：批准纯I/O兼容overlay并验证全部被捕获类/Storage适配器/优化文件未变，或批准新源码下重新采集C0。不能悄悄放宽source检查、改写旧manifest、伪造旧commit或自动挪用剩余额度。

优先验证目标是新进程实际处理RGB019；通过之后才按现有次序进入Short80及四组，不重跑DROID-SLAM。
''')
put('TASK004C_B_STORAGE_AND_PRESERVATION.md',f'''# 存储与保护

真实C0精确大小{integrity['actual_bytes']:,}bytes；852个Storage压缩载荷合计{cap['storage_file_bytes']:,}bytes。未压缩Storage {integrity['uncompressed_storage_bytes']:,}bytes。逻辑字节精确，文件系统分块/元数据使用明确预留，不冒称物理开销精确。

退出时数据盘可用{rstate['data_disk_free_bytes']:,}bytes，{rstate['data_disk_free_bytes']/1024**3:.6f}GiB。新Arena共5个文件、{rstate['new_Arena_bytes']:,}bytes（capture与restore两套），均保留，未清理。旧Arena和历史失败证据未删除。

3,759个受保护源/配置/权重/扩展身份全部一致；C0 metadata最终回读未变，源工作区clean；GPU compute apps为空。实例仍在线。无重启、关机、数据删除或其他Baseline运行。

记录：evidence/POST_FAILURE_PRESERVATION_SUMMARY.json；evidence/FINAL_RUNTIME_STATE_SUMMARY.json；raw_evidence/evidence/POST_FAILURE_PRESERVATION_AUDIT.json。
''')
put('EXECUTION_LOG.md',f'''# 本轮执行日志

1. 读取用户本轮授权，保护已接受ConfigDict/Metric3D Adapter，使用独立候选起点aa0cca3。
2. 单轮Format适配，0184690；22项专项、14项ConfigDict和152项回归实际运行。
3. 两次真实带权模型CPU新进程恢复：Format-only与最终runner源码分别通过。CPU fixture边界明确，不是RGB C0。
4. 完成阶段化源候选5d357c1；20项stage、3项driver、6项guard；最终源码历史152重新运行；总217。
5. CPU driver首次因测试缺少import src.utils报3个error；仅修测试后3/3，原始失败stdout/stderr保留。发布汇总首轮误把ConfigDict文本当JSON导致helper失败，改读原生JSON报告；不是模型/GPU重试。
6. 封存CPU_RELEASE，执行唯一一次capture：exit0，{capproc['runtime_seconds']:.6f}s。24次初始化BA后于RGB018保存C0，854个文件核验一致。
7. 启动一次独立restore_check：完整状态恢复通过，但native输出目录已存在，exit1，{rproc['runtime_seconds']:.6f}s。没有处理RGB019。
8. 立即停止后续GPU阶段，无自动重试。CPU实际SummaryWriter诊断复现目录错误，未改源或C0。
9. 3759项保护核验通过，GPU空闲，数据盘超过10GiB；C0、失败Arena和旧实验保留。收集所有必要文本证据，文件逐项SHA复核。
10. 收集脚本首次试图在候选repository解析上游c341 commit，git对象不可用，收集器停止；调整为保留该缺失证据并使用已核验保护pin及本轮两个真实commit diff。未切换/重写源码。一个本地报告脚本曾因嵌套字符串引号语法错误未连接远端，纠正本地工具后执行只读保护核验；不是GPU重试。
11. 生成独立脱敏评审包，完整性核验后发布新GitHub分支；发布结果以独立publication receipt为准，不能把尚未执行的步骤预写为成功。

本轮保持3090在线，没有关机或重启。所有原始执行收据、stdout/stderr、hash记录见raw_evidence和evidence。公开副本脱敏SHA与原始SHA有明确映射。
''')
put('SOURCE_AND_COMPARABILITY.md',f'''# 源码身份与可比性

接受起点aa0cca3ed0d6e5d381422d8219234b8c0c6ad065；Format提交0184690a51877223de32c78ada65002afa91103d；最终提交{commit}；tree{tree}。Format diff仅两个文件；stage runner diff另附。

原始研究DROID-W来源c3414af6047d06bafc1a6645d09f23247f3b2cdc；当前隔离候选仓库历史为审计/控制代码的独立提交链，该Git对象在此仓库不可解析，不能据此宣称已完成git diff c341..HEAD。对应失败stderr保留在source_diff/FROZEN_BASELINE_UNAVAILABLE.txt。原始生产关键文件、R2/权重/CUDA扩展身份由冻结lock核验；本轮新改动相对于已接受aa0cca3均有精确diff和SHA。

阶段runner的变动是实验控制接入和结果保存；它不是未经改变的上游生产副本，也不是Improved DROID-W算法。候选没有改BA公式、Metric3D生产forward、模型权重、R2文件或CUDA扩展。新RGB输入仅001～018；没有可用于轨迹精度对比的新487帧成绩。
''')
# Exact source subset: final pins, never label a stale intake file as final.
source_count=0
for parent in (ROOT/'source_intake',ROOT/'candidate_patch'):
 for p in parent.rglob('*'):
  if not p.is_file():continue
  rel=p.relative_to(parent).as_posix();key='source_candidate/'+rel
  if key not in release['candidate_pins']:continue
  if sha(p.read_bytes())!=release['candidate_pins'][key]:continue
  q=OUT/'candidate_source'/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
source_count=sum(1 for p in (OUT/'candidate_source').rglob('*') if p.is_file())
shutil.copytree(ROOT/'source_diff',OUT/'source_diff')
shutil.copytree(RAW,OUT/'raw_evidence')
shutil.copytree(ROOT/'tools',OUT/'test_tools',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for p in (ROOT/'evidence').glob('*.json'):
 q=OUT/'evidence'/p.name;q.parent.mkdir(exist_ok=True);q.write_bytes(p.read_bytes())
(OUT/'authorization').mkdir();shutil.copyfile(ROOT/'authorization/TASK_REQUEST.txt',OUT/'authorization/TASK_REQUEST.txt')
put('AUTHORIZATION_BOUNDARY.md','''# 授权与停止

本轮CPU验收后自动进入GPU的授权继承自TASK004C-B-AUTONOMOUS-CONTINUATION。无须阶段间重复批准，但状态/运行异常不得自动重试。

实际执行Format专项1轮；capture一次；restore_check一次。恢复目录异常后没有Short80/正式四组/新数据/算法开发/训练/关机/重启。三个关键区别：CPU fixture不是原生C0，状态恢复不是实际RGB019续跑，阶段Mock不是487帧GPU成功。
''')
gate={**ledger,'CPU_release_evidence_file':'raw_evidence/evidence/CPU_FINAL_ACCEPTANCE.json','CPU_passed':True,'RGB019_GPU_passed':False,'Short80_GPU_passed':False,'formal487_GPU_passed':False,'native_C0_saved':True,'native_C0_state_restored':True,'runtime_blocker':'EXISTING_NATIVE_OUTPUT_DIRECTORY','passed_tests_do_not_override_native_failure':True}
dump('TASK004C_B_CPU_FINAL_GATE.json',gate)
dump('evidence/SOURCE_SUBSET_VERIFICATION.json',{'files':source_count,'every_exported_file_matches_final_candidate_pin':True,'full_source_in_published_source_tree':True,'source_commit':commit,'source_tree':tree})
security={'gpu_requested_by_task':False,'existing_gpu_used':True,'cuda_context_initialized':True,'checkpoint_restored':True,'actual_RGB_frames_processed':18,'actual_next_rgb_processed':False,'DROID_SLAM_run':False,'Short80_run':False,'formal487_run':False,'automatic_retry':False,'BA_math_modified':False,'Metric3D_production_forward_modified':False,'weights_modified':False,'R2_file_modified':False,'CUDA_extension_recompiled':False,'historical_data_deleted':False,'Arena_deleted':False,'source_changed_after_capture':False,'instance_shutdown':False,'instance_rebooted':False,'GPU_kept_allocated':True,'browser_live_render_verified':False,'github_publication':'SEE_SEPARATE_VERIFIED_RECEIPT'}
dump('SECURITY_AUDIT.json',security)
# Explicit no-result rows, never fabricated zero performance.
rows=[{'arm':x,'status':'NOT_STARTED','D':d,'schedule':s,'Sim3_ATE_RMSE':'','SE3_ATE_RMSE':'','fixed_312_328_displacement_ratio':'','pose_rows':'','reason':'RGB019_RUNNER_FAILED_BEFORE_FRAME_INPUT'} for x,d,s in [('B1',1,'S1'),('B2',0,'S1'),('B4',0,'S0'),('B3',1,'S0')]]
table('TASK004C_B_METRICS.csv',list(rows[0]),rows)
for name in ('TASK004C_B_TRAJECTORY_COMPARISON.csv','TASK004C_B_FINAL_BA_COMPARISON.csv'):
 table(name,['arm','status','result_available'],[{'arm':x,'status':'NOT_STARTED','result_available':False} for x in ('B1','B2','B4','B3')])
resource=[]
for name in ('C0_POST_CAPTURE_INTEGRITY_SUMMARY.json','POST_FAILURE_PRESERVATION_SUMMARY.json','FINAL_RUNTIME_STATE_SUMMARY.json'):
 d=read(ROOT/'evidence'/name)
 resource.append({'evidence':name,'time_unix':d.get('time_unix'),'data_free_bytes':d.get('data_disk_free_bytes',d.get('data_disk',{}).get('free')),'source_commit':d.get('source_commit',commit)})
table('TASK004C_B_RESOURCE_TIMELINE.csv',list(resource[0]),resource)
qa={'status':'EVIDENCE_CROSSCHECK_PASS_NOT_EXPERIMENT_COMPLETION','release_test_total':217,'native_capture_exit':0,'native_restore_stage_exit':1,'CPU_failure_reproduction_is_expected_failure_not_repair':True,'RGB019_not_processed':True,'no_short_or_formal_launches':True,'source_subset_files':source_count,'original_C0_file_count':854,'no_new_ATE_or_causal_effect_claim':True,'source_commit':commit,'C0_source_pin_kept':True}
dump('publication/SCIENTIFIC_QA.json',qa)
print(json.dumps({'reports_ready':True,'source_subset_files':source_count,'raw_files':sum(1 for p in RAW.rglob('*') if p.is_file()),'review_files':sum(1 for p in OUT.rglob('*') if p.is_file()),'status':ledger['status']}))


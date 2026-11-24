"""Evidence-driven report generation. No models or experiment execution."""
import ast,csv,hashlib,json,pathlib,shutil,subprocess
from datetime import datetime,timezone,timedelta
ROOT=pathlib.Path(__file__).resolve().parents[1]
PRIOR=ROOT.parent/'DROID_W_TASK004C_B_MINIMAL_CONTROL_20261123T183335782Z'
e=ROOT/'evidence';f=json.loads((e/'FINAL_PROTECTION_handoff.json').read_text())
p=json.loads((e/'PHASE0_REVIEW_SAFE.json').read_text());lock=json.loads((ROOT/'configs/identity_lock.json').read_text())
alg=json.loads((e/'ALGORITHM_PRESERVATION.json').read_text())
cpu_path=e/'CPU_handoff/artifacts/CPU_SUITE_handoff/CPU_TEST_REPORT.json';cpu=json.loads(cpu_path.read_text())
assert cpu['total']==118 and cpu['passed']==118 and not cpu['cuda_initialized']
now=datetime.now(timezone(timedelta(hours=8))).isoformat();gib=lambda x:f'{x/1024**3:.4f}'
def put(name,text):
    with (ROOT/name).open('x',encoding='utf-8',newline='\n') as out:out.write(text.strip()+'\n')
def js(name,doc):put(name,json.dumps(doc,ensure_ascii=False,indent=2))
def git(*args):
    q=subprocess.run(['git','-C',str(ROOT/'source_candidate'),'-c','user.name=GameCam Native Integration','-c','user.email=gamecam@localhost',*args],capture_output=True,text=True,check=True);return q.stdout.strip()
# Track the exact new control code inside the local candidate, too. The local
# repository is a text subset; only the remote baseline is the full file tree.
for folder in ('native_control','checkpoint','schedule','runner'):
    for file in (ROOT/folder).rglob('*.py'):
        if '__pycache__' in file.parts:continue
        dest=ROOT/'source_candidate'/file.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dest)
shutil.copy2(ROOT/'control_common.py',ROOT/'source_candidate/control_common.py')
git('add','--all');git('commit','-m','Native control integration with CPU closure and bounded smoke guards')
local_commit=git('rev-parse','HEAD')
js('evidence/FINAL_GIT_IDENTITIES.json',{'local_text_candidate_commit':local_commit,'remote_full_candidate_commit':f['candidate_git_commit'],
   'remote_full_baseline_commit':f['baseline_candidate_git_commit'],'upstream_reference_commit':lock['baseline_commit'],
   'remote_worktree_status':f['candidate_git_status'],'local_worktree_status':git('status','--porcelain=v1','-uno'),
   'same_commit_not_claimed':'Local reference contains only exported source text; remote baseline contains the full original copy.'})
provenance={
 'stage':'TASK004C-B-NATIVE-INTEGRATION','created_asia_shanghai':now,'upstream_reference_commit':lock['baseline_commit'],
 'original_remote_source':'/root/rivermind-data/DROID_W_TASK004B_CONFIRMATORY_20261123T124144277Z/source',
 'original_source_is_git_checkout':False,'full_remote_copy_initial_sha_verified_count':3694,
 'remote_independent_baseline_commit':f['baseline_candidate_git_commit'],'remote_candidate_commit':f['candidate_git_commit'],
 'local_candidate_text_subset_commit':local_commit,'baseline_files':p['source_manifest'],
 'protected_asset_pins':lock['remote_pins'],'execution_source_pins':lock['execution_source_pins'],
 'original_source_postcheck_unchanged':f['original_source_unchanged'],'rgb_sha_verified':f['rgb_sha_matches'],
 'declared_patch_files':alg['changed_source_files'],'original_R2_YAML_modified':False}
js('TASK004C_B_NATIVE_BASELINE_MANIFEST.json',provenance)
put('TASK004C_B_NATIVE_SOURCE_PROTECTION.md',f'''# 原生接入源码保护

时间：{now}。

原始远端执行目录没有 `.git`，没有在其中初始化 Git。独立完整副本在修改前完成 **3694/3694** 路径核验，并建立冻结基线提交 `{f['baseline_candidate_git_commit']}`。最终候选提交为 `{f['candidate_git_commit']}`，工作区干净。

上游身份参考为 `{lock['baseline_commit']}`，由已有冻结身份、`.official_archive.json` 和实际执行文件锁共同追溯；没有声称原目录存在可读取的 HEAD。保留了历史 Task003/004 observer。执行文件与未经修改的官方源文件并不全部相同。

本地 Git 仅包含导出的源码文本及新增控制代码，是远端完整副本的文本参考子集。其提交 `{local_commit}` 与远端提交不同，不能互换。

| 保护项 | 实际核验 |
|---|---|
| 原执行目录全部记录 | 3694/3694 前后匹配 |
| 权重、R2 YAML、原扩展及8份执行源文件 | 14/14 SHA匹配 |
| 输入Manifest | `{f['input_manifest_sha256']}` |
| 原始RGB | 487/487 SHA与Manifest匹配；未解码或提交模型 |
| C/CUDA/头文件 | 1896份字节未改 |
| 原生扩展调用表达式 | AST完全一致 |
| Python BA数学和Corr实现 | 字节一致 |

仅在候选中修改10份Python文件，完整名单见 `evidence/ALGORITHM_PRESERVATION.json`，补丁见 `artifacts/NATIVE_CONTROL_INTERFACE.patch`。未编译扩展、未更改权重、未覆盖R2配置、未清理历史结果。父项目原有6项跟踪修改未操作；本报告不声称具有它们的任务前后SHA证据。
''')

classes={}
for file,cls in [('src/tracker.py','Tracker'),('src/motion_filter.py','MotionFilter'),('src/frontend.py','Frontend'),
                 ('src/factor_graph.py','FactorGraph'),('src/depth_video.py','DepthVideo'),('src/backend.py','Backend'),
                 ('src/trajectory_filler.py','PoseTrajectoryFiller'),('src/modules/droid_net/corr.py','CorrBlock')]:
    tree=ast.parse((ROOT/'source_before'/file).read_text(encoding='utf-8'))
    c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    fields=sorted({n.attr for n in ast.walk(c) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='self' and isinstance(n.ctx,ast.Store)})
    classes[cls]={'source':file,'static_self_assignments':fields,'capture_rule':'ALL_RUNTIME___dict___FIELDS_OR_FAIL'}
schema={'schema':'GAMECAM_NATIVE_EXPLICIT_OBJECT_STORAGE_V2','native_live_schema_instantiated':False,
 'candidate_boundary':{'rgb_id':18,'next_rgb':19,'status':'REQUIRES_LIVE_CONFIRMATION','init_D':0,'W':1,'U':1,
                     'required_successful_updates':{'frontend_init_neighborhood':8,'frontend_init_proximity':8,'frontend_init_second':8}},
 'cursor_fields':['next_input_index','prev_kf_idx','curr_kf_idx','prev_ba_idx','intrinsic'],
 'objects':classes,'full_model_state':'Parameters, persistent/nonpersistent buffers, module modes, Python tensor caches and shared object references',
 'rng':'Python, NumPy legacy state, Torch CPU/CUDA and registered explicit torch.Generator objects; saved runtime flags must match',
 'storages':['device','dtype','shape','stride','offset','requires_grad','parameter_kind','CPU shared flag','storage aliases','value and file SHA256'],
 'external_service_rebinding':['tracker pipe','event writer','printer','video counter coordination object','Rerun writer barrier','observer output file'],
 'separately_saved_service_values':['video.counter.value','printer.progress_counter.value'],
 'derived_not_live_at_C0':{'eta':'recomputed by unchanged graph.update from graph.damping and EP','effective_UBA_weight':'recomputed by unchanged native code from U and frozen switches'},
 'unsupported_state_policy':'STOP before native C0 installation; no omitted unknown fields or fabricated caches',
 'limitations':['No native live closure has run','Numpy views and opaque hooks require an explicit adapter; not silently copied',
               'No outstanding BA/CUDA work or Rerun dirty writer is permitted at the capture barrier']}
js('TASK004C_B_NATIVE_C0_SCHEMA.json',schema)
js('TASK004C_B_NATIVE_C0_MANIFEST.json',{'status':'NOT_CAPTURED_NO_CARD_STARTUP','artifact_kind':None,'c0_state_sha256':None,
  'actual_boundary_rgb':None,'actual_serialized_bytes':None,'native_process_pid':None,'substitute_CPU_fixture_used_as_C0':False,
  'reason':'User confirmed current instance is in no-card mode; GPU admission not passed.'})
put('TASK004C_B_NATIVE_CHECKPOINT_REPORT.md',f'''# 原生Checkpoint接入

结论：**CPU接口通过；真实C0未采集，原生恢复未验证。**

`native_control/snapshot.py` 使用显式JSON对象图和Tensor-only存储文件。保留Tensor别名、storage offset、stride、dtype、device、Parameter身份、CPU共享标志以及重复Python对象引用。逐文件、逐存储和逐Tensor核验SHA。恢复绕过对象构造器，不重跑模型构造或整个Tracker的pickle。保存原子安装，失败保留staging现场。

真实入口为 `native_control/binding.py::capture_c0`。要求三组各8次初始化graph.update已成功返回、第二阶段完成、Tracker帧尾、下一帧未读取，实际边界必须符合RGB018候选；不符合就停止提交协议复核。源码静态分析不能证明此次实际边界已达到。

保存前暂停Rerun写入并等待其CUDA同步应答，再持有video锁和同步Tracker CUDA。全容量Video、Tracker/MotionFilter/Frontend/Graph/Corr、先验模块、模型缓存和状态、observer、循环游标、RNG均进入对象闭合扫描。未知类型或无法保留的别名直接拒绝。eta与有效UBA权重在此边界没有活动的BA局部变量，保留其完整输入并沿原生路径重算。

Tracker帧尾存储5项活跃循环状态。`image/timestamp/starting_count/i` 的前一帧局部值在下次使用前由下一次取帧覆写；必要的持久特征由MotionFilter和Graph保存。新循环从保存的游标恢复，不把迭代器重新从0读起。

CPU测试实际验证了独立Python进程退出后恢复模拟、模型buffer/mode、绑定方法、共享storage、RNG、未知字段拒绝和构造器不执行。可检查的小型样本在 `evidence/CPU_DEMONSTRATION_handoff/`，其13个Tensor明确为CPU合成样本，**不是C0，也不是预训练模型**。

尚缺：真实模型对象闭合清点、CUDA/IPC恢复逐Tensor证据、真实Rerun跨进程屏障、原生下一帧与下一次BA收据。当前C0实际字节数和state SHA均为null。
''')

event_kinds={
 'frame.begin':'input index, RGB ID','frame.end':'next input index; native counter/RGB slot map verified',
 'motion.decision':'admitted, force, threshold, reason','keyframe.decision':'drop, reason',
 'keyframe.insert.begin/end':'stable RGB token, slot, insertion order via ordered context, counter',
 'keyframe.remove.begin/end':'stable RGB token and tail slot; unaudited non-tail compaction stops',
 'graph.create':'graph identity, implementation, capacity','graph.add.begin/end':'source/target slots with stable RGB/edge identity in context',
 'graph.remove.begin/end':'ordered edge mask, store flag and before/after context',
 'graph.filter.begin/end':'bad-edge lifecycle','graph.bad_mask':'scheduled bad-edge mask',
 'graph.init_age_reset':'initialization age reset','graph.clear.begin/end':'graph retirement',
 'graph.backend_plan':'backend edges, loop edge count and nonempty branch',
 'graph.update.begin/end':'graph ID, stage, t0/t1, iteration and phase switches',
 'graph.update_lowmem.begin/end':'backend steps and windows','native.ba.begin/end':'actual native BA invocation order, ii/jj, iteration and frozen scalar controls',
 'init.second_stage.begin/end':'second-stage lifecycle','init.complete':'24 successful initialization updates and actual boundary',
 'final.begin/end':'native final stages 7 then12','backend.dense.begin/end':'dense graph/BA controls',
 'filler.batch.begin/result/end':'batch RGB IDs, bracket anchors, temporary slots and counter restoration',
 'export':'final pose provenance: KEYFRAME_BA or TRAJECTORY_FILLER'}
js('TASK004C_B_NATIVE_EVENT_SCHEMA.json',{'schema':'GAMECAM_NATIVE_DISCRETE_SCHEDULE_V2','kind_catalog':event_kinds,
 'event_envelope':['index','kind','rgb','context','payload','previous_sha256','sha256'],
 'context':'Ordered stable RGB slot tokens; graph IDs; edge instance IDs; source/target RGB tokens, slots, active/inactive/bad state and age',
 'journal_continuous_result_fields_allowed':False,'continuous_results_location':'native_trace.jsonl and inherited observer.jsonl; never selected from a source schedule',
 'prefix_lifecycle':'Each frame019..080, nested operation pairing, immutable hash chain, footer only after complete RGB080',
 'GPU_validation_status':'NOT_EXECUTED'})
put('TASK004C_B_NATIVE_RECORDER_REPORT.md','''# Recorder原生接入

Motion Filter、关键帧管理、FactorGraph primitive、图过滤与低内存后端，以及真实DepthVideo.ba入口均已接入候选。Motion Filter的原始运动统计继续由Task003 observer记录；新journal记录可重放的接纳结果、force、阈值和理由。

事件采用begin/end分离，能表达add_factors内部再次rm_factors等嵌套调用。每次事件包含有序拓扑上下文和哈希链。RGB身份由原始0-based timestamp+1映射；同一buffer slot重用后获得新的RGB token。Filler临时槽有独立token。边具有实例ID、稳定RGB两端、age和active/inactive/bad状态。

实际BA的before/native-after/clamp-after仍由原observer记录。新增轨迹、disparity、U、target、weight和eta的SHA摘要写入独立trace。它们不进入可选调度输出。

CPU测试执行了实际FactorGraph Python方法体；CUDA decorators、CNN及扩展计算是明确的CPU mock。这证明接口位置与离散副作用的可测试行为，不证明真实CUDA优化行为。真实Recorder流尚未生成。
''')
put('TASK004C_B_FINAL_BA_FILLER_HOOK_REPORT.md','''# Final BA和Filler调用路径

保留原生流程：最终Backend临时关闭深度正则，先7步再12步dense_ba，之后恢复metric_depth_reg。没有使用F0，没有删掉任一最终阶段。CPU合成调用实际执行候选SLAM.backend方法体并验证顺序和恢复状态。

Filler保留临时槽、相邻关键帧锚点、最多16帧批次、12轮motion_only更新和counter回退。CPU合成调用执行原Filler方法体，SE3/CNN/extension计算是声明的mock。记录最终导出中直接关键帧与Filler Pose来源，避免混淆。

有限GPU driver在RGB080抛出前缀完成信号，不调用SLAM.terminate；Final BA和Filler的真实记录应由将来获批的正式实验产生。目前这两个阶段只有静态与CPU证据。
''')
put('TASK004C_B_NATIVE_REPLAY_REPORT.md','''# 跨D调度接入

S1定义为共同INIT_D=0后D=1自然记录；S0为同一C0下D=0自然记录。W/U使用原生模板；最初8次初始化原生enable_udba=False保持不变。D只在全部初始化阶段设为0，在后续frontend main-loop local BA依据分支选择。其他BA阶段保留原生开关。

Replay在Motion Filter和保留/删除决策之前选择源调度，在图primitive处强制相同增加、移除、窗口和调用次序。每个结果点验证真实有序拓扑。不能执行、不兼容的边/槽、无记录拓扑/age变化、帧或BA次序不符，均停止。当前范围只支持原Frontend使用的尾部候选删除；其他compaction会拒绝。

各分支重新计算RGB特征、Corr、net hidden updates、target、weight、damping、Pose、disparity和U。没有回放连续优化结果。CPU使用真实FactorGraph Python方法体和数值mock，已双向验证D0重放S1、D1重放S0时图事件一致而disparity不同。

这仍不是原生跨D成功证据。真实S0/S1、真实重放、真实下一次BA顺序均待GPU验证。自然关键帧选择的原始分数保留在诊断日志，源调度是明确的离散干预，不能声称所有连续输入在运行期间保持相同。
''')
js('TASK004C_B_NATIVE_SCHEDULE_VALIDATION.json',{'CPU_bidirectional_interface_test':'PASS_DECLARED_MOCK_NUMERICS',
  'actual_native_S1_generated':False,'actual_native_S0_generated':False,'actual_D0_S1_replay':False,'actual_D1_S0_replay':False,
  'actual_C0_sha256':None,'formal_crossovers_started':0,'decision':'GPU_VALIDATION_PENDING_NO_CARD'})

old_count=sum(x['test_id'].startswith('tests.test_control.') for x in cpu['tests']);new_count=cpu['total']-old_count
put('TASK004C_B_NATIVE_CPU_TEST_REPORT.md',f'''# CPU验证结果

**最终118/118通过，退出码0，CUDA未初始化。** 原有54项为{old_count}/{old_count}，新增原生接口相关测试为{new_count}/{new_count}。

原有54项测试源码保持不变，旧任务测试记录未覆盖。本任务每次修订均保存独立stdout/stderr、逐测试退出状态、耗时、种子和输出SHA。最终原始报告：`evidence/CPU_handoff/artifacts/CPU_SUITE_handoff/CPU_TEST_REPORT.json`。

| 修订 | 总数 | 通过 | 说明 |
|---|---:|---:|---|
| initial | 96 | 85 | PyTorch2.1 mmap要求字符串路径，错误已保留 |
| revision02 | 106 | 104 | 实际方法体fixture缺少observer模块绑定，已修正 |
| revision03 | 112 | 112 | 首轮完整通过 |
| revision04 | 116 | 116 | 增加RNG与槽管理核验 |
| final | 117 | 117 | 增加无构造器恢复测试 |
| release | 117 | 117 | 双向S0/S1接口复核 |
| handoff | 118 | 118 | 增加真实counter/timestamp与稳定RGB映射不符的拒绝测试 |

使用小型torch.nn合成fixture；没有构造DROID-W、Metric3D、FiT3D或DINO真实预训练模型。实际FactorGraph、Final BA、Filler的Python方法体在CPU fixture中运行，CUDA与神经前端由mock代替。新进程恢复也是合成状态，不能登记为原生C0恢复。

四份原YAML的参数检查、原Runner dry-run和启动保护均通过。正式runner的require_approved_runtime未删除。新有限runner只接受6种具名验证模式，硬限制RGB080，拒绝B1和487帧参数。
''')

put('TASK004C_B_NATIVE_GPU_SMOKE_TEST.md',f'''# 有限GPU验证状态

**NOT_EXECUTED — 用户确认当前仍为无卡启动。** 没有真实C0、没有CUDA恢复、没有模型forward、没有自然S0/S1或跨D重放，没有消耗正式B1/B2/B3/B4次数。

当前远端为 `sc01-ssh.gpuhome.cc:30414`，严格固定ED25519信任核验通过。GPU工具返回Exec format error，这与用户确认的无卡模式一起记录，不诊断为GPU硬件损坏，不修驱动、不重启或改变实例。

| 资源 | 最终实测/状态 |
|---|---|
| 数据盘可用 | {f['free_bytes_after']} bytes，{gib(f['free_bytes_after'])} GiB |
| /dev/shm可用 | {f['admission']['shared_memory']['free']} bytes，{gib(f['admission']['shared_memory']['free'])} GiB |
| 原生spawn的CPU共享存储候选 | 2,246,400,000 bytes；独立于GPU Tensor |
| 完整C0实际大小 | UNKNOWN，未创建 |
| 23份Video逻辑存储 | 7,468,230,540 bytes，尚不含Corr、所有模型及其他缓存 |
| 10GiB数据盘余量 | 后续真实每次写入前强制检查 |

上述共享存储候选有历史Task004B实测约2.09GiB占用佐证，不使用已撤回的8GiB固定门槛。不因无卡容器的2GiB而修改buffer=500。也不能把当前磁盘通过最低静态预算解释为完整C0预算通过；live闭合后必须先计算全部storage实际字节。

当前新有限runner已有软件范围及SHA保护，仍需新的有卡资源准入和真实状态闭合。只允许单份C0及恢复检查、S1/S0自然前缀、两次相反D重放；所有前缀最多RGB080，串行、无自动重试。不能执行正式四组487帧实验。
''')
js('TASK004C_B_NATIVE_RESTORE_RECEIPTS.json',{'native_C0_capture_count':0,'native_restore_process_count':0,
 'native_restore_receipts':[],'CPU_independent_process_fixture_test':'PASS','CPU_test_id':'tests.test_native.SnapshotTests.test_independent_process_exit_and_restore',
 'CPU_simulation_is_native_restore':False,'reason':'NO_CARD_STARTUP_CONFIRMED_BY_USER'})
with (ROOT/'TASK004C_B_NATIVE_CROSS_D_REPLAY.csv').open('x',encoding='utf-8-sig',newline='') as out:
    w=csv.DictWriter(out,fieldnames=['mode','producer_D','consumer_D','schedule','max_rgb','native_status','c0_sha256','CPU_interface_scope']);w.writeheader()
    for mode,d,c,s in [('natural_S1',1,1,'S1'),('natural_S0',0,0,'S0'),('replay_D0_S1',1,0,'S1'),('replay_D1_S0',0,1,'S0')]:
        w.writerow(dict(mode=mode,producer_D=d,consumer_D=c,schedule=s,max_rgb=80,native_status='NOT_EXECUTED_NO_CARD',c0_sha256='',CPU_interface_scope='PASS_WITH_DECLARED_NUMERICAL_MOCK'))

status='CPU_NATIVE_INTEGRATION_CANDIDATE_VERIFIED_GPU_VALIDATION_PENDING_NO_CARD'
js('SECURITY_AUDIT.json',{'status':status,'user_confirmed_platform_mode':'NO_CARD_STARTUP','GPU_requested':False,'GPU_started':False,
  'GPU_restarted':False,'GPU_released':False,'server_shutdown':False,'cuda_context_initialized':False,'cuda_tensor_created':False,
  'pretrained_checkpoint_deserialized':False,'real_model_constructed':False,'real_model_forward_executed':False,
  'CPU_synthetic_nn_fixture_constructed':True,'CPU_tensor_only_fixture_serialization_executed':True,
  'native_C0_captured':False,'real_RGB_submitted_to_models':0,'full_487_frame_runs':0,'formal_B1_B4_runs':0,
  'DROID_SLAM_run':False,'original_source_modified':False,'original_R2_YAML_modified':False,'original_weights_modified':False,
  'CUDA_extension_recompiled':False,'historical_results_deleted':False,'historical_results_overwritten':False,
  'SSH_trust_modified':False,'StrictHostKeyChecking_disabled':False,'dependencies_installed':False,'GitHub_push':False,
  'scope_note':'This audit covers the current native-integration task; prior completed cleanup is a separate task.'})
put('EXECUTION_LOG.md',f'''# 执行日志

交付生成时间：{now}。

1. 读取完整本次授权，恢复既有54项工具、源码参考和身份锁；没有复用历史CPU通过数字冒充本轮执行。
2. 固定SSH主机密钥只读检查当前实例，14项冻结资产匹配，导出源码文本参考；在独立远端完整副本和本地文本副本初始化Git。
3. 接入10份候选文件；保留原生C/CUDA、数学和扩展调用表达式。原始目录从未写入。
4. 完成显式对象/张量存储、循环恢复、Rerun屏障、native Recorder/Replay和限定模式driver；原正式runner保护未删除。
5. 多轮CPU验证修复PyTorch2.1路径兼容问题与测试fixture绑定；所有历史失败报告保留，最终118/118，完整收据见evidence。
6. 用户回复“当前仍是无卡启动”。没有尝试模型或CUDA，不修改实例资源。
7. 最终只读核验原始源码3694/3694、487张RGB、14项资产；候选上传58项一致，远端候选工作区干净。
8. 保留可检查CPU合成snapshot；不是C0。生成报告和评审包，并逐项检查CRC和SHA；结果写入ZIP外PACKAGE_INTEGRITY.json。

远端完整候选提交：{f['candidate_git_commit']}。本地文本候选提交：{local_commit}。没有申请或运行正式交叉实验，也没有关机。
''')
put('TASK004C_B_NATIVE_INTEGRATION_FINAL_REVIEW.md',f'''# Task004C-B 原生控制接入评审

**状态：{status}。CPU接入候选已提交，GPU三项验收均未执行；正式四组实验尚不可启动。**

用户在执行中确认当前仍为无卡启动。保留原始模型、配置与历史结果，没有启动或释放GPU，也没有改成完整487帧运行。

| 验收 | 结论 | 证据 |
|---|---|---|
| 原始资产保护 | PASS | 原源码3694/3694、RGB487/487及14项资产SHA一致 |
| 原生控制接入候选 | PASS_STATIC_AND_CPU | 10份源文件接口、显式状态恢复、离散重放 |
| CPU回归与新增测试 | **118/118 PASS** | 54项原测试+64项新增测试；退出0，CUDA未初始化 |
| CUDA/BA公式不变 | PASS_STATIC | 1896份C/CUDA/头文件、Python BA与Corr未改，原生调用AST一致 |
| 真实C0采集 | NOT_EXECUTED | actual SHA和字节数均null |
| 真实退出进程后恢复 | NOT_EXECUTED | 只有CPU独立进程fixture证据 |
| 真实S1→D0、S0→D1 | NOT_EXECUTED | 双向CPU接口测试通过，CUDA/CNN为mock |
| Final BA/Filler | PASS_STATIC_AND_CPU_ONLY | 保留7/12阶段和12次Filler motion-only；真实记录待正式授权 |
| 正式B1/B2/B3/B4 | NOT_AUTHORIZED | 0次；原启动保护保留 |

当前数据盘可用{gib(f['free_bytes_after'])}GiB。无卡容器的/dev/shm为2GiB，不调整buffer=500。完整C0大小仍未知，实际原生模型对象闭合、CUDA/IPC恢复和Rerun写屏障必须在将来有限GPU验证中逐项验收。

候选对未知运行字段、不能保留的对象/别名、未配对事件、图/age/输入/BA次序不符采用停止策略。不能把本次CPU通过解释成真实DROID-W恢复成功，更不能据此声称轨迹精度改善或直接启动487帧四组。

下一步仅为已有授权范围内的有限GPU验证：有卡实例准入后，一份C0、独立进程恢复、RGB019–080的S1/S0与相反D重放。若边界、状态闭合、存储或调度任一不符就停止；不自动延长，不自动重试。

先看本报告、GPU_SMOKE_TEST与原始CPU报告。全部新增代码、10份前后源码、完整patch、身份/保护清单和失败修订记录一并提交。ZIP外PACKAGE_INTEGRITY.json记录实际CRC/SHA核验值。
''')
put('README_请先读.md',f'''# Task004C-B 原生接入评审包

**118/118 CPU测试通过；当前用户确认无卡启动，真实GPU验证未执行。**

优先阅读：
1. TASK004C_B_NATIVE_INTEGRATION_FINAL_REVIEW.md
2. TASK004C_B_NATIVE_GPU_SMOKE_TEST.md
3. TASK004C_B_NATIVE_CHECKPOINT_REPORT.md
4. TASK004C_B_NATIVE_REPLAY_REPORT.md
5. evidence/CPU_handoff/artifacts/CPU_SUITE_handoff/CPU_TEST_REPORT.json

`TASK004C_B_NATIVE_C0_MANIFEST.json`是“未采集”状态说明。`CPU_DEMONSTRATION_handoff`中的小型fixture不是C0，不是预训练权重，没有真实视频输入。CPU接口成功不能替代原生C0、CUDA恢复或真实跨D成功。

最新保护记录：evidence/FINAL_PROTECTION_handoff.json。最新软件候选锁：evidence/CPU_NATIVE_RELEASE_handoff.json。较早记录保留供修订追溯，不能代替这些最终记录。

核验脚本：tools/verify_review.py。正式B1/B2/B3/B4未批准；完成评审后停止，不自动进入下一阶段。ZIP内部SHA清单不自我引用，ZIP外另给整体SHA和CRC检查记录。
''')
js('evidence/EVIDENCE_INDEX.json',{'latest_CPU_report':str(cpu_path.relative_to(ROOT)).replace('\\','/'),
 'latest_protection':'evidence/FINAL_PROTECTION_handoff.json','latest_candidate_lock':'evidence/CPU_NATIVE_RELEASE_handoff.json',
 'phase0_public_safe':'evidence/PHASE0_REVIEW_SAFE.json','phase0_raw_private_excluded':True,
 'native_C0_status':'NOT_CAPTURED','real_GPU_runs':0,'formal_crossovers':0})
print(json.dumps({'reports_created':True,'CPU_total':cpu['total'],'old_regressions':old_count,'new_tests':new_count,
  'remote_source_unchanged':f['original_source_unchanged'],'data_free_GiB':gib(f['free_bytes_after']),'local_git':local_commit,'remote_git':f['candidate_git_commit']}))

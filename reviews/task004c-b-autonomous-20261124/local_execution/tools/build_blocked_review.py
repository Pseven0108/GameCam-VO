import csv,hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
E=ROOT/'remote_evidence'
OUT=ROOT/'review_original';OUT.mkdir(exist_ok=False)
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def put(n,s):(OUT/n).write_text(s.strip()+'\n',encoding='utf-8')
def dump(n,d):(OUT/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state=load(ROOT/'TASK004C_B_AUTONOMOUS_RUN_STATE.json')
source=load(E/'evidence/AUTONOMOUS_SOURCE_PROVENANCE.json')
part=load(E/'cpu_tests/closure_roundtrip_r2_rng_validation/PARTIAL_REPORT.json')
forward=load(E/'cpu_tests/closure_roundtrip_r2_rng_validation/EXPECTED_FORWARD.json')
reg=load(E/'artifacts/RELEASE_CPU_AUTONOMOUS_R2/CPU_TEST_REPORT.json')
diag=load(E/'evidence/CONFIGDICT_BLOCKER_DIAGNOSTIC.json')
saved=load(E/'evidence/CPU_FAILED_SNAPSHOT_PRESERVATION.json')
final=load(ROOT/'evidence/FINAL_REMOTE_STATE.json')
assert reg['passed']==reg['total']==152 and state['status']=='BLOCKED'
assert state['budgets']['CPU_correction_rounds_used']==2 and state['budgets']['new_GPU_C0_lifecycles_used']==0
for folder in ['evidence','artifacts','cpu_tests','operational']:
 for p in (E/folder).rglob('*'):
  if p.is_file():
   q=OUT/'raw_evidence'/p.relative_to(E);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for folder in ['evidence','logs','tools','authorization']:
 for p in (ROOT/folder).rglob('*'):
  if not p.is_file() or p.suffix.lower() not in {'.json','.txt','.py','.md'}:continue
  if p.name in {'COLLECT_FINAL_PRIVATE_EVIDENCE_ONLY.stdout.txt','AUTONOMOUS_INTAKE.stdout.txt','FETCH_OWNING_SOURCES.stdout.txt','INSPECT_RUNTIME_MISC.stdout.txt'}:continue
  q=OUT/'local_execution'/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for p in (E/'source_candidate').rglob('*.py'):
 q=OUT/'candidate_source'/p.relative_to(E/'source_candidate');q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
shutil.copyfile(ROOT/'TASK004C_B_AUTONOMOUS_RUN_STATE.json',OUT/'TASK004C_B_AUTONOMOUS_RUN_STATE.json')
shutil.copyfile(ROOT/'TASK004C_B_AUTONOMOUS_EXECUTION_LOG.md',OUT/'TASK004C_B_AUTONOMOUS_EXECUTION_LOG.md')
with (OUT/'TASK004C_B_AUTONOMOUS_EXECUTION_LOG.md').open('a',encoding='utf-8') as f:
 f.write('''
## 实际执行与失败记录

1. 独立工作区从02f8c83建立；未更改原始R2或旧部署。
2. 最初CPU启动器导入GUI路径失败，尚未构造模型；改用原有模型工厂直接加载缓存。Windows命令长度和路径分隔符传输问题保留原日志，错误写入的新临时参考文件转入本任务operational/transport_preimages，未覆盖原始文件。
3. 真权重原对象审计：71个identity函数，8 Linear、1 ConvTranspose2d、62 Conv2d；FiT3D和DroidNet可遍历。
4. CPU修正轮1：仅Linear专用识别。全模型测试发现其余63个同源函数。完整诊断遍历实际CPU构造的Tracker/Video/Graph/Observer等及47族；这是诊断，不是原生C0证明。8×8相关体CPU夹具尺寸过小，改为16×16后完成诊断，未修改生产算法或断言。
5. CPU修正轮2：三种精确类白名单与无损完整存储压缩。152项历史回归再次全部通过。
6. 原安装xformers没有该CPU attention算子。CPU测试通过原安装源码的ImportError备用路径执行原有Attention.forward；GPU路径未改。CPU夹具按原公式预置depth_expectation_anchor，避免上游get_bins硬编码CUDA。原模型前向/梯度运行完成。测试自身最初把含Tensor的RNG对象交给JSON摘要，修正为逐字节RNG指纹后重新执行；这不是第三轮Checkpoint修正，生产序列化器自轮2后没有变化。
7. 模型快照已写入RAM盘；新Python进程退出1：ConfigDict不能用object.__new__构造。进一步只读核验发现其字典条目也没有被当前__dict__编码保存。未执行第三轮Checkpoint修正，未启动GPU。
8. CPU快照全部800个文件复制到本任务私有数据盘并逐一SHA匹配。仅回收两次诊断各自已退出且无映射的临时Arena共4个文件；旧失败Arena两文件完整保留。
9. 候选源码固定提交a324b577；本次GPU C0 0/2、真实恢复0、短程0/4、正式0/4。服务器和3090保持在线，不关机、不重启。
''')
put('README_请先读.md','''
# Task004C-B 自动连续执行 · 阻断评审

先读 TASK004C_B_AUTONOMOUS_FINAL_REVIEW.md，再读闭包修复报告和跨进程恢复日志。

**本轮停在CPU真实模型恢复门槛。新GPU采集0次，正式四组0次。**

152/152历史回归通过，不能代表实际Metric3D完整恢复通过。CPU模型快照是失败取证夹具，不是C0；其COMPLETE.json只证明文件封存，不证明状态语义完整。

报告、源码补丁、测试与执行日志可直接读；模型权重、RGB、Arena和CPU快照二进制不进入公开包。原始二进制在本任务私有数据盘保存。
''')
put('TASK004C_B_CLOSURE_FIX_REPORT.md',f'''
# Checkpoint闭包修复结果

最终状态：BLOCKED_CPU_RESTORE_CONFIGDICT。两轮修正已用尽，没有第三轮修改。

起点02f8c8308274489ff7eff83fa9b87b98db74122e；候选提交{source['source_commit']}；树{source['source_tree']}。
只有native_control/metric3d_identity.py和native_control/snapshot.py改变。BA公式、CUDA扩展、安装Metric3D前向源码、权重和原R2没有改变。

## 已完成

真实安装Metric3D权重加载到CPU；71个lora_dropout均来自源码SHA24b832c6e831d25a101ebb8c02b1b3df4b5d5474530481078d6df56c7ff93951，函数字节码7c005300，唯一位置参数、无defaults/kwdefaults/closure/freevars。
8个LoRALinear、1个ConvTranspose2dLoRA、62个Conv2dLoRA均检查严格同对象返回、输入无修改、CPU RNG不变、输入梯度为预期值。

专用标记metric3d_lora_identity_callable_v1，绑定三个实际类中的具体owner、属性、源码SHA、函数签名和字节码SHA。恢复对象由顶层受控callable构建，并经过memo。未知lambda、有闭包函数和不支持对象的拒绝测试3/3通过。

第二轮还采用gzip level1流式无损封装完整torch存储档案，格式V3。没有降低dtype、忽略未使用尾部、删去字段或修改优化计算。历史152项CPU用例在最终代码上全部通过；这是通用夹具证据。

## 尚未解决

真实加权模型的遍历产生17,447个节点，71个专用callable节点、{part['model_storage_bytes']:,}唯一存储bytes。**遍历接受不等于完整状态闭包成功。**

新进程恢复失败于mmcv.utils.config:ConfigDict。其MRO经过addict.Dict到dict；object.__new__不安全。更严重的是，现编码器只对精确dict类型保存items，对ConfigDict保存vars，实测vars只有__parent/__key/__frozen，不能表示alpha/nested等字典条目。
实际模型夹具的ConfigDict节点仅保存了这三个私有属性。因此只改构造器也不够，必须分别证明映射内容、类型、插入顺序、缺省/冻结语义、别名、循环引用和新进程还原。

本轮未实现上述新适配器。不能宣布真实模型恢复、网络Buffer/RNG/alias一致，也不能启动GPU来替代未通过的CPU门槛。
''')
put('TASK004C_B_CHECKPOINT_CPU_ROUNDTRIP.md',f'''
# 真实CPU模型跨进程验证

结果：FAIL，父进程与子进程退出码均为1。子进程确为新Python进程；在模型前向比较前，恢复ConfigDict失败。

已执行原模型：Metric3D深度/置信度/法线；FiT3D中间特征；DroidNet fnet/cnet；真实加权LoRALinear输出与输入梯度；71个identity语义检查。固定输入linspace(-1,1)，shape1×3×112×112，float32CPU。输出有限、CPU RNG未改变，SHA见EXPECTED_FORWARD.json。

CPU范围限制：使用真实权重和原有方法；CPU进程在导入时令可选xformers不可用，从而选择安装源码自带Attention.forward备用路径；原get_bins硬编码CUDA，夹具按同一公式在CPU预置非持久depth_expectation_anchor。没有改安装模型源码或GPU运行配置。这不是GPU内核数值等价验证，也不是640×360真实SLAM。

CPU封存夹具：{saved['bytes']:,}bytes，800文件，包括Tensor档案{part['CPU_snapshot_bytes']:,}bytes与元数据。独立数据盘副本800/800 SHA匹配。未将此夹具叫作C0。

未完成：恢复模型输出对比、恢复后梯度对比、完整运行对象alias/RNG还原证明。预期容差原定为逐输出SHA完全相同；没有因失败而放宽容差。

真实CPU构造的Video仍为buffer500、360×640，诊断加入合成recurrent/cache值并枚举47族。它不是GPU初始化状态；相关体夹具16×16不代表真实45×80相关体。不得把这项诊断写成47族真实C0恢复通过。
''')
put('TASK004C_B_CPU_REGRESSION.md',f'''
# CPU回归

最终候选：152/152 PASS；118历史用例+34既有Release Fix用例；failures0、errors0；{reg['seconds']:.3f}秒；CUDA未初始化。

原测试与断言未修改。每项输入、seed43、预期、实际、stdout、stderr、退出码和SHA见raw_evidence/artifacts/RELEASE_CPU_AUTONOMOUS_R2/CPU_TEST_REPORT.json。

第一轮候选也为152/152；第二轮后再次完整运行。两次通过不计为304个独立新科学实验。

这些测试不构造预训练模型，因此不能用它们覆盖真实模型恢复的ConfigDict失败。真实模型CPU测试单独记录为FAIL。
''')
put('TASK004C_B_C0_STORAGE_BUDGET.md',f'''
# 存储核算与边界

初始本轮数据盘可用23,718,236,160bytes；不是历史22.2907GiB的直接沿用。无模型资产检查时/tmpfs容量24GiB、容器RAM上限100GiB、3090空闲24,125MiB。

CPU实际构造与合成缓存图唯一Tensor存储9,237,036,956bytes；其中buffer500逻辑Video约7.468GB，真实三个加权模型约1.752GB。该数不含真实初始化相关体和GPU动态缓存，不能冒充完整C0预算。

无损压缩的真实CPU模型封存文件共{saved['bytes']:,}bytes，已在数据盘保存。原两块失败Arena2,246,400,000bytes永久保留。仅回收本轮已退出且无活动map/FD的诊断Arena，每次两文件；清理前后身份/SHA见收据。

最终实测数据盘可用{final['disk']['free']:,}bytes，约{final['disk']['free']/1024**3:.4f}GiB，超过10GiB底线。

完整真实C0文件字节、真实47族去重后总量、恢复工作空间和正式每臂存储均UNKNOWN，因为CPU门槛未通过，没有进行GPU初始化。本轮没有用CPU模型快照尺寸代替C0或签发空间准入。
后续仍须由prepare_state精确计数、每文件保存前check_budget、独立工作Arena、固定10GiB余量控制。实际压缩率不能用模型快照外推到完整C0。
''')
put('TASK004C_B_GPU_C0_FINAL_REPORT.md','''
# 新GPU C0阶段

NOT_EXECUTED_DEPENDENCY_BLOCKED。新GPU采集0/2；历史两次失败独立保留且不计入新预算。

没有新的RGB001～018初始化、24次BA、C0文件或真实C0大小。已有历史18帧/24次BA证据没有冒充本轮运行。
预备的autonomous_capture_entry.py未执行，不能把其源码当成实测D/W/U、47族或网络Buffer记录。

GPU保持在线，没有关机、重启、释放、驱动修复或环境重部署。硬件查询仅为只读检查。
''')
put('TASK004C_B_RESTORE_FINAL_REPORT.md','''
# 真实C0恢复

NOT_EXECUTED。没有真实C0，未启动GPU restore生命周期，未处理RGB019。

本轮只有CPU真实模型夹具的新进程restore尝试，失败于ConfigDict；这与恢复原生C0是不同证据层次。没有生成成功Restore Receipt。
''')
dump('TASK004C_B_RESTORE_RECEIPTS.json',{'native_C0_restore_runs':0,'native_C0_restore_receipts':[],'CPU_weighted_model_restore_status':'FAIL_CONFIGDICT','CPU_child_exit_code':1,'RGB019_processed_after_restore':False})
dump('TASK004C_B_C0_MANIFEST.json',{'artifact_kind':'NATIVE_C0_NOT_CREATED','complete':False,'status':'BLOCKED_BEFORE_GPU','C0_file_exists':False,'actual_C0_bytes':None,'47_native_families_persisted':False,'GPU_capture_lifecycles_this_task':0})
put('TASK004C_B_CROSS_D_REPLAY_REPORT.md','''
# S0/S1和跨D重放

NOT_EXECUTED_DEPENDENCY_BLOCKED。S0、S1事件流不存在；短程四臂0/4；没有跨D可执行性或同调度因果效应证据。
''')
(OUT/'TASK004C_B_S0_S1_SCHEDULES').mkdir()
(OUT/'TASK004C_B_S0_S1_SCHEDULES/NOT_EXECUTED.md').write_text('S0/S1未生成；CPU恢复门槛失败。\n',encoding='utf-8')
put('TASK004C_B_FORMAL_B1_B2_B3_B4_REPORT.md','''
# 正式四组实验

0/4，未启动。B1(D1,S1)、B2(D0,S1)、B4(D0,S0)、B3(D1,S0)均无新轨迹。

没有Final BA、Filler或统一离线GT评价；本轮没有读取GT。四臂指标CSV仅表头，表示没有观测，不表示误差为0。
''')
for name,headers in {
 'TASK004C_B_METRICS.csv':['arm','status','metric','value','unit','alignment'],
 'TASK004C_B_TRAJECTORY_COMPARISON.csv':['comparison','stage','metric','difference','evidence'],
 'TASK004C_B_FINAL_BA_COMPARISON.csv':['arm','before_stage','after_stage','metric','value'],
 'TASK004C_B_RESOURCE_TIMELINE.csv':['record','gpu_name','gpu_memory_used_MiB','gpu_memory_free_MiB','data_disk_free_bytes','scope']}.items():
 with (OUT/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.writer(f);w.writerow(headers)
  if 'RESOURCE' in name:w.writerow(['final_preservation','RTX 3090',0,24125,final['disk']['free'],'READ_ONLY_NO_MODEL_GPU_RUN'])
obj={'status':'INCOMPLETE_SEMANTIC_CLOSURE','real_installed_model_audit':load(ROOT/'evidence/CPU_REAL_MODEL_OBJECT_AUDIT_R0.json'),'accepted_encoding_node_count':17447,'registered_identity_nodes':71,'new_unsupported_stateful_container':diag,'actual_native_C0_verified':False,'reason':'generic object traversal can omit dict-subclass entries; cross-process restore failed'}
dump('TASK004C_B_OBJECT_GRAPH_AUDIT.json',obj)
dump('SECURITY_AUDIT.json',{'GPU_requested_by_agent':False,'GPU_restarted':False,'GPU_shut_down':False,'CUDA_context_initialized_this_task':False,'CUDA_tensor_created_this_task':False,'GPU_model_forward_executed':False,'CPU_model_forward_executed':True,'CPU_checkpoint_deserialized':True,'CPU_model_initialization_explicitly_authorized':True,'real_SLAM_executed':False,'native_BA_executed_this_task':False,'training_executed':False,'GT_used':False,'original_R2_modified':False,'weights_modified':False,'installed_Metric3D_source_modified':False,'BA_math_modified':False,'CUDA_extension_rebuilt':False,'historical_data_deleted':False,'historical_failed_Arenas_preserved':True,'new_task_CPU_diagnostic_Arena_files_reclaimed':4,'CPU_correction_rounds_used':2,'new_GPU_C0_lifecycles_used':0,'instance_kept_online':True,'credential_or_RGB_or_weight_payloads_in_public_review':False})
put('TASK004C_B_AUTONOMOUS_FINAL_REVIEW.md',f'''
# Task004C-B 自动连续任务最终评审 · 2026-11-24

**结论：BLOCKED，在CPU跨进程恢复门槛停止。新的GPU C0采集0/2，短程0/4，正式四组0/4。3090保持在线。**

| 阶段 | 实际结果 |
|---|---|
| A：闭包修复与CPU等价 | 两轮修正用尽；152/152回归通过；真实加权模型新进程恢复FAIL_CONFIGDICT |
| B：完整预算 | 实时资源和模型存储已审计；真实C0预算UNKNOWN |
| C：新GPU C0 | 未启动 |
| D：真实恢复并处理019 | 未启动 |
| E：四臂RGB080 | 未启动 |
| F：四臂完整487 | 未启动 |
| G：统一GT评价 | 未执行，未读GT |

## 本轮真正建立的证据

- 71个同源identity函数已逐个验证无闭包、严格identity、输入无修改、不消耗CPU RNG、梯度行为正确，三种具体owner类已白名单化，未知函数仍被拒绝。
- 原始真实权重的Metric3D、FiT3D、DroidNet在CPU夹具上完成固定输入前向；加权LoRALinear完成输入梯度计算。CPU测试用了上游原有无xformers备用分支和CPU常量buffer，不等于GPU前向等价。
- 最终候选152/152既有回归通过；真实模型快照800个文件、{saved['bytes']:,}bytes，已复制到本任务私有数据盘，800/800 SHA匹配。
- 新Python进程restore退出1。首个失败是`object.__new__(ConfigDict)`；只读复核进一步确认当前编码没有保存该dict子类的映射条目。

## 为什么必须停止

ConfigDict不是无状态函数。通用`__dict__`保存不能代表它的实际字典内容。仅把构造器改成dict.__new__会掩盖状态缺失；不能宣布完整闭包。
用户给定CPU闭包修正上限两轮已用尽。本轮没有第三轮修复，没有用GPU绕过CPU失败，也没有要求阶段之间重新审批。停止源自明确的技术门槛和修正预算。

## 最小下一步

需要额外的、单独明确的CPU闭包修正额度：为实际源码固定的ConfigDict建立映射/属性联合编码与构造适配；测试key-value、嵌套类型、顺序、冻结/缺省行为、循环与alias，并重新执行真实加权模型新进程等价测试和152回归。不得只改object.__new__。
既有后续GPU授权仍受CPU门槛约束；不是需要重新租GPU或重跑DROID-SLAM。未解决前不消耗两次新C0预算。

## 资产与源码

候选提交 `{source['source_commit']}`，父提交`02f8c8308274489ff7eff83fa9b87b98db74122e`；仅2个Checkpoint相关源码文件改变，完整diff随包。GitHub评审提交与运行候选提交分开记录。
BA数学、CUDA扩展、安装模型前向、四份权重、R2、VIPER和历史结果均未改。旧失败Arena保留。当前数据盘可用约{final['disk']['free']/1024**3:.4f}GiB；GPU查询0MiB占用、24125MiB空闲；没有关机/重启。

原始日志和失败记录均保留。公开包对私有连接信息脱敏，并有原始SHA→公开SHA映射；Tensor权重、RGB、Arena和CPU快照二进制不上传。

**本轮没有新的轨迹指标、消融效果或性能提升结论。**
''')
shutil.copyfile(OUT/'TASK004C_B_AUTONOMOUS_FINAL_REVIEW.md',OUT/'FINAL_REVIEW.md')
manifest=[]
for p in sorted(OUT.rglob('*')):
 if p.is_file():manifest.append({'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
dump('FILE_SHA256_MANIFEST.json',{'scope':'PRIVATE_ORIGINAL_REVIEW_FILES','self_excluded':'FILE_SHA256_MANIFEST.json','files':manifest})
print(json.dumps({'review':str(OUT),'files':len(manifest),'status':state['status'],'GPU_C0_runs':0},ensure_ascii=False))

"""Launch Audit orchestration: CPU/source/byte checks and dummy IPC only. No model execution."""
import datetime,hashlib,json,os,pathlib,shutil,subprocess,sys,time,traceback
from launch_contract import AUDIT,ROOT,PREFLIGHT,REFERENCE,FUTURE_ROOT,sha,load,frozen_artifacts
from protected_snapshot import capture
from linux_safety import atomic_json,EXPECTED_UUID
OUT=AUDIT;status='INSUFFICIENT_EVIDENCE';phase='START';errors=[];before=None;started=datetime.datetime.now(datetime.timezone.utc).isoformat()
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MPLBACKEND='Agg',QT_QPA_PLATFORM='offscreen',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
def save(name,obj):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def text(name,value):
    with (OUT/name).open('x',encoding='utf-8') as f:f.write(value)
def progress(value):
    global phase
    phase=value;r={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':value,'model_execution_authorized':False,'model_attempt_limit':0,'model_attempts':0};atomic_json(OUT/'audit_status.json',r);print(json.dumps(r),flush=True)
def protected():
    data=capture();pin=load(OUT/'scripts/preflight_manifest_pin.json');manifest=pathlib.Path(pin['remote_path'])
    if sha(manifest)!=pin['sha256']:raise RuntimeError('Previous GPU preflight manifest drift')
    rows=load(manifest)['files'];extra=[]
    for row in rows:
        p=PREFLIGHT/row['path'];h=sha(p)
        if h!=row['sha256'] or p.stat().st_size!=row['bytes']:raise RuntimeError('Previous GPU preflight evidence drift: '+row['path'])
        extra.append({'path':str(p),'group':'accepted_GPU_preflight','bytes':p.stat().st_size,'sha256':h,'real_path':str(p.resolve())})
    extra.append({'path':str(manifest),'group':'accepted_GPU_preflight_manifest','bytes':manifest.stat().st_size,'sha256':sha(manifest),'real_path':str(manifest.resolve())})
    data['files'].extend(extra);data['files_checked']=len(data['files']);data['accepted_GPU_preflight_files_checked']=len(extra)
    return data

def call(script,prefix,args=(),timeout=120):
    with (OUT/(prefix+'.stdout.txt')).open('x') as out,(OUT/(prefix+'.stderr.txt')).open('x') as err:
        command=[sys.executable,'-B',str(OUT/'scripts'/script),*map(str,args)]
        p=subprocess.run(command,env=os.environ.copy(),stdout=out,stderr=err,timeout=timeout)
    save(prefix+'.process.json',{'command':command,'exit_code':p.returncode,'CUDA_VISIBLE_DEVICES':'','model_attempts':0});return p.returncode

def gt_report():
    r=load(OUT/'02_GT_isolation_verification.json')
    if not r['passed']:raise RuntimeError('GT isolation proof failed')
    text('01_GT_dataflow_audit.md','''# GT数据流审计

范围仅为已冻结配置SHA `70b2527e0293d695c77cdbca1ee4045d75b6483ff262fadd6b0da3749b68cfe9`、dataset=youtube、debug=false、Mapping=false，以及独立受控原生Tracker启动器。不能把以下结论推广到所有dataset或任意run.py配置。

## 八项明确回答

1. **定义位置**：configs/droid_w.yaml第8行定义save_gt_poses=True，K5.1及GPU_09均沿用。GPU_09未修改。
2. **谁读取它**：datasets.py中TUM_RGBD和Dycheck构造函数分别在约336、509行读取该字段并保存GT。RGB_NoPose没有读取此字段。源码AST和实际CPU构造均验证这一点。
3. **是否读取GT文件**：run.py调用get_dataset，dataset_dict将youtube映射为RGB_NoPose，RGB_NoPose构造只枚举RGB文件，明确设depth_paths=None、poses=None。BaseDataset.__getitem__只有在poses非None时才转换pose；本分支返回pose=None。其他dataset确有load_poses，不能把save_gt_poses=False理解为对所有dataset都能阻止GT加载。
4. **是否传给Tracker/Frontend**：受控适配器在构造模型前断言stream.poses is None且depth_paths is None；每帧Stream断言pose is None。Tracker.run解包为timestamp,image,_,_，只把image与intrinsic交给MotionFilter，再把由图像推理得到的video状态交给Frontend。
5. **关键帧选择**：MotionFilter.track依赖预测flow delta、固定阈值3.0以及原有force_keyframe_every_n_frames规则；不使用GT。全部参数保持原样。
6. **BA**：Frontend、FactorGraph、DepthVideo.ba使用video中的估计位姿、视差、相关特征、网络权重和图像生成的单目先验，没有从stream.poses读取GT的链路。
7. **深度、特征、初始化**：mono_priors的深度和特征预测入口接收RGB、模型权重、时间索引及cfg；初始SE3.Identity及后续位姿来自网络和video状态。官方深度、Skeleton、NPC/State均不在输入通路。
8. **是否仅在结束后用于评价/保存**：本分支连GT保存也不执行，save_gt_poses=true在所选loader中无效。Tracker内GT评价受debug条件包围，而冻结debug=false；受控启动器只调用Tracker.run，不调用SLAM.run/terminate、最终BA、filler或原生评价。将来的官方GT评价必须在所有模型进程退出后以独立CPU程序进行，本轮未运行任何GT评价。

## 数据流图

```mermaid
flowchart TD
  C[冻结GPU_09配置: youtube, debug=false, Mapping=false] --> D[get_dataset / dataset_dict]
  D --> L[RGB_NoPose: poses=None, depth_paths=None]
  R[K4 RGB 120帧: 7953..8072] --> L
  K[K_input 512x288] --> L
  L --> S[审计Stream: pose必须为None]
  S --> T[原生Tracker.run: timestamp,image,_,_]
  T --> M[原生MotionFilter: RGB与内参]
  W[四份冻结模型权重] --> M
  M --> P[图像生成的深度/特征先验与video估计状态]
  P --> F[原生Frontend / BA]
  F --> O[原生估计关键帧位姿与帧索引]
  O --> X[全部模型与监控进程退出]
  X --> E[未来独立CPU评价程序]
  G[官方GT: 仅未来评价阶段可读] --> E
  U[其他dataset的GT加载/保存分支] -. 本配置不进入 .-> D
```

## 本轮实际验证与限制

真实导入冻结src.utils.datasets，在CPU上分别以save_gt_poses=true和false构造实际RGB_NoPose。仅在隔离fixture中替换glob文件名列表和get_color图像解码为合成CPU Tensor，实际分发、构造及BaseDataset.__getitem__保持原实现；两组均返回pose=None、depth_paths=None，长度120，无GT保存调用，CUDA未初始化。这个测试没有解码真实WildWorld图像，也没有运行Tracker。

附加IO边界的七项路径决策测试覆盖RGB放行、GT/Skeleton/NPC拒绝、历史GT评价文件拒绝、GT写入拒绝和本次输出目录中的新生成先验放行。未来原生子进程还会装入既有四权重loader校验和离线策略。Python审计钩子是调用链之外的补充保护，不是OS沙箱。

原生run.py是背景调用链审计对象；实际候选命令使用继承K6-A-GPU-R1的有界Tracker适配器，以避免run.py/SLAM.terminate触发额外最终BA、filler或进程内评价。适配器仅替换Linux安全Guard及会话IPC路径，Baseline核心没有更改。源码摘录、SHA、CPU测试与字段路径见02_GT_isolation_verification.json。

本轮结论：所选路径GT隔离可证明，不需要生成save_gt_poses=false候选配置。两个冻结SHA保持不变。所有实际模型路径仍待明确授权后首次运行。
''')

def architecture():
    text('06_linux_runner_architecture.md','''# Linux单次Runner架构与已验证范围

唯一候选命令为 `launch_single.py --execute --authorization <后续用户授权文件>`。当前只有 `--dry-run` 被执行；直接execute无授权和直接native_child无授权都拒绝，发生在模型导入、正式Attempt创建和输出目录创建之前。

生产流程：父Supervisor核对冻结配置、120帧字节SHA、四份权重SHA、代码SHA及精确目标；外部授权必须绑定本候选契约SHA，明确DROID-W/V56_01_middle/120帧/最多1次/不重试。随后只允许独占创建一个模型阶段及单次Ledger；启动独立NVML监控进程，取得至少间隔0.25秒的两个递增样本，再启动独立原生子进程组。子进程的CUDA心跳提供两个递增样本后，父进程才发出模型初始化许可。独立子进程还会再次验证授权与Ledger，装入原四权重loader pins和GT数据边界。

当前阶段candidate明确model_execution_authorized=false、model_attempt_limit=0、model_attempts=0。future_target中的maximum_authorizable_attempts=1仅描述待审批范围，不构成授权。没有生成授权文件。Dry Run的独占写入只使用CPU fixture的single_use_marker，不是正式模型Attempt。

真实模型适配器继承已审计的原生Tracker运行体，不执行SLAM.run/terminate，Mapping=false；仅Linux安全Guard和IPC目录发生外层适配。原生Tracker、MotionFilter、Frontend、DepthVideo/BA、先验模块及模型参数均不修改。原始/适配后的外层差异见native_adapter_control_only.diff。

安全语义：CUDA/NVML Free<512 MiB停止，等于512允许；CUDA查询后等待0.2秒，外部NVML查询后等待0.25秒，Supervisor轮询0.2秒；数据年龄>3秒或未来时间>1秒停止。会话号、序号和时间回退检查保持；监控退出、查询错误、CPU MemAvailable<768 MiB、有限cgroup剩余<768 MiB、数据盘剩余<总容量20%均停止。绑定GPU UUID，记录温度、利用率、GPU进程、CPU RAM、cgroup、磁盘、Torch Allocated/Reserved/Peak、时间戳与心跳。模型子进程还检查父进程PID与监督心跳；额外GPU计算进程拒绝。

30帧保护恢复为原始精确表达式：最近30个已完成原始帧的Allocated，`last-first>512 MiB`且所有相邻值`b>a`才停止。等于512、存在一次相等或下降、仅29个样本均不触发增长规则；采样是每个原始帧完成边界，不能用异步心跳次数或关键帧数替代。子进程本地Guard和父Supervisor消费的有序frame_samples共用GrowthGuard。

异常只终止本次拥有的进程组；先SIGTERM，等待5秒，只有仍未退出才SIGKILL并确认退出码，无自动重试。任何阶段都不使用Windows DXGI作为Linux进程显存。无法抢占正在执行的CUDA kernel。

本轮13组集成测试使用同一个生产supervise_once、独立CPU dummy worker与独立CPU Mock NVML进程，实际经过文件IPC、启动屏障、心跳、帧事件、信号和进程退出。真实CUDA查询接口已在上一阶段验证，本轮Mock测试不能冒称实际DROID-W的内存行为或故障停止已验证。Linux原生Guard与模型适配器本轮只做源码/语法/接线检查，没有构造DROID-W模型。未来首次模型运行仍可能暴露推理、BA或资源问题。
''')

try:
    if (OUT/'audit_status.json').exists():raise RuntimeError('Existing execution record; do not replay or overwrite evidence')
    assert OUT==ROOT.parent/'setup/K6-A-GPU-R2-LAUNCH-AUDIT'
    assert pathlib.Path(sys.prefix).resolve()==pathlib.Path('/opt/gamecam/envs/droidw-cu126')
    progress('PROTECTION_BEFORE');before=protected();save('protection_before.json',before)
    if not before['passed']:raise RuntimeError('Historical protection contract failed')
    q=subprocess.run(['nvidia-smi','--query-gpu=uuid,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
    processes=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader'],capture_output=True,text=True,timeout=5)
    save('readonly_GPU_identity.json',{'GPU_query_stdout':q.stdout,'GPU_query_stderr':q.stderr,'process_query_stdout':processes.stdout,'process_query_stderr':processes.stderr,'GPU_query_exit':q.returncode,'process_query_exit':processes.returncode,'CUDA_context_created':False,'passed':q.returncode==processes.returncode==0 and q.stdout.strip()==EXPECTED_UUID+', 22528' and not processes.stdout.strip()})
    if not load(OUT/'readonly_GPU_identity.json')['passed']:raise RuntimeError('Read-only GPU identity/process check failed')
    progress('FROZEN_INPUT_WEIGHT_AND_CONFIG_BYTE_CHECKS');status='BLOCKED_BY_INPUT_INTEGRITY'
    a=frozen_artifacts();save('03_input_120frame_integrity.json',a['input']);save('04_checkpoint_integrity.json',a['weights']);save('05_runtime_config_verification.json',a['config'])
    progress('GT_SOURCE_AND_ACTUAL_CPU_LOADER_TESTS');status='BLOCKED_BY_GT_ISOLATION'
    if call('audit_gt_dataflow.py','gt_audit')!=0:raise RuntimeError('Actual CPU GT isolation audit failed')
    gt_report()
    progress('PRODUCTION_SUPERVISOR_CPU_IPC_TESTS');status='BLOCKED_BY_SUPERVISOR'
    if call('test_runner_integration.py','runner_integration',[OUT],timeout=120)!=0:raise RuntimeError('Production supervisor integration failed')
    if not load(OUT/'08_memory_growth_guard_tests.json')['passed']:status='BLOCKED_BY_MEMORY_GROWTH_GUARD';raise RuntimeError('Historical growth rule tests failed')
    architecture()
    progress('FREEZING_LAUNCH_CANDIDATE_WITHOUT_AUTHORIZATION');status='BLOCKED_BY_RUNNER_INTEGRATION'
    runtime=[{'path':p.relative_to(OUT).as_posix(),'sha256':sha(p)} for p in sorted((OUT/'scripts').glob('*.py'))]
    reports=['readonly_GPU_identity.json','02_GT_isolation_verification.json','03_input_120frame_integrity.json','04_checkpoint_integrity.json','05_runtime_config_verification.json','07_supervisor_integration_tests.json','08_memory_growth_guard_tests.json']
    candidate={'version':'K6-A-GPU-R2-LAUNCH-AUDIT-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_execution_authorized':False,'model_attempt_limit':0,'model_attempts':0,'future_target':{'method':'droidw','case':'V56_01_middle','start_published_frame':7953,'max_frames':120,'stride':1,'mapping':False,'buffer':350,'warmup':12,'motion_filter':3.0,'maximum_authorizable_attempts':1,'automatic_retry':False},'python':'/opt/gamecam/envs/droidw-cu126/bin/python','GPU_UUID':EXPECTED_UUID,'original_config_SHA256':a['config']['original_sha256'],'prepared_config_SHA256':a['config']['prepared_sha256'],'input_published_end':8072,'future_output':a['config']['future_output'],'input_realpath':a['input']['input_realpath'],'frozen_runtime_files':runtime,'passed_report_pins':{n:sha(OUT/n) for n in reports},'authorization_required':{'model_execution_authorized':True,'model_attempt_limit':1,'authorized_launch_contract_sha256':'must_equal_actual_SHA256_of_this_file','method':'droidw','case':'V56_01_middle','max_frames':120,'automatic_retry':False},'authorization_file_generated':False,'formal_attempt_generated':False,'CPU_evaluation_only_after_all_model_processes_exit':True,'full_GPU_model_path_tested':False}
    save('10_launch_contract_candidate.json',candidate)
    # Exercise both command gates with NO authorization. Never create an approval record.
    gate=[]
    for name,script,args in [('supervisor_no_auth','launch_single.py',['--execute']),('child_no_auth','native_child.py',[])]:
        rc=call(script,name,args);row=load(OUT/(name+'.process.json'));lines=(OUT/(name+'.stdout.txt')).read_text().splitlines();reply=json.loads(lines[-1]);ok=rc==3 and reply['model_attempts']==0 and reply['torch_imported'] is False and not FUTURE_ROOT.exists();gate.append({'command':row['command'],'exit_code':rc,'reply':reply,'passed':ok})
    save('unauthorized_entry_gate_tests.json',{'tests':gate,'passed':all(x['passed'] for x in gate),'model_attempts':0})
    if not all(x['passed'] for x in gate):raise RuntimeError('Unauthorized model gate failed')
    progress('SINGLE_DROIDW_COMMAND_DRY_RUN');status='BLOCKED_BY_DRY_RUN'
    if call('launch_single.py','droidw_dry_run',['--dry-run','--out-json',OUT/'09_droidw_dry_run.json'])!=0:raise RuntimeError('DROID-W command dry run failed')
    assert load(OUT/'09_droidw_dry_run.json')['passed']
    assert not FUTURE_ROOT.exists()
    status='DROIDW_120_LAUNCH_READY_WAITING_FOR_USER_AUTHORIZATION'
except BaseException as exc:
    errors.append({'phase':phase,'error':str(exc),'traceback':traceback.format_exc()});print(json.dumps({'error':str(exc),'status':status}),flush=True)
finally:
    progress('PROTECTION_AFTER')
    try:
        after=protected();save('protection_after.json',after)
        old={x['path']:(x['bytes'],x['sha256'],x['real_path']) for x in before['files']} if before else {};new={x['path']:(x['bytes'],x['sha256'],x['real_path']) for x in after['files']}
        changed=[p for p in sorted(set(old)|set(new)) if old.get(p)!=new.get(p)]
        protect={'before_files':len(old),'after_files':len(new),'changed_added_or_missing_paths':changed,'approved_source_weight_extension_contracts_still_match':after['passed'],'previous_GPU_preflight_files_checked':after['accepted_GPU_preflight_files_checked'],'frozen_CPU_pointer_preserved':bool(before) and before['latest_CPU_pointer']==after['latest_CPU_pointer'],'formal_model_stage_created':FUTURE_ROOT.exists(),'model_execution_authorized':False,'model_attempt_limit':0,'model_attempts':0,'checkpoint_deserialized':False,'real_images_decoded':False,'GT_values_read':False,'raw_byte_hashing_of_historical_archives_only':True,'passed':bool(before) and before['passed'] and after['passed'] and not changed and not FUTURE_ROOT.exists()}
        save('12_protection_verification.json',protect)
        if not protect['passed']:status='INSUFFICIENT_EVIDENCE'
    except BaseException as exc:
        errors.append({'protection_error':str(exc),'traceback':traceback.format_exc()});status='INSUFFICIENT_EVIDENCE';save('12_protection_verification.json',{'passed':False,'error':str(exc),'model_attempts':0})
    finished=datetime.datetime.now(datetime.timezone.utc).isoformat();passed=status=='DROIDW_120_LAUNCH_READY_WAITING_FOR_USER_AUTHORIZATION'
    final={'started_utc':started,'finished_utc':finished,'status':status,'model_execution_authorized':False,'model_attempt_limit':0,'model_attempts':0,'real_tracking_frames':0,'CUDA_model_started':False,'CUDA_numerical_tests_run_this_stage':False,'checkpoint_deserialized':False,'real_images_decoded':False,'GT_values_read':False,'model_retry_count':0,'errors':errors,'passed':passed}
    save('audit_errors.json',errors);save('final_status.json',final)
    text('11_final_launch_readiness.md','# Launch Audit最终状态\n\n`'+status+'`\n\n本轮仅源码审计、文件字节完整性核验、真实CPU loader配合合成图像替身、Linux生产Supervisor与独立dummy进程集成、30帧增长规则边界和唯一命令Dry Run。未启动DROID-W/WildGS/Pi3MOS，未构造SLAM模型，未加载Checkpoint，未读取GT数值，未解码真实WildWorld图像，未执行CUDA数值运算或真实120帧。\n\n若通过，表示具备候选单次启动契约。模型授权=false、当前Attempt上限=0、已执行模型Attempt=0；候选future_target的最多1次仅为待批准目标。正式模型目录与Attempt均未创建。\n\nGT隔离只针对冻结youtube→RGB_NoPose、debug=false与有界Tracker适配器；save_gt_poses=true在该loader不被读取，无需修改GPU_09。两份配置SHA保持不变。测试不证明真实模型初始化、完整BA或120帧Tracking成功；GT评价仍须全部模型进程退出后独立运行。\n\n开始UTC：'+started+'\n\n结束UTC：'+finished+'\n\n所有原始stderr/stdout、进程退出码、Mock时间线、监控心跳和失败证据保留。本轮完成后停止，等待用户对精确候选契约的后续授权。错误详情见audit_errors.json。\n')
    atomic_json(OUT/'audit_status.json',final);print(json.dumps(final),flush=True)
raise SystemExit(0 if passed else 2)
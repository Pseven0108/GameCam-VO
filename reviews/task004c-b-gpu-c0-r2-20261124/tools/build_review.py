"""Build an auditable report of the loader fix and the single real GPU outcome."""
import csv,hashlib,json,pathlib,shutil,textwrap,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
def read(p):return json.loads((ROOT/p).read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,text):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
 text=textwrap.dedent(text);text='\n'.join(x[8:] if x.startswith(' '*8) else x for x in text.splitlines()).strip()+'\n'
 with p.open('x',encoding='utf-8') as f:f.write(text)
def jwrite(p,x):write(p,json.dumps(x,ensure_ascii=False,indent=2))
def main():
 post=read('evidence/GPU_C0_R2_POSTMORTEM.json');src=read('evidence/SOURCE_PROVENANCE.json');cpu=read('evidence/CPU_PHASE_FINAL_DECISION.json')
 assert cpu['CPU_passed'] and post['real_frames_completed']==18 and post['native_BA_calls_completed']==24 and not post['C0_created']
 loader=read('CPU_evidence/artifacts/REAL_LOADER_CPU/CPU_TEST_REPORT.json')
 old=read('CPU_final_evidence/artifacts/RELEASE_CPU_c0_r2_ready/CPU_TEST_REPORT.json')
 source=dict(src);source['upstream_DROID_W_commit']='c3414af6047d06bafc1a6645d09f23247f3b2cdc'
 source['GPU_run_uses_this_commit']=True;source['GitHub_publication_commit_is_not_runtime_commit']=True
 source['runtime_source_only_changed']='native_control/dataset.py';source['historical_assets_protected_after_run']=post['protected_pins_after']
 jwrite('TASK004C_B_SOURCE_PROVENANCE.json',source)
 shutil.copyfile(ROOT/'remote_evidence/artifacts/TASK004C_B_C0_STATE_MANIFEST.json',ROOT/'TASK004C_B_C0_STATE_MANIFEST.json')
 write('TASK004C_B_RGB_CONTRACT_FIX_REPORT.md',f'''
        # 首帧RGB-only合同修复

        本次运行候选：`{src['source_commit']}`，唯一父提交`668a88c74c7f7a88a572679d2bd8e86c0a05514b`，再上一层为完整候选`0931141cf88247dc8fb0c7628c1d91b6531fea90`。GitHub评审快照提交不作为运行提交。

        与668a88c7比较，运行源码只修改`native_control/dataset.py`。父类Dataset、BA、CUDA扩展、原R2、权重和RGB保持不变。

        修改前SHA：`{src['before_sha256']}`；修改后SHA：`{src['after_sha256']}`。原文件、改后文件和Git diff均保存在`remote_evidence/evidence/`。

        ## 严格接受条件

        - 在调用父类前拒绝任何非None的depth_paths或poses，防止标签读取。
        - row RGB ID必须是int并等于index+1；timestamp必须为对应int，游标必须连续。
        - color必须是Tensor，shape=(1,3,360,640)；返回pose必须为None。
        - depth必须是CPU、float32、strided Tensor，shape等于RGB的H/W，元素全部严格为零。
        - 原tuple和Tensor对象原样返回；失败不推进seen。

        没有删除depth检查。非零、NaN、Inf、错误shape/dtype、非CPU和标签输入均拒绝。

        **depth=None兼容性测试按本指令的“必须为Tensor”条款解释为拒绝用例。** 真实父类使用全零Tensor，运行路径不受此解释影响。非CPU负例用meta Tensor，CPU测试没有创建CUDA Tensor。

        ## 结果

        21/21真实Loader及负例测试通过，真实RGB001～018连续验证通过。后续GPU确实处理完18帧，旧首帧错误没有再次出现。该修复不代表C0序列化或恢复已经成功。
    ''')
 write('TASK004C_B_REAL_LOADER_CPU_TEST.md',f'''
        # 真实Loader CPU验证与历史回归

        最终结果：新增 **21/21 PASS**，原有 **152/152 PASS**，合计173个通过用例。真实连续RGB001～018共18帧，使用原RGB_NoPose父类、原RGB、原INPUT manifest与原R2预处理。

        新测试耗时{loader['seconds']:.3f}秒；最终152项耗时{old['seconds']:.3f}秒。CPU过程CUDA未初始化、无checkpoint加载、无GT读取、无GPU运行。

        覆盖：RGB001解码；零占位接受；原tuple/对象身份保持；depth=None拒绝；非零/NaN/Inf；pose非None；depth shape/dtype；非CPU(meta)；RGB shape；timestamp及bool；错误Frame ID；标签源在父类读取前拒绝；失败seen不前进；跳帧和越界拒绝；连续18帧。

        ## 首轮回归缺失测试资产

        第一次152项结果为151通过、1 ERROR，原因是独立目录缺少`source_before/src/depth_video.py`，并非断言发现BA变化。没有跳过或修改该断言。

        已从完整历史提交0931141导出这一原始对照文件，SHA=`cb668fab8f2d78c73e0e34efad6c561b9acdbe57df0463b79bd1407e1bfb1f48`，与前轮评审preimage一致。保留首次失败记录，再完整重跑152项全部通过后才发布GPU准入。

        前期另有Git作者元数据未配置导致的提交失败；只在独立克隆中恢复作者元数据，没有改算法或环境。此事不是CPU用例失败或GPU重试。

        ## 原始证据

        - `remote_evidence/artifacts/REAL_LOADER_CPU/CPU_TEST_REPORT.json`：21项逐项stdout/stderr/exit及SHA。
        - `RGB001_018_MANIFEST.json`：原文件SHA、处理后RGB逻辑SHA、shape/dtype、游标。
        - `RELEASE_CPU_c0_r2/CPU_TEST_REPORT.json`：首轮151/152记录。
        - `RELEASE_CPU_c0_r2_ready/CPU_TEST_REPORT.json`：最终152/152记录。
        - `remote_evidence/evidence/CPU_PHASE_FINAL_DECISION.json`：组合准入决定。

        每个test的exit_code为unittest结果映射；套件实际OS子进程退出码和stdout/stderr另存在PROCESS_RESULT.json。没有把每个unittest用例伪称为独立OS进程。
    ''')
 write('TASK004C_B_GPU_C0_R2_REPORT.md',f'''
        # GPU C0 R2 实际运行报告

        **最终：共同初始化完成，完整C0保存被状态闭包检查拒绝。任务完整成功标准尚未达到。**

        | 项目 | 实测 |
        |---|---|
        | 实例 | sc01-ssh.gpuhome.cc:30448；RTX3090 24GB |
        | 运行候选 | {src['source_commit']} |
        | 配置 | 原R2，buffer500，640×360，stride1，seed43，INIT_D=0 |
        | 本轮GPU生命周期 | 1次，PID2058，exit1，无自动重试 |
        | 运行耗时 | {post['runtime_seconds']:.3f}秒 |
        | 实际完成RGB | 001～018，下一输入index18/RGB019未读取 |
        | 第一阶段graph.update | neighborhood8 + proximity8 = 16 |
        | 第二阶段graph.update | 8 |
        | Native BA调用 | begin24 / end24 |
        | 请求的native内迭代 | 48（API参数合计；无逐retraction独立计数） |
        | 初始化完成与frame-end | 均有真实trace，下一帧输入前进入C0 callback |
        | C0文件与完整性 | 未生成，complete=false，47族未持久化 |
        | 完整C0字节数 | UNKNOWN，不记0 bytes |
        | 显存采样峰值 | {post['sampled_GPU_peak_used_MiB']:,}MiB |
        | shm采样峰值 | {post['sampled_shm_peak_bytes']:,}bytes（288KiB，包含启动前80KiB） |
        | 结束时可用数据盘 | {post['disk_after']['free']:,}bytes（{post['disk_after']['free']/1024**3:.4f}GiB） |

        ## C0语义边界证据

        `native_trace.jsonl`记录三阶段各8个完成的graph.update、24个native.ba.end、一次init.complete和RGB018的frame.end(next_input_index=18)，随后实际调用capture_c0。不是仅根据RGB编号或单条init_done判断。

        Native BA前后Pose/Disparity/U逻辑SHA均有记录。INIT_D=0依据固定controller与未改动的阶段路由；没有独立捕获每次CUDA实参的完整原始副本，不能把该项升级为逐字节CUDA重放证明。

        ## 本轮停止位置

        `capture_c0 -> state_inventory -> ObjectEncoder`遍历真实Metric3D模型时，在`LoRALinear.lora_dropout`遇到未注册函数对象并抛出ControlError。程序尚未进入prepare_state或实际checkpoint写入。

        不是磁盘门禁或OOM触发；监督器未发出资源停止信号。没有生成完整/部分类C0文件，没有执行后续恢复、S0/S1、跨D、正式四臂或Final BA。

        ## 资源与数据保护

        GPU前四份权重、原R2、扩展和历史源码pin核验通过；487张RGB逐SHA匹配INPUT manifest。旧Arena无文件或活动映射。GPU后14个保护pin再核验一致，运行源码仍只有输入适配层一项变化。

        两份本轮Arena包含已处理RGB/特征，合计2,246,400,000逻辑bytes，现保留作失败现场；无活动映射或残留本轮进程。没有删除历史数据。GPU/实例保持在线，没有重启或关机。

        原生Rerun录制文件3,450,264 bytes，记录SHA见postmortem。没有验证浏览器渲染，不将录制文件存在等同于可视化成功。stderr中的resource_tracker警告原样保留；没有擅自清理/dev/shm命名空间。
    ''')
 write('C0_CLOSURE_BLOCKER.md','''
        # C0首个真实状态闭包阻断

        直接证据：GPU traceback显示Metric3D路径`Tracker.motion_filter.metric_depth_estimator...LoRALinear.lora_dropout: Unregistered closure/function`。保存器按原安全策略停止，未丢弃该字段来凑齐C0。

        安装版本的Metric3D源码SHA：`24b832c6e831d25a101ebb8c02b1b3df4b5d5474530481078d6df56c7ff93951`。对应`RAFTDepthNormalDPTDecoder5.py`：LoRALayer第19～22行，dropout>0时用nn.Dropout，否则赋值`lambda x: x`；LoRALinear在第41行调用该基类构造器。

        这为lora_dropout函数对象的来源提供静态解释。GPU进程已退出，未恢复该真实函数对象，不能声称已核查其运行时closure/freevars。

        首次源码提取只扫描LoRALinear类体，因此lambda列表为空；后续沿LoRALayer基类定位到identity lambda。两份取证记录均保留，最终判断依据`evidence/CLOSURE_BASE_CLASS_EVIDENCE.json`。

        当前序列化器只接受可按模块符号重新解析的函数，拒绝lambda/局部函数是既有设计。本轮仅获准修复输入适配层，所以没有修改该保护、模型类或Metric3D源文件。

        这只是遇到的第一个真实闭包阻断，尚不能证明其后没有其他不支持字段。完整C0、Tensor别名、RNG和网络buffer的持久化核验仍未完成。
    ''')
 write('NEXT_PHASE_RECOMMENDATION.md','''
        # 下一步最小建议（未实施、未授权运行）

        建议限定为显式、只对已核验LoRALayer identity callable生效的序列化适配，保留其他未知函数拒绝策略。不要改BA、dropout率、模型前向、权重或原R2，也不要为保存而删除lora_dropout字段。

        候选适配应核验owner类、模型源文件SHA、确切属性名，以及运行时函数是否确为无闭包的单参数identity；使用有版本的符号标记持久化，并在恢复时重建等价无状态callable。先做CPU等价、Tensor对象身份/alias、dtype/shape/stride、NaN/Inf、梯度和RNG不变测试，同时证明其他lambda继续失败关闭。

        还需审查真实模型结构中是否有其他不支持字段，不能只解决第一个异常就宣布完整闭包通过。只有完整状态清单及CPU验证通过，并获得下一次GPU生命周期授权后，再采集C0。

        本轮没有应用上述设计，没有重跑GPU或进入restore/四臂。此报告不自动授予下一阶段授权。
    ''')
 write('FINAL_REVIEW.md',f'''
        # TASK004C-B-GPU-C0-R2 最终评审

        **阶段状态：BLOCKED_AT_C0_CLOSURE_UNREGISTERED_LORA_DROPOUT_FUNCTION。首帧修复和真实初始化通过；完整C0未生成。**

        | 验收项 | 结果 |
        |---|---|
        | 仅修NativeViperRGB | PASS，运行候选`{src['source_commit']}`，父提交668a88c7 |
        | 真实父类/真实RGB CPU测试 | 21/21通过；连续18帧通过 |
        | 原152项完整回归 | 最终152/152通过；首次缺对照文件的151/152记录保留 |
        | 487张RGB与原资产 | SHA一致，模型/扩展/原R2未改 |
        | 唯一一次真实GPU运行 | 已执行，56.164秒，exit1，无自动重试 |
        | 真实共同初始化 | RGB001～018完成；第一阶段16、第二阶段8次graph.update |
        | Native BA | 24次调用均有begin/end；当前帧完成后进入保存callback |
        | C0保存 | **未生成**，状态闭包检查拒绝未注册函数 |
        | 47族、model buffer、RNG持久化核验 | **未完成**，不得记PASS |
        | 真实C0大小 | **UNKNOWN**；完整预算尚未计算 |
        | Restore / S0/S1 / 跨D / B1-B4 | 全部未执行 |

        已确认首个保存阻断：Metric3D `LoRALinear.lora_dropout`函数对象不在序列化器注册范围。安装源码的LoRALayer用`lambda x: x`表示无dropout，符合该异常路径；没有修改模型或放宽闭包检查。

        完整状态没有持久化，因此本任务的“可验证完整C0”成功目标尚未达到。初始化完成不能替代完整C0，也不能证明恢复成功或轨迹性能改善。

        本轮GPU采样峰值13865MiB，shm峰值288KiB；结束数据盘约{post['disk_after']['free']/1024**3:.4f}GiB可用。两块含有效数据的Arena及所有失败现场保留，GPU进程已退出、无活动映射。服务器保持在线，历史删除0。

        请优先读`TASK004C_B_GPU_C0_R2_REPORT.md`、`C0_CLOSURE_BLOCKER.md`和47族状态清单。源代码修复、21项/152项逐项日志、首次测试资产缺失、GPU stdout/stderr、trace、资源采样与全部SHA都随包保存。
    ''')
 write('README_请先读.md','''
        # GPU C0 R2：首帧修复成功，C0闭包保存失败

        先读FINAL_REVIEW.md。新增21/21和历史152/152 CPU验收通过后，确实执行了1次真实GPU运行，完成18帧和24次初始化更新。保存前在Metric3D lora_dropout函数对象处失败，未生成C0，未自动重试。

        本包没有原RGB、模型权重、Arena或Rerun二进制；逐项身份、大小、SHA及远端保留路径都有记录。47族清单为失败状态登记，不是完整C0。下一阶段建议未应用。

        SHA清单覆盖除两份自清单之外的全部交付文件；ZIP另行做CRC与逐文件SHA验证。GitHub发布提交与运行提交分开记录。
    ''')
 security={'GPU_native_lifecycles':1,'GPU_used':True,'GPU_retried':False,'server_shutdown':False,'server_restarted':False,
  'runtime_source_commit':src['source_commit'],'runtime_source_files_modified':['native_control/dataset.py'],
  'original_BaseDataset_modified':False,'BA_formula_modified':False,'CUDA_extension_recompiled':False,
  'R2_YAML_modified':False,'weights_modified':False,'original_RGB_modified':False,'historical_results_modified':False,
  'CPU_real_loader_tests':{'passed':21,'total':21},'CPU_legacy_tests':{'passed':152,'total':152},
  'CPU_test_CUDA_initialized':False,'CPU_test_pretrained_weights_loaded':False,'test_GT_read':False,
  'GPU_real_RGB_frames_completed':18,'GPU_native_BA_calls_completed':24,'C0_created':False,'complete_C0_bytes':None,
  'Restore_executed':False,'S0_S1_created':False,'cross_D_executed':False,'B1_B2_B3_B4_executed':False,
  'Arena_files_retained':True,'historical_files_deleted':0,'unknown_callable_allowed_silently':False,
  'Rerun_recording_exists':True,'Rerun_browser_rendering_verified':False}
 jwrite('SECURITY_AUDIT.json',security)
 write('EXECUTION_LOG.md','''
        # 执行日志 · 2026-11-24 Asia/Shanghai

        1. 读取用户CPU修复+一次GPU采集授权，确认不需要再次批准。
        2. 独立克隆668a88c7；仅修改NativeViperRGB。Git作者元数据缺失后只修复独立仓库提交配置，保留失败记录。
        3. 提交02f8c830；新增真实Loader测试21/21，连续RGB001～018通过。
        4. 首轮历史回归151/152，一项缺少source_before基线输入；未启动GPU。按093原blob/SHA恢复测试输入，保留错误并完整重跑152/152。
        5. wild环境实时准入，487张RGB SHA与14项保护资产核验通过，确认旧Arena已无活动映射。
        6. 启动本轮唯一GPU生命周期，PID2058；完成18帧、16+8次graph.update和24个native.ba.end。
        7. frame.end后进入C0 callback；state_inventory遇Metric3D lora_dropout未注册函数，尚未保存任何C0 payload就失败。exit1，无自动重试。
        8. 只读收集日志、资源与源代码；沿LoRALayer基类定位静态identity lambda，未修模型或序列化器。
        9. 记录47族未持久化状态，保留两份Arena与失败现场；无残留本轮进程、无活动Arena映射。
        10. 打包并发布GitHub供评审。实例保持在线，没有自动进入restore/四臂。

        套件真实OS exit、逐用例stdout/stderr和SHA均保留。SSH包装返回0与内部GPU exit1分别报告。所有源码、模型缓存读取均只读，除明确允许的NativeViperRGB新候选之外未改运行代码。
    ''')
 samples=[json.loads(x) for x in (ROOT/'remote_evidence/attempts/capture/resource_samples.jsonl').read_text('utf-8').splitlines()]
 with (ROOT/'TASK004C_B_RESOURCE_TIMELINE.csv').open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['elapsed_seconds','GPU_used_MiB','GPU_free_MiB','GPU_utilization_percent','disk_free_bytes','shm_used_bytes','cgroup_memory_current_bytes']);w.writeheader()
  for row in samples:
   a=[x.strip() for x in row['GPU'].split(',')]
   w.writerow({'elapsed_seconds':row['elapsed_seconds'],'GPU_used_MiB':a[0],'GPU_free_MiB':a[1],'GPU_utilization_percent':a[2],
    'disk_free_bytes':row['disk_free'],'shm_used_bytes':row['shm_used'],'cgroup_memory_current_bytes':row.get('memory.current')})
 bundle=ROOT/'review_bundle';bundle.mkdir(exist_ok=False)
 for folder in ['remote_evidence','tools','evidence']:
  for p in (ROOT/folder).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.zip'):
    target=bundle/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
 for p in ROOT.iterdir():
  if p.is_file() and p.suffix in ('.md','.json','.csv'):shutil.copyfile(p,bundle/p.name)
 files=[]
 for p in sorted(bundle.rglob('*')):
  if p.is_file():files.append({'path':p.relative_to(bundle).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
 manifest={'self_exclusion':['FILE_SHA256_MANIFEST.json','TASK004C_B_SHA256_MANIFEST.txt'],'files':files}
 (bundle/'FILE_SHA256_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (bundle/'TASK004C_B_SHA256_MANIFEST.txt').write_text('\n'.join(x['sha256']+'  '+x['path'] for x in files)+'\n',encoding='utf-8')
 archive=ROOT/'TASK004C_B_GPU_C0_R2_REVIEW.zip'
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(bundle.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(bundle).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for row in files:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
 verification={'ZIP':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'CRC':'PASS',
   'manifest_files':len(files),'manifest_matches':len(files),'status':post['status'],'GPU_lifecycles':1}
 jwrite('REVIEW_PACKAGE_VERIFICATION.json',verification);print(json.dumps(verification))
if __name__=='__main__':main()

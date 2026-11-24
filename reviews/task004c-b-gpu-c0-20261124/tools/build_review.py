"""Package the actual failed GPU capture and confirmed CPU input diagnosis."""
import csv,hashlib,json,pathlib,shutil,textwrap,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=pathlib.Path(r'D:\aaa\GameCam-VO\maintenance\GITHUB_REVIEW_PUBLICATION_20261124_R1\repository\source\DROID-W')
def read(p):return json.loads((ROOT/p).read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):
 p=ROOT/p;p.parent.mkdir(parents=True,exist_ok=True)
 s=textwrap.dedent(s)
 s='\n'.join(line[8:] if line.startswith(' '*8) else line for line in s.splitlines()).strip()+'\n'
 with p.open('x',encoding='utf-8') as f:f.write(s)
def jwrite(p,d):write(p,json.dumps(d,ensure_ascii=False,indent=2))
def main():
 post=read('evidence/C0_POSTMORTEM_LOCAL.json');pre=read('evidence/C0_PREFLIGHT.json');clean=read('evidence/OWNED_ARENA_CLEANUP.json')
 assert post['GPU_process_exit_code']==1 and post['tracking_frames_admitted']==0 and not post['C0_created']
 diag=post['CPU_DIAGNOSIS'];assert diag['failed_predicates']==['depth_is_None']
 for name in ['native_control/dataset.py','src/utils/datasets.py','src/tracker.py','run.py']:
  path=ROOT/'source_evidence'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(SOURCE/name,path)
 assert sha(ROOT/'source_evidence/native_control/dataset.py')==diag['source_sha256']['native_control/dataset.py']
 assert sha(ROOT/'source_evidence/src/utils/datasets.py')==diag['source_sha256']['src/utils/datasets.py']
 err=(ROOT/'logs/ONE_CAPTURE_EXECUTION.stderr.txt').read_text('utf-8')
 failure=err[err.find('Traceback (most recent call last):'):]
 failure=failure.split('\ndebug1:')[0]
 write('evidence/PREMODEL_INTERPRETER_FAILURE.txt',failure)
 write('FINAL_REVIEW.md',f'''
        # Task004C-B-GPU-C0 最终评审 · 2026-11-24

        **状态：BLOCKED_AT_FIRST_RGB_INPUT_CONTRACT。已执行1次真实GPU启动；C0未生成。**

        | 项目 | 实际结果 |
        |---|---|
        | 当前实例 | sc01-ssh.gpuhome.cc:30448；RTX3090 24GB |
        | 运行源码 | 668a88c74c7f7a88a572679d2bd8e86c0a05514b；未改动 |
        | 独立原生进程生命周期 | 1次，退出码1；不自动重试 |
        | 总耗时 | {post['runtime_seconds']:.3f}秒，主要为模型/进程启动 |
        | 首帧 | RGB001已被CPU解码，进入Tracker前被输入合同拒绝 |
        | 进入跟踪的有效帧 | 0 |
        | Native BA / 初始化完成 | 0 / 否 |
        | 真实C0 / 完整C0大小 | 未创建 / UNKNOWN |
        | GPU显存采样峰值 | {post['sampled_GPU_peak_used_MiB']:,}MiB；不是完整初始化显存需求 |
        | shm采样峰值 | {post['sampled_shm_peak_bytes']:,}bytes（208KiB） |
        | Restore / 跨D / B1-B4 | 全部未执行 |

        ## 已确认根因

        `NativeViperRGB.__getitem__()`要求`depth is None`，但其实际父类`BaseDataset.__getitem__()`在`depth_paths=None`时返回`torch.zeros(H,W)`作为无深度占位。首帧得到float32、CPU、shape=(360,640)的全零Tensor，因此被这一项检查拒绝。

        CPU实读核对：timestamp=0正确；RGB shape=(1,3,360,640)正确；pose=None正确；仅depth_is_None为假。depth_paths与poses均为None，没有引入GT。已用未经改动的真实父类loader与真实第一张RGB复现，非模拟推测。

        ## 解释范围

        这是候选输入适配层的合同错误，不是DROID-W优化失败，也不是C0序列化、显存或磁盘不足。此前152项CPU测试通过仍然是历史事实，但没有覆盖这一真实loader分支，不能视为GPU-ready证明。

        原生Tracker与Rerun进程已创建，2255-byte录制文件存在；由于0帧进入跟踪，不能声称真实数据读写/几何显示已验证。浏览器未验证。完整C0与恢复能力仍未知。

        ## 现场和空间

        保存完整stdout/stderr、资源采样、native trace、CPU复现、配置/源码身份和运行收据。GPU进程组已退出，GPU无剩余compute进程。仅回收本次两份全零临时Arena，先核对owner、路径、inode、device、size、mode、SHA，并扫描/proc确认无活动映射。释放2,246,410,240个实际字节，历史删除0。清理后可用{clean['free_bytes_after']/1024**3:.4f}GiB。

        ## 停止状态

        未修改668a88c7源码、BA数学、R2配置、权重或扩展；没有自动重跑、恢复、跨D或正式B四臂。实例保持在线，没有重启或关机。

        下一步应先修正并CPU验证这一个占位深度合同，再另行批准一次C0采集。建议细节见`NEXT_CAPTURE_RECOMMENDATION.md`，本包未把建议应用到任何GPU运行。
    ''')
 write('GPU_C0_CAPTURE_REPORT.md',f'''
        # GPU C0采集运行报告

        ## 授权与执行

        仅限val_007初始化/C0采集，buffer500、640×360、stride1、seed43、INIT_D=0、原R2配置、原权重及CUDA扩展。C0保存成功后应立即停止，禁止恢复、跨D及B1-B4。本次未成功到达该边界。

        独立目录：`/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_20261124_R1`。原生进程PID773；命令见`remote_evidence/attempts/capture/PROCESS_STARTED.json`。实际运行{post['runtime_seconds']:.3f}秒，exit1，未自动重试。

        ## 启动前资源

        RTX3090总24576MiB、空闲24125MiB、无compute占用；数据盘{pre['disk']['free']:,}bytes可用；shm24GiB；容器RAM上限100GiB。实际保护pin、R2 YAML、INPUT manifest均匹配。克隆后的独立源码/元数据占用已在最终admission再次扣除。

        这里只证明静态下限和启动资源通过，不证明完整C0可放下。真实完整预算函数未执行，因为在第一帧检查就终止。

        ## 时间线

        1. 第一次运行准备使用了系统Python，stdlib admission查询不到Torch分发元数据，模型启动前退出；native生命周期0。完整失败收据保留。
        2. 使用既有wild Python环境读取同一元数据并通过admission；没有修改依赖或源码。
        3. 建立唯一capture launch intent，启动唯一GPU进程生命周期。启动器在构造SLAM之前设置spawn，与官方`run.py:26`一致；其余使用已评审CLI的model-child鉴权和实际capture函数。
        4. 加载预训练模型、创建file-backed Video与原生进程。Rerun产生小型录制文件。
        5. Tracker取RGB001时，严格适配层发现父类返回depth为Tensor而非None，抛出ControlError。
        6. 原生入口因没有SUCCESS/C0收据返回exit1；父进程停止，未重试。
        7. 用CPU、原loader及原RGB复现唯一失败谓词；完成收尾和安全临时Arena回收。

        ## 关键日志

        ```text
        native_control/dataset.py:29
        ControlError: R2 RGB-only input contract mismatch

        native_control/native_driver.py:98
        ControlError: Capture child failed; no automatic retry
        ```

        `INFO: 0 images got!`来自父类初始化时对文件布局的默认glob；子类随后使用已核验的487项INPUT manifest重设color_paths。首张图像能够实际解码，因此不能把该日志单独解释为数据集丢失。

        ## 资源与证据限制

        显存采样峰值7439MiB、shm采样峰值212992bytes、资源间隔约2秒。启动即失败，这不是完整RGB018初始化或完整C0的资源测量。无模型性能、无轨迹、无ATE/RPE。

        完整日志和逐样本资源记录在`remote_evidence/attempts/capture/`。本轮保留的候选与算法完全一致；新增的是启动收据、可见的spawn入口和诊断代码。
    ''')
 write('FIRST_FRAME_INPUT_CONTRACT_DIAGNOSIS.md',f'''
        # 首帧RGB-only合同错误取证

        结论等级：**CONFIRMED_BY_REAL_GPU_FAILURE_AND_CPU_LOADER_REPRODUCTION**。

        | 检查 | CPU实读 | 原适配层要求 | 结果 |
        |---|---|---|---|
        | timestamp | 0 | index=0 | PASS |
        | color shape | (1,3,360,640) | 同左 | PASS |
        | pose | None | None | PASS |
        | depth | float32 CPU Tensor，(360,640)，全零 | None | FAIL |

        对应代码：

        - `source_evidence/native_control/dataset.py:28-29`：调用父类后检查`depth is not None`。
        - `source_evidence/src/utils/datasets.py:202-229`：depthloader返回None时构造`torch.zeros(color_data.shape[-2:])`。
        - 同文件RGB_NoPose类把depth_paths、poses设置为None。
        - `source_evidence/src/tracker.py:66`：Tracker解包`timestamp,image,_,_`，本轮在loader抛错后没有进入图像处理。

        原始zero-depth SHA256：`{diag['depth']['sha256']}`。Native stream的seen在失败后仍为0。对原`NativeViperRGB[0]`再次调用仅发生在CPU诊断中，同样抛出相同异常；没有运行Tracker/模型或再次使用GPU。

        ## 诊断边界

        CPU诊断禁用CUDA并拦截torch.load以防加载预训练权重；末尾cuda_initialized=false。只读原第一张RGB，不读取Camera Pose GT、depth标签或测试GT。diag中depth_paths=None、poses=None。没有纠正RGB/Camera映射或改原始数据。

        ## 为什么原CPU测试没有发现

        此前152项验证控制、storage、快照格式与Mock接口；真实RGB_NoPose父类的无深度零占位分支没有形成该精确合同的端到端测试。GPU-ready状态不应再由这些测试计数单独判断。

        这不否定Local BA安全修复或mmap CPU压力实测，但限制真实输入与C0准入结论。本次0帧跟踪、0次BA，无法评价优化行为或深度正则的科学效果。
    ''')
 write('C0_STORAGE_STATUS.md',f'''
        # 真实C0与空间状态

        - 完整C0：**未生成**。
        - 完整C0大小：**UNKNOWN**，不以0 bytes代替未知大小。
        - 没有调用真实闭包序列化，因此没有真实精确C0预算结果，也没有可恢复checkpoint。
        - 静态Video下限、CPU合成38,616-byte fixture及既有152项测试均属于上一阶段证据，不冒充本轮C0。

        本次启动前可用{pre['disk']['free']:,}bytes；独立克隆与meta后为26,401,849,344 bytes；两块Arena合计2,246,400,000逻辑bytes；失败后24,155,353,088 bytes可用（不同采样时点日志有几KiB差别）。

        已完成临时Arena回收，实测可用{clean['free_bytes_after']:,}bytes（{clean['free_bytes_after']/1024**3:.4f}GiB），硬性10GiB余量保留。历史结果和模型权重没有删除。

        多次恢复的总空间仍未准入。生命周期清理本轮只证明这两个零数据临时文件可在无活动进程/映射时安全回收；没有验证真实C0恢复产生的完整Arena生命周期。
    ''')
 write('ARENA_LIFECYCLE_REPORT.md',f'''
        # 本次临时Arena生命周期

        原生SLAM创建了两块500-slot file-backed CPU存储，共2,246,400,000 bytes；GPU启动失败后两块均为全零。它们没有有效跟踪帧，属于可重建的本次临时存储。

        回收前后核验：

        1. 唯一进程组773已退出；nvidia-smi无compute进程。
        2. 扫描/proc所有可见maps，无这两块文件映射，权限失败0。
        3. 路径严格限定本次`attempts/capture/shared_cpu`，目录内只有这两块文件。
        4. 文件owner、mode0600、device、inode、size匹配；文件名与inode一致；不是symlink。
        5. SHA与失败后封存记录一致，并与同长度全零流的SHA一致。
        6. 仅逐文件unlink这两块临时存储；完整日志、收据、Rerun与诊断保留，历史删除0。

        回收逻辑bytes={clean['logical_bytes_removed']:,}；磁盘实际可用增加{clean['observed_free_increase']:,}bytes。14个保护pin再次核验一致，独立source和原release source均保持clean。

        Resource tracker曾报告一个leaked semaphore警告；完整stderr已保留。结束时shm使用81920bytes，没有擅自清理/dev/shm命名空间。不能将本轮空Arena回收等同于真实C0恢复后的完整共享生命周期验证。
    ''')
 write('NEXT_CAPTURE_RECOMMENDATION.md','''
        # 下一次采集前的最小修复建议（未应用）

        唯一已确认的前置缺陷是无深度数据的表示约定。建议只修改独立候选的NativeViperRGB适配层，不修改BaseDataset、原R2、BA公式或阈值。

        两种可评审方案：

        1. 明确父类零占位合同：仅在depth_paths=None、pose=None且depth为预期shape/dtype的全零Tensor时接受；保留原tuple给Tracker，仍禁止任何非零depth/pose标签。
        2. 在上述严格核验后将无标签占位规范化为None，以维持适配层对外接口；先证明与历史R2实际输入路径等价。

        不建议简单删除depth检查或对非零深度无条件放行。也不能因为depth非None就推断发生了GT泄漏。

        未来CPU验证应真实调用RGB_NoPose父类，覆盖：真实RGB001；zero placeholder；depth=None；非零depth拒绝；pose非None拒绝；shape错；Frame ID错；seen不应在失败后前进；连续RGB001至RGB018在CPU中逐帧校验。记录是否读取任何标签文件。

        这些是建议，不是已完成的新测试或修复。本轮未应用补丁，未更改668a88c7，未再启动模型。修复经过评审并另行获批后，才执行一次新的GPU C0采集；仍不自动进入restore、跨D或B四臂。
    ''')
 write('RUN_AUTHORIZATION.md','''
        # 本轮授权边界

        已批准：当前3090实例上的一次初始化/C0采集；源自已评审668a88c7；保持原R2参数、buffer500、stride1；file-backed CPU storage；采集后停止；完成后通过私有GitHub提供评审材料。

        本轮实际：1次原生GPU进程启动，第一帧输入检查失败，exit1，无自动模型重试。CPU postmortem与只回收本次全零临时Arena均保留证据。

        未执行：真实C0恢复、S1/S0、跨D重放、正式B1-B4、全487帧、DROID-SLAM、训练、算法修复运行。未重启或关闭GPU/实例。
    ''')
 security={'gpu_requested_by_agent':False,'GPU_already_allocated':True,'gpu_used':True,'gpu_restarted':False,
  'cuda_context_initialized':True,'pretrained_checkpoint_deserialized':True,'native_model_process_lifecycles':1,
  'real_RGB_tracking_frames':0,'native_BA_calls':0,'real_C0_created':False,'complete_real_C0_bytes':None,
  'restore_executed':False,'cross_D_executed':False,'B1_B2_B3_B4_executed':False,'automatic_model_retry':False,
  'CPU_diagnosis_used_CUDA':False,'CPU_diagnosis_loaded_checkpoints':False,
  'BA_formula_changed':False,'reviewed_source_changed':False,'R2_YAML_changed':False,'weights_changed':False,'extension_recompiled':False,
  'historical_files_deleted':False,'owned_zero_Arena_files_removed':2,'owned_Arena_logical_bytes_removed':2246400000,
  'instance_shutdown':False,'instance_restarted':False,'GT_labels_used_for_tracking':False,
  'constructor_internal_forward_fully_instrumented':False,'real_RGB_tracking_forward_executed':False,
  'GitHub_publication_authorized':True,'GitHub_repository_private':'Pseven0108/GameCam-VO'}
 jwrite('SECURITY_AUDIT.json',security)
 write('EXECUTION_LOG.md','''
        # 执行日志（Asia/Shanghai，2026-11-24）

        1. 已知Host Key核验sc01:30448，读取GPU、磁盘、shm与保护pin。
        2. 从完整已评审668a88c7建立独立克隆；复制原CPU proof/report，发布仅capture的鉴权元数据。
        3. 系统Python缺少Torch分发metadata，模型启动前中断。保留exit1收据，native预算消耗0。
        4. 采用已有wild环境，最终admission通过，启动PID773；native生命周期1。
        5. 运行58.316秒，首帧RGB-only合同失败，原生进程exit1，未自动重试。
        6. 原loader CPU实读复现，唯一失败谓词depth_is_None；没有初始化CUDA或加载权重。
        7. 采集全部日志、trace、resource与Rerun文件身份。C0未生成，不加载任何快照。
        8. 确认无进程/映射后回收本轮两个全零临时Arena；保护pin和源码再次核验，历史删除0。
        9. 本地打包，保留失败过程，并向已有私有GitHub评审分支发布。

        传输收据在evidence/*_TRANSPORT.json；实际native OS退出码见remote_evidence/attempts/capture/PROCESS_RECEIPT.json。
        SSH包装exit0不代表原生GPU成功。本次原生exit1、CPU诊断exit0必须分别解读。完整raw transport日志保留在本地logs/，评审包以结构化收据和原生stdout/stderr为主。
    ''')
 write('README_请先读.md','''
        # GPU C0首次真实采集：失败取证包

        先读FINAL_REVIEW.md，再读FIRST_FRAME_INPUT_CONTRACT_DIAGNOSIS.md。

        **1次GPU启动，0帧进入跟踪，0次BA，没有C0。** 原因已由CPU真实loader实读确认：无GT深度时父类返回全零占位Tensor，与适配层要求None冲突。

        包内包含实际运行日志、资源采样、CPU诊断、配置/源码锁、原CPU proof、临时Arena生命周期、源代码证据和启动器。没有真实模型权重或RGB数据。2255-byte Rerun文件留在远端并记录SHA，不能作为可视化几何成功证据。

        新建议未应用，未自动重跑；完整C0大小和恢复能力仍未知。SHA清单覆盖除自身外的全部包内文件，ZIP另有外部CRC/SHA验证。
    ''')
 jwrite('DECISION.json',{'status':post['status'],'GPU_attempts':1,'native_exit_code':1,'C0_created':False,
   'complete_C0_bytes':None,'confirmed_root_cause':'DEPTH_ZERO_PLACEHOLDER_VS_NONE_CONTRACT_MISMATCH',
   'approved_next_action':'USER_REVIEW_ONLY','GPU_retry_authorized_by_this_result':False})
 # Export compact resource data without interpreting samples as complete run bounds.
 samples=[json.loads(line) for line in (ROOT/'remote_evidence/attempts/capture/resource_samples.jsonl').read_text('utf-8').splitlines()]
 with (ROOT/'RESOURCE_SAMPLES.csv').open('x',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['elapsed_seconds','GPU_used_MiB','GPU_free_MiB','GPU_utilization_percent','disk_free_bytes','shm_used_bytes','cgroup_memory_current_bytes']);w.writeheader()
  for x in samples:
   gpu=[v.strip() for v in x['GPU'].split(',')]
   w.writerow({'elapsed_seconds':x['elapsed_seconds'],'GPU_used_MiB':gpu[0],'GPU_free_MiB':gpu[1],
    'GPU_utilization_percent':gpu[2],'disk_free_bytes':x['disk_free'],'shm_used_bytes':x['shm_used'],
    'cgroup_memory_current_bytes':x.get('memory.current')})
 bundle=ROOT/'review_bundle';bundle.mkdir(exist_ok=False)
 for folder in ['remote_evidence','source_evidence','tools','evidence']:
  for p in (ROOT/folder).rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.zip'):
    dest=bundle/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
 for p in ROOT.iterdir():
  if p.is_file() and p.suffix in ('.md','.json','.csv'):shutil.copyfile(p,bundle/p.name)
 rows=[]
 for p in sorted(bundle.rglob('*')):
  if p.is_file():rows.append({'path':p.relative_to(bundle).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
 manifest={'self_exclusion':['FILE_SHA256_MANIFEST.json'],'files':rows}
 (bundle/'FILE_SHA256_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 archive=ROOT/'TASK004C_B_GPU_C0_REVIEW.zip'
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in sorted(bundle.rglob('*')):
   if p.is_file():z.write(p,p.relative_to(bundle).as_posix())
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  for row in rows:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
 verification={'zip':archive.name,'zip_bytes':archive.stat().st_size,'zip_sha256':sha(archive),'CRC':'PASS',
   'manifest_files':len(rows),'manifest_matches':len(rows),'GPU_capture_status':post['status']}
 jwrite('REVIEW_PACKAGE_VERIFICATION.json',verification)
 print(json.dumps(verification))
if __name__=='__main__':main()

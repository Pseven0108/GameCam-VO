"""Assemble truthful terminal review; never synthesizes experiment outcomes."""
import csv, hashlib, json, re, shutil, subprocess, zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/aaa/GameCam-VO-TASK011E-R2')
REL='reviews/task011e-continuation-r2-20261128'
REVIEW=ROOT/REL
PARENT='49e803dd87e38e7254b77a30c9a03d8a675f1dc6'
SCIENTIFIC='ae5d98cf339b4ea867193362f384fe5a17737f26'
EVIDENCE=BASE/'terminal_evidence'
TASK=ROOT/'experiments/TASK011E'

def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def csvout(path,rows,fields=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def text(path,value):path.write_text(value,encoding='utf-8')

def main():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==PARENT
    assert not REVIEW.exists(),'Preserve sealed review'
    stop=json.loads((EVIDENCE/'task/BATCH_STOPPED.json').read_bytes())
    resource=json.loads((EVIDENCE/'FINAL_RESOURCE_STATUS.json').read_bytes())
    inv=json.loads((EVIDENCE/'CACHE_FILE_INVENTORY.json').read_bytes())
    terminal=json.loads((EVIDENCE/'task/execution_ledger/s43_val_038_00448-00511_A4/TERMINAL.json').read_bytes())
    assert stop['status']=='STOPPED' and terminal['status']=='ENGINEERING_FAILURE'
    assert resource['source_and_weights_preserved'] and not resource['gpu_compute_processes']
    assert len(inv)==1216 and not json.loads((EVIDENCE/'SNAPSHOT_FILE_INVENTORY.json').read_bytes())
    REVIEW.mkdir(parents=True)
    shutil.copytree(EVIDENCE,REVIEW/'evidence')
    for path in (EVIDENCE/'task').rglob('*'):
        if not path.is_file():continue
        rel=path.relative_to(EVIDENCE/'task')
        # Update only this independent E2 worktree. Sealed R1 files remain in history.
        dest=TASK/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    for name in ('monitor_current.py','collect_terminal_evidence.py','stop_failed_owned_attempt.py',
                 'prepare_startup_fix_candidate.py','test_startup_fix_candidate.py','build_continuation_review.py'):
        dest=REVIEW/'delivery_tools'/name;dest.parent.mkdir(exist_ok=True);shutil.copy2(BASE/name,dest)
    shutil.copytree(BASE/'startup_import_fix_candidate',REVIEW/'unapplied_cpu_candidate')
    for name in ('STARTUP_CANDIDATE_CPU_TEST_LOG.txt','TERMINAL_EVIDENCE_TRANSFER_VERIFICATION.json',
                 'REMOTE_SERVICE_START.json','SHUTDOWN_AUTHORIZATION.json'):
        shutil.copy2(BASE/name,REVIEW/name)
    cleanup=Path('D:/aaa/GameCam-VO/operations/SERVER_STORAGE_CLEANUP_TASK011E_20261128_R1')
    dest=REVIEW/'cleanup';dest.mkdir()
    for name in ('CLEANUP_RECEIPT.json','BACKUP_VERIFICATION.json'):
        shutil.copy2(cleanup/name,dest/name)
    cr=json.loads((cleanup/'CLEANUP_RECEIPT.json').read_bytes())
    assert cr['protected_checked']==4309 and not cr['protected_changed']
    csvout(dest/'REMOVED_FILES.csv',cr['deleted'])
    caches=[]
    for path in sorted((EVIDENCE/'cache').glob('*/CACHE_RECEIPT.json')):
        m=json.loads(path.read_bytes());window=path.parent.name
        assert m['status']=='COMPLETE' and len(m['records'])==64 and m['native_forward_RNG_unchanged']
        caches.append(dict(window=window,frames=64,bytes=sum(r['bytes'] for r in m['records']),
                           receipt_sha256=sha(path),precision=m['precision_protocol']))
    assert len(caches)==19
    csvout(REVIEW/'CACHE_COVERAGE.csv',caches)
    plan=list(csv.DictReader((TASK/'configs/EXECUTION_ORDER.csv').open()))
    outcomes=[]
    for job in plan:
        actual=terminal if job['job_key']==terminal['job_key'] else None
        outcomes.append(dict(**job,status=actual['status'] if actual else 'NOT_ATTEMPTED',
                             initialized=actual.get('initialized') if actual else None,
                             complete_trajectory=False))
    csvout(REVIEW/'E2E_PLANNED_AND_ACTUAL_STATUS.csv',outcomes)
    decision=dict(status='STOPPED_ENGINEERING_SPAWN_MODULE_COLLISION',scientific_source_release=SCIENTIFIC,
        previous_attempt_review=PARENT,complete_common_caches=19,preserved_cache_frames=1216,
        preserved_cache_bytes=sum(r['bytes'] for r in inv),reused_frames=336,new_cache_frames=880,
        cache_forwards_this_attempt=1760,total_cache_forwards_including_prior_unsaved_pair=2434,
        unique_planned_cache_forwards=2432,cache_forward_count_basis='complete receipts + prior stopped write control flow',
        E2E_planned=285,E2E_attempted=1,E2E_terminal=1,engineering_failures=1,not_attempted=284,
        initialized_unknown=1,algorithm_initialization_failures=0,complete_trajectories=0,native_BA_calls=0,
        A0_snapshots=0,FSR_runs=0,automatic_retries=0,secondary_thresholds_approved=False,
        CPU_import_candidate_tests_passed=8,CPU_candidate_applied_to_failed_attempt=False,
        native_GPU_import_candidate_verified=False,confirmatory_statistics_run=False,
        protected_source_files=102,protected_weights=4,cleanup_bytes_freed=cr['freed_measured_bytes'],
        shutdown_after_publication_authorized=True,shutdown_executed_at_review_seal=False)
    dump(REVIEW/'TASK011E_CONTINUATION_DECISION.json',decision)
    dump(REVIEW/'PRIMARY_STATISTICS_STATUS.json',dict(status='NOT_RUN_INCOMPLETE_PLANNED_STUDY',
        planned=285,terminal=1,estimate=None,CI95=None,failed_errors_imputed_as_zero=False))
    final=f'''# TASK011E R2：缓存完成，首次 E2E 因子进程模块冲突停止

2026-11-28，Asia/Shanghai。**19/19公共缓存完整；正式E2E尝试1/285，工程失败1，完整轨迹0，未尝试284。**

本包不是285次实验完成报告，也不是A5/A7优劣结论。

## 实际执行

清理后复用上一次5组完整缓存和第6组16帧，共336帧。R2只计算剩余880帧的Native+Flip，共1760次forward。现在1216份原始浮点NPZ全部保存，逐文件SHA256复核通过，共{sum(r['bytes'] for r in inv):,} bytes；19份完整收据保留原生FP16 autocast、CPU图像预处理和RNG不变证据。未下载RGB或权重。

此前失败写入已完成但未保存的一对forward，在用户明确续跑授权下重新执行。因此唯一计划是2432次缓存forward，而跨两次尝试实际为2434次；历史674次的计数来自停止位置与原代码控制流，不是独立GPU探针。不得忽略这两次未保存计算。

首个正式Job严格按冻结顺序：`s43_val_038_00448-00511_A4`。原生主进程及CUDA资源已启动；两个spawn子进程在进入tracking方法前报错，没有处理RGB、Native BA调用、Filler、导出轨迹或A0快照。

## 故障机制与停止

真实stderr显示：TASK011E的`authorization.py`执行`from common import TASK,sha`时，spawn环境解析到了TASK011B的`common.py`。于是授权文件检查错误地寻找`TASK011B/reports/SECONDARY_THRESHOLD_PROPOSALS.csv`，触发FileNotFoundError。

这不是缺少真正的TASK011E授权材料，也不是GPU硬件、磁盘或算法数值失效。不能通过在TASK011B目录伪造该CSV解决。

子进程失败后，原生父进程仍等待退出。监督器先确认两个子进程的原始异常、没有CHILD_ENTERED及BA日志，再以Job Key、脚本绝对路径及进程启动身份精确核验，只向这个失败的自有driver PID19852发送SIGTERM。其退出码-15记录的是监督停止，不是根因。调度器随后写入ENGINEERING_FAILURE终态并停止整个批次，没有跳过或重跑；没有终止其他进程。

## CPU候选修复：已验证但未部署

独立候选让授权与扩展身份检查使用唯一名称`task011e_io`，并以自身文件确定TASK目录，避免与冻结TASK011B的通用common模块混淆。8项新增CPU测试全部实际通过，包括在独立spawn子进程中注入错误common并验证两条身份检查、哈希函数、未授权失败关闭和不导入PyTorch。

候选仅修改导入和IO身份定位，不涉及BA公式、模型参数、精度、U/W、前后端或CUDA重编译。候选保存在`unapplied_cpu_candidate/`，没有部署进R2现场，没有新GPU重试。CPU合同通过尚不证明整个原生spawn链路已经通过，下一次正式尝试仍须取得单独续跑批准，并进行同名模块污染检查及失败子进程检测。

## 磁盘清理与保护

本次先将21个旧文件转存本地D盘，完成归档CRC与逐成员SHA核验，再删除指定远端文件：10个无活动映射的旧共享Arena、8个可再生Conda索引、3个旧/未完成下载。实际释放{cr['freed_measured_bytes']/1024**3:.3f}GiB；空间由{cr['before_free_bytes']/1024**3:.3f}升至{cr['after_free_bytes']/1024**3:.3f}GiB。

清理前后4309个保护文件核验一致。没有删除原始C0、VIPER、权重、环境、冻结源码或实验结果。完整恢复备份保留在本地`server_backups/SERVER_STORAGE_CLEANUP_TASK011E_20261128_R1/ATTEMPT_002/`，它不是待删除的评审ZIP。

停止后数据盘剩余{resource['disk_free_bytes']/1024**3:.5f}GiB，GPU计算进程为空。4份实际权重、102份冻结源码/配置、原安装与候选扩展的结束后SHA均匹配。R1失败现场及全部原始缓存继续保留。

## 研究与运行预算

只有1个正式工程失败终态；其初始化状态为unknown，不能计作算法初始化失败。其余284项未运行，不能计作失败或填零。0条轨迹，因此没有ATE/RPE、A5−A7、bootstrap或性能方向判断。15项Canary未通过，剩余270项未启动。secondary_thresholds_approved仍为false；FSR仍延后且未运行。

冻结窗口、19×5×3矩阵、执行顺序、640×360、stride1、buffer500、alpha0.01、R2配置、模型和CUDA扩展保持原样。

## 收尾关机

用户明确要求本轮结束后按平台文档在终端关机。归档封存时尚未执行关机；将在完整评审包发布并通过公开下载CRC和SHA核验、确认研究进程已退出后，执行平台`shutdown`。实际命令结果与连接复核另存本地收尾收据，不能在执行前宣称关机成功。

## 评审包范围

包含全部小型原始日志、运行配置、授权/协议/实现锁、19份缓存收据、1216份逐文件SHA清单、错误现场、精确停止记录、清理及备份核验、独立CPU候选和8项测试。大型浮点缓存仍保留服务器，不上传公开仓库；RGB、GT原件、权重、环境二进制及恢复备份不公开。本包不是只挑选几份结论摘要。
'''
    text(REVIEW/'FINAL_REVIEW.md',final)
    text(REVIEW/'SPAWN_FAILURE_AND_FIX.md',
        '# Import namespace isolation\n\nEvidence: evidence/task/execution_ledger/s43_val_038_00448-00511_A4/stderr.txt.\n'
        'Generic common was resolved to TASK011B during spawn, binding the E authorization root to B.\n'
        'CPU candidate replaces the generic import in authorization/native binding only. It is not deployed or GPU-certified.\n'
        'A future approval must also cover fail-fast detection of native child startup errors; no such retry occurred here.\n')
    text(REVIEW/'NEXT_STEP.md',
        '# Next authorized decision\n\nReview the CPU-only unapplied startup import candidate and child-failure supervision.\n'
        'After explicit retry approval, reuse all19 integrity-verified caches, keep R1/R2 attempts sealed,\n'
        'and restart the failed first job in a new independent attempt. Keep the original285 order and stop policy.\n'
        'Do not infer A5/A7 performance or start FSR from this incomplete study.\n')
    shutil.copy2(REVIEW/'FINAL_REVIEW.md',TASK/'FINAL_REVIEW.md')
    dump(TASK/'CONTINUATION_DECISION.json',decision)
    shutil.copy2(REVIEW/'CACHE_COVERAGE.csv',TASK/'CACHE_COVERAGE.csv')
    header=f'''# GameCam-VO — TASK011E R2 stopped at spawn import collision

2026-11-28 Asia/Shanghai. VIPER only. **19/19 caches; E2E1 engineering failure /285;0 trajectories;284 not attempted.**
Eight CPU import-isolation candidate tests pass; candidate unapplied and no GPU retry. No algorithm comparison.
Full evidence and cleanup records: [current review]({REL}/FINAL_REVIEW.md).
Shutdown requested after verified delivery. Source/weights/history preserved.

---

'''
    for name in ('README.md','PROJECT_STATUS.md','CURRENT_RESEARCH_STATUS.md'):
        path=ROOT/name;text(path,header+path.read_text(encoding='utf-8'))
    path=ROOT/'REVIEW_INDEX.md';text(path,f'# Current review\n\n- [TASK011E R2 cache complete; spawn engineering stop]({REL}/FINAL_REVIEW.md)\n\n'+path.read_text(encoding='utf-8'))
    files=sorted(p for p in REVIEW.rglob('*') if p.is_file())
    for path in files:
        raw=path.read_bytes()
        if path.suffix.lower() in ('.pt','.pth','.so','.npz','.npy','.jpg','.jpeg','.zip'):raise ValueError('Unexpected raw or binary asset')
        s=raw.decode('utf-8-sig')
        for pattern in (r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{30,}',r'https://[^\s/@]+:[^\s/@]+@'):
            if re.search(pattern,s):raise ValueError('Credential-bearing artifact: '+str(path))
    records=[dict(path=p.relative_to(REVIEW).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
    csvout(REVIEW/'SHA256_MANIFEST.csv',records);files.append(REVIEW/'SHA256_MANIFEST.csv')
    archive=ROOT/'review_packages/GAMECAM_TASK011E_CONTINUATION_R2_REVIEW.zip';archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in files:z.write(path,path.relative_to(REVIEW).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for r in records:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
    checksum=Path(str(archive)+'.sha256');text(checksum,sha(archive)+'  '+archive.name+'\n')
    extras=[p for p in TASK.rglob('*') if p.is_file() and not any(q in p.parts for q in ('private','__pycache__'))]
    extras+=[ROOT/n for n in ('README.md','PROJECT_STATUS.md','CURRENT_RESEARCH_STATUS.md','REVIEW_INDEX.md')]+[checksum]
    entries=[]
    for path in sorted(set(files+extras)):
        raw=path.read_bytes()
        entries.append(dict(path=path.relative_to(ROOT).as_posix(),source=str(path),bytes=len(raw),sha256=sha(path),
                            git_blob_sha=hashlib.sha1(('blob '+str(len(raw))+'\0').encode()+raw).hexdigest()))
    config=dict(parent=PARENT,root=str(ROOT),branch='codex/task011e-continuation-r2-20261128',review_directory=REL,
                archive=str(archive),archive_sha256=sha(archive),internal_sha256_count=len(records),
                release_tag='task011e-continuation-r2-spawn-stop-20261128',entries=entries,
                decision=decision,title='TASK011E R2 — all caches preserved; spawn startup engineering stop')
    dump(BASE/'PUBLICATION_ALLOWLIST.json',config)
    dump(BASE/'LOCAL_REVIEW_VERIFICATION.json',dict(status='PASS',CRC='PASS',internal_SHA=len(records),
          bytes=archive.stat().st_size,sha256=sha(archive),public_paths=len(entries)))
    canonical=Path('D:/aaa/GameCam-VO')/REL
    assert not canonical.exists();shutil.copytree(REVIEW,canonical)
    print(json.dumps(dict(status='REVIEW_READY',files=len(records),bytes=archive.stat().st_size,sha256=sha(archive),public_paths=len(entries))))

if __name__=='__main__':main()

"""Seal real startup repair, three successful trajectories and A0 storage stop."""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/aaa/GameCam-VO-TASK011E-R3')
REL='reviews/task011e-startup-fixed-r3-20261128'
REVIEW=ROOT/REL
TASK=ROOT/'experiments/TASK011E'
PARENT='10bb8de46730f37bbaf9953abace3fdd390d75da'
EVIDENCE=BASE/'terminal_evidence'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,text):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
def dump(path,value):write(path,json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def csvwrite(path,rows,fields=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==PARENT
    if REVIEW.exists():
        assert json.loads((REVIEW/'TASK011E_R3_DECISION.json').read_bytes())['status']=='SPAWN_REPAIR_GPU_VERIFIED_STOPPED_A0_SNAPSHOT_STORAGE'
    resources=json.loads((EVIDENCE/'FINAL_RESOURCE_STATUS.json').read_bytes())
    snapshots=json.loads((EVIDENCE/'SNAPSHOT_FILE_INVENTORY.json').read_bytes())
    compression=json.loads((BASE/'SNAPSHOT_COMPRESSION_VERIFICATION.json').read_bytes())
    assert resources['source_and_weights_preserved'] and not resources['gpu_compute_processes']
    assert len(snapshots)==2 and compression['status']=='PASS'
    actual={}
    for path in (EVIDENCE/'task/execution_ledger').glob('*/TERMINAL.json'):
        value=json.loads(path.read_bytes());actual[value['job_key']]=value
    assert len(actual)==4 and sum(row['status']=='COMPLETE' for row in actual.values())==3
    failure=actual['s43_val_038_00448-00511_A0'];assert failure['status']=='ENGINEERING_FAILURE' and failure['exit_code']==70
    exception=json.loads((EVIDENCE/'task/runs/43/val_038_00448-00511/A0/CHILD_EXCEPTION.json').read_bytes())
    assert exception['error']=='SNAPSHOT_STORAGE_BLOCKED'
    live=json.loads((EVIDENCE/'task/runs/43/val_038_00448-00511/A0/NATIVE_CACHE_EQUIVALENCE.json').read_bytes())
    assert live['status']=='PASS' and live['bitwise_equal'] and live['cpu_RNG_unchanged'] and live['cuda_RNG_unchanged']
    REVIEW.mkdir(parents=True,exist_ok=True);shutil.copytree(EVIDENCE,REVIEW/'evidence',dirs_exist_ok=True)
    for path in (EVIDENCE/'task').rglob('*'):
        if path.is_file():
            out=TASK/path.relative_to(EVIDENCE/'task');out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,out)
    for path in BASE.glob('*.py'):
        out=REVIEW/'delivery_tools'/path.name;out.parent.mkdir(exist_ok=True);shutil.copy2(path,out)
    for name in ('PREPARATION_RECEIPT.json','DEPLOYMENT_RECEIPT.json','PREFLIGHT_RECEIPT.json',
                 'REMOTE_SERVICE_START.json','TERMINAL_EVIDENCE_TRANSFER_VERIFICATION.json',
                 'SNAPSHOT_COMPRESSION_VERIFICATION.json','STARTUP_REPAIR_NOTES.md',
                 'STARTUP_SUPERVISION_REPAIR.patch','STOP_DIAGNOSTICS.txt'):
        shutil.copy2(BASE/name,REVIEW/name)
    plan=list(csv.DictReader((TASK/'configs/EXECUTION_ORDER.csv').open()))
    status=[];run_summary=[]
    for job in plan:
        value=actual.get(job['job_key'])
        status.append(dict(**job,status=value['status'] if value else 'NOT_ATTEMPTED',
            initialized=value['initialized'] if value else None))
        if not value:continue
        folder=EVIDENCE/'task/runs'/job['seed']/job['window']/job['arm']
        child=folder/'TRACKING_CHILD_COMPLETE.json'
        native=folder/'native_ba_calls.jsonl'
        row=dict(**job,status=value['status'],exit_code=value.get('exit_code'),
                 native_BA_log_records=sum(1 for _ in native.open()) if native.exists() else 0)
        if child.exists():
            record=json.loads(child.read_bytes())
            row.update(full_trajectory_frames=record['frames'],keyframes=record['keyframes'],
                       tracking_child_seconds=record['seconds'],peak_allocated_bytes=record['peak_allocated_bytes'],
                       peak_reserved_bytes=record['peak_reserved_bytes'])
        run_summary.append(row)
    csvwrite(REVIEW/'ALL_285_JOB_STATUS.csv',status)
    csvwrite(REVIEW/'ACTUAL_RUN_SUMMARY.csv',run_summary)
    inventory=json.loads((EVIDENCE/'CACHE_FILE_INVENTORY.json').read_bytes());assert len(inventory)==1216
    raw=sum(row['bytes'] for row in snapshots)
    decision=dict(status='SPAWN_REPAIR_GPU_VERIFIED_STOPPED_A0_SNAPSHOT_STORAGE',
        scientific_parent='ae5d98cf339b4ea867193362f384fe5a17737f26',previous_sealed_review=PARENT,
        complete_caches=19,cache_frames=1216,cache_bytes=sum(row['bytes'] for row in inventory),
        additional_cache_forwards=0,A0_live_equivalence_validation_forwards=1,
        planned_unique_jobs=285,attempted=4,terminal=4,complete_trajectories=3,
        engineering_failed=1,algorithm_initialization_failed=0,not_attempted=281,
        matrix_jobs_retried_without_a_fix=0,automatic_retries=0,FSR_runs=0,
        A0_snapshots=2,A0_raw_snapshot_bytes=raw,
        snapshot_archive_bytes=compression['archive_bytes'],snapshot_archive_raw_SHA_verified=True,
        snapshot_compression_deployed=False,collector_changed=False,
        local_CPU_passed=10,local_CPU_Linux_only_skipped=1,server_CPU_passed=11,
        original_spawn_failure_resolved_on_real_GPU=True,
        failed_child_supervision_verified_on_real_GPU=True,
        original_source_weights_and_extensions_preserved=True,
        frozen_order_and_controller_preserved=True,
        final_free_bytes=resources['disk_free_bytes'],confirmatory_statistics_run=False,
        shutdown_after_publication_authorized=True,shutdown_executed_at_review_seal=False)
    dump(REVIEW/'TASK011E_R3_DECISION.json',decision)
    dump(REVIEW/'PRIMARY_STATISTICS_STATUS.json',dict(status='NOT_RUN_INCOMPLETE_PLANNED_STUDY',
        planned=285,terminal=4,complete=3,not_attempted=281,CI95=None,failed_errors_imputed_as_zero=False))
    first=run_summary[0]
    report=f'''# TASK011E R3：启动修复获真实GPU验证，3组成功；A0快照空间阻断

2026-11-28，Asia/Shanghai。**285项计划中已尝试4项：A4/A7/A5完整成功，A0工程失败，281项未尝试。** 原来的spawn导入冲突已经修复，整轮285项尚未完成。

## 实际修复与验证

用户明确指令为“修复，然后自己重跑实验”。R1/R2封存现场保留，在独立R3目录重跑此前工程失败的首项，然后按冻结顺序继续。授权和扩展核验改用唯一的`task011e_io`，不再从可能指向TASK011B的通用`common`绑定TASK路径。主进程新增只观察自有子进程退出码的监督器；子进程非零退出时写收据并及时退出，独立启动器只清理本次私有进程组。

本地CPU回归10项通过、1项Linux专用跳过；服务器CPU回归11/11通过。真实GPU中，三个tracking子进程正常启动，Native BA、Final BA、Filler及64帧轨迹导出完成。A0后续发生空间错误时，监督器记录原始异常，driver以70退出，批次及时停止，GPU计算进程已清空。因此两项修复均有真实运行证据。

原始DROID-W源码、BA数学、CUDA扩展、权重、R2配置、buffer500、stride1、640×360、alpha0.01、U/W与19×5×3矩阵未变。结束后102项源码/配置、4份实际权重及原安装/候选扩展SHA一致。Frozen controller、预处理、Snapshot Collector和评价程序与封存R2逐字节一致；只改启动、授权和监督。

## 本轮GPU结果

冻结顺序前四项都是Seed43、Rain `val_038_00448-00511`。

| 顺序 | Arm | 状态 | 完整输出 | 关键帧 |
|---|---|---|---|---|
|1|A4|COMPLETE|64/64帧|26|
|2|A7|COMPLETE|64/64帧|28|
|3|A5|COMPLETE|64/64帧|26|
|4|A0|ENGINEERING_FAILURE：SNAPSHOT_STORAGE_BLOCKED|部分现场，不能评分|未登记完整终态值|

完整日志、逐次BA记录、配置、启动/终态收据和三条原始小型轨迹均在`evidence/task/`。A0的`initialized`在工程终态按原runner保留unknown，不能计作算法初始化失败。退出码70来自监督器，直接根因是`CHILD_EXCEPTION.json`记录的快照空间保护。

19/19完整公共缓存、1216份NPZ再次逐文件SHA验证并直接复用，本轮新增缓存forward为0。A0第一帧按原合同额外执行一次原生Metric3D一致性检查，结果逐位相同、最大误差0，CPU/CUDA RNG均未变化。这一次live validation与缓存生成次数分别记账。

## 新阻断：原始全量快照的真实尺寸

两份成功保存的完整BA输入各为2,812,382,226 bytes（约2.619GiB），共5,624,764,452 bytes（约5.239GiB）。第三次保存前，原Collector按2,952,981,868 bytes保守预算加10GiB安全余量检查空间。停止后可用{resources['disk_free_bytes']/1024**3:.5f}GiB，低于这一次保存所需约12.75GiB，因此正确触发`SNAPSHOT_STORAGE_BLOCKED`。磁盘没有写满，安全余量仍保留。

没有删除历史、跳过A0、减少快照采样、降低buffer或关闭Observer来凑齐结果。两份快照分别耗时约14.58秒和14.12秒；其完整Tensor Storage（包括未使用缓冲区）被原样保存，不能只按活跃关键帧数估算文件体积。

## 无损压缩的实测证据，尚未接入

停止后仅进行CPU只读归档。两份原始`.pt`完整字节流压缩为{compression['archive_bytes']:,} bytes（{compression['archive_bytes']/1024**2:.2f}MiB）。独立解压流重新计算原文件大小和SHA256，两份全部一致，gzip CRC通过；不反序列化Tensor、不运行GPU、不修改服务器原件。

这证明当前两份文件有很大的无损压缩空间。它还不证明流式压缩写入、失败恢复、原有FSR读取和整个285项的容量均已通过。不能把两份压缩比外推成57个A0运行的总容量保证。下一次需要明确限定为保存/读取层改造：保留所有合格调用、30项原生参数、Tensor alias/stride/offset、RNG及10GiB检查，验证后复用成功3项，只重跑受阻A0并继续原顺序。

本地完整恢复备份位于`server_backups/TASK011E_R3_A0_SNAPSHOTS_20261128/`，不是待删除的评审ZIP。服务器两份原始快照继续保留。

## 科研判断与停止边界

15项Canary只有4个终态，不能晋级剩余270项。3条成功轨迹来自同一窗口、同一种子，不是完整配对研究；不发布A5/A7优劣、ATE/RPE总体统计或bootstrap结论。281项未尝试，不填作失败或零误差。secondary_thresholds_approved仍为false，FSR为0。新工程错误后没有自动重试。

## 交付与关机

本包含原始日志、代码修复、CPU测试、实际配置、19份缓存收据/1216项SHA清单、四项运行收据、三条轨迹、A0失败现场及两份原始快照的SHA/无损压缩验证。大型NPZ视频（可能含原RGB）、缓存数组、原始快照、权重、环境二进制、RGB/GT和凭据不提交公开Git；原件保留并提供清单。

用户要求结束后终端关机。封包时尚未关机，将在发布并完成公开下载CRC/SHA核验后执行平台原生shutdown，实际结果独立记录，不能提前宣称成功。
'''
    write(REVIEW/'FINAL_REVIEW.md',report)
    write(REVIEW/'NEXT_STEP_STORAGE_PLAN.md',
        '# 下一步：只修复快照存储层\n\n'
        '已验证：两份5.239GiB原始快照可无损压缩为153.63MiB，两份解压SHA与原件一致。\n'
        '未验证：原生Collector的直接压缩写入、10GiB预算、失败原子性、完整恢复和FSR读取。\n'
        '保留原Collector采样规则和所有合格BA输入；禁止裁剪Storage以改变alias，禁止减少快照或关闭A0。\n'
        '需要验证压缩候选的dtype、数值、shape、stride、offset、alias和RNG恢复，记录逐份实际大小、时延及安全余量。\n'
        '续跑需复核并保留A4/A7/A5三个合法终态，不重算成功项；A0用新Attempt重试，失败现场仍保留，按原顺序继续。\n'
        '当前阶段已按新的工程错误停止，不自动发布修正性能结论或启动FSR。\n')
    dump(TASK/'CONTINUATION_DECISION.json',decision);shutil.copy2(REVIEW/'FINAL_REVIEW.md',TASK/'FINAL_REVIEW.md')
    header=f'''# Current: TASK011E R3 — startup fixed; A0 snapshot storage stop

2026-11-28. VIPER only. **3 complete64-frame trajectories (A4/A7/A5),1 A0 engineering failure,281 not attempted /285.**
11/11 Linux CPU regressions pass; original spawn failure fixed on real3090. No confirmatory A5/A7 conclusion.
All19 caches reused; source/weights/extensions preserved. Two raw snapshots5.239GiB, lossless archive153.63MiB; compression not deployed.
[Full current review]({REL}/FINAL_REVIEW.md). User-requested shutdown follows verified delivery.

---

'''
    for name in ('README.md','PROJECT_STATUS.md','CURRENT_RESEARCH_STATUS.md'):
        path=ROOT/name
        if not path.read_text(encoding='utf-8').startswith(header):write(path,header+path.read_text(encoding='utf-8'))
    path=ROOT/'REVIEW_INDEX.md';index=f'# Latest review\n\n- [TASK011E R3 startup fixed; three trajectories; A0 storage stop]({REL}/FINAL_REVIEW.md)\n\n'
    if not path.read_text(encoding='utf-8').startswith(index):write(path,index+path.read_text(encoding='utf-8'))
    files=sorted(path for path in REVIEW.rglob('*') if path.is_file())
    for path in files:
        if path.suffix in ('.pt','.pth','.so','.jpg','.jpeg','.gz','.zip'):raise ValueError('Unexpected large/private asset')
        if path.suffix=='.npz':
            assert path.name=='trajectory.npz' and path.stat().st_size<100000;continue
        if path.name.startswith('events.out.tfevents.'):
            assert path.stat().st_size<65536
            raw=path.read_bytes().decode('utf-8-sig',errors='ignore')
        else:raw=path.read_bytes().decode('utf-8-sig')
        for pattern in (r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{30,}',r'https://[^\s/@]+:[^\s/@]+@'):
            assert not re.search(pattern,raw),str(path)
    records=[dict(path=path.relative_to(REVIEW).as_posix(),bytes=path.stat().st_size,sha256=sha(path)) for path in files]
    csvwrite(REVIEW/'SHA256_MANIFEST.csv',records);files.append(REVIEW/'SHA256_MANIFEST.csv')
    archive=ROOT/'review_packages/GAMECAM_TASK011E_STARTUP_FIXED_R3_REVIEW.zip';archive.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as output:
        for path in files:output.write(path,path.relative_to(REVIEW).as_posix())
    with zipfile.ZipFile(archive) as output:
        assert output.testzip() is None
        for row in records:assert hashlib.sha256(output.read(row['path'])).hexdigest()==row['sha256']
    checksum=Path(str(archive)+'.sha256');write(checksum,sha(archive)+'  '+archive.name+'\n')
    extras=[path for path in TASK.rglob('*') if path.is_file() and not any(name in path.parts for name in ('private','__pycache__'))]
    extras+=[ROOT/name for name in ('README.md','PROJECT_STATUS.md','CURRENT_RESEARCH_STATUS.md','REVIEW_INDEX.md')]+[checksum]
    entries=[]
    for path in sorted(set(files+extras)):
        raw=path.read_bytes();entries.append(dict(path=path.relative_to(ROOT).as_posix(),source=str(path),bytes=len(raw),
            sha256=sha(path),git_blob_sha=hashlib.sha1(('blob '+str(len(raw))+'\0').encode()+raw).hexdigest()))
    config=dict(parent=PARENT,root=str(ROOT),branch='codex/task011e-startup-fixed-r3-20261128',review_directory=REL,
        archive=str(archive),archive_sha256=sha(archive),internal_sha256_count=len(records),
        release_tag='task011e-startup-fixed-r3-storage-stop-20261128',entries=entries,decision=decision,
        title='TASK011E R3 — spawn fixed; 3 trajectories; A0 snapshot storage stop')
    dump(BASE/'PUBLICATION_ALLOWLIST.json',config)
    dump(BASE/'LOCAL_REVIEW_VERIFICATION.json',dict(status='PASS',CRC='PASS',internal_SHA=len(records),
         bytes=archive.stat().st_size,sha256=sha(archive),public_paths=len(entries)))
    canonical=Path('D:/aaa/GameCam-VO')/REL
    assert not canonical.exists();shutil.copytree(REVIEW,canonical)
    print(json.dumps(dict(status='REVIEW_READY',files=len(records),bytes=archive.stat().st_size,sha256=sha(archive),public_paths=len(entries))))


if __name__=='__main__':main()

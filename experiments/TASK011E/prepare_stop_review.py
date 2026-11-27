"""Prepare the actual storage stop review, never scientific success results."""
import csv,json,shutil,sys
from pathlib import Path
from common import ROOT,TASK,REVIEW,REVIEW_REL,PARENT,dump,csvwrite,sha
from analyze_results import failure_accounting

def main():
    evidence=TASK/'evidence'
    resource=json.loads((evidence/'FINAL_RESOURCE_STATUS.json').read_text())
    stopped=json.loads((evidence/'task/BATCH_STOPPED.json').read_text())
    storage=json.loads(next((evidence/'cache').glob('*/STORAGE_BLOCKED.json')).read_text())
    inv=json.loads((evidence/'CACHE_FILE_INVENTORY.json').read_text())
    windows=json.loads((TASK/'configs/GPU_RGB_INPUTS.json').read_text())['windows']
    order=list(csv.DictReader((TASK/'configs/EXECUTION_ORDER.csv').open()))
    caches=[]
    for w in windows:
        window=w['window_id'];receipt=evidence/'cache'/window/'CACHE_RECEIPT.json'
        files=[r for r in inv if r['path'].split('/')[1]==window]
        m=json.loads(receipt.read_text()) if receipt.exists() else None
        caches.append(dict(window=window,sequence=w['sequence'],environment=w['environment'],
            status='COMPLETE' if m else ('PARTIAL_STORAGE_STOP' if files else 'NOT_ATTEMPTED'),
            frames=len(files),bytes=sum(r['bytes'] for r in files),
            complete_receipt_sha256=sha(receipt) if m else None,
            native_forward_RNG_unchanged=m['native_forward_RNG_unchanged'] if m else None,
            model_forwards_in_complete_receipt=m['model_forwards'] if m else None))
    assert sum(r['status']=='COMPLETE' for r in caches)==5
    assert len(inv)==336 and len(order)==285
    csvwrite(TASK/'CACHE_MANIFEST.csv',caches)
    csvwrite(TASK/'E2E_EXECUTION_LEDGER.csv',[dict(**j,status='NOT_ATTEMPTED',terminal=False,initialized=None) for j in order])
    dump(TASK/'BATCH_CHECKPOINT.json',dict(status='STOPPED_STORAGE',derived_final_rollup=True,
        original_remote_checkpoint='evidence/task/BATCH_CHECKPOINT.json',planned_caches=19,complete_caches=5,
        partial_cache_frames=16,preserved_cache_frames=336,preserved_cache_bytes=sum(r['bytes'] for r in inv),
        planned_E2E=285,E2E_attempted=0,E2E_terminal=0,canary_attempted=0,FSR_runs=0,
        no_automatic_retry=True,raw_stop_time_unix=stopped['when_unix']))
    dump(TASK/'FAILURE_ACCOUNTING.json',dict(status='NO_E2E_ATTEMPTS',engineering_storage_stop_in_cache_phase=True,
        per_arm=failure_accounting(order,[]),algorithm_failures_observed=0,
        missing_runs_are_not_initialized_or_failed_results=True))
    dump(TASK/'PER_WEATHER_FAILURE_ACCOUNTING.json',{weather:failure_accounting([r for r in order if r['environment']==weather],[])
        for weather in ['Day','Sunset','Rain','Snow','Night']})
    csvwrite(TASK/'TRAJECTORY_METRICS.csv',[],fields=['job_key','sequence','environment','seed','arm','status','ate_sim3_path_pct'])
    for name in ['PRIMARY_PAIRED_BOOTSTRAP.json','STRICT_THREE_SEEDS_SENSITIVITY.json']:
        dump(TASK/name,dict(status='NOT_RUN_285_TERMINAL_REQUIRED',E2E_terminal=0,planned=285,estimate=None,CI95=None,
            failures_imputed_as_zero=False,secondary_thresholds_approved=False))
    runtime_identity=json.loads((TASK/'MODEL_WEIGHT_IDENTITY.json').read_text())
    frozen_originals=['uniform_control.py','native_driver.py','runtime.py','transfer_audit.py',
        'score_completed_runs.py','analyze_results.py','fixed_state_replay.py']
    dump(TASK/'reports/ASSET_PRESERVATION.json',dict(status='PASS',D_release=PARENT,
        D_worktree_git_diff_exit=0,baseline_or_weight_modifications=False,history_deleted=False,
        unchanged_frozen_runtime_files=[dict(path=n,sha256=sha(TASK/n)) for n in frozen_originals],
        original_extension_after=resource['original_extension_sha256'],candidate_extension_after=resource['candidate_extension_sha256'],
        private_cache_arrays_remain_on_server=True,cache_inventory_entries=len(inv)))
    final=f'''# TASK011E-FAST 审查：GPU 准入通过，缓存阶段触发磁盘保护

日期：2026-11-28（Asia/Shanghai）。状态：**STOPPED_STORAGE**。正式 E2E：**0/285**。

## 实际完成

- 从 TASK011D Release commit `{PARENT}` 建立独立分支；冻结窗口、组别、种子和执行顺序未改。
- RTX3090 实机 PyTorch 2.1.0+cu118 / CUDA11.8 准入通过；buffer500、45×80、7/32个来源的 A7 合成 GPU 检查通过。FP32 reduction、1e-6 容差和仅统计包 D2H 得到验证，没有额外运行 Native BA。
- 四份冻结配置实际会加载的现有权重均匹配 SHA256；此次缓存阶段只加载 Metric3D，没有启动 DROID/FiT3D 跟踪。
- 14项新增授权/断点合同检查通过。没有重复 TASK011D 的169项测试、1216图像解码和预处理审计。1216张 RGB 通过原文件身份检查后硬链接复用，没有重新下载或传图。
- 5/19组缓存完整完成，各64帧、Native+Flip共128次 forward，并有完整缓存收据、逐帧SHA、原生 FP16 autocast 和 RNG 不变记录。第6组 `val_035_00464-00527` 保存16/64帧。
- 共保留336份原始浮点缓存，{sum(r['bytes'] for r in inv):,} bytes。五组完整收据确认640次 forward；第6组17对 forward 已运行，最后一对因写入保护未落盘，因此674次完成 forward 是由真实停止位置与源码推导的计数，而非独立 GPU 调用探针。

## 真实停止原因

首次实测数据盘 free=11,703,263,232 bytes，约10.90GiB。第6组 timestamp16 写入前：

| 项目 | bytes |
|---|---:|
| 当时可用空间 | {storage['free_bytes']:,} |
| 下一份缓存 | {storage['next_write_bytes']:,} |
| 固定安全余量 | {storage['safety_bytes']:,} |
| 额外写入保护余量 | 1,048,576 |

下一次写入无法同时满足安全线与保护余量，因此在写入前停止。最终 free={resource['disk_free_bytes']:,} bytes（约{resource['disk_free_bytes']/1024**3:.5f}GiB）。磁盘未写满；没有删除历史结果或已完成缓存。

GPU、模型和 CUDA 未报告运行错误。终止时 GPU计算进程为空、显存占用0MiB。服务器没有关机、重启或切换模式。第6组被保留为失败缓存尝试，未自动重试或覆盖。

## 四项快速门槛与边界

1. **Gate1 PASS**：实际3090合成Adapter、原安装扩展及冻结候选扩展均验证。整条 Native BA 链路仍待15项 E2E Canary 验证。
2. **Gate2 PASS**：已有权重身份已冻结。没有下载权重、替换模型或重编译 CUDA。
3. **Gate3 保护已实施**：A0原Snapshot Collector保留；逐次10GiB空间保护、累计字节数和Observer耗时记录已接入。A0尚未执行，因此真实快照大小和总需求仍未知。缓存写入也执行同一安全线。
4. **Gate4 PASS**：明确用户授权绑定协议、Implementation Lock、权重身份及Job Key。`secondary_thresholds_approved=false`；只允许PRIOR_CACHE、END_TO_END；FSR未授权。

官方冻结源码以 `.official_archive.json` 归档部署，未包含.git目录。启动器识别其commit c3414af6/官方归档SHA，同时仍逐一核验102份冻结源码与配置、原生扩展SHA。没有伪造 Git HEAD，也没有修改生产源码。两次前置检查失败没有启动模型或消耗正式E2E次数；实际缓存服务只启动一次。

## 统计结论

目前0条 E2E 轨迹、0项 Canary。无 ATE/RPE、A5−A7差值、置信区间或算法优劣结论。285项全部保留为NOT_ATTEMPTED，不能当作285次失败或填零。主统计预注册、5个百分点完成率边界和描述性次指标规则保持不变。

## 继续所需条件

数据盘需要扩容。仅剩余880份缓存预计还需约2.35GiB，属于按已产出缓存估算的存储量，不包含A0快照和正式输出。扩容大小不能据此宣称足够完成285项。

扩容后应只读实测容量，再由用户确认续接保存的部分缓存；当前禁止自动重试的状态不绕过。五份完整收据可原样校验复用，不需要重跑。第6份部分缓存、失败收据和现场均应保留，续接方式需单独记录。

正式执行顺序仍是：所有19缓存通过→原顺序前15项Canary→自动剩余270项。该续跑未在本次封存中执行。FSR继续延后。

## 包内与保留数据

完整审查包包含执行代码、协议和权重身份、真实日志、完整/部分缓存索引、空间停止证据、14项测试和保护记录。大型缓存数组仍保存在服务器，包内逐文件SHA可核对；RGB、GT原件、权重、环境和原生二进制不公开。原TASK011B/C/D及历史Release均保留。
'''
    (TASK/'FINAL_REVIEW.md').write_text(final,encoding='utf-8')
    REVIEW.mkdir(parents=True,exist_ok=False)
    shutil.copy2(TASK/'FINAL_REVIEW.md',REVIEW/'FINAL_REVIEW.md')
    for name in ['MODEL_WEIGHT_IDENTITY.json','GPU_PREFLIGHT_REPORT.json','RUNTIME_AUTHORIZATION.json','CACHE_MANIFEST.csv',
        'E2E_EXECUTION_LEDGER.csv','BATCH_CHECKPOINT.json','FAILURE_ACCOUNTING.json','TRAJECTORY_METRICS.csv',
        'PRIMARY_PAIRED_BOOTSTRAP.json','STRICT_THREE_SEEDS_SENSITIVITY.json','PER_WEATHER_FAILURE_ACCOUNTING.json']:
        shutil.copy2(TASK/name,REVIEW/name)
    for folder in ['evidence','reports','configs','intake']:
        shutil.copytree(TASK/folder,REVIEW/folder)
    live=['common.py','authorization.py','batch_service.py','run_end_to_end.py','cache_priors.py','collect_snapshots.py',
        'native_driver.py','uniform_control.py','native_binding.py','runtime.py','transfer_audit.py','score_completed_runs.py',
        'analyze_results.py','fixed_state_replay.py','gpu_gate.py','release_prepare.py','monitor_remote.py']
    dest=REVIEW/'reproducibility/experiments/TASK011E';dest.mkdir(parents=True)
    for name in live:shutil.copy2(TASK/name,dest/name)
    shutil.copytree(TASK/'frozen_metrics',dest/'frozen_metrics')
    dump(TASK/'private/PUBLICATION_SOURCE_ALLOWLIST.json',dict(code=live,review_directory=REVIEW_REL,
        large_cache_arrays_preserved_on_server=True,raw_images_or_weights_public=False))
    for name in ['README.md','PROJECT_STATUS.md','CURRENT_RESEARCH_STATUS.md']:
        path=ROOT/name;old=path.read_text(encoding='utf-8')
        current=f'''# GameCam-VO — TASK011E stopped at cache storage protection

2026-11-28, Asia/Shanghai. VIPER only. RTX3090 fast admission passed; five complete64-frame common caches and16 partial frames preserved. **Formal E2E0/285; Canary0/15.** Disk reserve prevents the next cache write. No historical deletion or automatic retry. Expand storage and confirm continuation before resuming. Secondary thresholds remain unapproved and descriptive-only; FSR is deferred.

[Current complete review]({REVIEW_REL}/FINAL_REVIEW.md).

---

## Previous status — archived

'''
        path.write_text(current+old,encoding='utf-8')
    index=ROOT/'REVIEW_INDEX.md';old=index.read_text(encoding='utf-8')
    index.write_text(f'# Current review\n\n- [TASK011E actual GPU cache execution — STOPPED_STORAGE, E2E0/285]({REVIEW_REL}/FINAL_REVIEW.md)\n\n'+old,encoding='utf-8')
    print('Actual storage-stop review assembled. No scientific metrics fabricated.')

if __name__=='__main__':main()

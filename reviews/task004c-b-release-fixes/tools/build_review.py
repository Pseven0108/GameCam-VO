"""Generate the evidence-grounded CPU release-fix review. No remote actions."""
import csv
import hashlib
import json
import shutil
import textwrap
import zipfile
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, content):
    p = ROOT/name
    if p.exists():
        raise RuntimeError('Review artifacts must be new: '+name)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Interpolated table rows may start in column zero while prose has a literal
    # eight-space template margin; strip that margin without indenting Markdown.
    content=textwrap.dedent(content)
    content='\n'.join(line[8:] if line.startswith(' '*8) else line for line in content.splitlines())
    p.write_text(content.strip()+'\n', encoding='utf-8')


def jwrite(name, value):
    write(name, json.dumps(value, ensure_ascii=False, indent=2))


def main():
    final = read('evidence/FINAL_RELEASE_AUDIT.json')
    baseline = read('evidence/REMOTE_BASELINE_IDENTITY.json')
    tests = read('evidence/CPU_final/artifacts/RELEASE_CPU_final/CPU_TEST_REPORT.json')
    proof = read('evidence/FULL_BUFFER/artifacts/FULL_BUFFER_CPU_PROOF/FULL_BUFFER_PROOF.json')
    assert tests['total'] == tests['passed'] == 152
    assert final['parent_is_exact_baseline'] and proof['PASS']
    original = ROOT/'evidence/ORIGINAL_118_CPU_TEST_REPORT.json'
    assert sha(original) == final['original_118_record_sha256']
    with zipfile.ZipFile(ROOT/'evidence/REMOTE_093_BASELINE_EXPORT.zip') as z:
        for name, expected in baseline['original_tests_sha256'].items():
            raw=z.read(name)
            assert hashlib.sha256(raw).hexdigest()==expected
            dest=ROOT/'evidence/ORIGINAL_118_TEST_SOURCES'/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('xb') as f:f.write(raw)
    commit = final['new_full_candidate_commit']
    base = final['baseline_commit']
    GIB = 1024**3
    free = final['data_disk_after']['free']
    floor = 10*GIB
    arena = 2246400000
    scratch = 512*1024**2
    metadata = 16*1024**2
    video = 7468230540
    # These are SOURCE-BASED logical estimates; no Video/Tracker is constructed.
    rows = [
        ('timestamp', (500,), 4, 'CUDA'),
        ('images', (500,3,360,640), 4, 'CPU file-backed'),
        ('dirty', (500,), 1, 'CUDA'),
        ('npc_dirty', (500,), 1, 'CUDA'),
        ('poses', (500,7), 4, 'CUDA'),
        ('disps', (500,45,80), 4, 'CUDA'),
        ('zeros', (500,45,80), 4, 'CUDA'),
        ('disps_up', (500,360,640), 4, 'CUDA'),
        ('intrinsics', (500,4), 4, 'CUDA'),
        ('mono_disps', (500,45,80), 4, 'CUDA'),
        ('mono_disps_up', (500,360,640), 4, 'CUDA'),
        ('depth_scale', (500,), 4, 'CUDA'),
        ('depth_shift', (500,), 4, 'CUDA'),
        ('valid_depth_mask', (500,360,640), 1, 'CUDA'),
        ('valid_depth_mask_small', (500,45,80), 1, 'CUDA'),
        ('fmaps', (500,1,128,45,80), 2, 'CUDA'),
        ('nets', (500,128,45,80), 2, 'CUDA'),
        ('inps', (500,128,45,80), 2, 'CUDA'),
        ('dino_feats', (500,25,45,384), 4, 'CPU file-backed'),
        ('dino_feats_resize', (500,384,45,80), 4, 'CUDA'),
        ('uncertainties', (500,45,80), 4, 'CUDA'),
        ('affine_weights', (385,), 4, 'CUDA'),
        ('temp_y_cdot', (500,45,80), 4, 'CUDA'),
    ]
    storage_rows = []
    for name, shape, element, device in rows:
        size = element
        for d in shape:
            size *= d
        storage_rows.append(dict(field=name, shape=list(shape), bytes_per_element=element,
                                 logical_bytes=size, device_by_frozen_config=device))
    assert sum(row['logical_bytes'] for row in storage_rows) == video
    jwrite('reports/VIDEO_STATIC_STORAGE_INVENTORY.json', {
        'scope':'STATIC_SOURCE_ONLY_NOT_REAL_C0', 'buffer':500, 'image_size':[640,360],
        'source':'candidate/src/depth_video.py:51-106', 'fields':storage_rows,
        'video_logical_bytes':video, 'complete_real_C0_bytes':None})
    ttable = '\n'.join('| '+r['field']+' | '+str(r['shape'])+' | '+r['device_by_frozen_config']+' | '+format(r['logical_bytes'],',')+' |' for r in storage_rows)
    categories = Counter(t['test_id'].split('.')[2] for t in tests['tests'] if 'test_release_fixes' in t['test_id'])
    write('TASK004C_B_RELEASE_FIX_REPORT.md', f'''
        # Task004C-B Native Release Fixes

        日期：2026-11-24（Asia/Shanghai）。状态：**CPU_FIXES_COMPLETE_WAITING_FOR_REVIEW**。

        ## 版本来源

        唯一基线是远端完整候选 `{base}`。本轮在独立目录和 `codex/task004c-b-native-release-fixes` 分支修改，生成完整候选 `{commit}`，其唯一父提交就是上述基线。未使用文本参考提交 `2e5e5767c8a4154ad184ef38721e2ab6f190f621` 作为源码来源。

        原候选目录 3,721 个路径与起始清单一致；14 个保护资产 pin 一致。1,906 个 C/CUDA、几何及网络核心路径保持不变，原生扩展调用的 AST 保持一致。原始 `task004_controls.py`、原始 R2 YAML、权重和 CUDA 扩展未修改。证据：`evidence/FINAL_RELEASE_AUDIT.json`、`evidence/REMOTE_BASELINE_IDENTITY.json`。

        ## 修复和验收

        | 项目 | 实际变更 | 验收范围 |
        |---|---|---|
        | Local BA 失败关闭 | 缺 phase、阶段错配、motion_only 立即 STOP；恢复全部 vanilla 前置条件 | CPU 单元测试 |
        | 初始化 D=0 | 三个初始化 observer 阶段保持 INIT_D=0；motion_only 初始化拒绝干预 | CPU 单元测试 |
        | 非 Local BA | 无 marker 时原样返回原生 D/W/U；有非法 marker 时 STOP | CPU 单元测试 |
        | 大型 CPU 共享存储 | 数据盘 MAP_SHARED + 受限 storage reducer；只改两处 CPU 分配 | 小型 alias/stride 测试及原尺寸双 spawn 进程实测 |
        | C0 保存 | 完整对象图去重后，逐 archive 预计算真实序列化字节和 SHA；每次写盘前检查余量 | CPU 合成快照；真实 C0 未创建 |
        | 路径入口 | 支持独立工作区 symlink 布局，保留已有运行授权保护 | 原118项中的 CLI 回归 |

        `selected_flags()` 位于 `candidate/native_control/install.py:9-33`。Local 条件仍要求原生 `metric_depth_reg/use_u/update_u/uncertainty_aware/enable_affine_transform` 为真、bidirectional U 与 loop 为假、`gamma_depth=0.01`。controller 只决定 D，W/U 不在此重写。

        ## 实测结果

        - 原118项保留并重新执行；新增34项，总计 **152/152 PASS**，退出码0，耗时 {tests['seconds']:.3f} 秒。
        - 原尺寸 CPU 缓冲区 **2,246,400,000 bytes**：父进程和两个独立 spawn 子进程内容 SHA、dtype、shape、stride、offset 一致；写入后双方和父进程看到相同更新。
        - 合成跨进程实测 `/dev/shm` 增量 **61,440 bytes（60 KiB）**，保持 buffer=500。
        - CPU 合成快照预算 **38,616 bytes**，实际逻辑文件总量 **38,616 bytes**，实际分配53,248 bytes。
        - 收尾数据盘可用 **{free:,} bytes（{free/GIB:.4f} GiB）**；`/dev/shm` 2 GiB，使用量恢复0。

        ## 未被本轮证据证明的事项

        1. CPU worker 是 Tracker/Rerun 的共享读写替身；没有运行真实 Tracker、Rerun Viewer 或任何模型。不能将其写成原生 GPU 跨进程验证通过。
        2. 完整真实 C0 大小仍是 UNKNOWN。7,468,230,540 bytes 只覆盖23个 Video 数组，不含模型、相关体、其他对象状态、元数据等。完整实时闭包的预算器已实现，但本轮没有权限生成该闭包。
        3. mmap 将容量压力转移到数据盘和页缓存；保留多个未来 attempt 的 backing 文件会累积占用。本轮没有授权自动删除历史或未来研究输出。
        4. admission 中64 MiB是小型 IPC 的静态预算，不是测得的真实 Tracker/Rerun 最低需求；CPU proof不会授予 GPU 运行权限。

        ## 变更与下一阶段边界

        补丁：`evidence/FINAL_ARTIFACTS/artifacts/RELEASE_FIXES_FROM_093.patch`。完整远端候选已提交；包内 `candidate/` 是用于审阅的相关源码子集，不包含全部官方仓库、权重或数据。

        本轮 GPU、CUDA 初始化、真实 C0、RGB前缀、B1/B2/B3/B4均为0。未重编译扩展、未降低buffer、未调整BA公式。完成后停止；未自动进入任何真实运行。
    ''')

    write('TASK004C_B_SHM_STORAGE_DESIGN.md', '''
        # CPU 共享存储设计

        ## 问题和已排除的简化方案

        2 GiB tmpfs 容量为2,147,483,648 bytes，小于两块CPU存储2,246,400,000 bytes。计算来自buffer=500、float32 images及DINO原生shape，未把CUDA Tensor算入tmpfs。

        对现有Torch 2.1.0+cu118的CPU实验发现：

        | 方案 | 实测 | 决定 |
        |---|---|---|
        | `torch.from_file(shared=True)` 后直接传Tensor，file_descriptor | spawn序列化触发Bad file descriptor | 不采用 |
        | 同上，file_system | 可共享，但映射迁入 `/dev/shm/torch_*`，原数据盘文件没有收到写入 | 不解决容量问题 |
        | 传路径descriptor、子进程重新打开 | 同inode映射、父子写入一致 | 作为受限reducer的基础 |

        首个未捕获异常的探索也保留在 `evidence/API_PROBE_RECEIPT.json`；后续v2对照将这些作为显式负对照。不是只凭API支持宣称通过。

        ## 选择的实现

        `candidate/native_control/file_backed.py` 使用独立的owner目录和0600 backing文件；先以 `posix_fallocate` 真实预分配，再用 `torch.from_file(shared=True)` 建立MAP_SHARED。ordinary Tensor的数值、dtype和view元数据由原Torch Tensor reducer保留。

        仅为注册过的 `torch.UntypedStorage` 使用自定义storage reducer，发送schema、绝对路径、长度、device/inode和权限信息；子进程验证后打开同一个文件。每进程cache保证同一storage只重建一次，保留别名。未注册的CPU storage退回安装版本的原reducer；没有改CUDA Tensor reducer。

        对 `src/depth_video.py` 仅替换 `images` 与 `dino_feats` 两个CPU分配。默认未设置 `GAMECAM_FILE_BACKED_CPU_ROOT` 时保留原有zeros/share_memory行为；未来独立attempt显式设置该变量。未改buffer、计算device、dtype、形状或BA。

        C0恢复通过可选CPU storage factory为每个已共享CPU storage分配一次mmap，再恢复各view。默认V2 reader仍可读原快照；没有将整套runtime object pickle化。

        ## 保持的语义和边界

        - 普通Tensor；values、dtype、shape、stride、storage offset、storage alias以真实spawn及序列化恢复测试验证。
        - 非连续transpose/slice、不同dtype、非零offset均有合成覆盖。
        - inode/文件长度/路径身份变更、非法目录等条件失败关闭。
        - 写入由既有锁/屏障调度，mmap不提供新的优化算法或额外并发锁语义。
        - Python强引用和backing文件在所有消费者退出前必须存活；无自动历史清理功能。
        - 私有目录并非恶意root隔离；路径检查用于运行身份与完整性，不声称安全沙箱。

        ## 容量与生命周期

        2,246,400,000 bytes现在占数据盘而非tmpfs。写盘前检查10GiB余量。两份大文件实际物理分配分别1,382,404,096与864,006,144 bytes。页缓存仍受容器RAM约束，本轮不声称真实GPU峰值RAM已测定。

        64MiB residual shm阈值仅是静态小型IPC预算；只有版本、模块SHA及完整尺寸CPU proof一致时才可选择mmap路径。缺失/过期proof不会放宽门禁。正式GPU授权保护保留。

        本轮测试完成后只回收本轮两块可重建的合成大payload：先查无活动映射、核对路径/inode/size和SHA。历史删除数0；完整证据与小型fixture保留。未来真实C0/研究输出不得套用该清理动作。

        ## 证据及来源

        主依据为本机安装版本的实测和 `evidence/artifacts/API_SHARING_PROBE_v2/INSTALLED_reduce_storage.py`。官方v2.1.0源可辅助核对：[PyTorch reductions.py](https://raw.githubusercontent.com/pytorch/pytorch/v2.1.0/torch/multiprocessing/reductions.py)。不将较新在线文档替代安装版本行为。

        结论：**CPU共享机制可行，真实Tracker/Rerun原生运行尚未验证**。不能据此跳过后续真实运行前的完整闭包、进程启动及资源核验。
    ''')

    write('TASK004C_B_SHM_CROSS_PROCESS_TEST.md', f'''
        # 共享存储跨进程CPU实测

        ## 原尺寸压力测试

        证据：`evidence/FULL_BUFFER/artifacts/FULL_BUFFER_CPU_PROOF/FULL_BUFFER_PROOF.json`；入口：`tools/full_buffer_stress.py`。Torch 2.1.0+cu118，spawn，CPU-only，随机种子固定；数值为合成确定性输入。

        | Tensor | shape | dtype | logical bytes |
        |---|---|---|---:|
        | images | (500,3,360,640) | float32 | 1,382,400,000 |
        | dino | (500,25,45,384) | float32 | 864,000,000 |
        | 合计 | buffer=500 | | 2,246,400,000 |

        父进程PID908，两个独立spawn子进程PID975、976，分别标记TRACKER_CPU_STANDIN和RERUN_CPU_STANDIN，退出码均0。二者是合成读写worker，不是真实Tracker或Rerun服务。

        过程：父进程填充数据；两子进程传入同一Tensor对象图，各自完整哈希；barrier之后一个worker更新尾部值（73.25、-18.5）；两worker再读并完整哈希；父进程同步核验。前后均比较dtype/shape/stride/offset和descriptor inode。完整结果为PASS。

        `/dev/shm` baseline={proof['shm_baseline_used_bytes']}、采样峰值={proof['shm_sample_peak_used_bytes']}、增量={proof['shm_delta_bytes']} bytes。测试时长{proof['duration_seconds']:.3f}秒；采样峰值不是对所有可能微瞬态或真实模型负载的上界证明。

        ## 别名与元数据测试

        新增FileSharingTests共11项：跨spawn别名；双reader；非连续stride、非零offset与核心dtype；未注册CPU storage保留Torch原行为；file_system全局策略下owned storage不迁回tmpfs；snapshot恢复别名；allocator有/无选项；物理预留及descriptor损坏拒绝。

        这些小型测试覆盖别名/布局；原尺寸压力测试覆盖容量和多进程同一文件。不能把原尺寸连续Tensor测试单独说成覆盖全部view关系。

        ## 证据留存

        最终152项测试逐项stdout/stderr、退出码和SHA在 `evidence/CPU_final/artifacts/RELEASE_CPU_final/CPU_TEST_REPORT.json`。全尺寸测试的外层退出码、stdout/stderr在 `evidence/FULL_BUFFER_RESULT.json`；受信SSH收据单独保存。

        两块大合成payload在验证所有worker结束、无活动映射并核对SHA后回收；不将2.09GiB测试payload塞入评审ZIP。测试参数、生成脚本、完整前后SHA和descriptor保留，用户可在独立目录复现。真实RGB/模型/C0均为0，CUDA未初始化。
    ''')

    budget_text = f'''# 完整C0存储预算与保存门禁

## 当前结论

**完整真实C0字节数：UNKNOWN。精确实时序列化预算器已实现并经CPU合成验证。** 本轮未加载模型、未执行RGB前缀，无法观测真实完整对象闭包，不能用Video小计冒充完整C0。

当前数据盘复核：{free:,} bytes（{free/GIB:.4f} GiB）可用。起始实测为{baseline['disk']['free']:,} bytes（{baseline['disk']['free']/GIB:.4f} GiB）；用户给出的25.3059 GiB不能当作本次最终值。

## 23项Video静态逻辑清单

以下按源码和固定buffer=500、H=360、W=640、feature_dim=384计算，**没有创建真实Video**。

| Field | Shape | 原配置device / 本候选CPU存储 | Logical bytes |
|---|---|---|---:|
{ttable}

合计 **7,468,230,540 bytes（{video/GIB:.4f} GiB）**。CUDA项需要写入快照，但不占/dev/shm。两块mmap合计{arena:,} bytes属于上述Video状态，写C0时仍会额外存在一份live backing，占用数据盘，必须同时计入。

完整C0还需要：graph/edge/correlation/hidden buffers、Tracker/MotionFilter/Frontend/Filler对象字段、model参数和buffer、RNG/observer/timer状态、源类pin、manifest、Torch ZIP头与padding等。按底层storage去重，view或重复对象引用不可重复计费。不能用checkpoint文件大小估计live model closure，后者可能包含额外状态。

## 精确实时算法

1. 在原writer barrier及Video锁下停止状态写入；保留真实闭包验证。
2. 现有ObjectEncoder枚举全部可注册对象和唯一storage；遇未知字段或非支持别名即STOP。
3. 对每个唯一storage使用当前安装版本的`torch.save`写入counting/hash sink，得到**精确archive逻辑bytes和SHA**，不创建临时archive。
4. 确定全部manifest字段与COMPLETE内容，计数其真实UTF-8字节。
5. 写盘前检查 `free >= round_each_file + 16MiB metadata reserve + 512MiB retained scratch + 10GiB floor`。
6. 每份tensor archive、manifest和COMPLETE实际保存前重新测量余量；tensor文件预分配实际块；实际大小和SHA必须与plan一致。
7. 如果状态在plan后变化、磁盘缩水或最终SHA不符，保留FAILED staging并STOP，不封存成功、不覆盖旧C0、不删除历史。

逻辑字节精确，filesystem物理overhead不声称精确；使用当前f_frsize向上取整及明确保守预留。动态其他进程写盘仍可能触发STOP，不能将预检当作独占容量保证。每块storage一次CPU副本/哈希产生RAM和I/O开销，未测真实闭包耗时或内存峰值。

## CPU实测预算闭环

合成fixture的3份storage archive总36,244 bytes；manifest2,286、COMPLETE86；合计**38,616 bytes**。实际逻辑总量也是38,616；实际块量53,248。不是NATIVE_C0。

测试覆盖serialize padding边界、完整storage而非仅view、alias去重、state变动、plan篡改、保存中磁盘缩水、每次写盘检查、floor边界、RNG不变。证据：`evidence/FINAL_ARTIFACTS/artifacts/EXACT_BUDGET_CPU_FIXTURE/`与最终测试报告。

## 当前空间可以说明什么

若只有一份live arena和一份C0，使用已知Video下限、10GiB floor、512MiB scratch与16MiB metadata后，剩余给未知闭包与其他新日志的理论上限约 **{(free-floor-arena-video-scratch-metadata)/GIB:.4f} GiB**，还要减实际archive头与文件系统开销。这不是完整C0可放下的证明。

若保留capture、restore-check及四个后续arm各自完整arena，共6份，光arena+C0的Video下限+10GiB floor就要 **{(6*arena+video+floor)/GIB:.4f} GiB**，已经高于当前可用{free/GIB:.4f} GiB，尚未含其他闭包和日志。即使只保留capture与四臂5份arena也不能直接宣布全阶段存储就绪。

因此必须逐阶段实测、分别预算；未来若需回收新产生的临时arena，应另有清晰生命周期和用户批准，或增加存储。**本候选不自动删除任何真实attempt或历史产物。** 不把单个CPU测试通过解释成B1/B2/B3/B4存储准入通过。

## 实现位置

`candidate/native_control/storage_budget.py`、`snapshot.py::prepare_state/save_prepared_state`；`binding.capture_c0`会保存`C0_EXACT_BUDGET_BEFORE_SAVE.json`。该实际NATIVE_C0路径本轮未执行。
'''
    write('TASK004C_B_C0_STORAGE_BUDGET.md', budget_text)

    test_categories = '\n'.join(f'| {name} | {count} | PASS |' for name, count in sorted(categories.items()))
    write('TASK004C_B_RELEASE_CPU_TEST_REPORT.md', f'''
        # Release CPU回归测试报告

        最终：**152/152 PASS，failures=0，errors=0，子进程退出码0**。原118项+新增34项，耗时{tests['seconds']:.3f}秒。所有Python子进程设置`CUDA_VISIBLE_DEVICES=""`；Torch版本2.1.0+cu118只用于CPU Tensor和spawn，不初始化CUDA。

        ## 原118项如何保留

        原始报告逐字节保留：`evidence/ORIGINAL_118_CPU_TEST_REPORT.json`，SHA256 `{final['original_118_record_sha256']}`。6份原测试源码也按baseline identity中的SHA逐项核验并保存在`evidence/ORIGINAL_118_TEST_SOURCES/`；新目录中重跑同118个test ID，不改历史文件。

        新目录中的`test_local_W_and_U_are_not_redefined`只为video fixture补充vanilla cfg字段，因为修复后恢复了原local_flags的严格前置校验；断言与test ID不变。原版本源码和补丁保留，不能说所有测试源码逐字节未变。

        ## 新增覆盖

        | 测试类 | 项数 | 结果 |
        |---|---:|---|
        {test_categories}

        用户要求的missing phase、incorrect phase、motion_only、有效INIT_D=0、有效Local D toggle均真实执行。另核对原local_flags所有vanilla拒绝条件，非Local无扩大D范围。

        ## 失败和修订记录

        | 轮次 | 结果 | 处理 |
        |---|---|---|
        | API探索v1 | 内层退出1，Bad file descriptor | 保留；v2显式对照重建失败机制 |
        | initial | 145/148，3个旧CLI用例失败 | 独立工作区symlink解析ROOT错误；修复两个CLI工作区寻址 |
        | revision02 | 148/148 | 验证路径修复与30项新测试 |
        | final | 152/152 | 再加入4项存储admission验证后重跑完整套件 |

        这属于获批CPU修复迭代，不是真实模型自动重试。全部历史测试结果保留，不能只展示最后一次通过。

        ## 可追溯证据

        最终逐项结果：`evidence/CPU_final/artifacts/RELEASE_CPU_final/CPU_TEST_REPORT.json`；每条包含input、seed、expected、actual、seconds、stdout、stderr、exit_code、stdout/stderr SHA。单项exit_code为测试框架映射的通过/失败结果，不声称每个用例都有独立OS进程。

        套件真实OS子进程stdout/stderr和退出码：`evidence/CPU_*_RESULT.json`；unittest原日志在各轮artifact目录。SSH包装进程退出码和CPU子进程退出码分别保存；例如initial的SSH包装退出0、测试子进程退出1，报告以内部测试结果为准。

        全尺寸共享压力测试另计一次CPU试验，非新增GPU运行；小型预算fixture另计CPU证据，不伪装为NATIVE_C0。当前候选完整提交为`{commit}`，父提交`{base}`。

        ## 复现方式及限制

        包内提供093基线相关文件、改后源码、patch、测试和合成生成脚本。应在独立副本/独立输出目录、同Torch版本执行CPU套件，标签必须唯一，避免覆盖已有结果。Linux文件映射与posix_fallocate测试不声称已在Windows验证。

        本轮没有导入实际DROID-W模型、加载预训练权重、运行RGB、重编译CUDA或启动B四臂。CPU结果不能证明正式GPU数值一致、速度或轨迹改进。
    ''')

    write('FINAL_REVIEW.md', f'''
        # TASK004C-B-NATIVE-RELEASE-FIXES 最终评审

        **结论：CPU修复与合成验证完成，提交人工评审；真实C0及B四臂未启动。**

        | 验收项 | 状态 | 证据 |
        |---|---|---|
        | 唯一093完整基线 | PASS | 新commit `{commit}`，父提交为`{base}` |
        | Local BA严格失败关闭 | PASS_CPU | 缺失/错配marker、motion_only、原vanilla边界全覆盖 |
        | INIT_D=0及非Local范围 | PASS_CPU | 三个初始化与非Local pass-through测试 |
        | 保持buffer=500 | PASS_STATIC_CPU | 原尺寸双CPU存储2,246,400,000 bytes |
        | 不占用大型tmpfs存储 | PASS_CPU_SYNTHETIC | 双spawn读写一致，shm增量60KiB |
        | dtype/shape/stride/offset/alias | PASS_CPU_SYNTHETIC | 小型view/alias测试+原尺寸压力测试 |
        | 真实Tracker/Rerun完整链路 | NOT_EXECUTED | 本轮禁止模型/GPU；CPU worker替身 |
        | 完整C0精确逻辑预算机制 | PASS_CPU_SYNTHETIC | 实测38,616/38,616 bytes，逐文件空间门禁 |
        | 真实完整C0大小及四臂总空间 | UNKNOWN / NOT_ADMITTED | 未创建真实闭包；保留多arena会超过当前容量 |
        | 完整回归 | PASS | 原118+新增34=152/152 |
        | 历史与BA数学保护 | PASS | 3721路径、14保护pin、1906核心路径核验；扩展调用AST不变 |

        关键发现：原生Torch对file-backed Tensor默认spawn传递并不能保证继续使用数据盘文件。候选使用仅作用于注册storage的重建方式，不改变BA公式。完整CPU证据已经建立，但尚不能将其宣布为真实模型运行准入完成。

        当前数据盘可用{free/GIB:.4f}GiB。真实C0包含Video以外未知状态；未来多个attempt的2.2464GB arena累积必须单独预算，不自动清理。

        本轮已完成授权范围：五份指定报告、相关源码、相对093的patch、原118记录、全部修复过程与失败记录、最终152项日志、API负对照、原尺寸共享proof及合成预算fixture。大合成payload已在无活动map后回收；历史删除0。

        GPU0、CUDA初始化0、模型加载0、真实C0=0、RGB前缀0、B1/B2/B3/B4=0。未降低buffer、未改原R2、未改BA公式、未编译扩展。未关闭或重启实例。状态：**STOPPED_FOR_USER_REVIEW**。
    ''')

    write('README_请先读.md', '''
        # Task004C-B 发布修复 CPU评审包

        请先读 `FINAL_REVIEW.md`，再读五份 `TASK004C_B_*.md`。

        本包包含：Local BA安全边界修复、文件映射共享存储实现、完整C0预算机制、原118项记录与152项最新回归、失败记录、原尺寸2.2464GB双CPU进程proof、小型快照预算实测、源代码preimage与patch。

        **没有真实GPU实验、没有C0、没有RGB前缀、没有B1/B2/B3/B4结果。** 完整C0大小未知；CPU共享机制通过不等于真实Tracker/Rerun已验证。

        文件导航：

        - `candidate/`：从完整远端093分支导出的相关改后源码子集。
        - `baseline_export/`与`source_before/`：远端093基线相关源码与Git preimage。
        - `tests/`与`configs/`：CPU套件及既有合同副本，未授权正式执行。
        - `evidence/FINAL_RELEASE_AUDIT.json`：完整版本、原资产保护、提交及空间收尾证据。
        - `evidence/CPU_final/.../CPU_TEST_REPORT.json`：152项逐项结果。
        - `evidence/ORIGINAL_118_CPU_TEST_REPORT.json`：原始118记录，原样保留。
        - `evidence/FULL_BUFFER/`：完整尺寸CPU proof。
        - `evidence/FINAL_ARTIFACTS/`：patch、版本绑定证书、小型CPU预算fixture。
        - `tools/`：合成试验及CPU传输辅助源；传输助手依赖本项目已有受信SSH bootstrap，不包含凭据。

        SHA清单覆盖除两份清单自身外的全部包内文件；外置验证记录提供ZIP CRC、清单匹配和ZIP SHA。包不含模型、RGB、完整官方仓库或两块2.09GiB大合成backing文件。不得将合成snapshot误标为真实C0。
    ''')

    security = {
        'scope':'CPU_ONLY_RELEASE_FIXES', 'base_commit':base, 'candidate_commit':commit,
        'forbidden_text_reference_commit_used':False,
        'gpu_requested':False, 'gpu_used':False, 'gpu_queried':False, 'instance_restarted':False,
        'instance_shutdown':False, 'cuda_context_initialized':False, 'cuda_tensor_created':False,
        'pretrained_checkpoint_deserialized':False, 'model_initialized':False,
        'model_forward_executed':False, 'real_C0_created':False, 'RGB_prefix_executed':False,
        'B1_B2_B3_B4_executed':False, 'BA_math_modified':False, 'CUDA_extension_recompiled':False,
        'buffer_changed':False, 'R2_YAML_modified':False, 'weights_modified':False,
        'original_093_directory_modified':False, 'historical_data_deleted':False,
        'SSH_pinned_identity_verified':True, 'StrictHostKeyChecking_disabled':False,
        'dependencies_installed':False, 'github_push_performed':False,
        'torch_imported_for_CPU_tensors':True, 'synthetic_tensor_fixture_deserialized':True,
        'synthetic_temporary_payload_files_removed':final['synthetic_temp_payloads_removed'],
        'deletion_scope':'Only two new deterministic CPU pressure-test backing files after no maps and SHA verification; no historical files',
        'evidence':'evidence/FINAL_RELEASE_AUDIT.json', 'final_status':'STOPPED_FOR_USER_REVIEW'}
    jwrite('SECURITY_AUDIT.json', security)
    events = []
    for p in sorted((ROOT/'evidence').glob('*_receipt.json')):
        d = json.loads(p.read_text())
        if 'started' in d:
            stamp = datetime.fromisoformat(d['started']).astimezone(timezone(timedelta(hours=8))).isoformat()
            events.append((stamp,p.name,d['exit_code']))
    event_table = '\n'.join('| '+stamp+' | '+name+' | '+str(code)+' |' for stamp,name,code in sorted(events))
    write('EXECUTION_LOG.md', f'''# CPU执行记录

时区Asia/Shanghai。SSH目标sc01-ssh.gpuhome.cc:30414，使用已有pin，未重启/关机、未查询GPU。以下exit是SSH包装进程值，模型运行次数均为0；测试子进程退出码见对应RESULT.json。

| 启动时间 | 收据 | SSH exit |
|---|---|---:|
{event_table}

1. 核验远端完整093候选，克隆独立副本，导出3721路径身份和原118记录。
2. 探索直接from_file的失败与迁回tmpfs现象；保留v1失败，v2做显式对照。
3. 修复Local flags、实现受限文件storage reducer与精确序列化预算。
4. initial完整回归145/148，发现3个CLI路径问题；修复工作区ROOT定位。
5. revision02完整回归148/148。
6. 执行原尺寸2.2464GB双spawn读写试验，PASS；没有加载真实模型。
7. 新增4项存储admission校验，final完整回归152/152。
8. 独立CPU预算fixture38,616 bytes闭环；核验原资产保护、核心AST，提交新完整候选{commit}。
9. 在无活动映射并校验SHA后回收两份本轮大合成payload，保留全部证据与小fixture；历史删除0。
10. 本地整理五份报告与评审包；真实C0、RGB前缀和B四臂仍未执行。

远端原始transport日志仍保存在工作区logs/；为避免无意义的base64返回包及SSH调试噪声，ZIP以结构化收据、内部stdout/stderr和原unittest日志为执行证据。未省略已知失败。
''')

    jwrite('reports/REVIEW_DECISION.json', {
        'status':'CPU_FIXES_COMPLETE_WAITING_FOR_REVIEW', 'CPU_tests':{'passed':152,'total':152},
        'file_backed_CPU_full_size_test':'PASS', 'native_Tracker_Rerun':'NOT_EXECUTED',
        'exact_serialization_budget_CPU_test':'PASS', 'complete_real_C0_bytes':None,
        'formal_B_storage_admission':'NOT_ESTABLISHED', 'GPU_authorization_consumed':0,
        'base_commit':base,'candidate_commit':commit})

    # A compact independent review bundle: no .git, credentials, weights or large files.
    bundle = ROOT/'review_bundle'
    bundle.mkdir(exist_ok=False)
    for folder in ('candidate','baseline_export','source_before','tests','configs','evidence','tools','reports'):
        for p in sorted((ROOT/folder).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts or p.suffix in ('.pyc','.zip'):
                continue
            target = bundle/p.relative_to(ROOT)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)
    for p in sorted(ROOT.glob('*.md')):
        shutil.copyfile(p,bundle/p.name)
    shutil.copyfile(ROOT/'SECURITY_AUDIT.json',bundle/'SECURITY_AUDIT.json')
    # The entire original report is preserved, not reconstructed from the new report.
    assert sha(bundle/'evidence/ORIGINAL_118_CPU_TEST_REPORT.json') == final['original_118_record_sha256']
    entries = []
    for p in sorted(bundle.rglob('*')):
        if p.is_file():
            entries.append({'path':p.relative_to(bundle).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
    manifest = {'schema':'GAMECAM_REVIEW_SHA256_V1',
                'excluded_self_manifests':['FILE_SHA256_MANIFEST.json','SHA256_MANIFEST.csv'],
                'coverage':'Every other file in the ZIP, including reports/code/evidence; external ZIP checksum avoids recursion',
                'files':entries}
    (bundle/'FILE_SHA256_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (bundle/'SHA256_MANIFEST.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(entries)
    out = ROOT/'TASK004C_B_NATIVE_RELEASE_FIXES_REVIEW.zip'
    with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(bundle).as_posix())
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        members=set(z.namelist())
        assert members == {x['path'] for x in entries}|{'FILE_SHA256_MANIFEST.json','SHA256_MANIFEST.csv'}
        for row in entries:
            data=z.read(row['path'])
            assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
        verification={'zip_file':out.name,'zip_bytes':out.stat().st_size,'zip_sha256':sha(out),
                      'zip_crc':'PASS','zip_members':len(members),'sha_files_checked':len(entries),
                      'sha_files_matched':len(entries),'manifest_coverage_complete':True,
                      'original_118_record_preserved':True,'GPU_runs':0,'real_C0_created':False}
    jwrite('REVIEW_PACKAGE_VERIFICATION.json',verification)
    write('TASK004C_B_NATIVE_RELEASE_FIXES_REVIEW.zip.sha256',verification['zip_sha256']+'  '+out.name)
    print(json.dumps(verification,ensure_ascii=False))


if __name__ == '__main__':
    main()

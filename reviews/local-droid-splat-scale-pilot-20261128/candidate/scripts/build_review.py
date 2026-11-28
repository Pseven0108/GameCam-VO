"""Seal this completed local pilot; never import a model or contact a server."""
import csv
import hashlib
import json
import pathlib
import shutil
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
TASK = ROOT / 'candidate'
REVIEW_NAME = 'local-droid-splat-scale-pilot-20261128'
REVIEW = ROOT / 'review' / REVIEW_NAME
DELIVERY = ROOT / 'deliveries'
ZIP_NAME = 'GAMECAM_LOCAL_DROID_SPLAT_SCALE_PILOT_REVIEW.zip'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(relative, text):
    path = REVIEW / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + '\n', encoding='utf-8')


def copy_file(source, relative):
    target = REVIEW / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def copy_tree(source, relative):
    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and '.git' not in path.parts:
            if path.suffix.lower() in {'.pyc', '.so', '.pyd', '.dll', '.pth', '.pt'}:
                raise RuntimeError('Unexpected excluded binary: ' + str(path))
            copy_file(path, pathlib.Path(relative) / path.relative_to(source))


def main():
    cpu = read(TASK / 'reports/FINAL_CPU_TEST_RESULTS.json')
    evidence = read(TASK / 'reports/FINAL_EVIDENCE_VALIDATION.json')
    result = read(TASK / 'evaluation/RESULTS.json')
    endpoint = read(TASK / 'outputs/A5_001/ENDPOINT_CHECK.json')
    assert cpu['successful'] and cpu['tests_run'] == 36
    assert evidence['all_shared_checkpoint_hashes_unchanged']
    assert evidence['original_installed_extension_preserved']
    assert all(x['passed'] for x in evidence['metric_checks'])
    assert all(x['within_tolerance'] for x in endpoint['comparisons'])
    assert [x['arm'] for x in result['results']] == ['BASE', 'A5', 'SCALE', 'SCALE_A5']
    if (REVIEW / 'SHA256_MANIFEST.csv').exists():
        raise FileExistsError('Already sealed review; do not overwrite')
    REVIEW.mkdir(parents=True, exist_ok=True)
    DELIVERY.mkdir(exist_ok=True)
    for folder in ['src', 'scripts', 'tests', 'configs', 'native', 'reports', 'evaluation', 'evidence', 'outputs']:
        copy_tree(TASK / folder, 'candidate/' + folder)
    copy_file(ROOT / 'README.md', 'WORKSPACE_README.md')
    for window in ['train_004_01658-01721', 'train_001_00309-00372']:
        source = TASK / 'data' / window
        if source.exists():
            for filename in ['INPUT_MANIFEST.json', 'offline_gt.npz']:
                if (source / filename).exists():
                    copy_file(source / filename, 'candidate/data/' + window + '/' + filename)
    for path in sorted((TASK / 'cache').rglob('*RECEIPT*.json')):
        copy_file(path, pathlib.Path('candidate/cache_receipts') / path.relative_to(TASK / 'cache'))

    # The frozen export audit enumerates tracked source blobs, not downloaded
    # submodule examples or datasets. Preserve exactly those reviewed blobs.
    source_audit = read(TASK / 'reports/SOURCE_AND_ASSET_AUDIT_V2.json')
    omitted_source_assets = []
    for entry in source_audit['export_git_blob_checks']:
        assert entry['match']
        relative = pathlib.Path(entry['path'])
        if relative.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.pdf'} or 'dataset/splits/' in relative.as_posix():
            omitted_source_assets.append(entry)
            staged_copy = (REVIEW / 'source_reference/DROID-W' / relative).resolve()
            assert staged_copy.is_relative_to(REVIEW.resolve())
            if staged_copy.is_file():
                staged_copy.unlink()  # Only this unpublished staging copy.
            continue
        copy_file(ROOT / 'upstream/DROID-W' / entry['path'], 'source_reference/DROID-W/' + entry['path'])
    save('SOURCE_EXPORT_PACKAGE_SELECTION.json', json.dumps(dict(
        audited_git_blobs=len(source_audit['export_git_blob_checks']),
        copied_blobs=len(source_audit['export_git_blob_checks'])-len(omitted_source_assets),
        omitted_upstream_media_and_dataset_splitlists=omitted_source_assets,
        original_export_unchanged=True), indent=2))
    for path in ['LICENSE', 'README.md', 'src/depth_video.py', 'src/geom/__init__.py']:
        copy_file(ROOT / 'upstream/DROID-Splat' / path, 'source_reference/DROID-Splat/' + path)
    refs = {
        'controller.py': pathlib.Path('D:/aaa/GameCam-VO-TASK011B/experiments/TASK011B/CADP_DR_EXPERIMENTAL_BRANCH/controller.py'),
        'reliability.py': pathlib.Path('D:/aaa/GameCam-VO-TASK011B/experiments/TASK011B/scripts/reliability.py'),
        'frozen_r2.yaml': pathlib.Path('D:/aaa/GameCam-VO-TASK011B/experiments/TASK011B/configs/frozen_r2.yaml'),
        'offline_eval_reference.py': pathlib.Path(evidence['scorer_source']),
    }
    for name, path in refs.items():
        copy_file(path, 'source_reference/GameCam-VO/' + name)
    for path in sorted((ROOT / 'toolchain/native_api_compat').rglob('*')):
        if path.is_file() and path.suffix in {'.cu', '.cpp', '.h', '.hpp'}:
            copy_file(path, pathlib.Path('toolchain/native_api_compat') / path.relative_to(ROOT / 'toolchain/native_api_compat'))

    rows = result['results']
    table = '\n'.join(
        f"| {r['arm']} | {r['ate_sim3_rmse']:.6f} | {r['ate_se3_rmse']:.6f} | "
        f"{r['rpe1_translation_rmse']:.6f} | {r['rpe15_translation_rmse']:.6f} | "
        f"{r['ate_sim3_change_vs_BASE_percent']:+.2f}% | {r['raw_path_ratio']:.4f} |"
        for r in rows
    )
    a5 = next(r for r in rows if r['arm'] == 'A5')
    both = next(r for r in rows if r['arm'] == 'SCALE_A5')
    worse_vs_a5 = 100 * (both['ate_sim3_rmse'] / a5['ate_sim3_rmse'] - 1)

    fits = list(csv.DictReader((TASK / 'evaluation/SCALE_FITS.csv').open(encoding='utf-8-sig')))
    fit_summary = []
    for arm in ['SCALE', 'SCALE_A5']:
        all_fit = [f for f in fits if f['arm'] == arm]
        accepted = [f for f in all_fit if f['accepted'] == 'True']
        assert accepted and all(float(f['after_mae']) <= float(f['before_mae']) + 1e-9 for f in accepted)
        fit_summary.append(dict(arm=arm,records=len(all_fit),accepted=len(accepted),
                                minimum_support=min(int(f['valid_pixels']) for f in accepted),
                                all_accepted_map_mae_nonincreasing=True))
    save('SCALE_ACTIVITY_SUMMARY.json', json.dumps(fit_summary, indent=2))

    save('FINAL_REVIEW.md', f'''
# 本地 DROID-Splat 尺度校正迁移：最终评审

日期：2026-11-28（Asia/Shanghai）。状态：**LOCAL_PILOT_COMPLETE / SCALE_CANDIDATE_NOT_PROMOTED**。

**已在本地 RTX 5060 8GB 完成四组真实 DROID-W 推理和离线评分。当前 scale-only 校正没有改善这个窗口；A5 最好。远端 TASK011E-R4 未连接、未查询、未修改。**

## 结果

VIPER **Train / Day004 / RGB1658–1721**，64 帧、stride=1、seed43。Camera1657–1720。
所有平移指标使用 VIPER 游戏单位，**未建立米制单位**。ATE 越低越好。
完整轨迹只拟合一个全局 Sim3 尺度；RPE 使用该全局尺度，不对各个区段另拟合。

| 组 | Sim3 ATE | SE3 ATE | 平移 RPE1 | 平移 RPE15 | Sim3 ATE 相对 BASE | 原始路径/GT |
|---|---:|---:|---:|---:|---:|---:|
{table}

SCALE+A5 的 Sim3 ATE 相对 A5 上升 **{worse_vs_a5:.2f}%**。四组均完整输出 64 个位姿，保留 52 个关键帧，**关键帧 ID 完全相同**（Jaccard=1）。
这次窗口不支持“新增尺度校正改善当前 Baseline”的假设，不能据此否定完整 DROID-Splat 系统，或推广至其他环境。

![全局对齐轨迹及逐帧误差](candidate/evaluation/FOUR_ARM_TRAJECTORIES.png)

## 接入了什么

参考 DROID-Splat 固定源码 `f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2` 中 `linear_align_prior` 和加权尺度/偏移求解，移植**固定相机、估计地图对齐的逐帧 disparity scale-only**。shift 固定为 0。
候选对原始 Metric3D disparity 计算尺度，在独立 BA 调用中使用校正先验，不累计修改原始先验。
只作用于 Frontend Main-loop Local BA；初始化、第二阶段初始化、Final BA、Filler 走原生路径。
原生 U/UBA 保持；A5 仅改变深度正则强度，不改几何 UBA 权重。完整公式和作用范围见 [IMPLEMENTATION_AND_MATH.md](IMPLEMENTATION_AND_MATH.md)。

**这不是完整 DROID-Splat 复现**：没有 Gaussian mapping、JDSA、偏移优化或完整交替优化。把先验对齐到估计地图，也不等于恢复物理米制尺度。

## 拟合实际生效与负结果

SCALE_002 有 1260 条拟合记录、561 条通过；SCALE_A5_002 有 1260 条、562 条通过。记录数不是独立实验样本。
所有通过的拟合都降低了同一支持区域上的先验—地图 disparity MAE，但最终轨迹更差。
因此，当前结果说明**更贴合内部估计地图，不足以保证轨迹更接近 GT**。地图误差反馈和稀疏支持可能有关，但本轮未证明唯一因果机制。
部分单帧拟合仅有 1～2 个有效像素；300 像素门槛是全地图门槛。这是明确的估计稳定性局限，未在看到 GT 结果后追加阈值调参。

## 本地运行的共同条件

DROID-W 源码固定 `c3414af6047d06bafc1a6645d09f23247f3b2cdc`，原权重、K、Metric3D、DINO、原生 Tracker/Final BA/Filler 保留。
本地使用已有 WSL Python3.10、PyTorch2.7.1+cu128，buffer=96，单进程 Tracker，缓存公共 prior/features；关闭在线 Viewer。
64 帧加 Filler 16 槽没有容量淘汰。该本地协议不替代远端 buffer500 正式协议。
Metric3D 可选 xFormers 注意力在本地 sm120 不兼容，运行时替换为 SDPA；所有组相同，不能声称与远端 cu118 逐位等价。
显存峰值 allocated 约 5.302GiB，reserved 约 6.355～7.078GiB。该量不包含整台桌面的所有显存。

## 验证与尝试完整性

- CPU 数学、控制边界与离线评分测试：**36/36 PASS**。
- 冻结导出源码：**208 个 Git blob 核验通过**，CRLF 差异已明确记录。
- 与既有 full-sequence 评价程序交叉核验：**32 个字段全部一致**。
- A5 首个真实 Local BA 状态上，原安装扩展重复、候选关闭、全 1 强度端点：**21 项容差比较通过**，最大绝对差约 4.77e-7。这是单状态局部验证，不是全场景 Native 等价证书。
- 共享三份 Checkpoint 与原安装 CUDA 扩展 SHA-256 保持一致。
- 共 8 次 Tracker 尝试：2 次失败、2 次完整但尺度未激活、4 次正式完整对照。全部日志保留，见 [ATTEMPT_ACCOUNTING.md](ATTEMPT_ACCOUNTING.md)。

初始 Day001 近静止窗口无法初始化；统一改用历史已验证有运动的 Day004。Day004 首次运行因显存碎片 OOM，后续各组统一启用 expandable_segments。
第一版尺度组因门槛适用范围错误而全部回退单位尺度；在轨迹评分之前按官方源码修正，只重跑两组尺度候选。未激活轨迹也公开评分，未混入正式结果。

## 研究决定与边界

**保留 A5 与原始 BASE，本候选封存，不接入生产 Baseline，不扩大实验。**
只有一个 Train 开发窗口、一个 seed，没有置信区间或跨环境泛化结论。这里报告总轨迹效果，未冻结 BA 中间输入做因果重放。
如果后续获批准继续，优先在已有状态上检查尺度拟合支持和地图误差反馈；先确定可辨识的尺度约束，不能直接以当前地图替代真实尺度。当前不自动开发偏移/JDSA，不启动新序列。

## 完整审查入口

- [数学和接入](IMPLEMENTATION_AND_MATH.md)
- [本地兼容与协议差异](LOCAL_RUNTIME_COMPATIBILITY.md)
- [全部尝试](ATTEMPT_ACCOUNTING.md)
- [来源与许可证](SOURCE_PROVENANCE.md)
- [局限和下一步](LIMITATIONS_AND_NEXT_STEP.md)
- [精确指标 CSV](candidate/evaluation/FOUR_ARM_METRICS.csv)
- [最终证据核验](candidate/reports/FINAL_EVIDENCE_VALIDATION.json)
- [归档范围](PACKAGE_CONTENTS.md)；全部文件由 `SHA256_MANIFEST.csv` 覆盖。

本阶段在本地完成。没有读取远端运行状态，因此不对服务器当前进度作判断。
''')

    save('IMPLEMENTATION_AND_MATH.md', r'''
# 实现与数学

## 对应源码

上游：DROID-Splat `src/depth_video.py:591`、`:440`、`:660` 与 `src/geom/__init__.py:159`。
本地：`candidate/src/scale_alignment.py`、`scale_controller.py`；A5 来源位于 `source_reference/GameCam-VO/`。

令 p 为原始 Metric3D 逆深度，d 为当前 BA 估计逆深度，v 为有效支持。固定相机，只拟合 s，偏移为零：

\[
s^*=\arg\min_s\sum_p v_p(s p_p-d_p)^2
=\frac{\sum_p v_p p_p d_p}{\sum_p v_p p_p^2},\qquad \widetilde d_m=s^*p.
\]

归约使用 float64，输出回原生 float32。s 非有限、s<0.05、分母退化或支持不足时回退 s=1，不根据 GT 选 s。
逆深度乘 s 对应深度除 s。每次从原始先验生成校正副本，禁止累乘，原始 `mono_disps` 不改写。

支持条件：native depth_filter 的至少 2-view 支持、阈值 0.05；d>1e-3、d>0.01*帧均值；对应边权先按边均值再取 xy 范数>0.1；排除最新候选关键帧。depth_filter 只看到有效帧，未用 buffer 槽不计支持。
先检查选定地图总支持>=300，再对各帧有正分母的支持拟合。门槛作用范围和置信度归约经过 V3 源码修正。
这里用 DROID-W 原生对应边权近似 DROID-Splat 的 tracker confidence，属于迁移适配，不是完整上游数据流复制。
同一输入帧首次 eligible BA 拟合，后续 BA 复用该帧拟合，下一输入帧重新拟合。不是把所有 BA 内部迭代改成尺度优化。

## 四组与 BA 方程

| 组 | 先验 | 强度 a |
|---|---|---|
| BASE | 原始 d_m | 1 |
| A5 | 原始 d_m | 原有 ValidityAwareMax |
| SCALE | s*d_m | 1 |
| SCALE_A5 | s*d_m | 原有 ValidityAwareMax |

A5 的系数从原始 depth、native confidence、flip disagreement 计算，不因 scale 拟合重新校准。
它保持 TASK011B 的零效应端点与部分强度插值：

\[
C=C_g+(m a)\alpha+(1-m a)\eta,\quad
b=b_g-(m a)\alpha(d-\widetilde d_m),\quad \alpha=\gamma_{depth}=0.01.
\]

m 是原生有效先验掩码；BASE/SCALE 使用 a=1，A5 使用原有系数。a=0 恢复原生无先验 eta 阻尼，a=1 恢复有效先验正则。
**A5 降低强度时也改变该插值下的深度曲率与 eta 分支，不能描述成只乘 residual。** 原始 BA 数学没有在生产扩展中改写；独立 A5 扩展复用既有 TASK011B 实现。
UBA 几何对应权重、U 更新开关、原生 Schur 消元、阻尼、Pose/Disparity retraction 保持原有路径。SCALE 不增加新的 CUDA BA 算术。

## 作用范围与恢复

实例级代理只允许 `FRONTEND_MAIN_LOOP_LOCAL_BA` 且 metric_depth_reg=True、motion_only=False 时介入。
初始化/第二阶段初始化、Final Global BA、Trajectory Filler、Online Global BA 透传安装的原扩展；未知阶段停止。
本轮 Online Global BA 和 mapping 原本关闭，未为了对照打开。Final BA 沿用原生 7+12 外层调用及其暂时关闭 metric_depth_reg 的流程。
Tracker/Frontend 自然选择关键帧，没有强制固定选择；事后发现四组关键帧 ID 相同。图边与状态仍可能不同，因此不主张纯固定状态效应。

## 与完整 DROID-Splat 的差异

本轮只借用固定 Pose 地图对齐与加权 LS 思路，改成 scale-only；没有 affine shift、联合 depth/scale 求解、完整交替优化、上采样 confidence 存储或 3DGS mapping。
官方 `linear_align_prior` 自身也提示地图对齐与 optical-flow 目标不同，不保证正确的单目尺度。
本轮结果不能被标为 DROID-Splat 系统的复现成绩。
''')

    save('LOCAL_RUNTIME_COMPATIBILITY.md', '''
# 本地运行环境与共同协议差异

仅使用本地 RTX5060 8GB；远端连接、资源变更与服务变更均为0。
Windows 控制入口 `D:\\aaa\\envs\\gamecam-vo\\python.exe`；实际 Linux CUDA 运行环境为已有 WSL `/home/lsuser/.local/share/gamecam-vo/envs/droid-w/bin/python3.10`。
Python3.10.22、PyTorch2.7.1+cu128、CUDA12.8、sm120。没有安装驱动或修改原共享环境。

| 项目 | 本地共同处理 | 可比性限制 |
|---|---|---|
| 输入 | 原始1920×1080，原生预处理到640×360，stride1 | K 来自准确窗口 Manifest，加载后与 tracker 内参核对 |
| buffer | 所有组96 | 最多64输入+16 filler槽，没有淘汰；不等同于服务器500槽协议 |
| 进程 | 原生Tracker单进程 | 不复现服务器spawn/GUI调度开销 |
| Metric3D | sm120不兼容可选xFormers，运行时改用SDPA | 权重/预处理/归一化不改，浮点后端不同 |
| FiT3D | pretrained=False创建同结构，严格加载完整fine-tuned checkpoint | 跳过会被完整checkpoint覆盖的基础权重下载，所有key匹配 |
| prior/features | 各模型顺序生成公共缓存，运行时按帧取回 | 避免8GB中模型和BA同时常驻；正式计时不包含公共缓存生成 |
| A5扩展 | 单独构建local_a5_splat_c3414af6 | 仅候选兼容副本更新dispatch API与头文件搜索，未替换安装扩展 |
| allocator | expandable_segments:True，所有正式组一致 | Day004首次BASE因碎片OOM，失败完整保留 |
| Viewer | 本地关闭在线Viewer | 不影响/不查询远端可视化；最终派生图完整保存 |

本地安装扩展来自既有依赖树43c1425b；已与c3414af6原生CUDA源码比较，BA算术相同，差异为旧PyTorch `.type()` dispatch API到`.scalar_type()`。
候选A5原文与本地构建兼容副本分别保留。不要把本地构建等价检查推广为远端所有配置的逐位一致。

四组Tracker+FinalBA+Filler计时约BASE63.66s、A567.32s、SCALE57.81s、SCALE_A559.19s。
A5计时包含4次端点核验BA；公共缓存生成未计入，因此这些数据不能作为稳定的速度改进结论。
allocated峰值约5.302GiB；reserved分别为6.355/6.746/7.078/6.863GiB。reserved不是Windows桌面总显存。

三份共享checkpoint、安装的原扩展SHA最终一致；208份源码按Git blob/LF归一化核验。
最初SOURCE_AND_ASSET_AUDIT.json的byte-exact=false源于CRLF，V2记录预期Git blob与LF归一化匹配；两份报告均保留，不隐藏最初告警。

所有新代码、编译产物、数据副本和缓存位于D盘。原始源码工作树、权重与原安装扩展未修改。
''')

    status = {
        'BASE_001': ('FAILED_INITIALIZATION', 'Train Day001近静止；64帧仅1个关键帧。'),
        'BASE_002': ('FAILED_GPU_OOM', 'Day004初始化后factor-removal相关性复制OOM；随后统一改allocator。'),
        'BASE_003': ('PRIMARY_COMPLETE', '正式BASE。'),
        'A5_001': ('PRIMARY_COMPLETE', '正式A5，包含单状态端点核验。'),
        'SCALE_001': ('INACTIVE_COMPLETE', '1260条拟合全部单位回退，保留轨迹且单独评分。'),
        'SCALE_A5_001': ('INACTIVE_COMPLETE', '同上；不算有效尺度消融。'),
        'SCALE_002': ('PRIMARY_COMPLETE', 'V3源码门槛修正后561条拟合通过。'),
        'SCALE_A5_002': ('PRIMARY_COMPLETE', 'V3源码门槛修正后562条拟合通过。'),
    }
    records = []
    for name, (state, why) in status.items():
        attempt = read(TASK / 'outputs' / name / 'ATTEMPT.json')
        fallback_window = 'train_001_00309-00372' if name == 'BASE_001' else 'train_004_01658-01721'
        records.append(dict(attempt=name,status=state,window=attempt.get('window', fallback_window),
                            arm=attempt.get('arm', name.rsplit('_', 1)[0]),reason=why))
    with (REVIEW / 'ATTEMPT_ACCOUNTING.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    attempt_table = '\n'.join(f"| {r['attempt']} | {r['status']} | {r['reason']} |" for r in records)
    save('ATTEMPT_ACCOUNTING.md', f'''
# 全部Tracker尝试

共8次，4次纳入正式四组对照，2次失败，2次完整但尺度未激活。未把失败或未激活运行删除或替换成成功记录。

| Attempt | 状态 | 说明 |
|---|---|---|
{attempt_table}

Day001改窗与统一allocator修正发生在有效四组比较之前。源码V3修正发生在任何ATE/RPE比较评分之前，依据官方norm和全地图300像素门槛，不根据GT选参数。
旧版controller、runner及测试保留于 `candidate/evidence/controller_v2_noop`。V3 active运行另存runtime_source_snapshot。

未激活的SCALE_001 Sim3 ATE为1.107686，较BASE约-1.50%；SCALE_A5_001为0.763890，较A5约+0.605%。
这些是观察到的同类输入数值差异，**不是正式独立重复，也不是噪声置信界**，详见INACTIVE_CANDIDATE_ATTEMPTS.csv。
为审查保留common prior smoke、模型兼容和编译失败日志；这些不是额外完整轨迹比较。正式对照只有本表4次PRIMARY_COMPLETE。
''')

    save('SOURCE_PROVENANCE.md', '''
# 来源和许可证

所有官方引用固定提交，链接不依赖main后续变化。

| 资产 | 固定来源 | 本轮用途 |
|---|---|---|
| DROID-Splat | https://github.com/ChenHoy/DROID-Splat/tree/f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2 | 固定Pose的尺度/偏移LS及过滤思路；本轮只用尺度 |
| 先验对齐实现 | https://github.com/ChenHoy/DROID-Splat/blob/f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2/src/depth_video.py#L591 | linear_align_prior、全地图支持门槛、正尺度保护 |
| confidence归约 | https://github.com/ChenHoy/DROID-Splat/blob/f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2/src/depth_video.py#L440 | 边均值，再对xy向量取范数 |
| 加权LS | https://github.com/ChenHoy/DROID-Splat/blob/f0cb0316e1ee7f88f8a63c37a6fe19dd623e6eb2/src/geom/__init__.py#L159 | 独立scale-only特例及CPU测试 |
| DROID-W | https://github.com/MoyangLi00/DROID-W/tree/c3414af6047d06bafc1a6645d09f23247f3b2cdc | 冻结Tracker、Frontend、原生BA、FinalBA与Filler |

包内 `source_reference/DROID-Splat/LICENSE` 与 `source_reference/DROID-W/LICENSE` 保留各自Apache2.0正文。
原作者信息及版权以对应原文件为准，保留原始声明。本地adaptation不主张原作者实现了本轮候选。
A5控制、reliability.py和冻结R2 YAML来自GameCam-VO TASK011B，原样副本及SHA清单放入source_reference/GameCam-VO。
本地A5构建保留CUDA源与API兼容副本，编译.so不发布。

208项DROID-W源文件使用Git blob审计；包内选择代码、配置和许可证，省略上游媒体/示例图片和数据split清单；清单见SOURCE_EXPORT_PACKAGE_SELECTION.json。第三方依赖源码借用本机已有只读目录。
官方源码链接仅用于出处；本轮精度证据来自独立输出、轨迹和离线评分，不能用官方论文结论替代本轮验证。
''')

    save('LIMITATIONS_AND_NEXT_STEP.md', '''
# 局限与后续研究边界

**结论：当前候选不晋升。** 单独尺度与尺度+A5都没有改善当前Train Day004窗口，A5最好。

1. 只在Train单窗口、seed43比较；不是Validation成绩，没有n=3重复、显著性或跨环境证明。
2. 这次最终关键帧ID相同，但对应图、更新状态和浮点轨迹不固定；不能把结果写成同状态直接因果效应。
3. 这里只借用DROID-Splat的地图对齐和LS；没有完整仿射偏移/交替优化/3DGS，不能视作系统复现。
4. 地图本身可能带偏，尺度拟合支持很稀疏；拟合误差下降不保证独立GT误差下降。
5. scale乘逆深度意味着改变先验参考尺度；单位和绝对物理尺度未被独立建立。
6. A5系数仍针对原始Metric3D+TTA信号，不针对校正后深度重算；组合负结果可能包含信号与先验不匹配，尚未验证。
7. 本地SDPA、cu128、buffer96、缓存和单进程属于共同本地协议，不能直接与远端buffer500绝对成绩合并。
8. 原生CUDA/U路径有浮点波动；本地只做一个状态的有界端点容差检查，未建立全序列确定性。
9. 每次拟合的MAE、BA事件和像素不是独立统计重复；不对数千个事件作显著性推断。

如果之后另获批准，建议先审查已保存的支持像素数量、尺度与内部地图漂移，提出固定状态对照，检验是否需要稳健性与尺度锚定。
不要立即增加shift/JDSA、替换模型或按本轮GT挑门槛。先明确可以否证的机制假设，再决定是否重跑。
本次不自动扩窗、加seed、改候选、不接入生产、不访问远端。
''')

    save('PACKAGE_CONTENTS.md', '''
# 评审包范围

包含：最终中文报告、实现/公式/兼容说明；候选Python与CUDA源、测试；原始/修订协议；36项真实测试日志；四组结果和图；全部8次Tracker输出与失败日志；未激活候选旧源快照；BA调用日志、关键帧/前端/最终轨迹、端点对照数组；common-cache哈希收据；208项冻结上游blob核验记录及其中的代码/配置/许可证、DROID-Splat关键源码；原A5/reliability/评分器参考源。上游媒体和示例图片、dataset splitlists不发布，选择记录单独保存。

为了复算离线指标，还保留64帧Camera pose派生的offline_gt.npz小型评价fixture和输入ID/CRC/SHA Manifest；不含原始Camera CSV归档或RGB像素。
这些派生fixture只用于审查评分，推理进程没有读取GT。

排除：原始RGB、原始数据集ZIP、模型权重、庞大深度/特征缓存、环境/驱动二进制、编译.so、凭据、SSH配置、其他实验结果。
因此本包可独立复算离线评分、检查候选实现；完整重新推理仍需要原始数据、获许可的模型权重和兼容本地环境。

所有展开文件由SHA256_MANIFEST.csv覆盖，清单不含自身以避免循环。ZIP内成员与展开目录一一对应；外部ZIP SHA和CRC结果另附。
发布到独立codex评审分支，不改默认分支、不覆盖远端实验，也不改变仓库公开状态。
''')
    save('REVIEW_START_HERE.md', '''
# 审查入口

先读FINAL_REVIEW.md，再检查四组精确CSV、ATTEMPT_ACCOUNTING、数学与兼容说明。所有失败和未激活尝试都保留。
本轮是local RTX5060四组64帧pilot，结果为当前scale-only候选未改善。不要把该结果当成整个DROID-Splat方法的结论。
SHA256_MANIFEST.csv覆盖完整展开材料；完整ZIP保留相同文件。
CPU测试36/36、32字段评分交叉核验、单状态21项端点核验均来自真实执行记录。
远端TASK011E-R4没有任何操作；本包不报告远端进度。
''')

    files = sorted(p for p in REVIEW.rglob('*') if p.is_file())
    blocked_suffixes = {'.pth', '.pt', '.ckpt', '.safetensors', '.so', '.pyd', '.dll', '.exe', '.jpeg', '.jpg'}
    for path in files:
        if path.suffix.lower() in blocked_suffixes:
            raise RuntimeError('Excluded asset slipped into review: ' + str(path))
    save('ARCHIVE_SCOPE_AUDIT.json', json.dumps(dict(
        contains_raw_rgb=False, contains_model_weights=False, contains_compiled_extensions=False,
        contains_credentials=False, contains_derived_camera_fixture=True,
        remote_connections=0, remote_changes=0, frozen_droid_w_blobs=208,
        completed_primary_runs=4, failed_tracker_attempts=2, inactive_complete_attempts=2,
        cpu_tests=36, scoreboard_crosschecks=32, endpoint_checks=21,
    ), indent=2))
    files = sorted(p for p in REVIEW.rglob('*') if p.is_file())
    with (REVIEW / 'SHA256_MANIFEST.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream);writer.writerow(['path', 'bytes', 'sha256'])
        for path in files:
            writer.writerow([path.relative_to(REVIEW).as_posix(), path.stat().st_size, digest(path)])
    archive = DELIVERY / ZIP_NAME
    if archive.exists():
        raise FileExistsError(archive)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(p for p in REVIEW.rglob('*') if p.is_file()):
            z.write(path, path.relative_to(REVIEW).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.infolist()) == len(files) + 1
        rows_manifest = list(csv.DictReader(z.read('SHA256_MANIFEST.csv').decode('utf-8').splitlines()))
        for record in rows_manifest:
            content = z.read(record['path'])
            assert hashlib.sha256(content).hexdigest() == record['sha256']
            assert len(content) == int(record['bytes'])
    sha = digest(archive)
    (DELIVERY / (ZIP_NAME + '.sha256')).write_text(sha + '  ' + ZIP_NAME + '\n', encoding='utf-8')
    receipt = dict(review_directory=str(REVIEW), archive=str(archive), bytes=archive.stat().st_size,
                   sha256=sha, crc_pass=True, manifest_entries=len(files),
                   archive_members=len(files) + 1, internal_sha256_all_pass=True,
                   local_zip_deletion='ONLY_AFTER_PUBLISHED_HASH_VERIFICATION')
    (DELIVERY / 'PACKAGE_VERIFICATION.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()

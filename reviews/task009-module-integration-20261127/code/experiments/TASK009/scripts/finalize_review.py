"""Assemble TASK009's existing evidence. Never starts inference or downloads."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import shutil
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / 'experiments/TASK009'
OUT = EXP / 'outputs'
REVIEW = ROOT / 'reviews/task009-module-integration-20261127'
ORIGINAL = Path('D:/aaa/GameCam-VO')
MIG = ROOT / 'maintenance/STORAGE_MIGRATION_20261127'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write(p, text):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + '\n', encoding='utf-8')


def dump(p, data):
    write(p, json.dumps(data, indent=2, ensure_ascii=False))


def table(rows, fields):
    def fmt(v):
        return f'{v:.6f}' if isinstance(v, float) else str(v)
    return '\n'.join(['| ' + ' | '.join(fields) + ' |',
                      '| ' + ' | '.join(['---'] * len(fields)) + ' |'] +
                     ['| ' + ' | '.join(fmt(row.get(k, '')) for k in fields) + ' |' for row in rows])


def verify_results(rows):
    spec = importlib.util.spec_from_file_location('task009_score', EXP / 'scripts/evaluate_trajectories.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with np.load(OUT / 'native_priors_216x384_r3/offline_gt.npz', allow_pickle=False) as gt:
        ids, truth = gt['rgb_ids'], gt['c2w']
    assert np.array_equal(ids, np.arange(301, 333))
    results = []
    assert len(rows) == 9
    for row in rows:
        folder = OUT / row['run']
        receipt = read(folder / 'receipt.json')
        assert receipt['status'] == 'COMPLETE' and receipt['frames'] == 32
        assert receipt['keyframes'] == 16 and receipt['native_ba_calls'] == 117
        with np.load(folder / 'trajectory.npz', allow_pickle=False) as trajectory:
            assert np.array_equal(trajectory['rgb_ids'], ids)
            recomputed, _, _ = mod.score(trajectory['c2w'], truth, ids)
        errors = {k: abs(v - row[k]) for k, v in recomputed.items()
                  if isinstance(v, (int, float)) and v is not None}
        assert max(errors.values()) < 1e-10, (row['run'], errors)
        results.append({'run': row['run'], 'status': 'PASS', 'pose_count': 32,
                        'recomputed_numeric_fields': len(errors), 'maximum_absolute_difference': max(errors.values()),
                        'trajectory_sha256': sha(folder / 'trajectory.npz')})
    return results


def prepare():
    rows = read(OUT / 'evaluation_final/results.json')['results']
    verification = verify_results(rows)
    dump(EXP / 'intake/final_metrics_recalculation.json', {'status': 'PASS', 'runs': verification,
         'method': 'CPU recalculation from all nine original trajectories and the same frozen offline GT; no inference'})
    config = {
        'status': 'DOCUMENTED_EXISTING_RUNS_NOT_A_NEW_EXECUTION',
        'device_tier': 'local RTX5060 exploratory', 'rgb_ids': list(range(301, 333)),
        'height': 216, 'width': 384, 'stride': 1, 'buffer': 64, 'warmup': 6,
        'force_keyframe_every_n_frames': 2, 'seed': 43, 'gamma_depth': .01,
        'native_u': True, 'native_uba': True, 'final_ba_iterations': [7, 12], 'filler': True,
        'online_visualization': False, 'mapping': False,
        'prior_cache': 'experiments/TASK009/outputs/native_priors_216x384_r3',
        'motion_cache': 'experiments/TASK009/outputs/mdtracker_metric_32f_160x280_fp32_r1',
        'conditions': {
            'E0': {'pi3_gate': False, 'static_targets': False},
            'E1': {'pi3_gate': True, 'static_targets': False, 'alpha': 1., 'beta': 1., 'floor': .1},
            'E2': {'pi3_gate': False, 'static_targets': True, 'blend': .15, 'min_visibility': .9, 'max_dynamic': .1},
            'E3': {'pi3_gate': True, 'static_targets': True, 'alpha': 1., 'beta': 1., 'floor': .1},
            'E1_weak': {'pi3_gate': True, 'static_targets': False, 'alpha': .5, 'beta': .5, 'floor': .5},
            'E3_weak': {'pi3_gate': True, 'static_targets': True, 'alpha': .5, 'beta': .5, 'floor': .5},
            'E4': {'status': 'NOT_ADMITTED', 'reason': 'Scene-trained WildGS heads lack validated VIPER feature-domain compatibility'},
            'E5': {'status': 'CANDIDATE_SELECTION_ONLY', 'selected': 'E2', 'independent_validation_run': False}},
        'timing': 'Tracker + final BA + filler + observer after loading; cached prior inference and cold startup excluded',
        'scope': 'Offline future-aware module exploration, not online speed or the sealed formal R2 protocol'}
    dump(ROOT / 'configs/task009/local_exploration.json', config)

    source = r"""
# TASK009 源码、权重和许可证审计

2026-11-27。本轮以独立实验代码完成候选移植，未修改原项目的冻结 DROID-W。
版本与许可证原始文件 SHA 见 `evidence/intake/source_identities.json`；表中的根许可证不是全部依赖或权重的自动授权证明。

| 项目 | 核验版本 | 实际复用模块与接口 | 许可证和迁移判断 |
|---|---|---|---|
| DROID-W / MoyangLi00/DROID-W | c3414af6047d06bafc1a6645d09f23247f3b2cdc | `DepthVideo.ba` 输入 `[1,E,H/8,W/8,2]`；Frontend、Backend、TrajectoryFiller；U 保留 | 根 Apache-2.0；仅独立候选做构建兼容修改，BA 公式未改 |
| π³MOS / PRBonn/Pi3MOS-SLAM | 缓存生成 1b81d729c4259a5a775eb4aae41f959eea38ae14 | TASK008 已生成的 RGB301..332 动态概率、conf、local_points z；本轮读取连续概率 | 当前参考克隆 HEAD 是 c56453704eeff0c0fef673fb4d9282c147889a23，与缓存生成版本不同；未在其根找到许可证，不能推定无条件再分发。只发布自有适配器、统计与派生展示，不复制模型正文/权重 |
| BA-Track / wrchen530/batrack | a66925e1f78b57ae81e2fa02760e37d7fafcb49d | `main/frontend/md_tracker.py:MDTracker.forward`：RGBD `[B,T,4,H,W]`；total_xy、static_xyz、visibility、dynamic_probability | 根 Apache-2.0；官方训练权重 strict 加载。Static 的前三维含图像 x/y 和深度，不能整体当欧氏 XYZ |
| WildGS / GradientSpaces/WildGS-SLAM | 11e85220bf25ba0a27172e5b91453c4b324fd9e8 | `src/utils/dyn_uncertainty/uncertainty_model.py:MLPNetwork.forward`；384 维输入，输出不是校准动态概率 | 根 Apache-2.0；实际使用 WW_A/WW_B 场景训练 head，非随机初始化。eval 下函数式 dropout 仍运行；384 维相同不代表 FiT3D 分布匹配。禁止据此替换原 U |
| Easi3R / Inception3D/Easi3R | 146a77d77c863ddd0bd7a559fa35f69722fc3c50 | DUSt3R 双图 `[B,3,H,W]`；六有向帧对 attention、pts3d、conf；仅抽取外部原函数做聚合/聚类/Otsu | 根 CC BY-NC-SA-4.0；外部隔离，不把正文混入核心。本轮不是完整 Easi3R，不运行 RAFT/SAM2/全局优化 |
| LEAP-VO / wrchen530/leapvo | 7667cf31acc62e27e9278940ce093c6fc95b952a | 作者页 `https://wrchen530.github.io/projects/leapvo/` 指向官方仓库；LEAP kernel 小窗口输出 tracks、vis、cov、dynamic | 根 CC BY-NC-4.0；独立加载，不复制核心、不运行完整 VO、不接入 DROID |

Metric3D 固定 `eb5b6fac0dc155e4e52f576e304fbf11655ff339`（根 BSD-2-Clause）；FiT3D 固定 `18200c21f047b5add8b7e796d6aab97fba25e790`（根 MIT）。
LieTorch 为 archive 导出而非独立 Git repo：`0fa9ce8ffca86d985eca9e189a99690d6f3d4df6`，Eigen `824272cde8ca2541e8b67b0887f5ded92b128d1f`。逐文件身份和完整候选补丁已封存。

## 权重身份

| 权重 | SHA-256 | 使用方式 |
|---|---|---|
| DROID tracker | 46476ef64cde45a97504910d6f3de2eef7b398ec1c6e4e668815c29076024526 | 历史官方原件只读复用，按官方接口裁剪输出头并 strict 加载 |
| Metric3D | 15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972 | 历史官方原件只读复用 |
| FiT3D | 09db495b0788df23591de1bc9ccb721b182dfb511136398a2caed3896a39c8e4 | 历史官方原件只读复用 |
| MDTracker tensor-only | c1189d8d6912798e66b99b3e853ce644f587ed57837a5e7bb768405980dc1422 | 官方文件提取 210 tensor，移除 module. 前缀，strict 加载 |
| WildGS WW_A | fea6b224bdaec5c2ab1138134a8135efb5c71c9d6bc902039c73c203d730badf | 真实场景训练 head，仅迁移探针 |
| WildGS WW_B | ca26e3715eadbcd6bfda144bd599456c3f0ebf5ef6a91d3f711433bb93c652cc | 同上 |
| LEAP kernel | 8bd20f5dde2015748840c509b6dd5b40a78785e06dce5778a35b60749e27c124 | 官方 leap_kernel.pth，strict 加载 |
| DUSt3R | 9f194a32e34fc124ed10f64115b8e848b7da87c2d1ed131d34b4806721c19dbd | 官方 512 DPT checkpoint，strict 加载，128×224 探索输入 |

本轮核对了仓库许可证、权重来源及身份，但不将源码许可证自动等同为每份权重/训练数据的独立许可证。没有单独明确条款者记录为未独立核验，不对外分发权重、外部模型源码或训练数据。

## 实际资源与优先级

MDTracker 32 帧 FP32 的峰值 tensor allocated 0.477 GiB；LEAP 16 帧 0.279 GiB；Easi attention 3 帧 2.211 GiB。
这些测量是各自独立模型前向，不能相加解释为并行驻留需求，也不能预测完整 SLAM 的显存。
迁移顺序为 π³MOS 门控 → MDTracker 静态目标 → WildGS 准入审查 → Easi3R/LEAP 独立验证。
轨迹结果反过来支持优先保留静态目标辅助，而不是模块越多越好。
"""
    architecture = r"""
# TASK009 实际架构与接口

本轮为可运行的独立 Improved DROID-W 候选原型。主干网络、原 U/UBA 和原生 BA 保留；新增逻辑在 `DepthVideo.ba` 前修改观测输入。

```mermaid
flowchart TD
  RGB[匹配的 RGB301..332] --> F[DROID-W 原前端]
  P[π³MOS 历史概率缓存] --> G[DynamicObservationGate]
  M[MDTracker 真实静态轨迹] --> S[StaticTrackCache]
  F --> T[原 target / weight / eta]
  T --> S
  S --> G
  G --> U[原 UBA / U 更新]
  U --> BA[原生 CUDA BA]
  BA --> B[原 Final BA 7+12]
  B --> X[原 Filler 与全帧轨迹]
```

图为两个模块同时启用时的实际调用顺序：静态适配器先改变 target，动态适配器随后在更新后的预测对应位置采样概率。
开关关闭时对应 hook 不安装。E0 两个 hook 都不安装，但仍属于本轮缩小协议而不是旧 R2 复现。

## 动态门控

`gamecam/modules/dynamic_prior/feature_alignment.py:ImageGeometry` 实现像素中心/stride 对齐。
`pi3_adapter.py:Pi3Cache` 根据原始 RGB ID 读取真实连续概率，拒绝身份不一致与非有限值。
`dynamic_mask.py:DynamicObservationGate` 计算 `G=max(floor,(1-Mi)^alpha*(1-Mj)^beta)`，并乘原始 weight。
`droid_adapter.py:install_video_gate` 根据 video.timestamp → 原始 RGB ID 找到两端；Mi 在源特征点采样，Mj 在 target 预测对应坐标采样。
越界采样有显式统计，未将目标帧的同像素位置冒充对应点；原 U 只由原生流程使用，没有重复乘入。
Confidence 只保存/显示，没有经 GT 验证，未偷偷乘入门控。

## 静态辅助

`gamecam/modules/motion_decomposition/droid_adapter.py:StaticTrackCache.observations` 将模型图像 x/y 按半像素 resize 映射到 DROID 图像，再除 stride=8。
两端 visibility≥0.9、dynamic≤0.1、正深度、有限/界内坐标、源点距格点≤0.35 才可使用。
辅助目标为 `cell+(static_xy[b]-static_xy[a])/8`；以 `0.15*quality` 混合现有 target。
每个边/源格点只保留最高质量点，不新增重复边、不修改 weight、eta 或 U。
深度用于无效点筛选；原 K、pose、disparity 继续参与原生重投影 BA。
这是一项二维反事实静态重投影目标实验，不是独立测得的三维位移约束，也不是移植整套 BA-Track 后端。

## 作用范围与时间信息

两个 hook 的实际范围是所有 `video.ba`，包含初始化、Frontend、Final BA、Filler；本轮没有做分阶段隔离。
MDTracker 从完整 32 帧窗口获得离线轨迹，不能宣称因果在线模块或实时系统。
Pi3 缓存身份固定；不启动 TASK008 服务器，不重做模型训练。
强制每2帧关键帧的本地协议使九组均16关键帧，不支持“改善自然关键帧选择”的结论。

## 可重跑入口

统一说明配置：`configs/task009/local_exploration.json`；实际逐组收据与 YAML 优先于该事后汇总。
原生入口 `experiments/TASK009/scripts/run_native.sh` 配置 D: 上独立 WSL 环境。
运行器 `run_droid_window.py` 的 `--gate` 与 `--static-tracks` 可独立开关，alpha/beta/floor 可显式设定。
无需修改生产 DROID-W 或其 YAML 来开关候选。
"""
    compact = []
    for r in rows:
        compact.append({'运行': r['run'], 'Sim3 ATE': r['sim3_ate_game_units'],
                        'SE3 ATE': r['se3_ate_game_units'], 'RPE-t Δ1': r['rpe_translation_offset1_game_units'],
                        'RPE-R Δ1°': r['rpe_rotation_offset1_deg'],
                        '312→328比例': r['312_328_global_scaled_displacement_ratio'],
                        '秒': r['total_seconds'], '峰值allocated GiB': r['peak_allocated_bytes'] / 2**30})
    report = """
# TASK009 实验报告

2026-11-27。状态：**LOCAL_PROTOTYPE_DELIVERED / EXPLORATORY_EVIDENCE_ONLY**。

实际完成9次本地原生 DROID-W 运行；π³MOS Gate 和 MDTracker 静态辅助均真正进入 BA，未以光流探针替代轨迹评价。
本窗口内 E2 静态辅助两次均优于 E0；Gate 与组合均恶化，不能据此宣布多模块组合成功。

## 统一探索协议

- 本地 RTX5060 8GB；Windows Conda torch2.15.0+cu132 用于先验/独立模型，WSL Python3.10/torch2.7.1+cu128 用于 DROID 原生 CUDA 扩展。
- VIPER Night val007 RGB301..332，32帧，stride1；实际是车载视角，不能称第三人称验证。
- 216×384、buffer64、warmup6、强制每2帧关键帧、seed43、gamma_depth0.01。
- 原网络/跟踪器、U/UBA、Final BA 7+12、Filler；每组32/32完整导出、16关键帧、117次原生 BA 调用。
- Metric3D canonical392×700 BF16 生成真实缓存；FiT3D 15×27×384；相同 RGB/K/缓存用于各组，半像素内参同步变换。
- 串行单 tracking 进程，无 Gaussian mapper 或实时 GUI。生成真实观测坐标、权重、轨迹与先验的离线可视化。
- 减小分辨率/缓冲区、先验缓存、warmup/关键帧协议、精度和环境均与正式 R2 不同；不合并旧结果。

## 九次原始结果

平移距离单位为 **VIPER 游戏单位，未证明为米**。每条轨迹仅一个全局 Sim3；RPE 和所有区间共用该尺度，没有逐段拟合。

""" + table(compact, list(compact[0])) + """

E0=无外部 hook；E1=π³MOS Gate；E2=静态目标辅助；E3=两者组合。
weak 的 alpha=beta=0.5、floor=0.5；默认 alpha=beta=1、floor=0.1。
完整旋转、RPE Δ1/5/15、309→325/312→328/301→332、原尺度和方向误差见 `evidence/results/evaluation_final/metrics.csv`。

## 研究判断

1. E2 ATE 2.733–3.500 对比 E0 6.497–6.619，且 RPE-t Δ1 1.228–1.424 对比 2.142–2.276；312→328 全局缩放位移比约1.020–1.023，对比0.846–0.873。支持在本窗口继续研究静态目标约束。
2. E1 ATE8.923，E3两次13.954–14.685；弱门控也未超过 E0。动态门控在这里没有轨迹收益，组合存在明显运动压缩。没有逐项因果隔离，不能把恶化直接归因为 Mask 错误、某一 BA 阶段或数值条件性。
3. 全局尺度仍很大，E0/E2的 Sim3 scale约717–798，SE3 ATE约15。形状改善不等于恢复物理米制尺度。
4. 所有32帧有有限 pose，只证明导出覆盖率100%，不是动态检测准确率或跨序列跟踪成功率。
5. 同seed重复结果不逐位一致；本轮没有隔离原生求解器波动来源。样本小、参数探索、相同窗口复用，不计算显著性或泛化置信区间。
6. E2/E3 r2使用批量 CUDA 适配器；同输入3次CUDA检查均与标量实现逐位相等。整条 SLAM 的重复性仍不能据此保证。

## 耗时定义

表中时长包含加载之后的跟踪、Final BA、Filler 和观测记录，不含 Metric3D/Pi3/MDTracker 缓存推理、模型加载与冷启动。
E2初版71.55秒→批量版12.33秒，E3初版79.95秒→23.57秒。只有适配器同输入计算已逐位核验，不能把这几次端到端耗时视为严格性能基准。
峰值为 PyTorch tensor allocated，不含其他进程和整套桌面/驱动显存；reserved 在各 receipt 中保留。

## 其他模块实际结果

| 模块 | 完成范围 | 时间 / 峰值allocated | 研究限制 |
|---|---|---|---|
| MDTracker | 8/16/32帧独立推理；用于 E2/E3 的32帧160×280、100点、FP32 | 1.648秒 / 0.477GiB | 使用Metric3D预测深度，非官方UniDepth管线；预测有越界/负深度，接入前筛选 |
| WildGS | 2份真实scene-trained head，4图×4seed | 见原收据 | eval仍随机dropout；特征域未验证，输出非校准动态概率；E4不准入 |
| Easi3R attention | RGB301/312/325、6有向帧对、BF16前向/FP32聚合，cluster64+Otsu | 1.635秒前向 / 2.211GiB | 不是完整Easi3R；注意力Mask大片覆盖路面，存在静态误判风险；无GT不能报准确率 |
| LEAP | 16帧128×224、64点、FP32；tracks/vis/cov/dynamic有限 | 0.835秒 / 0.279GiB | 不是完整LEAP-VO；未接入DROID，无轨迹增益证据 |

Easi动态比例约0.122/0.136/0.053是阈值面积统计，不是检测准确率，也不是校准概率。
没有训练新模型，没有额外真实场景数据实验，没有证明雨雪/白天/第三人称泛化。

## E0–E5 完成矩阵

| 组 | 状态 |
|---|---|
| E0 | 2次真实原生轨迹 |
| E1 | 默认1次+弱门控1次，均无本窗口收益 |
| E2 | 2次真实原生轨迹，本窗口最值得保留 |
| E3 | 默认2次+弱门控1次，均劣于E0 |
| E4 | NOT_ADMITTED：WildGS场景权重未获跨域准入，不替换原U |
| E5 | 暂选E2作为候选；没有伪造独立E5运行或最终组合结论 |

## 失败与修复

原生构建r1–r4失败日志保留，r5成功：适配ATen dtype接口、sm120编译、include路径；未改BA数学。
torch_scatter wheel因GLIBC不兼容，改从官方未变Python正文加载sum/mean，它们本来使用torch.scatter_add_；不是自行更换求和公式。
先验r1/r2有导入/API故障；r2已产出的32份深度逐个SHA核验后由r3复用，再完成FiT3D，不改旧收据。
MDTracker早期16帧较大输入未完成（目录无完整终态收据，控制台曾出现主机内存/LLVM错误，未保留完整stderr）；降低尺寸后16/32帧成功。不把失败目录计入成功。
Easi首次因缺scikit-learn在建输出前失败；补齐依赖后r2成功。日志保留。

## 下一步建议，不自动执行

固定E2当前参数，在未用来选型的Night与非夜间窗口验证；恢复自然关键帧策略并做分阶段hook消融。
同时检查静态目标筛选、前瞻信息和各段运动压缩。真实场景与第三人称仍是未来验收要求。
Gate先独立检查目标采样/Mask可靠性与BA作用阶段，勿默认纳入最终组合；WildGS、Easi和LEAP不因独立推理成功就准入主算法。
"""
    changes = r"""
# TASK009 代码、环境和复现说明

新增代码在 `gamecam/modules/dynamic_prior`、`gamecam/modules/motion_decomposition`、`gamecam/compat`；运行/评价/可视化/证据收集脚本与23项CPU测试在 `experiments/TASK009`。
统一配置位于 `configs/task009/local_exploration.json`。归档内 `code/` 是交付时自有代码快照。
原工作区6份用户dirty文件SHA全部保持；详情见保护收据。没有执行reset、clean或stash，没有连接远端。

## 候选上游差异

外部DROID-W候选只变更构建sm120、ATen `.scalar_type()`分派和未使用DepthAnythingV2的延迟导入。
LieTorch的ATen兼容、构建路径和仅核心扩展的构建变更单独以完整patch公开；未替换原生产二进制。
`src/lib/droid_kernels.cu` BA求解公式不变。单纯编译成功不代表跨环境数值等价。
两个算法hook完全在自有代码中运行，不复制第三方后端。

## 实际环境与依赖

Windows现有Conda迁到 `D:\aaa\envs\gamecam-vo`，Python3.11.18、torch2.15.0+cu132/torchvision0.29.2+cu132。
新加独立模型所需omegaconf/einops/timm/evo/roma/scikit-image/scikit-learn等；安装前后快照在证据目录，pip check通过。
DROID原生运行库单独在D盘 `runtime/wsl310`（torch2.7.1+cu128）及 `runtime/cuda128`；Python3.10.18。
本地驱动与其他Conda环境没有改动。代码、运行库、环境、缓存、临时文件和结果均写D；Windows/WSL发行版根盘/驱动/分页文件未整体迁移。
环境与缓存共107416文件两端SHA核验；evo配置另2文件核验；C旧路径通过Junction兼容。

## 重跑命令

以下命令会新建输出，**本轮交付后没有自动再执行**。需先按来源收据恢复外部repo、权重与本地RGB/先验；公开ZIP不含这些资产。
路径对应本机独立worktree，换机器须修改run_native.sh与运行器显式输入根；不要用旧结果目录作为新输出。

```powershell
# CPU合同检查，不启动模型
Set-Location D:\aaa\GameCam-VO-TASK009
& D:\aaa\envs\gamecam-vo\python.exe -m unittest discover -s experiments/TASK009/tests -v

# E0 / E1 / E2 / E3，用全新的输出目录
wsl -d Ubuntu -- bash /mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/scripts/run_native.sh experiments/TASK009/scripts/run_droid_window.py --priors experiments/TASK009/outputs/native_priors_216x384_r3 --output experiments/TASK009/outputs/NEW_E0
wsl -d Ubuntu -- bash /mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/scripts/run_native.sh experiments/TASK009/scripts/run_droid_window.py --priors experiments/TASK009/outputs/native_priors_216x384_r3 --gate --output experiments/TASK009/outputs/NEW_E1
wsl -d Ubuntu -- bash /mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/scripts/run_native.sh experiments/TASK009/scripts/run_droid_window.py --priors experiments/TASK009/outputs/native_priors_216x384_r3 --static-tracks experiments/TASK009/outputs/mdtracker_metric_32f_160x280_fp32_r1 --output experiments/TASK009/outputs/NEW_E2
wsl -d Ubuntu -- bash /mnt/d/aaa/GameCam-VO-TASK009/experiments/TASK009/scripts/run_native.sh experiments/TASK009/scripts/run_droid_window.py --priors experiments/TASK009/outputs/native_priors_216x384_r3 --gate --static-tracks experiments/TASK009/outputs/mdtracker_metric_32f_160x280_fp32_r1 --output experiments/TASK009/outputs/NEW_E3
```

不安装hook即可回到**本地探索E0**，不是宣称复现旧正式R2。原生产分支/冻结扩展始终保留，无需回滚。
独立MDTracker、WildGS、Easi与LEAP入口及其参数均在 `code/experiments/TASK009/scripts`；对应实际配置保存在statistics/receipt。

## 公开交付边界

公开：自有代码、候选patch、配置、9组完整小型轨迹/关键帧/BA观测/日志、独立模型小型预测、评价/派生可视化、来源/保护/迁移收据。
不公开：权重、安装环境、二进制扩展、原始RGB、原始GT、32份大先验数组、107416文件的完整本机迁移清单以及包含临时下载链接的日志。
省略物的路径/大小/SHA写入 `LOCAL_ONLY_ARTIFACTS.csv`，不是伪称公开包含全部本地文件。
早期运行未在receipt写自有source SHA，保存的初版runner/静态adapter及后续同输入逐位核验作为补充；不追写旧receipt、不伪称每次都有完整提交身份。
"""
    documents = {'TASK009_SOURCE_AUDIT.md': source, 'TASK009_ARCHITECTURE.md': architecture,
                 'TASK009_EXPERIMENT_REPORT.md': report, 'TASK009_CODE_CHANGES.md': changes}
    for name, content in documents.items():
        write(ROOT / 'docs' / name, content)

    # This final check is intentionally CPU/file based, with no CUDA or model imports.
    checks = []
    for legacy, target in [
        ('C:/Users/Administrator/.conda/envs/gamecam-vo', 'D:/aaa/envs/gamecam-vo'),
        ('C:/Users/Administrator/.cache/huggingface', 'D:/aaa/caches/huggingface'),
        ('C:/Users/Administrator/.cache/torch', 'D:/aaa/caches/torch'),
        ('C:/Users/Administrator/.conda/pkgs', 'D:/aaa/caches/conda_pkgs'),
        ('C:/Users/Administrator/AppData/Local/pip/cache', 'D:/aaa/caches/pip'),
        ('C:/Users/Administrator/.evo', 'D:/aaa/caches/evo')]:
        actual = Path(legacy).resolve()
        assert str(actual).lower() == str(Path(target).resolve()).lower()
        checks.append({'legacy': legacy, 'target': str(actual), 'matches': True})
    disk = {drive: {'free_bytes': shutil.disk_usage(drive).free} for drive in ('C:/', 'D:/')}
    dump(EXP / 'intake/final_storage_check.json', {'status': 'PASS', 'links': checks, 'disk': disk,
         'sample_note': 'Finalization-time sample, not migration-time free-space estimate',
         'windows_driver_pagefile_and_wsl_distro_root_moved': False})
    final = """
# TASK009 最终评审

2026-11-27。**可运行候选原型已交付；仅完成单窗口探索，没有建立泛化版 Improved DROID-W 的性能结论。**

- 本地RTX5060完成9次真实DROID-W、原生BA/Final BA/Filler；每次32/32帧、16关键帧。
- E0 Sim3 ATE 6.497–6.619；E2静态辅助2.733–3.500。E1门控8.923，E3组合13.954–14.685；弱门控也未优于E0。
- 位移比例和RPE同时支持本窗口优先保留E2；仍需独立窗口/场景验证。距离是游戏单位，不是米；没有恢复米制尺度的证明。
- 23项CPU合同测试、3次同输入CUDA向量化逐位对照、9份轨迹指标CPU复算通过。它们不证明原生BA确定性或跨设备数值等价。
- MDTracker/Easi attention/LEAP真实独立推理已完成；WildGS使用真实场景权重但未通过跨域准入。E4未运行；E5只是候选选择，不伪造新实验。
- 用户要求的环境/缓存/临时存储已迁D；107416文件SHA一致，旧路径Junction兼容；evo另2文件核验。WSL发行版根盘和系统文件未整体搬迁。
- 原基线、原权重、历史结果、6份用户dirty文件保护核验一致；没有远程操作、训练、重启或关机。

优先阅读：

1. [实验报告](TASK009_EXPERIMENT_REPORT.md)
2. [实际架构和作用范围](TASK009_ARCHITECTURE.md)
3. [来源与许可证](TASK009_SOURCE_AUDIT.md)
4. [代码变更/重跑方法](TASK009_CODE_CHANGES.md)
5. [原始评价表](evidence/results/evaluation_final/metrics.csv)
6. [完整交付范围](DELIVERY_SCOPE.md)

本包包括完整的小型运行证据与自有代码；权重/数据集/大型先验留本地，详见省略清单。
下一阶段建议冻结E2参数并在未用于选型的窗口验证，而非继续在当前窗口调参。
**本轮已停止推理，不自动扩展至新的数据、种子或正式服务器实验。**
"""
    write(EXP / 'FINAL_REVIEW.md', final)
    return rows, documents, final


def assemble(rows, documents, final):
    REVIEW.mkdir(parents=True, exist_ok=False)
    for name, content in documents.items():
        write(REVIEW / name, content)
    write(REVIEW / 'FINAL_REVIEW.md', final)
    copied = []

    def copy(src, rel):
        src = Path(src)
        dest = REVIEW / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append({'source': str(src), 'published': str(rel), 'bytes': src.stat().st_size, 'sha256': sha(src)})

    for directory in (ROOT / 'gamecam', EXP / 'scripts', EXP / 'tests'):
        for p in sorted(directory.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py', '.sh', '.ps1'):
                copy(p, Path('code') / p.relative_to(ROOT))
    copy(ROOT / 'configs/task009/local_exploration.json', Path('code/configs/task009/local_exploration.json'))
    copy(ROOT / 'scripts/run_gamecam_local.py', Path('code/scripts/run_gamecam_local.py'))
    intake = EXP / 'intake'
    for p in sorted(intake.iterdir()):
        allowed = p.name.startswith(('cpu_tests_', 'droid_E', 'native_build_', 'native_core_smoke', 'native_full_smoke',
                    'native_priors_r', 'evaluation_', 'static_vectorization_', 'easi_attention_', 'mdtracker_16f_r2',
                    'mdtracker_32f_r1', 'mdtracker_metric_', 'leap_16f_', 'wildgs_head_probe'))
        allowed |= p.name in {'source_identities.json', 'protected_user_files.json', 'protected_user_files_after.json',
            'native_prior_checkpoint_provenance_supplement.json', 'droid_candidate_compatibility.patch',
            'lietorch_candidate_compatibility.patch', 'lietorch_archive_source_identity.json', 'native_source_preparation.json',
            'easi_dependencies_before.json', 'windows_dependencies_final.json', 'windows_pip_before.txt',
            'run_droid_window_r1.py.txt', 'static_adapter_r1.py.txt', 'final_metrics_recalculation.json', 'final_storage_check.json',
            'cuda128_package_inventory.json', 'mdtracker_weight_receipt.json', 'leap_weight_receipt.json', 'easi_weight_receipt.json'}
        if allowed and p.is_file():
            copy(p, Path('evidence/intake') / p.name)
    selected = [r['run'] for r in rows] + ['evaluation_final', 'visualization_r1', 'gpu_gate_probe_r1',
        'mdtracker_8f_fp32', 'mdtracker_16f_160x280_fp32_r2', 'mdtracker_32f_128x224_fp32_r1',
        'mdtracker_metric_32f_160x280_fp32_r1', 'wildgs_scene_trained_probe_r1',
        'leap_16f_128x224_fp32_r1', 'easi_attention_3f_128x224_r2']
    for name in selected:
        for p in sorted((OUT / name).rglob('*')):
            if p.is_file():
                copy(p, Path('evidence/results') / p.relative_to(OUT))
    copy(OUT / 'native_priors_216x384_r3/receipt.json', Path('evidence/priors/receipt.json'))
    for name in ['MIGRATION_REPORT.md', 'environment_migration_complete.json', 'cache_migration_complete.json',
                 'environment_verified.json', 'environment_cuda_verified.json', 'huggingface_verified.json',
                 'torch_verified.json', 'conda_pkgs_verified.json', 'pip_verified.json', 'evo_config_migration.json']:
        copy(MIG / name, Path('evidence/storage') / name)

    # Original raw assets are identified, never added to the publication tree.
    local = []
    for directory in [OUT / 'native_priors_216x384_r3', ROOT / 'external/weights']:
        for p in sorted(directory.rglob('*')):
            if p.is_file() and p.name != 'receipt.json':
                local.append({'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p),
                              'reason': 'Local model weights or large prior/raw GT; excluded from public delivery'})
    for p in sorted(MIG.glob('*.files.jsonl')):
        local.append({'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p), 'reason': 'Large local migration inventory'})
    with (REVIEW / 'LOCAL_ONLY_ARTIFACTS.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['path', 'bytes', 'sha256', 'reason'])
        w.writeheader(); w.writerows(local)
    dump(REVIEW / 'EVIDENCE_COPY_RECEIPT.json', copied)
    write(REVIEW / 'DELIVERY_SCOPE.md', r"""
# 交付范围与证据等级

本包是TASK009完整的可公开评审包：4份报告、自有适配器/运行器/测试、9组实际轨迹与关键帧/BA观测/日志、评价表、独立模型小型输出、派生可视化、候选源码patch、来源/保护/迁移收据。
不是完整实验硬盘镜像。为保护原始数据、权重和凭据，不包含原始RGB、GT文件、模型权重、环境或扩展二进制、大先验缓存及大迁移清单。需复现者按来源身份在授权本机恢复。
带RGB的联系表是少量派生研究展示，不是原始RGB数据集。原始与派生输出均未被重新包装成动态准确率GT。
`LOCAL_ONLY_ARTIFACTS.csv`列出本轮外部权重、大先验和迁移清单的身份；原始RGB/旧权重的SHA另见prior receipt与provenance supplement。
下载/安装的原始日志留本地，公开干净收据和版本快照，避免发布临时签名下载链接。

直接观察：原生轨迹、权重/target输入、推理输出、运行时间、显存、SHA。
数值验证：23CPU合同、3个同输入CUDA向量化对照、9组指标CPU复算。
探索结论：当前窗口E2较好，E1/E3较差。
尚未验证：跨场景泛化、第三人称、米制尺度、Mask准确率、自然关键帧机制、因果在线性、正式R2数值等价、最终E5独立验证。
不把GPU过程成功解释为论文复现成功或通用算法提升。

内部SHA清单覆盖除自身之外全部文件；Review ZIP的外部SHA单独存放，避免自引用。
""")
    # Do not ship access-bearing links or credentials. Generic source identifiers are fine.
    patterns = [re.compile(x, re.I) for x in (
        r'gh[pousr]_[A-Za-z0-9]{20,}', r'github_pat_[A-Za-z0-9_]{20,}',
        r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
        r'Authorization\s*[:=]\s*[\"\x27]?(?:Bearer|Basic)\s+[A-Za-z0-9+/=_-]{12,}',
        r'https?://[^\s\"<>]+[?&](?:X-Amz-Signature|X-Goog-Signature|token|access_token|auth)=',
        r'https?://[^/\s:@]+:[^/\s@]+@')]
    findings = []
    for p in REVIEW.rglob('*'):
        if p.is_file() and p.suffix.lower() in {'.py', '.sh', '.ps1', '.md', '.txt', '.json', '.jsonl', '.yaml', '.log', '.csv', '.patch'}:
            content = p.read_text(encoding='utf-8', errors='replace')
            for index, pattern in enumerate(patterns):
                if pattern.search(content):
                    findings.append({'path': p.relative_to(REVIEW).as_posix(), 'pattern_index': index})
    # The scanner's own regex source contains only patterns, never real secret values.
    assert not findings, findings
    dump(REVIEW / 'PUBLICATION_CONTENT_AUDIT.json', {'status': 'PASS', 'findings': findings,
         'scope': 'Explicit allowlist plus credential/access-bearing URL scan; model weights/raw dataset/runtime omitted',
         'no_repository_visibility_change': True})
    entries = []
    for p in sorted(REVIEW.rglob('*')):
        if p.is_file():
            entries.append({'path': p.relative_to(REVIEW).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)})
    with (REVIEW / 'SHA256_MANIFEST.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['path', 'bytes', 'sha256']); w.writeheader(); w.writerows(entries)
    delivery = ROOT / 'deliveries'
    delivery.mkdir(exist_ok=True)
    package = delivery / 'GAMECAM_TASK009_REVIEW.zip'
    if package.exists():
        raise FileExistsError(package)
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(REVIEW.rglob('*')):
            if p.is_file():
                z.write(p, p.relative_to(REVIEW).as_posix())
    with zipfile.ZipFile(package) as z:
        assert z.testzip() is None
        for row in entries:
            assert hashlib.sha256(z.read(row['path'])).hexdigest() == row['sha256']
        count = len(z.infolist())
    write(delivery / 'GAMECAM_TASK009_REVIEW.zip.sha256', f'{sha(package)}  {package.name}')
    dump(delivery / 'TASK009_PACKAGE_VERIFICATION.json', {'status': 'PASS', 'zip_crc': 'PASS',
         'members': count, 'internal_sha256_verified': len(entries), 'zip_bytes': package.stat().st_size,
         'zip_sha256': sha(package), 'expanded_review': str(REVIEW)})
    print(json.dumps({'review': str(REVIEW), 'zip': str(package), 'bytes': package.stat().st_size,
                      'members': count, 'internal_sha256_verified': len(entries), 'sha256': sha(package)}, indent=2))


if __name__ == '__main__':
    assemble(*prepare())

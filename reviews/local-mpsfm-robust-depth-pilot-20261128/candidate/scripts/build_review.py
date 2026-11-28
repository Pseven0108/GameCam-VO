"""Seal complete source/results evidence. No credentials, RGB or checkpoints."""
import csv,hashlib,json,pathlib,shutil,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[2];TASK=ROOT/'candidate'
NAME='local-mpsfm-robust-depth-pilot-20261128';REVIEW=ROOT/'review'/NAME
ZIP='GAMECAM_LOCAL_MPSFM_ROBUST_PILOT_REVIEW.zip';DEL=ROOT/'deliveries'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,text):
    p=REVIEW/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text.strip()+'\n',encoding='utf-8')
def copy(src,dest):
    p=REVIEW/dest;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p)
def main():
    if REVIEW.exists():raise FileExistsError(REVIEW)
    REVIEW.mkdir(parents=True);DEL.mkdir(exist_ok=True)
    result=json.loads((TASK/'evaluation/RESULTS.json').read_text());rs=result['results'];by={r['arm']:r for r in rs}
    tests=json.loads((TASK/'reports/FINAL_CPU_TEST_RESULTS.json').read_text())
    if len(rs)!=4 or not tests['passed']:raise RuntimeError('Incomplete evidence')
    for folder in ['src','scripts','tests','native','configs','reports','outputs','evaluation','data']:
        for p in sorted((TASK/folder).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts:continue
            if p.suffix.lower() in {'.pth','.pt','.so','.pyd','.pyc','.jpg','.jpeg','.ckpt','.safetensors'}:raise RuntimeError('Unexpected excluded asset '+str(p))
            copy(p,'candidate/'+p.relative_to(TASK).as_posix())
    copy(ROOT/'bootstrap.py','bootstrap.py');copy(ROOT/'README.md','CANDIDATE_README.md')
    for p in (ROOT/'toolchain/native_api_compat').glob('*'):
        if p.is_file() and p.suffix in {'.cpp','.cu'}:copy(p,'build_source/'+p.name)
    prev=ROOT.parent/'GameCam-VO-DROID-SPLAT-CANDIDATE/candidate'
    for n in ['depth_RECEIPT_064.json','features_RECEIPT_064.json']:
        copy(prev/'cache/train_004_01658-01721'/n,'common_cache_receipts/'+n)
    export=[]
    for p in sorted((ROOT/'upstream/DROID-W').rglob('*')):
        if not p.is_file():continue
        n=p.relative_to(ROOT/'upstream/DROID-W').as_posix()
        selected=p.suffix.lower() in {'.py','.cu','.cpp','.h','.hpp','.yaml','.yml','.md','.json'} or p.name in {'LICENSE','requirements.txt','.gitmodules'}
        export.append(dict(path=n,sha256=sha(p),included=selected))
        if selected:copy(p,'source_reference/DROID-W/'+n)
    save('SOURCE_EXPORT_PACKAGE_SELECTION.json',json.dumps(export,indent=2))
    selected=json.loads((TASK/'reports/STAGING_RECEIPT.json').read_text())['selected_source_files']
    for rec in selected:copy(ROOT/'upstream/mpsfm'/rec['path'],'source_reference/MP-SfM/'+rec['path'])
    base=ROOT.parent/'GameCam-VO-TASK011B/experiments/TASK011B'
    for source,n in [('CADP_DR_EXPERIMENTAL_BRANCH/controller.py','controller.py'),('scripts/reliability.py','reliability.py'),('configs/frozen_r2.yaml','frozen_r2.yaml')]:
        copy(base/source,'source_reference/GameCam-VO/TASK011B/'+n)
    scorer=ROOT.parent/'GameCam-VO/experiments/VIPER_FULLSEQ_FRESH_OFFICIAL_DUAL_3090_20261120_061408/pipeline/offline_eval.py'
    copy(scorer,'source_reference/GameCam-VO/established_offline_eval.py')
    table='\n'.join(f"| {r['arm']} | {r['ate_sim3_rmse']:.6f} | {r['ate_se3_rmse']:.6f} | {r['rpe1_translation_rmse']:.6f} | {r['rpe15_translation_rmse']:.6f} | {r['keyframes']} |" for r in rs)
    save('FINAL_REVIEW.md',f'''# 本地 MP-SfM 风格鲁棒深度约束：最终评审

2026-11-28，GameCam-VO。**结论：当前迁移候选没有改善本窗口，不能替代 A5 或晋升生产 Baseline。**

本地 RTX5060 8GB 已实际完成四组独立 DROID-W 64帧推理。仅 Cauchy 对原版
Sim3 ATE 增加 **{by['ROBUST']['ate_change_vs_BASE_percent']:.2f}%**；
Cauchy+A5 对 A5 增加 **{by['ROBUST_A5']['ate_change_vs_A5_percent']:.2f}%**。数值越低越好。
这是特定迁移、参数与开发窗口的负结果，不能写成 MP-SfM 原系统无效。

## 输入与四组成绩

VIPER **Train / Day004 / RGB1658–1721**，Camera1657–1720；seed43、stride1、640×360。
每组都导出64个有限的最终Pose，Final BA 与 Filler 完整执行，无失败重跑、无参数搜索。
平移单位为 **VIPER 游戏单位**，没有建立真实米制。

| 组别 | Sim3 ATE RMSE | SE3 ATE RMSE | RPE1 平移 | RPE15 平移 | 保留关键帧 |
|---|---:|---:|---:|---:|---:|
{table}

每条轨迹只做一次完整窗口全局 Sim3 对齐；RPE沿用这个尺度，不逐段重新拟合。
BASE/A5关键帧ID完全一致，两个鲁棒组各少1674、1696两帧，保留50帧。
因此本轮比较的是完整前端反馈效果，并非固定输入图的纯直接因果效应。

## 实际接入的数学模块

官方 MP-SfM commit：`fa49640862391437865b2fd89ca3db3e6948b63b`。
借用 Cauchy 深度鲁棒化和以相对不确定性定义损失尺度的思路。
原官方调用使用 log-depth；本实验明确保留 DROID-W 的线性 disparity 残差并重新推导。
没有复制完整 SfM、MAD、深度积分、截断法向损失、跨视图遮挡筛选或尺度修正。

`q=1/(1+((d-dm)/tau)^2)`，`tau=max(0.1*abs(dm),1e-6)`。
0.1在评分前固定为官方 Metric3D-large相对噪声下限0.05乘rob_std2。
它是迁移参数，不是已经校准的VIPER置信区间。原始目标dm不变。

`C=Cg+m*a*alpha*q+(1-m*a)*eta`

`b=bg-m*a*alpha*q*(d-dm)`，`alpha=0.01`。

a是A5系数或1。q只改变prior曲率和梯度，**不改变eta分支**。
每个原生内部迭代重算q，保留双迭代、U/affine/temp反馈及原Schur求解器。
仅干预Frontend Main-loop Local BA；初始化、Final BA、Filler调用原安装扩展。
详见[MATH](candidate/reports/MATHEMATICAL_DERIVATION.md)与[实现](IMPLEMENTATION_AUDIT.md)。

## 为什么这次值得保留为负证据

两个鲁棒组的估计路径长度/GT路径长度仅为{by['ROBUST']['raw_path_ratio']:.4f}、{by['ROBUST_A5']['raw_path_ratio']:.4f}，
相应全局Sim3尺度为{by['ROBUST']['global_sim3_scale']:.4f}、{by['ROBUST_A5']['global_sim3_scale']:.4f}。
SE3误差同样更高，说明不仅是对齐口径差异。
观测到约75%/80%的事件像素q小于0.1，先验大量降权并伴随轨迹压缩。
这与弱化尺度牵引的解释相容，但没有像素深度GT或固定状态反事实，不能证明错误来自哪个深度位置。
这些重复BA事件不是独立统计样本，不给出伪造显著性。

## 验证与资源

- {tests['tests']}/{tests['tests']} CPU测试真实通过。
- 208个冻结源码Git blob、3份共享权重、原安装扩展哈希前后保持一致。
- 16个原有CUDA kernel函数正文逐一一致；新数学只在独立候选BA装配处实现。
- 一个真实BA状态的21项Native端点比较通过；另有7项A5兼容比较、4项CPU/GPU公式比较通过。
- 两个鲁棒组各保存双迭代72,000位置，q/C/b逐元素通过独立CPU float64复算。
- 32个实际轨迹评分字段与既有全序列评分器完全一致。
- 峰值PyTorch张量分配约{max(r['peak_allocated_GiB'] for r in rs):.3f}GiB，峰值预留约{max(r['peak_reserved_GiB'] for r in rs):.3f}GiB。
  预留不是整机显存测量，也不表示其他模型必然适合8GB。
- BASE耗时包含额外端点检查；所有组使用缓存，耗时不能当作完整模型端到端速度排名。

独立WSL本地运行环境为PyTorch2.7.1+cu128/sm120；使用已有环境，不安装新依赖或改驱动。
共用buffer96、单进程Tracker与缓存先验，这些与远端cu118/buffer500正式协议不同。
**服务器TASK011E-R4未连接、未检查、未更改。**

## 决策

工程实现与小规模实验完成；当前候选研究准入为 **NO_PROMOTION**。
保留原版与A5，不覆盖生产代码。没有继续调tau、换窗口、加seed或扩大正式实验。
后续若另获授权，应先解释强降权和尺度约束的关系，而非把这个负结果包装成改善。

完整源码、四组日志、逐轮证据、轨迹、评分快照和SHA清单均在本包。
''')
    save('IMPLEMENTATION_AUDIT.md','''# 实现与独立性审计

候选实现位于candidate/native/droid_kernels.cu的robust_prior_terms_cuda和BA itr循环。
所有16个原生__global__ kernel正文与既有A5候选逐字一致；BA的C/b装配有预期修改，
不得将build记录中的kernel_arithmetic_changed=False误读为“BA公式完全未改”。
原安装扩展没有被替换。以独立名称local_mpsfm_robust_c3414af6编译。
correlation/altcorr只做PyTorch dispatch API的type→scalar_type兼容替换。

robust_controller.py限定MAIN、非motion-only、metric prior开启的调用。
未知或缺失阶段停止；初始化、Final BA、Filler均直通原版。
REAL_STATE_IRLS_ORACLE.json和FIRST_ROBUST_NATIVE_STATE.npz提供逐元素核查。
完整原生两轮迭代保留；没有将两轮拆成独立调用。

A5的coefficient_map来自原TASK011B ValidityAwareMax，使用同一深度、Flip和confidence缓存。
A5作用于深度先验，不将其描述为UBA几何权重。q与a相乘只用于先验项；阻尼始终(1-ma)eta。
没有Scale/Shift、物体mask或GT回流。GT fixture只被离线评分器读取。

端点证据仅涵盖一个真实状态的容差验证，原生U atomic累加仍可能数值波动；
不宣称整个系统逐位确定或与远端正式环境等价。
''')
    save('LOCAL_RUNTIME_AND_ATTEMPTS.md','''# 本地运行与尝试登记

四次Tracker尝试：BASE_001、A5_001、ROBUST_001、ROBUST_A5_001，全部首次完成，无自动重试。
额外6次双迭代BA仅用于同状态端点诊断，不是新的轨迹重复；另有一次合成GPU prior公式检查。
GPU前的第一次只读preflight因WSL PATH未含nvidia-smi失败，指定已有绝对路径后完成核验。
保留PREFLIGHT_LOG.txt及PREFLIGHT_LOG_002.txt，未改驱动、共享环境或算法。

沿用上一轮local buffer96、单进程Tracker、固定原始K、缓存原生深度/特征、cu128/sm120。
64输入外加16个Filler临时槽不会耗尽96槽；无buffer淘汰。原正式协议buffer500没有被改写。
Metric3D/DINO缓存复用相同原生预处理和此前声明的本地SDPA数值后端；本轮未重新推理这两个模型。
GUI未启动，以控制8GB共驻显存。图表来自完成后的离线结果。

run_four_arms.py固定串行顺序；算法参数和窗选择在PROTOCOL.json评分前封存。
所有原始日志、配置、轨迹、关键帧状态、逐轮权重、Endpoint数组完整保留。
本轮没有SSH、服务器进程修改或关机动作。
''')
    save('SOURCE_PROVENANCE.md','''# 官方来源与迁移范围

- [MP-SfM论文，CVPR2025](https://openaccess.thecvf.com/content/CVPR2025/papers/Pataki_MP-SfM_Monocular_Surface_Priors_for_Robust_Structure-from-Motion_CVPR_2025_paper.pdf)：C_reg使用Cauchy；C_int中的其他深度/法向项使用截断损失。本实验只取前者思想。
- [官方BA源码](https://github.com/cvg/mpsfm/blob/fa49640862391437865b2fd89ca3db3e6948b63b/mpsfm/sfm/mapper/bundle_adjustment.py#L22)：depth_loss_name=cauchy、rob_std=2；约L159-L176计算逐点损失尺度并使用logloss=True。
- [官方Metric3D-large配置](https://github.com/cvg/mpsfm/blob/fa49640862391437865b2fd89ca3db3e6948b63b/configs/defaults/m3dv2-large.yaml#L9)：相对噪声下限0.05。
- [官方depth.py](https://github.com/cvg/mpsfm/blob/fa49640862391437865b2fd89ca3db3e6948b63b/mpsfm/sfm/scene/image/depth.py#L75)：融合模型方差与相对噪声下限；这里没有迁移全套方差和绝对单位项。
- [Ceres2.2.0 CauchyLoss实现](https://github.com/ceres-solver/ceres-solver/blob/2.2.0/internal/ceres/loss_function.cc)：rho(s)=c²log(1+s/c²)，rho'=1/(1+s/c²)。本原型独立推导IRLS，不运行Ceres。
- [冻结DROID-W](https://github.com/MoyangLi00/DROID-W/tree/c3414af6047d06bafc1a6645d09f23247f3b2cdc)。

MP-SfM已从官方仓库新克隆，HEAD核验固定，未执行pip install、下载其模型或运行SfM。
source_reference保留选定源码、各自Apache2.0 LICENSE及原作者声明。
迁移不是官方实现的二进制复制，也不主张原作者实现了本轮candidate。
DROID-W208项blob审计及打包选择清单可复核；媒体/示例/模型资产不发布。
''')
    save('LIMITATIONS_AND_NEXT_STEP.md','''# 局限与研究边界

本候选不晋升，单窗口下仅Cauchy和Cauchy+A5都差于各自对照。
不能由此推断所有Cauchy、全部参数或MP-SfM完整系统无效。

1. 一个Train开发窗口和一个seed，没有跨场景、重复方差或显著性证据。
2. 前端关键帧变化，估计对象为完整反馈效果，不是同状态直接效应。
3. 官方使用log-depth与不确定性，迁移采用原生disparity和固定相对尺度；小扰动传播近似对严重错误不精确。
4. 没有公开准入的逐像素深度GT，不能识别被降权的prior究竟正确还是错误。
5. 鲁棒权重很小可能削弱尺度约束；这里只观察到关联，未分解深度/位姿/图结构因果链。
6. q不进入eta分支是刻意隔离；与启发式a*q同时更改阻尼不是同一个算法。
7. 单先验无几何时鲁棒IRLS仍可能完整走向prior，有界梯度不构成更新步长硬上限。
8. buffer96、单进程、缓存和cu128为共用本地8GB执行条件，不与远端285次成绩合并。
9. 数千次事件和数百万次像素访问不是独立实验重复，不能拿来做虚假显著性。

后续如另获授权，可先用已保存状态提出尺度牵引/阻尼的可证伪假设，再决定是否需要新的固定状态对照。
本轮不自动调参、不扩大窗口、不启动服务器或生产集成。
''')
    save('PACKAGE_CONTENTS.md','''# 完整评审包范围

包含：中文最终评审、数学推导、实现审计、原协议；候选Python/CUDA源码与构建源码；
37项CPU测试日志；全部四次Tracker的配置、日志、逐轮权重、前端/最终关键帧状态与64Pose轨迹；
真实状态IRLS详表、端点复放数组、评分器交叉验证、图表、完整SHA256清单；
固定上游来源与许可证、A5和既有评分器参考源码、缓存hash收据。

小型offline_gt.npz是64帧相机Pose的派生评分fixture，供审查者复算评分，不含原始RGB或Camera ZIP。
不含模型权重、JPEG、完整数据集、庞大深度/特征cache、环境二进制、编译.so、凭据和SSH配置。
可独立复算CPU指标和检查源码；重新做Tracker推理仍需要合法数据与权重、兼容环境。
共用依赖和缓存由既有本地只读路径引用，不将整个本地环境打包。

SHA256_MANIFEST.csv覆盖全部其他成员，避免自引用。完整ZIP和展开材料内容相同。
发布独立codex评审分支，不改仓库可见性/默认分支，不覆盖历史结果；核验后仅删除本轮本地交付ZIP。
''')
    save('REVIEW_START_HERE.md','''# 从这里开始评审

先读FINAL_REVIEW.md。当前迁移没有改善，A5在本批最好。
检查candidate/evaluation/FOUR_ARM_METRICS.csv、原协议、数学公式、真实状态oracle，
再检查源代码差异和全部attempt日志。不要将本次结果写成MP-SfM系统复现或跨域泛化结论。
服务器TASK011E-R4未触碰，本包不报告其当前进度。
''')
    manifest=[]
    for p in sorted(REVIEW.rglob('*')):
        if p.is_file():manifest.append(dict(path=p.relative_to(REVIEW).as_posix(),bytes=p.stat().st_size,sha256=sha(p)))
    with (REVIEW/'SHA256_MANIFEST.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);w.writeheader();w.writerows(manifest)
    archive=DEL/ZIP
    if archive.exists():raise FileExistsError(archive)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(REVIEW.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(REVIEW).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise RuntimeError('Archive CRC failed')
        for r in manifest:
            b=z.read(r['path'])
            if len(b)!=r['bytes'] or hashlib.sha256(b).hexdigest()!=r['sha256']:raise RuntimeError('Internal hash failed')
        members=len(z.infolist())
    digest=sha(archive)
    (DEL/(ZIP+'.sha256')).write_text(digest+'  '+ZIP+'\n')
    receipt=dict(review_directory=str(REVIEW),archive=str(archive),bytes=archive.stat().st_size,sha256=digest,
        crc_pass=True,manifest_entries=len(manifest),archive_members=members,internal_sha256_all_pass=True,
        local_zip_deletion='ONLY_AFTER_VERIFIED_PUBLICATION')
    (DEL/'PACKAGE_VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()

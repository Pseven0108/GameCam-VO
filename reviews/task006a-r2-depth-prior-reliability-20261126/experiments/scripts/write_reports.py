"""Write the R2 partial research review, preserving observed evidence and absent results."""
import csv, hashlib, json, pathlib, textwrap

ROOT = pathlib.Path(__file__).resolve().parents[2]
METRIC = 'eb5b6fac0dc155e4e52f576e304fbf11655ff339'
DROID = 'c3414af6047d06bafc1a6645d09f23247f3b2cdc'
WEIGHT = '15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972'
BASE_URL = 'https://github.com/YvanYin/Metric3D/blob/' + METRIC + '/'


def write(rel, text):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as file:
        file.write(textwrap.dedent(text).strip() + '\n')


def table(rel, rows, fields=None):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def document(rel, text):
    write(rel, text.replace('@METRIC@', METRIC).replace('@DROID@', DROID).replace('@WEIGHT@', WEIGHT))


def main():
    test = json.loads((ROOT / 'experiments/unit_tests_002/CPU_TEST_REPORT.json').read_text(encoding='utf-8'))
    assert test['success'] and test['passed'] == 61
    data = list(csv.DictReader((ROOT / '03_dataset_audit/R2_03_DATASET_MANIFEST.csv').open(encoding='utf-8')))
    assert len(data) == 100
    sums = {key: sum(int(row[key]) for row in data) for key in ['valid_depth_count', 'inf_count', 'nan_count']}
    assert sums == {'valid_depth_count': 45412636, 'inf_count': 6427364, 'nan_count': 0}

    document('README.md', '''
    # TASK006A-R2｜Metric3D 深度先验可信度研究：阶段证据包

    日期：2026-11-26（Asia/Shanghai）。状态：**PARTIAL / WAITING_GPU_AND_GT_ADMISSION**。
    进入联合可信度控制器的决策：**NO-GO — INSUFFICIENT_INDEPENDENT_EVIDENCE**。

    请先读 [最终研究报告](TASK006A_R2_FINAL_RESEARCH_REPORT.md) 和
    [阻断与恢复入口](TASK006A_R2_CODEX_HANDOFF.md)。本包不是完整的 GPU 可信度验证结果。
    61/61 是 CPU 评价器、源代码监督 mask 和数据合同测试，不能当作 Metric3D 准确率。

    已完成：实际模型/权重身份核验、Confidence 生成与监督源码审计、四篇核心论文阅读、
    100 帧真实 RGB/EXR/相机数据审计、300 个 MVS 文件身份复核、投影诊断、独立 CPU 评价器。
    未执行：模型加载、Confidence 数值推理、TTA 推理、真实 bin 分布提取、梯度实验、GT 准确性评价。

    实测远端 nvidia-smi 返回 Exec format error，未确认可用 GPU；没有重启、申请 GPU 或修驱动。
    审计的本地 VIPER 输入没有配套 Dense Depth GT；MVS-Synth 0000 的物理单位尚未建立，
    且只有一条完整序列，不具备序列独立的校准与测试划分。

    所有未测数值 CSV 保留空值和 NOT_EXECUTED 状态；空值不是零误差。
    03_dataset_audit 中的图是真实 GT 审计图，不是预测深度或 Confidence 热力图。

    可复算代码在 experiments/scripts。源代码快照及许可证在 evidence/sources；
    SHA256_MANIFEST.csv 覆盖发布负载，ZIP 内文件原样对应展开目录。
    为避免递归，清单不包含其自身、外部 ZIP 及验证收据；详见 PACKAGE_CONTENTS.md。
    无模型权重、原始数据集或论文全文随包发布。R1 和 Baseline 资产保持封存。
    ''')

    document('00_project_audit/R2_00_PROJECT_STATE_AUDIT.md', '''
    # R2-0 项目与运行身份审计

    **SOURCE_IDENTITY_PASS；MODEL_INFERENCE_BLOCKED。** 本轮只进行了只读远端访问和本地 CPU 工作。

    ## 实际工作区

    本地项目 D:\\aaa\\GameCam-VO；HEAD `388fedf14ab1a071ab9c6955174ff092589300f3`，
    分支 repro/2026-11-01-phase5。已有六个 tracked 修改，见 LOCAL_GIT_STATE.json；没有清理、重置或暂存它们。
    R2 的发布分支独立创建，不改变本地研究分支或远端默认分支。

    只读 SSH 指向 sc01-ssh.gpuhome.cc:30601，使用历史用户确认的 ED25519 指纹并开启严格校验。
    认证和主机身份核验通过。REMOTE_PROBE.stdout.txt 记录当前主机及完整探针。
    nvidia-smi 执行失败（Exec format error）；这不能证明硬件损坏，也不能据此假定当前有 3090。
    数据盘可用 12,522,487,808 bytes，/dev/shm 容量 2 GiB；都是该次探针时的值。
    本轮不将历史 SLAM 的共享内存安全门槛套用到独立 Metric3D 推理。

    ## 模型与配置

    - 基础 DROID-W 冻结身份：@DROID@；实际 metric_depth_estimators.py 与 R0 源码快照逐字节一致。
    - Metric3D 当前实际 hub HEAD：@METRIC@；283/283 个 Git blob 与官方固定提交一致。
    - metric3d_vit_large，ViT Large + RAFTDepthNormalDPT5，8 次迭代。
    - 权重 metric_depth_vit_large_800k.pth，1,647,972,663 bytes，SHA-256：@WEIGHT@。
    - 封存配置 gamma_depth=0.01；本轮没有改动。该参数属于 BA，不参与本轮独立可信度推理。
    - 元数据读取：PyTorch 2.1.0+cu118、torchvision 0.16.0+cu118、NumPy 1.26.4、OpenCV 4.8.1.78、timm 0.9.10。
      这是包元数据证据，不是 CUDA 可执行性测试。未导入模型或反序列化权重。

    生产 hub 调用没有 pin revision，不能用注释 34afafe... 代表运行版本；当前缓存的真实版本已单独锁定并核验。

    ## R1 与历史边界

    读取 R1 最终报告、数学推导、决策与数值局限。R1 完成 CPU float64 几何协方差原型，
    97 项测试和合成端点实验通过，不是实际深度先验可靠性的证明。
    R1 的深度边缘协方差依赖不加 Metric3D 先验的几何系统；R2 研究模型先验本身。
    R1 的不准确先验反例说明必须独立审查先验，不能把几何协方差拿来当先验误差 GT。

    Task003/004/005 的 BA、D/W/U、调度与归约证据是上游动机，不是原生 Confidence 标定数据。
    本轮未加载 C0、R3 张量或旧 SLAM uncertainty 作为可信度标签。
    现有生产入口只保存深度，不保存原生 Confidence；本轮没有找到可用于本任务的已核验 Confidence/TTA 推理收据。
    这一检查覆盖当前指定入口和已审阅证据，不声称扫描了所有历史二进制文件。

    ## 数据流与缺口

    RGB → native resize/normalize/pad → Metric3D → (depth, confidence, output_dict)；
    生产代码只保留 depth → unpad/bicubic/focal scaling/clamp → DROID-W。
    Confidence 在 tuple unpack 时被丢弃。代码行为可确认，作者为何这样设计没有文档证据，记为 UNVERIFIED。
    当前缺口是输出数值实测及独立 GT 误差验证，而不是再一次 SLAM 重跑。
    ''')

    document('01_source_audit/R2_01_METRIC3D_CONFIDENCE_SOURCE_AUDIT.md', '''
    # R2-1 Metric3D 原生 Confidence 源码结论

    **生成与监督路径已确认；实际输出统计未测。** 所有行号对应 @METRIC@ 快照。
    代码保存在 evidence/sources/Metric3D-eb5b6fac，SHA 见 SOURCE_COPY_MANIFEST.json。

    ## 身份与预处理

    283 个实际缓存文件与官方 Git blob 对应；权重 SHA 为 @WEIGHT@。
    DROID-W loader 使用 torch.hub.load("yvanyin/metric3d", depth_model, pretrain=True)，没有 revision 锁定。
    当前真实缓存 HEAD 不能用入口注释中的旧提交代替。

    输入形状 B×3×H×W，ViT Large canonical 616×1064。按 min(616/H,1064/W) resize，整数尺寸，
    ImageNet normalize 后以零填充，左右/上下余数保留。输出深度先移除相同 padding，再 bicubic 到原网格，
    乘实际输入 fx/1000，并 clamp 到 [0,300]。源码在 DROID-W-runtime/metric_depth_estimators.py:121–164。
    这些是现有代码规则，不能根据它自动确定外部 GT 的米制单位。

    ## Confidence 生成链

    1. mono/model/monodepth_model.py:10–13 的 inference 返回 depth、confidence、output_dict；入口使用 no_grad。
    2. decode_heads/RAFTDepthNormalDPTDecoder5.py:915–930：ViT/DPT 的 ref_feat 分解为共享深度/法线特征、
       深度 confidence 初值、normal confidence 初值。深度 confidence 是独立通道。
    3. 同文件 FlowHead:314–327 输出线性增量；959–984 在每次 RAFT 中把增量加入坐标状态，
       其中深度 confidence 与深度共同迭代更新。最后一次（第 8 次）confidence 随最终 depth 返回。
    4. 858–872 的 mask softmax 用于局部凸上采样；983–995 从上采样状态第 1 通道取 depth confidence。
       softmax 不是对最终 confidence 进行概率归一化。GRU 的 sigmoid gate 也不是输出 confidence sigmoid。

    深度 confidence 没有末端 sigmoid/softmax 或固定 [0,1] 约束，不能直接作为正确概率、方差或标准差。
    源码允许无约束实数，但本轮没有推理，不能声称实测有负值、极值、NaN 或 Inf。
    静态预期 canonical 形状 B×1×616×1064；实际 shape、min/max/quantiles 一律待测。
    研究脚本会保存原始 map；恢复到输入网格使用同一 unpad 后 bilinear，避免 bicubic 对 score 额外过冲。
    这是显式研究选择，不冒充上游已有 confidence resize 生产规则。Confidence 不乘 fx/1000。

    ## 训练监督的精确定义

    training/mono/model/losses/GRUSequenceLoss.py:33–37 中，令 t 为 GT target，z 为 prediction：

    M = valid_mask AND (abs(t-z) < t)

    c_target = (1 - abs((z-t)/t)) * M

    L_conf = sum(abs(c - c_target) * M) / (sum(M) + eps)

    误差分母是 GT t。相对误差 >=1 的位置被这项 confidence loss 排除，
    并不是以零 confidence 作为有效监督。有限正 GT 域的独立复算测试确认：改变这些被排除位置的 c，不改变该项 loss。
    这是监督盲区风险，**不是已经观察到测试 Confidence 失败**。其他深度/法线损失仍可能影响共享表示。
    同文件 84–98 逐次迭代应用 confidence loss。

    官方 training 配置列出 GRUSequenceLoss loss_weight=0.5、loss_gamma=0.9、stereo_sup=0.0，
    混合实拍和合成深度数据，法线使用独立 loss。配置不能证明指定 checkpoint 的全部训练历史，
    也不能证明 VIPER 的 Night、Rain、Snow 已充分覆盖。

    ## 四种不确定性必须分开

    | 信号 | 来源/约束 | 本轮允许的解释 |
    |---|---|---|
    | Depth confidence | RAFT 更新的单通道，输出不受 [0,1] 约束 | 待实测的预测质量 score |
    | Normal confidence | normal 输出第四通道，ELU(raw)+1+0.01 等正值变换（237–243） | 法线集中度相关量，不是深度置信度 |
    | DINO/FiT3D U | DROID-W 特征与优化反馈状态 | 不能冒充独立深度误差标签 |
    | R1 几何协方差 | prior-off Schur 系统及原生阻尼 | 几何模型量，不是原生 Confidence GT |

    ## Depth-bin 与输出字典

    同文件 761 显式定义 256 anchors，794–836 为 log 间隔 anchor、logit softmax 和初始深度期望。
    anchor 由真实配置产生，不能用随意线性 bin 代替。实现的 get_bins 硬编码 CUDA；
    本地 CPU-only 且无 Torch 环境不适合伪装成完整官方 CPU 推理。
    最终 output_dict 的 pred_logit=None（987–995），即使前面计算了 binmap。
    独立只读 forward hook 可读取 depth_regressor 输出，必须返回 None 且验证不改变模型输出。

    ## 入口丢弃行为及未决问题

    DROID-W-runtime/metric_depth_estimators.py:150 附近使用 pred_depth, _, _。
    可确认的是没有传播/保存 native Confidence；丢弃的设计理由没有直接证据，不填成 CONFIRMED。
    输出数值审计和真实 heatmap 因 GPU 不可用未执行，见数值 CSV。

    官方固定来源：
    [decoder](https://github.com/YvanYin/Metric3D/blob/@METRIC@/mono/model/decode_heads/RAFTDepthNormalDPTDecoder5.py)、
    [confidence loss](https://github.com/YvanYin/Metric3D/blob/@METRIC@/training/mono/model/losses/GRUSequenceLoss.py)、
    [模型接口](https://github.com/YvanYin/Metric3D/blob/@METRIC@/mono/model/monodepth_model.py)。
    ''')

    numerical_fields = ['environment','sequence','model','execution_status','inferred_samples','min','max','mean','median','standard_deviation','P1','P5','P25','P75','P95','P99','nan_count','inf_count','reason']
    table('01_source_audit/R2_01_CONFIDENCE_NUMERICAL_AUDIT.csv', [dict(environment=env,sequence='',model='metric3d_vit_large',execution_status='NOT_EXECUTED_GPU_UNAVAILABLE',inferred_samples=0,reason='No runtime output; absent statistics are not zero') for env in ['Day','Sunset','Rain','Night','Snow','MVS_UNCLASSIFIED']], numerical_fields)
    document('01_source_audit/visualizations/NOT_EXECUTED.md', '''
    # Confidence 图像未生成
    本轮未加载 Metric3D，没有真实 Confidence、预测 depth 或直方图。
    不使用随机数组、合成结果或旧 SLAM 的 U 代替本次预测图。
    数据集真实 RGB/GT 的审计证据见 03_dataset_audit/R2_03_DATA_ALIGNMENT_EVIDENCE.png。
    ''')

    document('02_literature/R2_02_LITERATURE_REVIEW.md', '''
    # R2-2 文献与适用边界

    阅读的是与本任务有关的 Method、Experiments 和 limitations/conclusion；下述论文结果均是作者报告，
    不是 GameCam-VO 的复现实验。访问路径及全文读取范围见 PAPER_READING_LOG.json。

    ## Metric3D v2

    Mu Hu, Wei Yin, Chi Zhang, Zhipeng Cai, Xiaoxiao Long, Kaixuan Wang, Hao Chen, Gang Yu, Chunhua Shen,
    Shaojie Shen. *Metric3D v2: A Versatile Monocular Geometric Foundation Model for Zero-shot Metric Depth and Surface Normal Estimation*.
    IEEE TPAMI 46(12), 10579–10596, 2024；DOI 10.1109/TPAMI.2024.3444912。arXiv v4 日期是 2025，不能把它当期刊年份。
    [论文](https://arxiv.org/abs/2404.15506)；[官方代码](https://github.com/YvanYin/Metric3D)。
    Canonical camera transformation 配合联合 depth-normal 迭代预测，提供跨相机的零样本几何估计。
    其跨数据集 depth/normal benchmark 支持研究动机，未提供本项目 VIPER confidence 的误差识别或概率校准证书。
    本轮还追踪了实际 ViT Large decoder 和 confidence supervision；init-bin 分布与最终 confidence 是不同信号。

    ## GrUMoDepth

    Julia Hornauer, Vasileios Belagiannis. *Gradient-based Uncertainty for Monocular Depth Estimation*. ECCV 2022。
    [论文](https://arxiv.org/abs/2208.02005)；[官方代码](https://github.com/jhornauer/GrUMoDepth)。
    利用原图与扰动图预测的辅助差异反向传播，读取 decoder 特征梯度并进行通道归约；固定预训练模型即可做后处理，
    不需要重新训练深度模型。其范式约需两次 forward 和一次 backward，成本和梯度层选择依赖网络。
    作者在 Monodepth2、KITTI/NYU 等设置研究 uncertainty ranking；不能把其结果直接转移到 Metric3D/VIPER。
    Metric3D inference 的 no_grad 入口和八轮 RAFT 会增加迁移工作；应在 A/B/C 证据不足后才花费该成本。

    ## Uncertainty from Motion (UfM)

    Soumya Sudhakar, Vivienne Sze, Sertac Karaman. *Uncertainty from Motion for DNN Monocular Depth Estimation*. ICRA 2022，
    DOI 10.1109/ICRA46639.2022.9812222。
    [作者论文页](https://lean.mit.edu/papers/ufm-icra)；[官方代码](https://github.com/mit-lean/ufm)。
    原 PDF 主站 TLS 超时，改由作者页面链接的 CDN 取得 7 页全文（SHA 见 receipt），不是只读摘要。
    方法跨帧投影高斯混合深度分量，循环抽取 ensemble/MC-dropout 成员并增量维护均值方差。
    作者实验涉及 TUM、KITTI、NYU 和多种较小网络；已有模型还需要 aleatoric/ensemble 支持。
    缺少可靠基础方差时效果可差，pose 噪声也改变估计。仓库另注明 ensemble 初始化修正后的结果与原文不同。
    依赖运动与对应关系，适合后续理论参考；本轮不把它作为独立于 R1 的 GT，不运行 UfM。

    ## DepthCov

    Eric Dexheimer, Andrew J. Davison. *Learning a Depth Covariance Function*. CVPR 2023。
    [CVF 论文页](https://openaccess.thecvf.com/content/CVPR2023/html/Dexheimer_Learning_a_Depth_Covariance_Function_CVPR_2023_paper.html)；
    [全文备用](https://arxiv.org/abs/2303.12157)；[官方代码](https://github.com/edexheim/DepthCov)。
    从图像学习非平稳 log-depth GP 协方差，显式保留像素误差相关性，用于稀疏深度条件化及联合优化。
    方法及论文实验说明对角置信图不能表达完整相关性，但这是需要训练的协方差网络，
    不能直接替代 Metric3D score，也不等同于 R1 的优化 Hessian 逆。本任务不训练其网络。
    CVF PDF 访问受限，实际完整方法与实验通过 arXiv HTML 阅读。

    ## 方法选择

    Native score 是最低额外 forward 成本；翻转 TTA 增加一次 forward，测的是输入敏感性；
    depth-bin hook 不增加 forward，但额外存储/同步和统计不是零成本。
    MC Dropout 要确认模型真实含有适合采样的 dropout，不能把 model.train() 当作免费、无副作用的方案。
    Ensemble 通常要求独立成员或可解释的模型差异，当前只有一个固定 checkpoint，不能伪称 ensemble。
    ECE 只在明确概率事件和合法校准后使用；单纯把 score 归一化到 [0,1] 不构成概率校准。
    本轮候选优先顺序仍为 A→B/C→必要时 D，不根据未执行实验宣布某候选优于其他候选。
    ''')

    paper_log = {'papers':[
        {'paper':'Metric3D v2','source':'https://arxiv.org/html/2404.15506v4','read':['Method canonical transform/joint GRU','Supervision','Experiments','Conclusions'],'code_scope':'actual 283-file identity; selected inference/decoder/config/loss bodies'},
        {'paper':'Gradient-based Uncertainty for Monocular Depth Estimation','source':'https://arxiv.org/html/2208.02005v1','read':['Method','Experiments','Ablations','Conclusion'],'code_scope':'official README and generate_maps.py entry workflow, not every module'},
        {'paper':'Uncertainty from Motion for DNN Monocular Depth Estimation','source':'https://cdn.prod.website-files.com/5e91dee07859bc2d42686903/62228ef2ba88686c0d8bed65_2022_icra_ufm.pdf','read':['IV Method','V metrics','VI Experimental setup','VII Results','VIII Conclusion'],'code_scope':'official README; corrected ensemble caveat','PDF_bytes':1394379,'PDF_sha256':'68c7f1eab757374b96e1bef7a139eae63dd29ecd0a3ad0b57becb8cddb8e6b08'},
        {'paper':'Learning a Depth Covariance Function','source':'https://arxiv.org/html/2303.12157v2','read':['Method','Experimental calibration','BA/VO experiments','Conclusions'],'code_scope':'official README, no training or full implementation audit'}],
        'fulltext_republication':False,'author_reported_results_are_not_our_measurements':True}
    write('02_literature/PAPER_READING_LOG.json',json.dumps(paper_log,ensure_ascii=False,indent=2))
    comparison = [
        dict(method='Metric3D native confidence',needs_new_training='No for fixed checkpoint',extra_forward='0',backward='No',mechanism='Joint GRU scalar score with masked confidence loss',limitation='Uncalibrated output; severe-error supervision excluded in this loss',current_execution='SOURCE_ONLY'),
        dict(method='Flip TTA',needs_new_training='No',extra_forward='1',backward='No',mechanism='Restore flipped output and compare',limitation='Consistently wrong predictions can agree',current_execution='SYNTHETIC_EVALUATOR_ONLY'),
        dict(method='Initial depth-bin statistics',needs_new_training='No',extra_forward='0 if hook works',backward='No',mechanism='Entropy/anchor variance/pmax/neff before RAFT',limitation='Initial distribution is not final-depth error distribution',current_execution='SOURCE_AND_SYNTHETIC_ONLY'),
        dict(method='GrUMoDepth',needs_new_training='No fixed-depth retraining in author method',extra_forward='Typically 1 beyond original',backward='1',mechanism='Auxiliary prediction discrepancy gradients',limitation='Layers/loss/cost need Metric3D validation',current_execution='PAPER_AND_ENTRY_CODE_ONLY'),
        dict(method='UfM',needs_new_training='Author setup uses aleatoric ensemble/MC-dropout models',extra_forward='Temporal sampling replaces simultaneous members',backward='No at inference',mechanism='Pose-based temporal mixture moments',limitation='Geometry dependent and base uncertainty dependent',current_execution='PAPER_READ_ONLY'),
        dict(method='DepthCov',needs_new_training='Yes or valid pretrained covariance network',extra_forward='Covariance CNN required',backward='Training only',mechanism='Learned correlated log-depth GP',limitation='Not a no-training plug-in native score',current_execution='PAPER_READ_ONLY'),
        dict(method='MC dropout',needs_new_training='Depends on compatible existing architecture',extra_forward='T-1',backward='No',mechanism='Repeated stochastic masks',limitation='Enabling train mode may change more than dropout',current_execution='NOT_SELECTED'),
        dict(method='Ensemble',needs_new_training='Requires separately justified model members',extra_forward='M-1',backward='No at inference',mechanism='Diverse predictor disagreement',limitation='Current single fixed checkpoint is not an ensemble',current_execution='NOT_SELECTED')]
    table('02_literature/R2_02_METHOD_COMPARISON.csv',comparison)

    document('03_dataset_audit/R2_03_DATASET_AND_GT_AUDIT.md', '''
    # R2-3 数据与 GT 审计

    **100 帧真实数据审计已执行；独立模型误差评价未准入。** 所有原始数据只读。

    ## VIPER：审计范围内没有 Dense Depth GT

    读取当前本地 11 个 RGB ZIP 的中央目录，以及已有 train_camera.zip（78 个成员）与冻结 R2 清单。
    RGB 包为 JPG/TXT；当前审阅输入中没有配套逐像素深度。已有 dense 的目录索引二进制不是数据载荷。
    Camera/K/天气与帧身份可用于无 GT 的模型分布检查，但不能由 pose 或 DROID-W 深度生成伪 GT。
    没有把语义/instance 当成已读取的稠密标注；本轮相应可用性仍为未核验。
    这不意味着官方 VIPER 从未提供其他模态，只说明本轮已审计本地资产不含所需深度。
    val_007 是 Night、487 帧 stride=1 的历史样本，不重新运行 SLAM。

    ## MVS-Synth：一条完整 RGB/Depth/Pose 序列

    路径：D:\\aaa\\GameCam-VO\\data\\mvs_synth\\GTAV_540\\0000。
    实际读取 100 PNG +100 EXR +100 JSON。RGB/GT 均为 960×540，EXR 的 Y 通道为 float16，
    45,412,636 个有限正深度，6,427,364 个 +Inf，NaN 为 0。官方说明 sky 为 +Inf，保持原值并排除评价。
    GT 来源独立于 R1，但单位到米的换算未建立。frame0000 的有限正深度中位数 223.125 是 native game unit，不能写成米。
    相机 JSON 的 W2C 上块 determinant 约 -1；直接相对变换 Et @ inv(Es) 保留其坐标约定，没有强行改成 SO(3)。

    300/300 文件当前 SHA 与既存镜像清单一致。镜像 revision c886d86505054f18f79d0a1c838150d9e98935b2；
    历史官方子集 13/13 当前复核一致，官方 revision 73e4b0abff2806a67c0f9bc038c3a1ac5df9ef0b。
    没有把 13 文件官方对照扩大描述为 300 文件全部官方逐字节核验。
    另有 0001/0039/0079/0119 的 12 张 RGB 预览，但没有相应完整 GT，不能作为独立测试集。

    [作者页面](https://phuang17.github.io/DeepMVS/mvs-synth.html)描述 GTA-V 的 120×100 帧 RGB/EXR/相机数据，
    540p 归档约 9GB，research/educational use。没有新增下载；完整论文与数据的许可、单位仍需按来源分别核验。

    ## 实际多视图一致性诊断

    网格每 8 像素采样，使用 target 最近邻深度，不缩放 EXR。比较 Z-depth 与 ray-range 假设，报告遮挡/采样边界影响。

    | 对应帧 | Z 假设中位相对差 | ray-range 中位差 | Z 差 <1% 比例 | 解释 |
    |---|---:|---:|---:|---|
    | 0000→0001 | 约 1e-15 | 约 9e-16 | 100% | 相机几乎静止，不能区分 Z 与 range |
    | 0049→0050 | 0.00087188 | 0.0267152 | 97.329% | 非零基线，支持 Z-depth 与网格对应 |
    | 0098→0099 | 0.00089048 | 0.0317710 | 92.337% | 非零基线，同样支持 Z-depth |

    错配 target-depth 对照的 Z 中位差分别约 0.45257 和 0.78070，远大于正确配对。
    0→1 的平移只有 2.34e-13 native units；其小误差不能当作有效可观测性证据。
    此处约 0.09% 是 **GT 跨视图数值一致性**，不是 Metric3D 误差或独立采集时钟/米制准确性证书。
    光栅化、遮挡、动态物体、EXR HALF 量化以及最近邻采样均可能影响残差。

    ## 评价网格与有效 mask

    准入后在原始 GT 网格评价，保留有限正 GT，Inf sky 不参与。原始深度不重写、不填空、不截成看似有效的常数。
    输出 depth/score 使用显式相同 unpad/crop 对应，GT 不做 bilinear 混边；物体边缘作为独立分层。
    有效 GT 上非有限/非正预测必须保留失败信息并停止该 sample，不能过滤后报告漂亮指标。
    深度分层范围要在单位核实后冻结；不能把当前 native-unit 数值直接命名为近/中/远米制阈值。

    ## 划分与准入

    当前唯一完整序列 0000 只做数据审计，未拟合 scale、confidence calibration 或选择阈值。
    不能随机拆相邻帧形成伪独立 Calibration/Test。单条序列未来可以作探索性评价，但不能同时校准与独立验证。
    未知单位不意味着永远不能做排序研究：可先获得可信的物理换算，或预注册仅在校准序列拟合一个全局数值单位映射，
    再在另一完整序列测试，并明确该操作不证明物理米制。当前两个条件均不足，严格误差阶段保持停止。

    DATA_ADMISSION.json、MVS_PROVENANCE_OBSERVABILITY_ADDENDUM.json 和逐帧 manifest 给出全部范围与原始 SHA。
    图 R2_03_DATA_ALIGNMENT_EVIDENCE.png 是真实 RGB/GT/mask，未包含任何模型预测。
    ''')

    document('04_native_confidence/R2_04_NATIVE_CONFIDENCE_EVALUATION.md', '''
    # R2-4 Native Confidence 评价状态

    **NOT_EXECUTED — GPU_UNAVAILABLE / GT_ADMISSION_INCOMPLETE。**
    没有得到 native confidence map，因此没有 Spearman、Pearson、AUROC、AUPRC、AUSE、AURG、ECE 或模型失败案例。
    空 CSV 数值不是零。不能回答 Night 是否可靠，也不能据源码监督风险宣布已经失败。

    已实现并实际测试独立 CPU 评价器 reliability_metrics.py；61 项合同与数值测试通过。
    AUROC 使用 tie-aware rank；AUPRC 明确定义为 average precision（阶梯 recall 积分），与 sklearn 对照。
    单类别事件返回 UNDEFINED，不填入虚假 0/1；恒定信号的相关系数同样未定义。

    后续固定方向：raw c 越高应越可靠；用于高误差检测的 risk=-c。
    同时保留 error-vs-c 的原始相关性。若方向相反，报告相反，不根据测试结果静默翻向。
    AbsRel 和 absolute log error 需要独立正深度 GT、像素对齐、坐标约定与匹配单位全部准入。
    error>0.1/0.2/0.5 全部报告，不挑最有利阈值。

    Risk-Coverage 以保留 k/N 像素的 mean AbsRel 定义，score ties 用均匀置换的期望前缀风险。
    AUSE=积分(risk-oracle)，AURG=积分(random-risk)，本实现使用原始 AbsRel，不是归一化论文指标。
    恒定分数恰好等于 random baseline，避免 tie 的输入顺序带来虚假提升。
    以 coverage=0 的右极限补点后梯形积分；不同定义的论文数字不能直接横比。

    分桶图只能称 score-error diagram，不能称概率 reliability diagram。
    ECE 需明确定义 P(error<=t)，在序列隔离的 Calibration Split 拟合后，才允许在 Test 评价。
    工具会拒绝 calibration/test 序列交叉；尚未执行校准。
    近/中/远、纹理、边缘/平面、物体边界分层与天气分层待有 GT 后预注册。
    语义类别需要真实标签，不用图像直觉冒充 semantic GT。

    Bootstrap 按独立序列重采样，先算每序列指标再做等权 macro。
    一条序列的 frame bootstrap 最多描述同一场景内不确定性，不能代表跨环境泛化；本轮不提供此类置信区间。
    ''')
    metric_fields = ['candidate','environment','threshold','metric','value','status','sample_count','reason']
    table('04_native_confidence/R2_04_NATIVE_CONFIDENCE_METRICS.csv', [dict(candidate='NativeConfidence',environment='UNMEASURED',threshold=t,metric=m,value='',status='NOT_EXECUTED',sample_count=0,reason='GPU unavailable; independent matched-unit GT not admitted') for t,m in [('', 'Spearman'),('', 'Pearson'),('0.1','AUROC'),('0.2','AUROC'),('0.5','AUROC'),('0.1','AUPRC_AP'),('0.2','AUPRC_AP'),('0.5','AUPRC_AP'),('','AUSE_raw_AbsRel'),('','AURG_raw_AbsRel'),('','ECE')]],metric_fields)
    for folder in ['04_native_confidence/R2_04_RISK_COVERAGE','04_native_confidence/R2_04_CONFIDENCE_ERROR_VISUALIZATIONS','04_native_confidence/visualizations']:
        document(folder+'/NOT_EXECUTED.md','No model outputs or qualified GT comparison. No empirical risk curve/heatmap was generated; see the stage report.')

    document('05_tta/R2_05_TTA_EVALUATION.md', '''
    # R2-5 Flip TTA

    **真实模型未执行。** 无单帧/双帧推理时间、GPU 型号实测、显存或正确率数据。
    两次 forward 是理论调用次数，不能宣称耗时恰为两倍。

    保留整个输入原图，沿水平方向 flip 后使用与 native 完全相同的 resize/normalize/padding。
    先分别 unpad 并恢复到相同原始网格，再 flip 回第二个输出；非对称 padding 不能直接在 canonical map 上逆转。
    fx 在水平翻转中不变；完整 K 的主点若涉及几何处理应采用 cx'=W-1-cx，并记录像素中心约定。
    当前 Metric3D 包装器只把 fx 用于 depth canonical 恢复，不把完整 K 作为 model 输入。
    native 与 flip 的 fx/1000 必须相同，不逐帧或逐图拟合 scale 以减少差异。

    指标：abs(D1-D2_restored)/(abs(D1)+eps)；另记录 abs(log(D1+eps)-log(D2_restored+eps))。
    Confidence 同样保留 raw 两份及 flip-back 后差异；不做无依据的概率变换。
    CPU 测试覆盖正确逆转、padding 奇数边界、zero-bottom-pad、防止无效深度被变成可信零。
    一个模型两次都预测 2×GT 时 flip disagreement=0，真实 AbsRel=1；这一合成反例说明一致性不等于准确性。

    真实增益需用同一独立 GT/valid mask，与 Native Confidence 配对评价，边缘带单独报告。
    Native+Flip 的任何参数只能在独立 calibration 序列确定。当前没有拟合组合，也没有入选组合模块。
    ''')
    table('05_tta/R2_05_TTA_METRICS.csv',[dict(candidate='FlipTTA',metric=m,value='',status='NOT_EXECUTED_GPU_UNAVAILABLE',reason='No real model outputs') for m in ['relative_disagreement','log_disagreement','GT_AUROC','GT_AUSE','native_forward_seconds','two_forward_seconds','GPU_peak_allocated_bytes','incremental_runtime']],['candidate','metric','value','status','reason'])
    document('05_tta/visualizations/NOT_EXECUTED.md','No TTA inference was performed. Synthetic evaluator tests are not TTA model heatmaps.')

    document('06_depth_bin/R2_06_DEPTH_BIN_UNCERTAINTY.md', '''
    # R2-6 Depth-bin 统计

    **256 bins 已由实际源码确认；真实分布未提取。**
    RAFTDepthNormalDPTDecoder5.py:761 定义 num_depth_regressor_anchor=256；794–836 生成 log-spaced anchors、
    执行 softmax 并计算期望。期望用于初始深度，再经 8 轮 RAFT 修正。
    不能把初始 entropy 解释成最终深度方差，不能把 anchor 编号的方差当深度方差。

    未来使用只读 depth_regressor forward hook，返回 None，读取实际 logits 和真实 depth_expectation_anchor。
    output_dict 的 pred_logit=None 不是证明模型没有 bin 分支。hook 不重写 decoder、不增加训练或 CUDA kernel。
    Prepared runner 会取原生 hook，但没有 GPU smoke 通过收据，不能视为已认证可运行。

    统计公式：H=-sum(p log p)，归一化 H/log(K) 另外命名；
    mean=sum(p*d_anchor)，V=sum(p*(d_anchor-mean)^2)，pmax=max(p)，Neff=exp(H)。
    Variance 单位是 canonical depth squared，不能乘错 fx 线性比例；若映射物理深度，方差应乘尺度平方。
    低分辨率 bin 网格与 full-resolution 最终深度必须显式对应，物体边缘分层，不能静默改 GT。
    CPU 测试验证稳定 softmax、均匀/尖峰分布、非均匀 anchors 以及无效输入。
    原始 entropy 与初始/最终误差之间的关系、以及超出 Native Confidence 的增益，均未测。
    ''')
    table('06_depth_bin/R2_06_DEPTH_BIN_METRICS.csv', [dict(quantity='bin_count',value=256,evidence_level='CONFIRMED_SOURCE',status='MEASURED_CODE_CONSTANT'), *[dict(quantity=m,value='',evidence_level='NO_MODEL_OUTPUT',status='NOT_EXECUTED') for m in ['entropy','entropy_normalized','anchor_variance','max_probability','effective_bins','initial_error_correlation','final_error_correlation','GT_AUROC','runtime_overhead']]],['quantity','value','evidence_level','status'])

    document('07_gradient_uncertainty/R2_07_GRADIENT_UNCERTAINTY_REVIEW.md', '''
    # R2-7 梯度候选：DEFERRED

    没有执行 backward 或训练。A/B/C 尚无真实 GT 评价，不能将“未执行”解释成“三者已失败”，
    因此没有满足用户规定的梯度备用方法启动前提。
    已读 GrUMoDepth 方法、实验、局限及官方入口；其固定模型辅助预测 loss 的特征梯度可无需微调提取，
    但 Metric3D 的 inference 包含 no_grad，不能直接在该入口得到梯度。
    未来若需要，应在独立脚本里走明确可微的 forward、冻结参数更新、只取指定特征梯度，
    保持生产模型 eval、禁止 optimizer.step，并测真实显存。这里不修改模型、不执行该候选。
    原论文 Monodepth2 的层选择、通道归约和热图归一化不能直接当作 Metric3D 的最优规则。
    ''')

    document('08_comparison/R2_08_METHOD_COMPARISON.md', '''
    # R2-8 对照：当前没有可宣告的实测优胜者

    | 方法 | GT 排序/高错识别 | 校准 | 额外 forward | 当前证据 |
    |---|---|---|---:|---|
    | Native Confidence | 未执行 | 未执行，非概率 | 0 | 完整关键生成/监督源码 |
    | Flip TTA | 未执行 | 未执行 | 1 | 独立 CPU 评价器、反例 |
    | Depth-bin statistics | 未执行 | 未执行，非最终后验 | 0（hook 及统计另有成本） | 实际 256 bins 与公式测试 |
    | Gradient uncertainty | 按条件延后 | 未执行 | 通常额外 1 加 1 backward | 论文与官方入口研究 |

    Native score 与深度共 forward，理论额外推理最少；实际热图/搬运开销未测。
    不能由计算量推导可靠性，也不能由训练 mask 风险推导失败。
    夜间/雨雪/低纹理/远距表现、TTA 独立增益、bin 独立增益、校准必要性、系统性盲区均为未建立。
    R2 用合成 wrong-but-consistent 反例验证了评价逻辑的必要性，没有声称该现象已在 Metric3D 实际发生。
    当前不选择组合权重或融合网络，不进入 CADP/BA。
    ''')

    document('09_final_design/R2_09_FINAL_RELIABILITY_DESIGN.md', '''
    # R2-9 独立质量接口候选（DESIGN_ONLY / NOT_ADMITTED）

    当前不发布经过校准的 prior reliability。仅定义可审计的实验输出结构，禁止接入优化。

    输入：RGB uint8 H×W×3；sample/sequence ID、RGB SHA；输入 K/fx、输入尺寸、原生预处理记录；
    固定 model commit/checkpoint SHA。真实 depth GT 只进入离线 evaluator，不进入推理。

    输出候选：

    | 字段 | dtype/形状 | 范围/方向 | 约束 |
    |---|---|---|---|
    | depth | float32 H×W | 深度，单位必须声明 | 与 baseline 恢复规则相同并记录 clamp |
    | native_confidence_raw | float32 H×W | 未限定范围；预期高值可靠 | 不强行 sigmoid，不称概率 |
    | native_confidence_canonical | float32 616×1064 | 原生 score | 保留原始值和 padding 信息 |
    | flip_relative_disagreement | float32 H×W | >=0，高值表示不一致 | 仅追加推理后可填；不是误差 |
    | flip_log_disagreement | float32 H×W | >=0，高值不一致 | 同 fx、恢复方向、mask |
    | bin_entropy | float32 低分辨率网格 | [0,log K]，高值分散 | 不是最终深度后验 |
    | bin_variance | float32 同 bin 网格 | >=0，canonical unit squared | 必须保存 actual anchors |
    | validity | bool H×W | 有效/无效 | confidence 无效必须独立标记 |
    | probability_good_depth | optional float32 H×W | [0,1] | 仅有独立校准及事件定义时存在 |
    | frame_summary | JSON | quantiles、无效率、事件统计 | 不把未校准分位数称正确概率 |

    Confidence 非有限或 depth 非正/非有限时保留失败记录与独立 valid 标识，不把无效值映射为最高可靠度。
    Frame-level quality 暂不聚合成固定 rho；公式及阈值需要独立测试后确定。
    校准元数据必须包含事件、方法、calibration/test sequence IDs、单位、适用场景、SHA 与版本。
    无 GT 的 VIPER 分布观察只能说明输出变化，不能授予准确性或 Night 使用范围。
    当前所有环境都处于 accuracy UNVERIFIED，已知失效场景尚未由模型实验建立。
    ''')
    document('09_final_design/R2_09_GO_NO_GO_DECISION.md', '''
    # 决策：NO-GO — 当前证据不足以进入联合可信度设计

    此决策针对“现在能否把模型质量信号接入后续控制器”，不等于“Metric3D Confidence 被证伪”。
    阶段状态为 TASK006A_R2_PARTIAL_WAITING_GPU_AND_GT_ADMISSION。

    已核验：实际代码/权重身份；score 生成和 mask；文献；100 帧真实 GT 文件与多视图诊断；61 项 CPU 测试。
    缺少：原生 score 数值分布、真实预测图、独立匹配单位 GT、序列隔离的 calibration/test、候选的真实效能与开销。
    当前不能授予 CONDITIONAL GO，因为连某个明确环境下的有效性也没有独立模型实验支撑。

    恢复顺序：
    1. 用户确认有卡启动/当前 SSH，严格核验同一可信主机身份；不自动申请、重启或修驱动。
    2. 先少量现有 RGB 做 Native/Flip/bin 的独立推理和数值审计，失败即保留现场。
    3. 确认 MVS 的单位与坐标，或预注册校准序列上的全局数值单位映射；获得另一条完整独立 GT 序列才测试校准。
       新数据下载先评估规模和存储；当前不下载整个 9GB 数据集。
    4. 冻结有效 mask、分层、阈值及测试准则，按序列评价 A，再判断 B/C 的独立增益。
    5. 只有 A/B/C 真实证据不足才考虑梯度。没有单独授权不进入 CUDA/BA/训练或 CADP 集成。
    ''')

    document('TASK006A_R2_FINAL_RESEARCH_REPORT.md', '''
    # TASK006A-R2｜Metric3D 深度先验可信度阶段研究报告

    2026-11-26 · GameCam-VO · **PARTIAL / 明确阻断后停止**。
    **NO-GO — 当前证据不足，不应接入 CADP 或 BA；不是认定原生 Confidence 无效。**

    ## 首页：七个核心问题

    | 问题 | 当前回答 | 原因 |
    |---|---|---|
    | 1. 能否识别 GTA-V/VIPER 错误深度？ | INSUFFICIENT_EVIDENCE | 未执行模型与独立 GT 比较 |
    | 2. Night/Rain/Snow/低纹理/远距可靠吗？ | UNVERIFIED | 没有相应独立误差实验 |
    | 3. 需要后处理校准吗？ | 若要解释为概率则必须定义事件并校准；当前排序表现未知 | 原生输出没有概率约束 |
    | 4. Flip TTA 有独立提升吗？ | UNVERIFIED | 评价器已测，模型 TTA 未执行 |
    | 5. Depth-bin entropy 有额外信息吗？ | UNVERIFIED | 初始 256 bins 已确认，真实提取与 GT 未测 |
    | 6. 最终应选哪种信号？ | 暂不选；优先实测 Native | 不能由理论成本选择准确性优胜者 |
    | 7. 足以进入联合控制器吗？ | NO-GO_INSUFFICIENT_EVIDENCE | GPU 推理和 GT 准入均未完成 |

    ## 研究背景与实际执行

    R1 已验证 prior-off Schur 几何协方差的 CPU 数学定义，未证明 Metric3D 先验本身可靠。
    本轮追踪原生质量 score，独立审计数据和评价器，不改变 BA、RAFT、U/W 或调度。
    已实际执行：可信 SSH 只读核查、实际源文件身份核验、全文及官方代码相关部分阅读、
    100 帧真实 RGB/EXR/相机审计、300 文件来源比对、非零基线投影对照及 61/61 CPU 合同测试。
    不是只交方案；但也不是完整的推理评价完成包。

    ## 源码与模型身份

    实际 Metric3D @METRIC@，283/283 Git blobs 与官方固定提交一致。
    权重 SHA @WEIGHT@，大小 1,647,972,663 bytes；未反序列化。
    DROID-W 目标 @DROID@，入口与封存 R0 对照相同；gamma_depth=0.01 保留。
    生产 torch.hub.load 没有版本 pin；运行缓存已单独核验，不能用注释旧 commit 冒充实际版本。

    Confidence 是联合 depth/normal RAFT 状态中的单独深度 score，经 8 次更新和凸上采样输出，
    没有最终 sigmoid 或 [0,1] 约束。Normal concentration、DINO U 和 R1 几何协方差都不是这个 score。
    Confidence loss 的相对误差分母为 GT；relative error>=1 的像素被该项监督 mask 排除。
    这给出严重错误风险的可检验假设，不能代替实际失败证据。
    生产入口丢弃 score 的行为已确认，作者动机 UNVERIFIED。
    [官方 decoder](https://github.com/YvanYin/Metric3D/blob/@METRIC@/mono/model/decode_heads/RAFTDepthNormalDPTDecoder5.py)，
    [官方 loss](https://github.com/YvanYin/Metric3D/blob/@METRIC@/training/mono/model/losses/GRUSequenceLoss.py)。

    ## 文献依据

    阅读 Metric3D v2（TPAMI 2024）、GrUMoDepth（ECCV 2022）、UfM（ICRA 2022）、DepthCov（CVPR 2023）
    的相关方法、实验和局限；完整记录在 02_literature。作者实验不等于本项目复现。
    Native score、翻转一致性、初始 bin 分布、梯度是不同的证据源；
    UfM 依赖运动，不适合当独立 GT；DepthCov 需训练，本轮不实现。

    ## 真实数据结果

    VIPER 审阅的 11 个本地 RGB ZIP 与 camera 输入没有配套 Dense Depth GT；不声称官方永远没有。
    MVS-Synth 0000 有 100 RGB/100 EXR/100 pose，960×540，45,412,636 个有限正深度，
    6,427,364 个 Inf sky，NaN 0。300/300 当前文件与镜像清单匹配，历史官方子集 13/13 复核。
    没有把子集比对扩大到所有文件的官方身份。

    非零基线 49→50 与 98→99 的 Z-depth 中位跨视图相对差约 0.0872% 和 0.0890%，
    ray-range 假设约 2.67% 和 3.18%。错配深度明显更差，支持样本几何与网格对应。
    0→1 几乎静止，不具有 Z/range 区分力。上述不是模型准确性、米制标定或物理时钟证明。
    GT 物理单位仍未知；本地只有一条完整序列，另外四条只有 RGB 预览，不能独立校准/测试。
    [数据作者说明](https://phuang17.github.io/DeepMVS/mvs-synth.html)。

    ## 已执行实验与未执行部分

    61/61 CPU 测试覆盖 GT 准入、防泄漏、relative/log error、tie-aware AUROC/AP、risk-coverage、
    raw AbsRel AUSE/AURG、概率事件门禁、分组 bootstrap、TTA 逆转与 bin anchors、监督 mask。
    数值对照包括 sklearn 指标 oracle 和枚举 tie 排列；这些是评价工具验证，不是模型 score 准确性。
    合成 consistently-wrong TTA 反例说明“稳定”不等于“正确”，不是 Metric3D 实测失败案例。

    | 项目 | 真实执行状态 |
    |---|---|
    | Confidence 数值分布/热图 | 未执行，无 GPU |
    | Native score 对 GT 的 Spearman/AUROC/AP/AUSE | 未执行，GT 单位/划分未准入 |
    | Flip forward/效果/性能 | 未执行 |
    | bin hook 的真实输出与初始/最终误差 | 未执行 |
    | 梯度反向传播 | 未执行，A/B/C 还未评价，不满足备用阶段前提 |
    | 概率校准/独立测试 | 未执行 |
    | CADP/BA 接入 | 禁止，未执行 |

    CSV 的空值表示未测，NaN/Inf 计数也没有擅自填 0。
    没有预测图时不以审计 GT 图冒充 RGB/GT/Pred 三联图。

    ## 资源与停止原因

    当前可信端点 sc01-ssh.gpuhome.cc:30601 的 nvidia-smi 返回 Exec format error。
    未确认可用 GPU，不修驱动、不重启、不申请卡。数据盘探针可用 12,522,487,808 bytes，/dev/shm 2 GiB。
    模型 checkpoint 加载、CUDA context、GPU inference、训练、SLAM、C0 读取均为 0。
    本地使用 CPU Python 3.9.13/NumPy 2.0.2/SciPy 1.13.1。
    OpenEXR 3.3.3 和 pypdf 5.9.0 只放进本研究 runtime_site，不替换既有核心依赖。
    没有下载新数据；论文 PDF 与小型工具依赖的网络读取不能误报为“完全零网络”。
    独立 GPU 脚本已准备、未 smoke；其 12000 MiB 保护是保守预算，非模型最低显存实测。

    ## 方法比较与阶段结论

    没有证据选择 Native、TTA 或 bins 中的优胜者。Native 理论额外 forward 最少，
    TTA 和 bins 是否带来独立信息尚待配对 GT 实验。也没有证据声明某个环境中已有效，因此不是 CONDITIONAL GO。
    下一步是恢复小规模模型输出实测，并建立独立 matched-unit depth GT；不是重新跑 SLAM 或训练新网络。
    详见 09_final_design 和 CODEX_HANDOFF。后续 GPU 可先做分布审计，GT 问题不妨碍其统计；
    但准确性结论仍必须等 GT 准入。新阶段不得自动开始。
    ''')

    document('FINAL_REVIEW.md', '''
    # TASK006A-R2 最终阶段评审入口

    **PARTIAL_WAITING_GPU_AND_GT_ADMISSION / NO-GO_INSUFFICIENT_INDEPENDENT_EVIDENCE。**

    完整报告：[TASK006A_R2_FINAL_RESEARCH_REPORT.md](TASK006A_R2_FINAL_RESEARCH_REPORT.md)。
    已完成源码/权重核验、四篇论文相关全文阅读、100 帧真实数据审计、61/61 CPU 测试；没有模型推理结果。
    Confidence 监督 mask 排除 relative error>=1 的位置；需要真实误差验证，不能据此宣布模型无效。
    当前 GPU 不可用，VIPER 本地无配套 dense-depth GT，MVS 单位及独立序列划分不足。
    不能使用 R1 几何输出作伪 GT，不能把 raw score 称为概率，不能接入 CADP/BA。
    评审包保留完整本轮相关脚本、原始读写收据、结构化结果、源码和可视化；
    论文全文、工具依赖、权重和原始数据集仅列来源或 SHA，不再分发。
    ''')

    document('TASK006A_R2_CODEX_HANDOFF.md', '''
    # 下一对话恢复入口

    当前任务仅部分完成，不能把此包当作可信度效能验证通过。
    根目录：D:\\aaa\\GameCam-VO\\reviews\\task006a-r2-depth-prior-reliability-20261126。
    R1 已封存，发布 commit b6e8b552aa1d5f57ada46fae4b809aedfbaaed94。

    已完成：00/01 的关键源码与状态、02 文献、03 数据审计、独立 evaluator 与 61 项 CPU 测试。
    未完成：01 输出分布、04 Native 对 GT、05 TTA、06 bin 真值效果、08 实测比较。
    07 梯度按条件延后；09 只有输出合同候选，不是获准使用的模块。

    当前远端 sc01-ssh.gpuhome.cc:30601，可信 ED25519：
    SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA。
    remote_probe.py/remote_read.py 使用专用 known_hosts、HostKeyAlias、StrictHostKeyChecking=yes；
    不清空 known_hosts，不自动接受新 key。端口变了先由用户提供；指纹不同独立确认。
    当前探针 nvidia-smi 为 Exec format error，不能用历史 RTX3090 作为当前硬件证据。

    remote runtime：/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python。
    模型目录与 checkpoint 在 metric3d_confidence_probe.py 的 BASE/HUB/CHECKPOINT 常量；
    预期 Metric3D @METRIC@，权重 @WEIGHT@。
    该推理脚本 **UNEXECUTED**。恢复时先 AST/来源/shape/预处理复核，再在可用 GPU 上少量 smoke，
    不能宣称已经运行通过。hook 需确认只读，加载 key 不匹配应停止，不准静默继续。
    1..16 图的 manifest 必须先逐张身份/fx 核验；不要直接全量 VIPER。

    独立输出仅允许 /root/rivermind-data/GAMECAM_TASK006A_R2_*，不要写历史模型/SLAM目录。
    每 sample 保留 native/flip 原始 confidence、depth、真实 anchors 和 bin 统计；
    记录 runtime、峰值显存、分位数、异常计数。GT 只进 evaluator，不能作推理输入。

    GT 当前：MVS-Synth GTAV_540/0000 100 帧，单位未知，另四序列只有 preview。
    先核单位；若采用数值单位校准，需要预注册且独立完整 Calibration/Test 序列。
    未授权整包大下载；不要将同序列相邻帧随机拆开。
    Native risk=-c，error thresholds 0.1/0.2/0.5；tie handling、AP、AUSE 定义见 evaluator 与报告。

    本地复算（PowerShell，各行依次执行）：

    ```powershell
    $env:CUDA_VISIBLE_DEVICES=''
    $env:PYTHONUTF8='1'
    $env:OPENBLAS_NUM_THREADS='1'
    $env:OMP_NUM_THREADS='1'
    ```

    用新的 test output 路径执行 test_reliability.py（参数见脚本），不要覆盖已封存的 unit_tests_001/002。
    audit_datasets.py 需要本研究 runtime_site 中的 OpenEXR；第三方依赖不随评审 ZIP 分发，
    可在新的独立 target 安装相同版本，不升级生产环境。

    不运行 SLAM、不训练、不修改生产/CUDA、不把 confidence 接入 CADP；没有后续单独授权不进入算法实现。
    最后仍须上传完整 ZIP 与展开评审文件，保持 Public，不改仓库可见性，提供固定 commit 链接。
    ''')

    document('evidence/source_references.md', '''
    # 原始来源与证据分级

    - 官方 Metric3D 固定代码：https://github.com/YvanYin/Metric3D/tree/@METRIC@
    - DROID-W 目标：https://github.com/MoyangLi00/DROID-W/tree/@DROID@
    - Metric3D v2：https://arxiv.org/abs/2404.15506
    - GrUMoDepth：https://arxiv.org/abs/2208.02005 ，https://github.com/jhornauer/GrUMoDepth
    - UfM：https://lean.mit.edu/papers/ufm-icra ，https://github.com/mit-lean/ufm
    - DepthCov：https://arxiv.org/abs/2303.12157 ，https://github.com/edexheim/DepthCov
    - MVS-Synth：https://phuang17.github.io/DeepMVS/mvs-synth.html

    OBSERVED：实际文件哈希、CPU测试与GT审计。SOURCE_DERIVED：score含义、mask、256 bins。
    AUTHOR_REPORTED：论文数据集和效果。HYPOTHESIS：严重错误可能缺乏低confidence监督。
    UNVERIFIED：模型实际数值分布、真实误差预测力、跨环境表现和runtime。
    不将这些级别互换。没有联系作者。
    ''')

    document('EXECUTION_LOG.md', '''
    # 执行记录（证据顺序，不捏造逐条时间戳）

    日期 2026-11-26；所有 CPU Python 子进程 CUDA_VISIBLE_DEVICES=''。
    1. 读取用户完整附件、R1 最终交付与当前配置，建立独立 R2 目录；保存 106 文件保护快照。
    2. 严格 pin 的 SSH 只读探针；GPU 未确认可用，继续 CPU 工作，不重启不修驱动。
    3. actual Metric3D HEAD/283 Git blob、checkpoint SHA 和入口来源核验；未反序列化。
    4. 官方生成/监督/RAFT/bin 源码审阅；关键源码只读快照，保留许可证。
    5. 论文/官方代码 Method/Experiments/limitations 阅读；UfM 主站 TLS 失败后改用作者链接 CDN。
    6. 独立 CPU 评价器与测试；第一轮 57 项、补充后 61 项真实通过，初版记录不覆盖。
    7. isolated target 加入 OpenEXR/pypdf；读取 100 RGB/EXR/pose，300 文件哈希复核，
       三组多视图诊断与错配对照；识别 0→1 为退化基线，保留 addendum。
    8. 准备但不执行 GPU probe；输出未执行状态 CSV、明确阻断、接口候选与恢复说明。
    9. 最终保护复核、负载扫描、SHA manifest、ZIP CRC、发布身份复核另见相应机器收据。

    未执行的 stage 没有伪造 stdout、推理时间、GPU型号、热图或GT指标。
    独立源码工作没有覆盖旧报告。只有当前审计原始日志的失败记录被保留，没有自动修复旧结果。
    ''')

    document('ACCEPTANCE_MATRIX.md', '''
    # 用户验收逐项状态

    | 项目 | 状态 | 证据/限制 |
    |---|---|---|
    | 实际模型/权重/代码 | PASS | 283 blobs + checkpoint SHA |
    | Confidence 路径与训练 | PASS_SOURCE | 具体源码及 mask CPU复算 |
    | 输出 shape/分布实际推理 | BLOCKED | GPU未确认 |
    | 区分 depth/normal/DINO/R1 | PASS_SOURCE | 源码报告 |
    | Baseline为何丢弃score | PARTIAL | 行为确认，动机UNVERIFIED |
    | 核心论文与代码适用性 | PASS_READING | 阅读范围记录，不称全面代码复现 |
    | VIPER/MVS本地模态 | PASS_AUDIT | 已实际检查，非全官方模态结论 |
    | GT像素/几何 | PARTIAL | 非零基线支持；不是时钟/独立精度证明 |
    | GT物理单位 | BLOCKED | native units未核实 |
    | 独立校准/测试划分 | BLOCKED | 只有1条完整GT序列 |
    | 无效GT处理 | PASS_CONTRACT | Inf sky排除，原文件不修改 |
    | Native/TTA/bin真实评价 | NOT_EXECUTED | 不填假数据 |
    | 梯度候选 | DEFERRED_BY_PROTOCOL | A/B/C未评价不是失败 |
    | 模型计算开销实测 | NOT_EXECUTED | 只有理论forward次数 |
    | 最终信号/环境适用性 | INSUFFICIENT_EVIDENCE | 暂不选择 |
    | 联合设计决策 | NO-GO | 证据不足，非算法否定 |

    本任务没有达到全部最终验收项，按用户停止条件交付部分证据包。
    ''')

    status = {'stage':'TASK006A-R2','date_Asia_Shanghai':'2026-11-26','status':'PARTIAL_WAITING_GPU_AND_GT_ADMISSION',
              'integration_decision':'NO-GO_INSUFFICIENT_INDEPENDENT_EVIDENCE','CPU_tests_passed':61,
              'model_inference_count':0,'calibration_executed':False,'GT_accuracy_evaluation_executed':False,
              'GT_files_audited':100,'RGB_files_audited':100,'pose_files_audited':100,
              'blocking_reasons':['GPU availability unconfirmed: nvidia-smi Exec format error',
                                  'No dense depth GT in audited local VIPER assets',
                                  'MVS depth physical units not established; only one complete local GT sequence'],
              'confidence_failure_established':False,'next_stage_automatically_authorized':False}
    write('DECISION.json',json.dumps(status,ensure_ascii=False,indent=2))
    print(json.dumps({'reports_written':True,'status':status['status'],'tests':61},ensure_ascii=False))


if __name__ == '__main__':
    main()

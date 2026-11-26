"""Build the R2.2 review from recorded measurements; no model or dataset writes."""
import datetime,textwrap
from common import *

def j(p):return json.loads((ROOT/p).read_text('utf-8'))
def table(p):
    with (ROOT/p).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def write(p,t):
    # Table substitutions already start in column zero; remove only the four
    # spaces introduced by the multiline report template, not table content.
    t='\n'.join(line[4:] if line.startswith('    ') else line for line in t.splitlines())
    with (ROOT/p).open('x',encoding='utf-8',newline='\n') as f:f.write(t.strip()+'\n')
def md(rows,fields):
    return '| '+' | '.join(fields)+' |\n| '+' | '.join(['---']*len(fields))+' |\n'+''.join('| '+' | '.join(str(r[k]) for k in fields)+' |\n' for r in rows)

def main():
    cpu_only()
    gt=j('03_gt_audit/GT_QUALITY_SUMMARY.json');restore=j('02_restoration/RESTORATION_SUMMARY.json')
    tests=j('tests/CPU_TEST_REPORT.json');pres=j('00_evidence/PRESERVATION_AFTER.json')
    evaluation=j('04_evaluation/EVALUATION_STATUS.json');scales=j('04_evaluation/CALIBRATION_ONLY_SCALES.json')
    macros=[r for r in evaluation['macros'] if r['sequence']=='0001']
    ranks=[r for r in table('04_evaluation/CONFIDENCE_AND_TTA_RANKING.csv') if r['sequence']=='0001' and r['variant']=='BILINEAR_SAME_FOCAL' and r['signal']=='NativeConfidence']
    high=[r for r in table('04_evaluation/SPATIAL_ERROR_STRATA.csv') if r['sample_id'].startswith('MVS_0001_') and r['variant']=='BILINEAR_SAME_FOCAL' and r['region']=='high_raw_confidence_cal_Q75']
    primary=md([{ '方案':r['variant'],'三帧等权AbsRel':f"{r['AbsRel_mean']:.12f}",
      '严重错误比例':f"{r['severe_error_ge_1_fraction']*100:.8f}%",'有效GT上的零预测':r['zero_predictions']} for r in macros],
      ['方案','三帧等权AbsRel','严重错误比例','有效GT上的零预测'])
    gates=[
      {'item':'封存输入/历史结果保护','status':'PASS','evidence':'799/799本地文件、16/16远端封存输出身份一致'},
      {'item':'bicubic负值机制及独立恢复修复','status':'PASS','evidence':'32张图237个旧负值/截零→0；正值canonical输入的bilinear凸组合'},
      {'item':'独立数值实现','status':'PASS_WITH_TOLERANCE','evidence':'71/71 CPU测试；32张真实图均满足预定混合容差，不逐位等价'},
      {'item':'GT有限值/Inf/尺寸及内部几何','status':'PARTIAL','evidence':'200帧、198相邻对及最大平移控制支持；无独立真值精度证书或物理时间戳'},
      {'item':'raw EXR物理单位','status':'BLOCKED','evidence':'作者原始单位换算、导出元数据及独立物理长度均缺失'},
      {'item':'准确性改善','status':'NOT_SUPPORTED','evidence':'AbsRel及严重错误比例略升，不能把恢复正值写成精度改进'},
      {'item':'大量高Confidence严重错误','status':'NOT_SUPPORTED_IN_THIS_SAMPLE','evidence':'0001三帧高分Q75区域分别0/204054、0/112800、1/23359'},
      {'item':'新鲜独立测试/跨场景泛化','status':'BLOCKED','evidence':'0001已在R2.1观察，只有3张带预测的复用审计帧'},
      {'item':'生产接入/概率校准/检测器训练','status':'NOT_AUTHORIZED_NOT_EXECUTED','evidence':'独立评估器；没有修改DROID-W、BA、CUDA或训练'}]
    dump(ROOT/'R2_2_DECISION.json',{'task':'TASK006A-R2.2','date_client':'2026-11-26 Asia/Shanghai',
      'final_status':'R2_2_PARTIALLY_READY_FOR_REVIEW','gates':gates,'new_model_forwards':0,'GPU_used':False,
      'accuracy_improvement_demonstrated':False,'physical_metric_depth_GT_established':False,
      'fresh_test_established':False,'production_integration_approved':False,'automatic_next_stage':False})
    csvwrite(ROOT/'05_reports/DECISION_MATRIX.csv',gates)
    write('FINAL_REVIEW.md',f'''
    # TASK006A-R2.2 最终评审：深度恢复与 GT 质量审计

    **最终状态：R2_2_PARTIALLY_READY_FOR_REVIEW。** 2026-11-26（Asia/Shanghai）。

    双线性恢复消除了本次封存输出中的插值负值及截零；GT 的内部空间几何对应得到支持。
    物理单位仍未核实，整体深度误差没有改善，尚不能把这些数据作为已获认证的米制深度评测集。
    本轮仅复用 R2.1 的16张RGB对应的模型输出，新增模型前向0次、GPU计算0次。

    ## 1. 先看三项直接结果

    - 16张RGB的Native/Flip共32张图：旧bicubic负值及截零 {restore['old_clamped_zero_all_maps']} 个，独立bilinear恢复后非正值0个。
    - 有效MVS GT上，旧Native零预测7个→0个；同一GT mask保留全部坏预测，没有按结果删点。
    - 复用0001的三帧，AbsRel **0.133119978304→0.133160183481**；严重错误比例 **0.15240566%→0.15751653%**。没有准确性改善证据。

    {primary}

    聚合为每帧先计算再等权平均。每种恢复方案只在0000的0000/0049/0099拟合一个全局scale，再固定用于0001；
    这个scale是原生GT单位对齐，不是米制换算。0001已经在R2.1被观察，不能改称新鲜独立测试。

    ## 2. GT 的资格与局限

    200帧RGB/EXR/Pose全部匹配960×540；有效有限正深度87,239,937个，+Inf 16,440,063个；
    零、有限负值、NaN、-Inf均为0。对+Inf只作非有限深度处理，不填成远平面。
    198对相邻帧的pair-median相对Z-depth差异再取median为0.0793494%。
    最大平移控制支持Z-depth、原生W2C及现有K的内部对应；不能据此证明真实时间同步、独立绝对精度或物理米制。
    六个推理用EXR的reader原生dtype为float16；GT源精度本身有限。

    作者Issue#13记录过早期GTAV_540的810×540/K问题；本地实际是960×540。
    本轮核验的是当前文件，不自动套用历史810/960修正，也没有获得发行修复版本的完整证明。

    ## 3. Confidence 观察

    严重错误定义为AbsRel≥1.0（含边界）。Calibration0000的raw Confidence Q75={scales['confidence_Q25_Q50_Q75'][2]:.10f}。
    在复用0001三帧的高分区域，严重错误分别为 **0/204054、0/112800、1/23359**。
    当前样本不支持“大量高置信度严重错误”的预设。原生分数尚未概率校准，0.9不等于90%合格概率。
    Native严重错误AUROC约0.9781/0.9524/0.8755，但正例基率仅约0.12%–0.19%；AP和区域分布一起交付。

    ## 4. 两个改动严格分开

    主要隔离因素只改恢复插值bicubic→bilinear，保留历史fx/1000。
    另发现官方示例使用canonical resize后的fx：MVS额外倍率1.1083333、VIPER额外倍率1.6625。
    这是独立的尺度约定差异；本轮另列敏感性，不修改生产DROID-W，不把两项变化混成同一个收益。

    ## 5. 工程验收与保护

    - CPU自动化测试 **{tests['tests_run']}/{tests['tests_run']} PASS**。
    - 本地封存保护 **{pres['checked']}/{pres['checked']} PASS**；远端16份原输出与18份本轮CPU输出身份一致。
    - 独立float32恢复与PyTorch CPU最大绝对差0.000968933；32图满足事先固定rtol=3e-5、atol=3e-4，不宣称逐位相同。
    - 最初float64坐标算术未通过对照的失败证据保留；调整为匹配原生float32算术后通过，没有放宽容差。

    ## 6. 评审建议

    建议接受独立评估器的正值恢复与本次原生单位诊断协议；GT米制认证及新的独立测试资格继续保留阻断。
    如下一阶段做概率校准，应先明确误差标签的scale语义，并另行批准从未观察过的独立序列。
    本轮没有训练可靠性检测器、没有接入CADP/BA、没有启动新的SLAM或TASK007；完成后停止。

    详细证据：`05_reports/`、`02_restoration/`、`03_gt_audit/`、`04_evaluation/`；判定矩阵见`R2_2_DECISION.json`。
    完整原始CPU数组、逐像素误差图、脚本、日志和五组图包含在评审ZIP。原始RGB/GT及权重不重新分发。
    ''')
    write('README_请先读.md','''
    # GameCam-VO · TASK006A-R2.2 评审入口

    先读 `FINAL_REVIEW.md` 和 `R2_2_DECISION.json`。本轮是深度恢复与GT评价资格审计，不是新的模型训练或VO性能实验。

    **要点：237个旧负值截零→0；整体AbsRel没有改善；GT内部几何有支持，物理单位仍未核实。**

    - `05_reports/`：GT资格、恢复数学、focal差异、误差/Confidence、局限、复现合同。
    - `02_restoration/torch_CPU/`：16份完整恢复输出、原生CPU收据及插值fixture。
    - `02_restoration/source_grid_examples/`：五环境原RGB网格的深度示例。
    - `03_gt_audit/`：200帧元数据、198相邻几何检查及控制。
    - `04_evaluation/pixel_maps/`：6张GT配对帧的全分辨率误差/置信度/严重错误数组。
    - `figures/`：PNG、SVG、PDF及图注；RGB缩略图仅用于科学比较，不替代原始数据分发。
    - `code/`、`tests/`、`logs/`：可检查源码、71项测试和完整执行证据。

    本轮依赖已封存R2.1的canonical预测，不包含其原始RGB/EXR/权重。
    完整R2.1评审基准Commit：`9e8e1f609796ed78a0a27b942d3d7440bcf23d72`。
    R2.1完整ZIP SHA256：`fc8dfeb8e2746c8033621af9647a382e9e3138ff09bf46e8ddee453f678c7ae8`。
    R2.1 ZIP获取位置见`05_reports/REPRODUCIBILITY.md`。

    当前是原生GT单位下的配对审计；不能称作米制benchmark或新鲜独立Test。
    新增GPU前向0；没有修改生产Baseline；不自动进入R2.3、R2.4、R2.5或R3。
    ''')
    write('05_reports/GT_UNITS_VALIDITY_AND_ALIGNMENT.md',r'''
    # GT 深度单位、无效值与空间对应

    ## 审计对象

    两条本地MVS-Synth/GTAV_540序列0000、0001各100帧。200份RGB、EXR和Pose全部逐文件读取，
    检查SHA、尺寸、EXR data/displayWindow、通道、有限值和相机矩阵。没有新数据下载或GT重写。
    所有结果在`03_gt_audit/FULL_200_FRAME_METADATA_AUDIT.csv`。

    200×960×540=103,680,000像素，其中87,239,937为有限正值，16,440,063为+Inf。
    0个零、有限负值、NaN或-Inf。此结论只覆盖已审文件；无零不能证明未见文件中零值的语义。
    作者代码使用raw depth !=0掩码，随后的inverse-depth使+Inf对应0 inverse-depth；
    本轮有限深度误差评价使用finite且>0，不把+Inf填成任意有限距离。
    这两个mask不能未经说明互换。

    ## 单位证据

    200份EXR header无单位属性；六张推理用源EXR的reader原生dtype为float16。
    六张在中位深度附近的可表示步长约0.125–0.25原生单位，相对间隔约0.056%–0.086%。
    几何差异0.079%与源量化间隔量级接近，但未证明全部残差来自量化。

    作者Issue#16说明从RenderDoc Z-buffer和图形矩阵导出深度/相机；未给出raw EXR到米的换算。
    Issue#25仍只有用户求单位和另一用户同问，不能将提问当单位答案。
    第三方处理器使用0.1等常数不能认证本地原始文件的物理尺度。
    **米制资格：BLOCKED / NOT_ESTABLISHED。** 不转成米，不把calibration scale解释成物理单位。

    原始来源快照与检索SHA在`01_sources/SOURCE_RETRIEVAL_MANIFEST.json`；
    作者/非作者发言身份分开列在`01_sources/GT_AUTHOR_STATEMENTS.json`。

    ## 内部几何与RGB对齐

    采用官方reader约定W2C：T_target_source=E_target inv(E_source)。
    整数像素反投影X_s=z K_s^-1 [x,y,1]^T；投影到目标后比较预测Z和最近整数采样的目标有限正GT。
    每8像素采样、图像边缘留4像素；可投影且目标有效点计入几何差异，不按差异删点。
    单独的RGB诊断只在几何差异<1%的点上比较，不能将此子集当无偏深度精度。

    198对相邻帧的pair-median相对Z-depth差异再取median为0.00079349395。
    六个指定相邻对做42项z/range、pixel-center±0.5、外参方向、GT单独×0.1/×10控制。
    某些pair几乎静止，因此再用**Pose最大相邻平移**独立选择控制：

    |序列与pair|Z-depth差异|Ray-range差异|Warp RGB误差|未warp RGB误差|
    |---|---:|---:|---:|---:|
    |0000 0098→0099|0.00089048|0.0317710|约0.009505|约0.163399|
    |0001 0000→0001|0.00108357|0.0289044|约0.008854|约0.139869|

    深度差异为相对值，RGB误差是[0,1]三通道绝对差均值的中位数。
    这些证据支持当前文件的内部Z-depth/Pose/K/RGB空间对应，不证明真实采集时钟或独立绝对准确性。

    ## 为什么不能从投影识别米制

    同时把全部深度和相机平移乘s，齐次投影不变。只缩GT而固定平移可以检查内部相对scale，
    但不能决定s对应米、厘米还是引擎单位；纯旋转/静止pair甚至无法判定深度与平移的相对scale。

    ## 历史GTAV_540问题

    Issue#13作者承认过早期810×540宽度和fx的错误。本地文件实际960×540，且本轮几何检查支持现有K。
    不机械应用810/960修正，也不据当前通过宣称所有历史版本已修复。
    发行修复版本、物理长度标尺、独立相机精度与真实逐帧timestamp仍缺少证据。
    ''')
    write('05_reports/DEPTH_RESTORATION_MATHEMATICS.md',r'''
    # 深度恢复：独立数值修复与实现验证

    ## 问题与隔离

    R2.1封存canonical深度均为正值。DROID-W wrapper去padding后使用bicubic恢复，再fx/1000、clamp[0,300]。
    cubic插值核含负系数，在正值深度不连续处可以下冲为负。截零只隐藏负值，并非有效正深度。
    本轮固定canonical预测，只在独立评估器把恢复核换成bilinear。

    输出坐标到源像素中心为u=(x+0.5)W_in/W_out-0.5；边界采用edge extension。
    bilinear输出是四个相邻源值的非负权重凸组合：
    z'=(1-a)(1-b)z00+a(1-b)z01+(1-a)b z10+ab z11。
    对有限严格正值源深度，恢复不会产生负值或零。本实现拒绝不合法canonical输入，
    不用epsilon、掩码或其他像素填充伪造正值；Confidence可为任意分数，另走通用插值函数。

    ## 实际验证

    - 原生PyTorch2.1.0+cu118环境中，只用CPU tensor和F.interpolate；CUDA_VISIBLE_DEVICES为空。
    - 没有模型导入、checkpoint反序列化、CUDA API或前向。
    - 16图×Native/Flip=32图，旧bicubic CPU与保存GPU值最大差≤1.5258789e-5，均通过原对照容差。
    - Confidence的CPU重放与保存值逐位一致（最大差0）。
    - 独立NumPy float32坐标/权重复算32图，全部满足rtol=3e-5、atol=3e-4，最大绝对差0.000968933。
    - 6个独立CPU fixture覆盖单行、单列、单像素、非整数比例、降采样和恒等映射。

    初版float64坐标算术与float32原生结果比较，有940个像素超过上述容差、最大差约0.006105。
    失败记录保留；依据原生dtype实现float32算术后通过，未放宽标准。
    此处PASS表示约定混合容差内一致，不能写成逐位相同，也不是GPU生产接入认证。

    ## 结果

    32图旧负值与截零237个→0；有效MVS GT上的Native零值7个→0。
    七个位置全部列在`04_evaluation/ORIGINAL_SEVEN_ZERO_PIXELS.csv`，原始坏预测完整保留。
    恢复后它们的AbsRel仍约0.0499–0.5590；修复正值不保证每个深度准确。

    ## 原图网格

    MVS GT/RGB为960×540，已直接恢复到其原图网格。
    VIPER模型输入640×360，原RGB1920×1080；五环境各保存canonical→input→source两步恢复示例。
    这只是图像网格放大，不凭空增加深度细节，不因第二次图像放大再次乘深度单位。
    没有VIPER配对深度GT，本轮不评价VIPER绝对深度准确性。

    源码：`code/depth_restoration.py`、`code/common.py`、`code/remote_cpu_restore.py`。
    数值证据：`02_restoration/INTERPOLATION_INDEPENDENT_VALIDATION.json`及原生CPU收据。
    生产DROID-W wrapper、CUDA、权重、R2配置均未接入或修改。
    ''')
    write('05_reports/FOCAL_AND_INTRINSICS_AUDIT.md',r'''
    # Focal转换与像素网格：独立于插值的第二因素

    固定Metric3D提交eb5b6fac0dc155e4e52f576e304fbf11655ff339的hubconf.py：
    第160–163行将RGB缩放到canonical网格并同步缩放intrinsic；第193行bilinear恢复；
    第197–199行用**缩放后fx/1000**转换深度并clamp[0,300]。
    新下载该固定文件与封存文件SHA一致，均为b29ffc0530109bd55ce4067afd5dffd87fb2567416afb145e2cfdd0a1a0c8119。

    封存DROID-W wrapper使用bicubic及未乘canonical resize的input fx/1000。
    因此设置三个方案，保持变化可区分：旧bicubic；bilinear+相同focal；bilinear+官方resized focal。
    不修改原始生产代码，不用GT精度选择插值或focal方案。

    MVS的nominal resize=1.1083333333333334，VIPER=1.6625。
    实际resized=598×1064，纵向因整数截断与nominal scale略有差别。
    `02_restoration/FOCAL_AND_GRID_TRANSFORM_AUDIT.csv`逐帧保留source/input/resized/canonical尺寸及倍率。

    half-pixel图像网格矩阵S具有translation=(sx/2-1/2,sy/2-1/2)；K'=S K。
    canonical pad再左乘平移矩阵P。独立投影与roundtrip测试验证S、P组合，不将该推导冒称旧wrapper已经这样做。
    官方示例中intrinsic乘nominal scale的写法与严格half-pixel K是不同约定，报告分别保留。

    Calibration0000每方案拟合一个global scale后，常量focal倍率基本被scale吸收，
    因而两个bilinear方案的0001误差几乎一致；这不能认证物理尺度。
    另交付固定历史scale的`04_evaluation/FOCAL_FIXED_SCALE_SENSITIVITY.csv`，避免隐藏尺度变动。

    R2.1网络输入使用torchvision Resize，官方示例使用OpenCV resize。
    本轮固定已有网络输出，仅审计恢复/focal；不能称为完整官方端到端预处理复现。
    若未来生产迁移，应单独冻结K、输入resize、focal和恢复约定，再申请GPU验证。
    ''')
    write('05_reports/ERROR_AND_CONFIDENCE_REPORT.md',f'''
    # 配对误差、严重错误和 Native Confidence

    ## 评价合同

    同一批6张GT配对图；0000三帧用于原生单位的单一log-median scale，0001三帧只做复用审计。
    valid=finite(GT)&(GT>0)。不裁剪、插值、转换GT，不按预测质量删点。
    e=abs(scale*prediction-GT)/GT；可靠e≤0.2，不确定0.2<e<1，严重e≥1。
    旧零预测使e=1，完整计入严重错误，log误差为无穷时另报计数，不静默删除。

    {primary}

    bilinear相同focal在0001的mean AbsRel增加约0.0000402052；严重错误比例增加约0.00511087个百分点。
    三帧差值不作为统计显著性或跨序列泛化证据。
    此结果反对“插值修复等于整体准确性提升”的表述；它仍是消除数值伪影的有效修复。

    ## Confidence 检测严重错误

    分数方向固定为risk=-NativeConfidence，没有在0001翻号。下表均为bilinear相同focal、e≥1事件：

    {md([{'样本':r['sample_id'],'AUROC':r['ge_1_0_AUROC'],'AP':r['ge_1_0_AP'],'正例比例':r['ge_1_0_prevalence']} for r in ranks],['样本','AUROC','AP','正例比例'])}

    稀有正例下必须同时报告AP和基率。AUROC高不等于已获概率解释，也不证明VO改善。
    不能直接与R2.1的AbsRel>0.2事件AUROC0.8122比较为“算法升级”，因为这里事件阈值不同。

    高分阈值由Calibration0000 Q75={scales['confidence_Q25_Q50_Q75'][2]:.10f}固定，未用0001选阈值。

    {md([{'样本':r['sample_id'],'高分区域像素':r['GT_valid_pixels'],'严重错误':r['severe_count'],'区域AbsRel':r['AbsRel_mean']} for r in high],['样本','高分区域像素','严重错误','区域AbsRel'])}

    观察到1个高分严重错误，不足以支持“大量高Confidence严重错误”。
    高分段的平均AbsRel未必单调下降，尤其0099最高分bin；连续误差与严重事件的识别能力必须分开。
    原生Confidence仅为raw score，0.9不等于90%合格概率；本轮未拟合Logistic或Isotonic。

    ## 空间分布

    每帧完整保留误差/严重mask、8连通域及Top10区域bbox。进一步按Calibration GT距离tercile、
    图像5%边缘、相对Sobel深度边界proxy、Confidence Q25/Q75分层。
    深度边界proxy不是人工语义标签或可见性GT；Inf邻接会影响该proxy，不据此作因果归因。
    RGB可视化中的树叶、灯杆和物体边缘只是场景观察，不等价于独立语义标注。
    `SPATIAL_ERROR_STRATA.csv`和全图`pixel_maps/`为主证据，`PIXEL_ERROR_CONFIDENCE_SAMPLED.csv`仅是每16像素的便捷抽样表。

    Flip TTA及初始depth-bin entropy均重算为次级诊断，未训练新特征、未改entropy符号，
    未将它们纳入控制器。全部逐帧/逐事件结果见`CONFIDENCE_AND_TTA_RANKING.csv`。
    ''')
    write('05_reports/LIMITATIONS_AND_NEXT_STAGE.md','''
    # 关键局限和下一阶段条件

    1. MVS原始EXR物理单位、导出标尺和真实timestamp仍不明。只能在明确标注的原生单位/单一校准scale协议下做诊断。
    2. 200帧GT审计不等于200帧模型评价：只有6张MVS真实预测，0001仅3张且已经被观察。
    3. 当前两序列同属GTAV_540来源；不能作为独立游戏/真实世界泛化证明。下一阶段需要单独批准新的未见来源序列。
    4. calibration scale依赖GT。它是离线评价操作，不可在RGB-only线上系统中使用或由test重新拟合。
    5. GT无官方visibility/occlusion mask。跨视图RGB的depth-consistent子集是诊断选择，不能当准确性无偏估计。
    6. 六个源EXR为float16；量化、GT重采样与导出质量均可能影响边缘误差。200帧内部一致不能替代独立精度认证。
    7. bilinear恢复消除负值，不提升本次整体AbsRel；上限300沿用旧配置，未调参寻找收益。
    8. 官方focal差异尚未在DROID-W生产路径验证；当前没有修复生产代码，也没有重跑VO。
    9. Native分数不是概率；严重错误很稀有。高AUROC不能替代AP、事件基率、覆盖率和独立序列校准。
    10. VIPER十张预测缺少深度GT，只验证恢复正值和网格，不推断Night深度精度。

    建议下一次评审先选择明确的误差定义：物理米制准确性，或冻结单一Calibration-scale后的相对精度。
    前者继续阻断直到取得独立单位证据；后者可作为另行批准的相对深度可靠性研究，但必须诚实标注。
    概率校准时序列分离Calibration/Test，不能把已观察0001重新封成Test，也不能用测试序列选择k、tau或分类阈值。
    暂不接入CADP或BA，不提前训练检测器；R2.3/R2.4/R2.5/R3由用户分别决定。
    ''')
    write('05_reports/REPRODUCIBILITY.md',r'''
    # 复现与数据合同

    本轮所有计算均CPU-only。Python3.9.13、NumPy2.0.2、SciPy、Pillow、OpenEXR、Matplotlib；
    PyTorch CPU恢复使用已有远端2.1.0+cu118环境，CUDA_VISIBLE_DEVICES为空，无模型加载。

    原R2.1依赖：Commit9e8e1f609796ed78a0a27b942d3d7440bcf23d72；完整ZIP
    https://github.com/Pseven0108/GameCam-VO/releases/download/task006a-r2-1-metric3d-gpu-pilot-20261126/GAMECAM_TASK006A_R2_1_METRIC3D_GPU_REVIEW.zip
    SHA256 fc8dfeb8e2746c8033621af9647a382e9e3138ff09bf46e8ddee453f678c7ae8。
    该包提供canonical预测与padding/resize/K收据；原始RGB/GT需通过原官方数据来源及本地受保护目录获得，本包不分发。

    新代码根目录由common.py的文件位置推导。默认作为GameCam-VO/reviews/<本轮slug>保存，
    前轮R2.1及R2协议目录为相邻reviews目录；OpenEXR runtime_site复用前轮。
    不携带模型权重，不执行torch.load，不读取封存C0，不导入DROID-W。

    原始GT路径：data/mvs_synth/GTAV_540/0000；R2.1/inputs/MVS-Synth/GTAV_540/0001。
    原始模型NPZ路径来自R2.1两份INFERENCE_RECEIPT.json，以SHA验证，不猜测文件匹配。

    ```powershell
    $env:CUDA_VISIBLE_DEVICES=''
    $env:PYTHONUTF8='1'
    $env:OPENBLAS_NUM_THREADS='1'
    $env:OMP_NUM_THREADS='1'
    & 'D:\Python\Python3\Python3.9.13\python.exe' -B code/run_tests.py
    ```

    按目录从新副本复现：intake→collect_sources→remote_cpu_restore或现有torch_CPU输出→validate_restoration→
    audit_gt→alignment_conditioning→precision_audit→full_resolution_audit→evaluate_restored→plot_results。
    脚本采用exclusive create，拒绝覆盖已封存产物；已完成包不要直接原地全量重跑。
    复现者应另建空目录，保留relative依赖关系；远端transport含本机历史路径/端点，需要显式配置可信主机密钥，不能自动接受新密钥。
    无需远端即可读取本包已生成全部CPU数组和6帧逐像素误差图。

    单位合同：raw GT native units，finite且>0；不插值GT，不填Inf，不按预测有效性删除GT点。
    scale只由0000三帧的log-ratio中位数拟合；0001仅复用审计，无fresh-test claim。
    fixed historical scale敏感性与每variant独立Calibration scale结果分别保留。

    SHA清单覆盖封包内所有payload文件，清单自身不自哈希；ZIP外的PACKAGE_VERIFICATION和sha256 sidecar覆盖ZIP。
    Git展开文件不含NPZ，所有NPZ均在完整Release ZIP；PUBLICATION_NOTES和发布清单记录对应身份。
    ''')
    write('EXECUTION_LOG.md','''
    # TASK006A-R2.2 执行记录

    所有时间的用户日期为2026-11-26 Asia/Shanghai；机器收据保留UTC及实际耗时。

    1. 固化PROTOCOL，复核R2.1全部198个SHA条目，建立799文件保护清单。
    2. 检索固定Metric3D/PyTorch源码及DeepMVS原始作者issue，保存响应状态、检索时间、SHA；新增数据集下载0字节。
    3. 严格HostKey核验连接31136，执行单独CPU interpolate脚本：16图/32图深度，0模型前向，0CUDA调用。
    4. 取回18份192,022,421bytes的CPU产物，传输大小和SHA逐项一致。
    5. 初版float64坐标复算超差；保留失败证据，检查原生float32算术后在不放宽容差条件下通过32图及fixture。
    6. 全量读取200帧本地GT/RGB/Pose；完成198相邻检查、42控制和最大平移控制，单位仍未建立。
    7. 在6个已有模型输出上完成三种恢复方案的配对误差、严重错误、分层和Confidence/TTA/Entropy诊断。
    8. CPU自动化71/71通过；补充源EXR精度记录、五环境source-grid深度和五组科研图。
    9. 实际打开全部五张PNG检查轴、标签、分辨率/显示截断及图注。没有裁掉失败数据，没有隐瞒误差略升。
    10. 最终本地799文件、远端16封存NPZ和18本轮CPU输出身份复核通过，未删除或修改原资产。
    11. 形成分项判定和研究局限，按长期交付授权准备完整原始ZIP及GitHub展开材料；发布结果另由封包外收据记录。

    本轮只修改自己的独立评估器和新报告。无GPU计算、无模型/权重加载、无SLAM、无训练、无实例重启/关机。
    在R2.2停止；后续训练、概率校准、生产集成或新实验均未执行。
    ''')
    dump(ROOT/'figures/FIGURE_QA.json',{'status':'PASS_VISUAL_INSPECTION','inspected_all_five_PNG':True,
      'checks':['axes and labels readable','no cropped panel labels','same comparison ranges documented',
      'all three observed frames displayed','zero-pixel crop bounds disclosed','native GT unit labels retained',
      'no calibrated-confidence or new-test claims','complete original numerical outputs retained'],
      'figure_count':5,'formats':['PNG','SVG','PDF'],'scientific_accuracy_claim_from_figures_alone':False})
    print(json.dumps({'reports_created':True,'decision':'R2_2_PARTIALLY_READY_FOR_REVIEW','tests':tests['tests_run'],
      'protected':pres['checked'],'new_model_forwards':0}))

if __name__=='__main__':main()

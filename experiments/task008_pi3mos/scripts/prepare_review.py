"""Build the full review, with all-frame derived views and explicit raw-array exclusions."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image

TASK=Path(__file__).resolve().parents[1];PROJECT=TASK.parents[1]
SLUG='task008-pi3mos-night007-independent-inference-20261126'
R=PROJECT/'reviews'/SLUG;R.mkdir(exist_ok=False)
src=TASK/'retrieved';summary=json.loads((src/'TASK008_SUMMARY_STATISTICS.json').read_text())
audit=json.loads((TASK/'analysis/CPU_ARTIFACT_VALIDATION.json').read_text())
weight=json.loads((src/'WEIGHT_LOAD_RECEIPT.json').read_text());a,b=summary['mode_summary']

def write(name,text):
    p=R/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(text.rstrip()+'\n')

def copy(source,name):
    p=R/name;p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists();shutil.copyfile(source,p)

main=f'''# TASK008：π³mos 独立动态先验与 Night007 验证

2026-11-26，Asia/Shanghai。状态：**独立推理与可视化完成；有限窗口定性证据有希望，未验证检测准确率或 DROID-W 收益。**

## 主要结论

官方 π³mos 在 RTX3090 上完成同一32帧窗口的3帧、5帧对照，各32次、共64次前向，退出码0，无OOM。官方权重 strict=True，缺失/额外键均为0。连续概率、二值 Mask、Overlay、Confidence、辅助深度、输入映射及全部运行统计均已保存。

两组 Mask 在 RGB301–323 连续响应左侧卡车，RGB324–332 均为空；查看全部64张 Overlay，未见建筑、路面或护栏的大面积标红。RGB-only 预先定义的道路、右侧护栏、蓝灯/建筑区域在32帧中均无 M>0.4 像素。它们是图像区域探针，不是像素级静态GT，不能转换成误检率。卡车的真实世界运动状态也没有独立真值。

**未证明5帧优于3帧。** 五帧的全图概率变化较小，但二值 Mask 的未补偿相邻帧IoU略低；全图指标受静态背景和相机运动影响。三帧已有相似可视响应，且速度/显存代价更低。不能把“概率更平滑”写成“检测更准确”。

建议保留 π³mos 为外部动态先验候选，先补停放车辆、行人及相机旋转的独立验证；本轮不接入DROID-W，也不宣称改善VO。

## 真实运行范围

| 项目 | 实际值 |
|---|---|
| 数据 | 已有 VIPER Validation Night007，val_007_full_00001-00487 |
| 目标帧 | RGB301–332，32帧，stride=1 |
| 使用的源图像 | RGB281–332，共52张，全部匹配历史Manifest SHA-256 |
| A | [t-10,t-5,t]，每次只保存最后帧 |
| B | [t-20,t-15,t-10,t-5,t]，每次只保存最后帧 |
| 原始 / 输入尺寸 | 1920×1080 → 672×378，等比例0.35，无裁剪/填充 |
| 执行 | A的32次完成后执行B的32次；batch size=1 |
| 精度 | 原始FP32参数，BF16 autocast，inference_mode |
| 可选6帧 | 未运行 |
| 数据与模型边界 | 无新VIPER下载、无训练、无DPVO跟踪/BA、无DROID-W/Metric3D运行 |

窗口在模型输出前按既有312–328诊断区域选定，ROI同样在RGB-only预览时登记。本画面带车头/机盖，属于车辆安装视角的单一夜间驾驶片段，**不构成第三人称跟随相机的验证**。没有可明确核验的停放车辆、行人或纯旋转控制片段。

## 性能与连续性诊断

| 指标 | A：3帧 | B：5帧 |
|---|---:|---:|
| 完成目标 | 32/32 | 32/32 |
| GPU前向均值（含首帧）ms | {a['mean_forward_GPU_ms']:.3f} | {b['mean_forward_GPU_ms']:.3f} |
| GPU前向均值（各组去首帧）ms | {a['mean_forward_GPU_ms_excluding_first']:.3f} | {b['mean_forward_GPU_ms_excluding_first']:.3f} |
| GPU前向中位数 ms | {a['median_forward_GPU_ms']:.3f} | {b['median_forward_GPU_ms']:.3f} |
| PyTorch峰值 allocated GiB | {a['maximum_peak_allocated_GiB']:.4f} | {b['maximum_peak_allocated_GiB']:.4f} |
| PyTorch峰值 reserved GiB | {a['maximum_peak_reserved_GiB']:.4f} | {b['maximum_peak_reserved_GiB']:.4f} |
| 每目标端到端均值，含压缩/出图 s | {audit['additional_mode_statistics'][0]['mean_end_to_end_seconds']:.4f} | {audit['additional_mode_statistics'][1]['mean_end_to_end_seconds']:.4f} |
| 平均原图 M>0.4 比例 | {100*a['mean_dynamic_area_p04']:.4f}% | {100*b['mean_dynamic_area_p04']:.4f}% |
| 相邻帧全图概率MAD | {a['mean_Eulerian_probability_MAD']:.6f} | {b['mean_Eulerian_probability_MAD']:.6f} |
| 相邻二值Mask IoU（非GT） | {a['mean_Eulerian_mask_IoU']:.6f} | {b['mean_Eulerian_mask_IoU']:.6f} |

成功进程总时长115.999s，包含模型构造、严格加载、64次前向、数值检查、CPU恢复、压缩及可视化；不含首次部署下载。三帧首个前向1509.733ms，五帧首个429.759ms；两组共享同一进程/模型，按固定顺序执行，不能把冷启动均值直接当公平稳定吞吐。记录了CUDA event及同步墙钟时间。端到端吞吐明显低于仅前向吞吐，本轮不是实时系统性能证明。

相邻IoU只在23对非空并集上平均，8对空/空不记为1；第一帧无前帧。它没有光流补偿或物体身份对应，不能代表跟踪准确率。A/B全图概率MAD均值{summary['A_B_probability_MAD_mean']:.6f}；全量逐帧数据见 PER_FRAME_STATISTICS.csv、A_B_FRAME_COMPARISON.csv。

## 用户关心的逐项判断

| 问题 | 证据与判断 |
|---|---|
| 车辆是否响应 | 近处卡车在两组RGB301–323均被连续标出；边界有软化，未做像素精度评分 |
| 停放车辆会否误判 | 未验证；缺少已知静止车辆，不能由“检测到卡车”推导真正理解运动 |
| 摄像机旋转时建筑/路面是否静态 | 本片段背景未出现大面积高概率；缺少独立纯旋转片段，泛化未知 |
| 夜间灯光/反光/阴影 | 蓝灯/建筑、亮护栏、道路的预注册探针M>0.4均为0；小型远处目标、阴影类别没有GT，不宣称全面通过 |
| 连续性 | 可视卡车轮廓连续变化并离开图像；阈值0.4下两组同样23帧非空、9帧空 |
| 3帧还是5帧 | 无足够证据选出更准确者；5帧约多51%前向时间、0.412GiB allocated显存，三帧是较低代价候选 |
| 像素坐标对应 | 显式RGB无裁剪变换、原图概率恢复与阈值Mask逐像素一致；不是与动态GT对齐的准确性证明 |
| 是否值得接入DROID-W | 值得保留候选和补控制样本；尚不能据此批准生产集成或宣称VO提升 |

## 模型与权重身份

- 官方源：[PRBonn/Pi3MOS-SLAM](https://github.com/PRBonn/Pi3MOS-SLAM/tree/1b81d729c4259a5a775eb4aae41f959eea38ae14)，HEAD固定且工作区干净。
- 官方权重：[Google Drive](https://drive.google.com/file/d/145bC76pMHikhdTGkqDK0t9Ta0R7tw51v/view)，4,100,235,800 bytes。
- SHA-256：`{weight['sha256']}`；这是本次下载/传输/加载的身份校验，不是作者发布的独立精度证书。
- 实际二进制为 safetensors，1276个张量，{weight['parameters']:,}个参数；strict=True，missing/unexpected均空。
- 首次适配器误按本地`.pth`文件名调用torch.load，在权重读取时停止，**前向0次**。文件头确认safetensors后创建独立R2目录，使用官方支持的safetensors读取器完成运行。初次错误现场、原适配器和配置保留；未使用不受限pickle回退、未修改模型权重。
- 远端官方clone后checkout超时；随后从官方仓库在本机重新clone同一提交并传输9,845,623-byte bundle。未复用历史Baseline源码。详细记录见 installation_evidence 和 SOURCE_PROVENANCE.md。

## 输入、输出和概率语义

Pillow解码并convert('RGB')，float32除以255一次；模型内部执行ImageNet均值/标准差归一化。CPU合成颜色测试与官方独立RGB Reader逐位一致，并检查了uint8/BGR错误域的差别；没有照搬DPVO原始cv2路径。

模型输入 `[1,N,3,378,672]`；动态原生输出 `[1,N,1,378,672,1]`，已sigmoid，规范化为 `[N,378,672]`，只提取最后一帧。conf也已sigmoid；它与DROID-W的U完全不同。两者均是模型分数，本轮没有概率校准。local_points[...,2]仅作非米制辅助深度；逐窗口camera_poses不当VIPER真值或可拼接的全局轨迹。

原图恢复使用bilinear、align_corners=False：`x_m=0.35*(x_o+0.5)-0.5`，y同理。保存原生分辨率及恢复到1080×1920的float32概率，在原图网格上用严格`M>0.4`生成Mask，另统计0.2和0.6。PNG灰度是显示量化，不能替代浮点预测。

## 验证与资产保护

- 520份结果文件、866,457,714 bytes已取回本地，传输SHA全部一致。
- 64份NPZ在`allow_pickle=False`下检查输入上下文、ID、shape/dtype、有限性、范围、深度与local_points一致性、阈值面积、RGB身份、Mask与概率精确对应；全部通过。
- 独立NumPy float64半像素插值复算，与保存的float32恢复概率最大绝对差 `{audit['independent_float64_vs_saved_float32_restoration_max_abs']:.9g}`，预设浮点容差5e-5；不重新运行模型。
- 52张原始输入与1830份既有DROID-W源码/配置/观测JSON文件在运行前后SHA一致；官方π³mos工作区干净。
- 成功运行结束GPU无计算进程，未关闭/重启实例；未运行本地RTX5060，不能将3090显存结果当作本地环境兼容性结论。

## 交付与局限

本目录含报告、独立适配器、所有运行/部署记录、64帧统计、输入及大数组SHA清单、全部64张Overlay和二值Mask、概率/Confidence/深度显示及完整联系表。为遵守发布边界，模型权重、环境二进制、原始RGB和约821MB浮点预测NPZ不公开上传；它们保留在本地及服务器，RAW_OUTPUT_AVAILABILITY.md记录准确位置和身份。公开显示图的降采样规则和SHA详见VISUAL_DELIVERY_MANIFEST.csv；完整原始预测没有被覆盖或删除。

没有动态GT、没有跨序列/环境重复、没有停放车辆或行人控制；不报告Precision/Recall/GT IoU，不把动态面积或非空率解释成准确率。TASK007D关于OmniWorld严格米制GT的NO-GO仍然有效，本轮没有改变GT准入或Confidence校准结论。

**本阶段到此停止；不自动进入DROID-W集成、BA实验或下一研究阶段。**
'''
write('FINAL_REVIEW.md',main);write('TASK008_REPORT.md',main)
(TASK/'reports').mkdir(exist_ok=True)
with (TASK/'reports/TASK008_REPORT.md').open('x',encoding='utf-8') as f:f.write(main)
write('README.md','''# TASK008 Review 阅读入口

先阅读 FINAL_REVIEW.md，再查看 figures/A_ALL32_OVERLAYS.jpg、figures/B_ALL32_OVERLAYS.jpg、figures/A_B_SELECTED_COMPARISON.jpg 和 figures/RGB312_FIVE_FRAME_DETAIL.jpg。
全部64张逐帧显示在 visuals/A、visuals/B；所有32个目标均保留，不按结果筛选。
statistics 保存全量统计及独立CPU复核，evidence保存真实运行身份/接口/退出码，installation_evidence保留部署与首次加载失败记录。
scripts保留独立实验代码，configs固定输入；没有Baseline修改或模型训练。
原始浮点NPZ和RGB保留本地/服务器，不随公开Review ZIP提交。它们的逐文件SHA及位置见RAW_OUTPUT_AVAILABILITY.md与evidence/RESULT_COLLECTION_MANIFEST.json。
''')
env='''# 独立环境与部署记录

仅新建 `/opt/gamecam-pi3mos/envs/pi3mos-infer`，环境位于系统盘。Python3.10，torch2.3.1+cu121，torchvision0.18.1+cu121，NumPy1.26.4，huggingface_hub0.26.5；完整冻结清单见evidence/ENVIRONMENT_PIP_FREEZE.txt。pip check通过。

RTX3090 24GiB，驱动580.119.02。模型/权重/输入结果位于数据盘。没有运行pip install .，没有安装DPVO扩展、下载DPVO权重或编译CUDA。使用原源码的Torch RoPE回退和可选xformers缺失时的原生路径。

远端官方源码checkout超时后，按授权从本地新clone官方仓库再传输；HEAD保持指定commit。远端Torch/CUDA依赖下载实测过慢，两次仅停止本任务自己的未完成pip下载进程，随后在本地下载精确Linux wheel，逐个传输SHA验证并离线安装到新环境。没有改动旧DROID-W或本地gamecam-vo环境。

初始官方权重被本任务命名为.pth，但实际是safetensors。第一次读取失败时前向0次；保存R1现场，单独R2采用safetensors安全读取并strict=True。未修改权重字节、未使用随机初始化代替、未放宽参数键校验。

最终系统盘剩余约0.68GiB、数据盘约3.68GiB。当前实验已完成，所有后续推理输出均写数据盘；下一阶段安装前需重新核验空间。未清理历史资产、未重启、未关机。

GitHub原有授权在新克隆实例仍可用，仓库Public、默认分支及历史Release均保持。token始终留在既有专用wrapper中，不进入报告、源码或归档。
'''
write('environment_notes.md',env)
with (TASK/'environment_notes.md').open('x',encoding='utf-8') as f:f.write(env)
write('MODEL_INTERFACE.md','''# 独立 Pi3.forward 接口

输入：RGB float32 [B,N,3,H,W]，0–1，不重复ImageNet归一化。当前B=1，N=3或5，H=378，W=672。

| 输出 | 原生形状 | 本次保存 |
|---|---|---|
| dynamic_masks | [1,N,1,H,W,1] | float32最后帧模型网格与原图网格概率 |
| conf | [1,N,H,W,1] | float32最后帧；不是DROID-W U |
| local_points | [1,N,H,W,3] | float32最后帧及z辅助深度 |
| camera_poses | [1,N,4,4] | 最后帧；不拼接为正式相机轨迹 |
| points / dynamic_logits | 见真实接口收据 | 检查有限性；未作为后续DROID输入 |

模型在BF16 autocast下计算，但原始参数与最终返回张量为float32；实际收据见evidence/MODEL_INTERFACE_RECEIPT.json。规范化动态输出：dynamic_masks[0,:,0,:,:,0]。不再次sigmoid，不转换成U，不推导米制尺度。

每个目标NPZ包括 dynamic_probability_model、dynamic_probability_original、confidence_model、depth_model、local_points_last、camera_pose_last、context_rgb_ids、target_rgb_id；原始连续值不由8bit图像重建。
''')
write('PREPROCESS_AND_COORDINATES.md','''# RGB与像素坐标合同

1. 原图Pillow convert RGB；除255一次，float32 CHW。
2. 按官方255000像素上限选14倍数，1920×1080恰好变成672×378（254016pixels），无裁剪、无填充、宽高比不变。
3. 模型内部ImageNet归一化；适配器不重复。
4. 仅最后时刻概率在CPU bilinear align_corners=False恢复原尺寸，再做M>0.4。
5. 半像素映射矩阵：[[0.35,0,-0.325],[0,0.35,-0.325],[0,0,1]]。输入、每帧mapping与源SHA完整保存。

CPU合成RGB红/绿/蓝与官方load_images_as_tensor逐位一致。错误uint8/BGR送入通用tensor helper会产生差别，说明应验证域；这不等于断言官方所有调用路径有错误。
独立float64插值复算及64张Mask检查见statistics/CPU_ARTIFACT_VALIDATION.json；边界的双线性软化是已记录后处理，不是原生全分辨率分割。
''')
write('QUALITATIVE_CASE_REVIEW.md','''# 全32帧人工可视复核

复核依据为全部A/B联系表及预注册6个目标的原图对照，不仅展示最高响应帧。

| 可见情况 | 观察 | 不能据此声称 |
|---|---|---|
| 左侧卡车 | RGB301–323两组连续覆盖，经过画面左边缘后RGB324–332均无阈值区域 | 已证明真实世界运动/精确轮廓或召回率 |
| 道路纹理及明亮护栏 | 未见随路面位移产生大面积标红；固定探针面积为0 | 所有静态背景的误检率为0 |
| 蓝色灯带、路灯与反光 | 本窗口未出现大面积阈值误判，热图仍保留低值响应 | 各类灯光/阴影条件已普遍验证 |
| 机盖 | 相机耦合区域低概率；其世界运动语义未独立标注 | 机盖是静态GT |
| 停放车辆、行人 | 无明确控制目标 | 不会误判停放车/可以识别人 |
| 纯旋转/第三人称跟随 | 不存在独立验证片段；当前为车头视角 | 对第三人称与强旋转鲁棒 |

五帧概率MAD较小，但相邻阈值IoU并未提高；没有运动补偿和GT，不能认定更稳定或更准确。阈值0.6下A/B的区域比例也不同，提示上下文会改变分数大小，固定0.4的相似轮廓不等于概率已校准。
''')
write('CPU_VALIDATION_REPORT.md',f'''# CPU合成与真实产物复核

- 合成颜色/像素域/尺寸/逆映射检查通过，与官方独立RGB reader逐位一致，未初始化CUDA。
- 64份真实NPZ的ID、上下文、SHA、shape/dtype、有限性、概率范围、正深度与local_points z、源RGB复制身份均通过。
- 64份原图概率的独立float64半像素插值最大差{audit['independent_float64_vs_saved_float32_restoration_max_abs']:.9g}（预设容差5e-5）；所有二值Mask逐像素等于保存概率>0.4。
- 0.2/0.4/0.6面积及Confidence均值从数组重新计算，与运行统计一致。
- 520份传输文件SHA全部通过；52张源图与1830份既有DROID源码/配置/JSON前后SHA一致。

这些是产物、数学坐标与资产保护合同验证，**不是64个独立场景，也不是动态检测准确性测试**。审计脚本不导入Torch，不运行模型或GPU；详细逐帧结果见statistics/SAVED_PREDICTION_AUDIT.csv。
''')
write('RAW_OUTPUT_AVAILABILITY.md',f'''# 原始数组与公开Review范围

完整运行目录（服务器）：`/root/rivermind-data/GAMECAM_TASK008_PI3MOS_20261126_R2_FORMAT_VERIFIED`。
完整取回目录（本机）：`D:/aaa/GameCam-VO/experiments/task008_pi3mos/retrieved`。
原始浮点数组：`outputs/night007/A/predictions/00301.npz` 至 `00332.npz`，B同名，共64份，821,090,264 bytes。
原始RGB复制与上下文仍在本机/服务器；输入对应表和SHA见evidence/INPUT_IDENTITY_BEFORE.json、INFERENCE_INPUT_OUTPUT_MANIFEST.json。独立校验的520项清单见evidence/RESULT_COLLECTION_MANIFEST.json。

为遵守“不提交模型权重和大型预测文件”和仓库数据边界，公开包不包含NPZ、原始RGB、权重、环境二进制或源码clone。全量浮点预测没有删除或重编码。
公开包保留全部64张Overlay、64张原图网格二值Mask、每帧概率灰度/热力显示、Confidence/辅助深度、完整联系表、所有推理/分析代码、配置、运行/部署日志和身份清单。概率显示为8bit派生图，不替代float32概率。
部分公开显示图缩为640×360以便浏览：Overlay/概率热力用LANCZOS，概率灰度用BILINEAR；Mask不重采样，Confidence/深度保留原生672×378。VISUAL_DELIVERY_MANIFEST.csv逐项列出原/派生SHA与处理方式。
''')
write('NEXT_STAGE_RECOMMENDATION.md','''# 研究建议（未执行）

保留π³mos为独立动态先验候选。优先补可独立确认的停放车辆、移动车辆、行人及纯旋转控制，尤其需要第三人称跟随相机；在现有单一夜间车头窗口上不能建立普遍动态判别能力。
以3帧作为低代价候选、5帧为对照继续保留，不据全图平滑度宣称5帧优越；若比较时间一致性，应明确运动补偿/目标对应及标签来源。
先确定动态概率语义、边界处理和时序延迟，再单独审批DROID-W接口实验。不能把动态M直接替换U，也不能将本轮深度当米制GT。
没有启动下一阶段、修改DROID-W、训练模型或接入BA。
''')
decision={'stage':'TASK008','status':'PASS_INDEPENDENT_INFERENCE_LIMITED_QUALITATIVE_EVIDENCE',
    'A_targets':32,'B_targets':32,'GPU_forwards':64,'GPU_OOM':False,'strict_weight_loading':True,
    'first_pre_forward_format_error_preserved':True,'GT_accuracy_established':False,
    'five_frame_superiority_established':False,'DROID_W_integration_performed':False,
    'automatic_next_stage':False,'wait_for_human_review':True}
write('DECISION.json',json.dumps(decision,indent=2))

for p in sorted((TASK/'scripts').glob('*.py')):copy(p,'scripts/'+p.name)
for p in sorted((TASK/'configs').glob('*.json')):copy(p,'configs/'+p.name)
for p in sorted((TASK/'analysis').iterdir()):
    if p.is_file():copy(p,'statistics/'+p.name)
for p in sorted(src.iterdir()):
    if p.is_file() and p.suffix in ['.json','.csv','.txt']:copy(p,'evidence/'+p.name)
for p in (src/'logs').iterdir():
    if p.is_file():copy(p,'runtime_logs/'+p.name)
for p in (TASK/'installation_evidence').rglob('*'):
    if p.is_file():copy(p,'installation_evidence/'+p.relative_to(TASK/'installation_evidence').as_posix())
for name in ['SOURCE_ACQUISITION_VERIFIED.json','ASSET_TRANSFER_weight.json','ASSET_TRANSFER_wheels.json',
             'ASSET_TRANSFER_dependency_wheels.json','WEIGHT_FORMAT_CORRECTION.json','RESULT_TRANSFER_VERIFICATION.json',
             'INITIAL_PREFLIGHT.stdout.txt']:
    copy(TASK/'logs'/name,'evidence/'+name)
for p in (src/'outputs/night007/contact_sheets').iterdir():copy(p,'figures/'+p.name)

visual=[]
for mode in ['A','B']:
    for category in ['overlays','masks','probability_gray','probability_heat','confidence','depth']:
        for p in sorted((src/'outputs/night007'/mode/category).iterdir()):
            target=R/'visuals'/mode/category/p.name;target.parent.mkdir(parents=True,exist_ok=True)
            with Image.open(p) as im:
                original_size=list(im.size)
                if category in ['overlays','probability_heat','probability_gray']:
                    method=Image.Resampling.BILINEAR if category=='probability_gray' else Image.Resampling.LANCZOS
                    im=im.resize((640,360),method)
                    if p.suffix=='.jpg':im.save(target,quality=94)
                    else:im.save(target)
                    processing='Display resize to640x360 '+('BILINEAR' if category=='probability_gray' else 'LANCZOS')
                else:shutil.copyfile(p,target);processing='Byte-identical original derived view'
                saved_size=list(im.size)
            visual.append({'path':target.relative_to(R).as_posix(),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                'public_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'source_wh':str(original_size),
                'public_wh':str(saved_size),'processing':processing})
with (R/'VISUAL_DELIVERY_MANIFEST.csv').open('x',encoding='utf-8',newline='') as f:
    wr=csv.DictWriter(f,list(visual[0]));wr.writeheader();wr.writerows(visual)

official=Path(r'D:\aaa\external_models\Pi3MOS-SLAM_TASK008_FRESH');commit='1b81d729c4259a5a775eb4aae41f959eea38ae14'
assert subprocess.check_output(['git','-C',str(official),'rev-parse','HEAD'],text=True).strip()==commit
assert not subprocess.check_output(['git','-C',str(official),'status','--porcelain'],text=True).strip()
files=['README.md','environment.yml','pi3/models/pi3.py','pi3/utils/basic.py','pi3/models/layers/pos_embed.py',
       'pi3/models/layers/attention.py','dpvo/dpvo.py','dpvo/stream.py','dpvo/net.py','config/default.yaml']
source_rows=[]
for name in files:
    canonical=subprocess.check_output(['git','-C',str(official),'show',commit+':'+name])
    blob=subprocess.check_output(['git','-C',str(official),'rev-parse',commit+':'+name],text=True).strip()
    source_rows.append({'path':name,'git_blob_sha':blob,'bytes':len(canonical),'sha256':hashlib.sha256(canonical).hexdigest(),
                        'url':'https://github.com/PRBonn/Pi3MOS-SLAM/blob/'+commit+'/'+name})
write('SOURCE_PROVENANCE.json',json.dumps({'HEAD':commit,'clean':True,'files':source_rows},indent=2))
write('SOURCE_PROVENANCE.md','''# 官方源码与独立适配器依据

全部官方文件以固定提交1b81d729c4259a5a775eb4aae41f959eea38ae14的Git blob核验，身份见SOURCE_PROVENANCE.json。

- [Pi3.forward及原生sigmoid输出](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/pi3/models/pi3.py)：独立模型、内部ImageNet归一化、dynamic/conf输出、exp正深度。
- [官方独立RGB读取与通用tensor预处理](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/pi3/utils/basic.py)：PIL RGB、255000像素、14倍数、LANCZOS与ToTensor。
- [DPVO Pi3权重读取及调用](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/dpvo.py#L159)：官方支持safetensors加载；本轮不运行DPVO。
- [DPVO图像流](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/stream.py)：cv2路径需核查通道/数值域；独立适配器使用明确RGB路径。
- [原生阈值0.4](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/net.py#L110)：只作参考阈值，不是当前数据上调优的阈值。
- [官方安装与权重来源](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/README.md)：本轮绕过setup.py和完整SLAM，仅安装独立forward需要的依赖。

本报告的实际行为以运行收据和保存数组为证据，源码推导不冒充GPU结果；定性观察不冒充GT评价。
''')

task_readme='''# TASK008 Pi3MOS Independent Inference

Frozen official Pi3MOS source remains outside GameCam-VO. See configs/night007_safetensors.json and reports/TASK008_REPORT.md.
Use the independent pi3mos-infer environment. The completed adapter is scripts/infer_pi3mos_safetensors.py; initial infer_pi3mos.py is preserved as the failed pre-forward format attempt, not a second valid pipeline.
No DPVO extension/setup.py, no DROID-W modification, no BA integration. Only approved Night007 A/B inputs. Full float32 outputs are retained privately, excluded from Git.
Review directory: reviews/task008-pi3mos-night007-independent-inference-20261126.
'''
with (TASK/'README.md').open('x',encoding='utf-8') as f:f.write(task_readme)
base=json.loads((PROJECT/'maintenance/GITHUB_TASK008_PUBLICATION_20261126/BASE_ENTRY_IDENTITIES.json').read_text())
entry_head='''2026-11-26（Asia/Shanghai）。当前阶段：**TASK008 π³mos独立推理完成，Night007两组各32帧；有限定性证据，不宣称准确率或VO改进。**

[最终评审](reviews/SLUG/FINAL_REVIEW.md) · [完整展开证据](reviews/SLUG) · [完整Review ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/SLUG/GAMECAM_TASK008_PI3MOS_NIGHT007_REVIEW.zip)

- 官方固定commit、官方safetensors权重strict加载；3090上64次前向完成，无OOM。
- 3帧预热后282.575ms、5.916GiB；5帧426.992ms、6.328GiB。保存所有连续概率、Mask、Overlay、Confidence及辅助深度。
- 卡车轮廓连续，未见大面积背景阈值响应；无动态GT、停放车/行人/纯旋转控制，未证明5帧更优或第三人称泛化。
- 52张RGB和1830份既有DROID-W源码/配置/观测JSON前后SHA一致，Baseline不变，无训练或BA集成。
- 64份数组及像素映射合同复核通过；原始RGB/浮点NPZ/权重不公开提交，位置和SHA随完整Review提供。
- TASK007D的严格米制GT NO-GO继续有效，不自动启动Confidence校准、CADP或下一阶段。

上一封存阶段：[TASK007D固定提交](https://github.com/Pseven0108/GameCam-VO/tree/3bf7da7bb39192081cefe9898e948784ae6cd5aa)。等待人工评审。
'''.replace('SLUG',SLUG)
titles={'README.md':'# GameCam-VO · TASK008','PROJECT_STATUS.md':'# GameCam-VO 项目状态 · TASK008',
        'REVIEW_INDEX.md':'# 当前评审：TASK008','REVIEWING.md':'# 当前审查：TASK008'}
entry_plan=[]
for row in base['files']:
    name=row['path'];path='project_entries/'+name;write(path,titles[name]+'\n\n'+entry_head)
    entry_plan.append({'path':name,'source_file':path,'base_git_blob_sha':row['base_git_blob_sha']})
write('project_entries/ENTRY_UPDATE_PLAN.json',json.dumps({'base_commit':base['base_commit'],'files':entry_plan},indent=2))
write('REVIEW_SCOPE.json',json.dumps({'all_target_frames_shown':True,'visual_files':len(visual),
    'raw_original_RGB_included':False,'large_prediction_NPZ_included':False,'model_weights_or_environment_binaries_included':False,
    'full_review_payload_included':True,'raw_outputs_preserved_at_documented_locations':True},indent=2))
print(json.dumps({'review':str(R),'visual_files':len(visual),'payload_files':sum(p.is_file() for p in R.rglob('*')),
                  'payload_bytes':sum(p.stat().st_size for p in R.rglob('*') if p.is_file())},indent=2))

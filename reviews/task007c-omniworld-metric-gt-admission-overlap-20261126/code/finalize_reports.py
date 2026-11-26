"""Assemble an evidence-tiered admission decision; never infer metric accuracy.

Offline CPU only. Original images, source archives and sealed audits are read-only.
"""
import csv
import hashlib
import json
import platform
from pathlib import Path
import sys
import textwrap

import numpy as np
import PIL

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
SLUG = ROOT.name
ZIP_NAME = "GAMECAM_TASK007C_OMNIWORLD_METRIC_GT_ADMISSION_REVIEW.zip"
BASE = "46a616925a77ada679f2e9975b17f790ff44bdfa"


def read(name): return json.loads((ROOT / name).read_text("utf-8"))
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(name, value):
    p = ROOT / name; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as f: json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write("\n")
def text(name, value):
    p = ROOT / name; p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="\n") as f: f.write(textwrap.dedent(value).strip() + "\n")
def csvout(name, rows):
    with (ROOT / name).open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)


def main():
    intake = read("evidence/CANDIDATE_INTAKE.json")["candidates"]
    transfer = read("evidence/ACQUISITION_RECEIPT.json")
    decode = read("evidence/DECODE_AND_DUPLICATE_VERIFICATION.json")
    tests = read("tests/CPU_TEST_REPORT.json")
    visual = read("evidence/VISUAL_OBSERVATIONS.json")
    camera = read("evidence/CAMERA_CONTRACT_CORRECTION.json")
    assert tests["status"] == "PASS" and tests["tests"] == 16
    assert decode["actual_pairs_checked"] == camera["pairs_verified"] == 9
    assert transfer["compressed_bytes_read"] == 18759680 and len(transfer["files"]) == 18
    assert transfer["model_forwards"] == 0 and "torch" not in sys.modules

    protected = []
    for r in read("evidence/INPUT_PRESERVATION_BEFORE.json")["files"]:
        b = Path(r["path"]).read_bytes()
        assert len(b) == r["bytes"] and sha(b) == r["sha256"]
        protected.append({**r, "unchanged": True})
    prior_reviews = []
    for slug in ["task007a-mpsfm-confidence-calibration-audit-20261126", "task007b-depth-gt-availability-alternative-data-audit-20261126"]:
        prior = PROJECT / "reviews" / slug
        manifest = json.loads((prior / "FILE_SHA256_MANIFEST.json").read_text("utf-8"))
        records = manifest["files"]
        for r in records:
            b = (prior / r["path"]).read_bytes()
            assert len(b) == r["bytes"] and sha(b) == r["sha256"]
        prior_reviews.append({"review": slug, "sealed_manifest_entries_checked": len(records), "status": "PASS"})
    dump("evidence/ORIGINAL_EVIDENCE_PRESERVATION.json", {"original_input_files": protected, "prior_sealed_reviews": prior_reviews,
         "scope": "Five reused input files before/after plus original TASK007A/B manifests; no claim of exhaustive hashing of every historical baseline/data file", "original_files_written": 0})
    dump("evidence/CPU_ENVIRONMENT.json", {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
         "numpy": np.__version__, "Pillow": PIL.__version__, "torch_imported_in_this_process": "torch" in sys.modules,
         "GPU_calls": 0, "model_forwards": 0, "new_dependencies_installed": 0})
    rows = []
    for c in intake:
        obs = next(v for v in visual["observations"] if v["uid"] == c["uid"])
        checks = [v for v in transfer["UID_checks"] if v["uid"] == c["uid"]]
        rows.append({"uid": c["uid"], "frames": "000000;000001;000002", "sample_pairs": 3,
            "caption_viewpoint": "TP_CANDIDATE", "visual_viewpoint": obs["viewpoint"],
            "strict_third_person_eligible": c["uid"] in visual["strict_TP_candidates_supported"],
            "scene_context": obs["context"], "declared_scale": c["metric_scale"],
            "scale_source_row_unique": True, "physical_accuracy_verified": False,
            "valid_pixel_fraction_min": min(v["GT_valid_fraction"] for v in checks),
            "valid_pixel_fraction_max": max(v["GT_valid_fraction"] for v in checks),
            "initial_split_not_official_test": True, "metric_GT_admitted": False})
    csvout("CANDIDATE_UID_AUDIT.csv", rows)
    csvout("DEPTH_SAMPLE_STATISTICS.csv", [{k: v for k,v in q.items() if k not in {"pixelwise_RGB_alignment", "metric_depth_quantiles", "cx_plus_half", "cy_plus_half"}} |
        {"declared_scaled_depth_min": q["metric_depth_quantiles"][0], "declared_scaled_depth_P01": q["metric_depth_quantiles"][1],
         "declared_scaled_depth_median": q["metric_depth_quantiles"][2], "declared_scaled_depth_P99": q["metric_depth_quantiles"][3],
         "declared_scaled_depth_max": q["metric_depth_quantiles"][4]} for q in transfer["UID_checks"]])
    gates = [
        ("VKITTI family training-overlap correction", "PASS", "Public ViT-Large active training data_array includes Virtual_KITTI; exact2.0.3 frame membership of the installed weight unverified"),
        ("Minimal payload integrity", "PASS_WITH_SCOPE", "18 PNG chunk CRCs/full decodes; prefix HTTP identity. No whole archive SHA/gzip CRC claim"),
        ("RGB/depth/member and split mapping", "PASS_SOURCE_INDEX", "9 exact ID pairs, split0 list and camera lengths consistent, all1280x720; no substitutes"),
        ("Depth decoder and source mask", "PASS", "9 actual pairs bitwise equal to official load_depth;16 synthetic boundary tests"),
        ("Metric Scale row and application", "PASS_SOURCE_DECLARATION", "3 unique positive source factors; valid-only scaling and sentinel preserved"),
        ("Independent physical metric scale accuracy", "BLOCKED_UNVERIFIED", "No factor-generation provenance or independently anchored error bound for these UIDs"),
        ("Pixel-accurate RGB/depth sync/alignment", "PARTIAL", "Same grids and broad contour support; no independent calibration or per-frame timestamp certificate"),
        ("Strict third-person candidate eligibility", "PARTIAL", "2 visually supported; night racer text label not confirmed"),
        ("UID-disjoint TP calibration/dev/evaluation", "BLOCKED_INCOMPLETE", "Only2 eligible UIDs; development role pending. No fitting and no shared UID across roles"),
        ("Metric3D training-unseen OWG certification", "UNVERIFIED", "No OWG item found in inspected public recipe; private annotations/backbone web membership not exposed"),
        ("Camera GT/temporal geometry admission", "NOT_ADMITTED", "Existing parking remains; nonunit source quaternion fields observed, no independent camera precision established"),
        ("Metric3D Confidence metric calibration", "NO_GO", "Strict metric GT/independence/holdout gates unresolved; no inference, NLL or Coverage performed")]
    csvout("ADMISSION_GATE_MATRIX.csv", [{"gate": a, "status": b, "evidence_or_limit": c} for a,b,c in gates])
    split = {"state": "PROVISIONAL_NOT_EXECUTABLE", "unit_of_partition": "entire scene UID, including every split/frame/augmentation",
         "calibration_UIDs": ["016d3596da27"], "development_UIDs": [], "evaluation_UIDs": ["0caf78b8eeac"],
         "diagnostic_UIDs_excluded_from_strict_TP": ["03b9161e3ff2"],
         "all_current_9_pairs": "ADMISSION_INSPECTED_ONLY; no fitting and no untouched-test claim",
         "needs": ["Independent scale/admission evidence", "A distinct visually confirmed TP development UID", "Audit cross-UID scene/game duplication before claiming independent scenes"],
         "future_fresh_evaluation": "Reserve new UID or preregister untouched remaining material; already inspected admission samples cannot be relabelled fresh test evidence",
         "official_test_splits_used": False, "fit_rows": 0, "no_role_UID_overlap": True,
         "authorization": "Proposal only; no added UID download, split freeze, model run or fitting this stage"}
    assert not set(split["calibration_UIDs"]) & set(split["evaluation_UIDs"])
    dump("UID_DISJOINT_SPLIT_PROPOSAL.json", split)
    dump("DECISION.json", {"task": "TASK007C", "audit_execution": "COMPLETED", "strict_independent_metric_GT_admission": "NO_GO",
         "state": "TASK007C_COMPLETED_STOPPED_BEFORE_INFERENCE", "decoder_integrity": "PASS", "source_declared_scale_contract": "PASS",
         "physical_scale_accuracy": "UNVERIFIED", "alignment": "QUALITATIVE_ONLY", "training_unseen_status": "UNVERIFIED",
         "candidate_UIDs": 3, "TP_visually_supported": 2, "pairs": 9, "new_compressed_payload_bytes_read": transfer["compressed_bytes_read"],
         "whole_archive_downloads": 0, "CPU_contract_tests": 16, "CPU_failures": 0, "GPU_runs": 0, "model_forwards": 0,
         "NLL": None, "Coverage": None, "Confidence_calibration_fit": None,
         "stop_trigger": "Independent physical metric factor provenance/accuracy not established; no new sampling or expansion after identified blocker",
         "next_stage_started": False, "VIPER_mainline_changed": False, "OWG_camera_benchmark_parking_revoked": False})

    text("TASK007B_DATA_SOURCE_SELECTION_ADDENDUM.md", """
    # TASK007B 数据源选择增补纠正

    2026-11-26。本文件是新增纠正记录；不倒改已经封存的 TASK007B ZIP、报告或历史提交。

    **撤回“Virtual KITTI 2 可作为 Metric3D 训练未见的独立测试集”的推荐。**
    已固定的 Metric3D 公开 ViT-Large 训练配置在 `data_array` 中启用 `Virtual_KITTI`，
    并导入 VKITTI 配置及 train.json。故至少存在训练数据源/家族层面的重叠证据。
    当前检查不能确认实际权重中的 VKITTI 版本、2.0.3 的具体帧或 Train/Test 精确交集。
    不把“精确成员未知”当作“可以证明无重叠”；也不反向捏造每张2.0.3图均参与训练。

    TASK007B 关于 VIPER dense 归档为 RGB、公开像素GT尚未准入、MVS单位局限的证据保留。
    本轮不下载 Virtual KITTI 2，不重跑 Metric3D，不更改 VIPER VO 主线。
    详见 [训练重叠审计](METRIC3D_PRETRAINING_OVERLAP_AUDIT.md) 与 [本轮最终报告](FINAL_REVIEW.md)。
    """)
    text("METRIC3D_PRETRAINING_OVERLAP_AUDIT.md", """
    # Metric3D 训练重叠证据分级

    | 判断 | 等级 | 固定来源 |
    |---|---|---|
    | Virtual_KITTI 在公开 ViT-Large 活跃训练列表 | CONFIRMED_SOURCE | `sources/metric3d/vit.raft5.large.py:24,75,810`；不是只在注释中出现 |
    | VKITTI 配置的训练注释路径 | CONFIRMED_SOURCE | `sources/metric3d/vkitti.py:16`；`public_datasets.py:370-377`有数据登记 |
    | 本项目实际 Metric3D 权重的精确 VKITTI2.0.3 帧清单 | UNVERIFIED | 公开训练说明称私有训练注释JSON未提供；公开重实现不等于权重逐帧训练记录 |
    | OmniWorld-Game 名称未出现在本轮检查的公开训练配置 | LIMITED_NEGATIVE_EVIDENCE | 不能由名称缺失证明所有私有训练、DINO预训练和网络图像均无重叠 |
    | OWG Game 原始 render depth 不是 Metric3D 的预测输出 | SUPPORTED_BY_AUTHOR_PIPELINE | ReShade渲染缓冲区来源；与其他OWG子集的估计pipeline区分 |
    | 这3个UID的米制缩放来源独立、精确 | UNVERIFIED | CSV数值与使用方法已核实，因子生成/物理锚点仍缺 |

    Metric3D固定提交：`eb5b6fac0dc155e4e52f576e304fbf11655ff339`。
    对应历史R2.1权重SHA256：`15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972`；本轮未加载。
    7份来源文件的Git Blob与SHA验证在 `evidence/SOURCE_BLOB_VERIFICATION.json`。

    结论：VKITTI2不得标为训练未见独立测试；OWG也暂不能获得“预训练完全无重叠”的证书。
    UID不跨Calibration/Dev/Evaluation解决本项目内部泄漏，不能解决基础模型训练数据未知问题。

    来源：[Metric3D训练配置](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/training/mono/configs/RAFTDecoder/vit.raft5.large.py)、
    [公开训练说明](https://github.com/YvanYin/Metric3D/blob/eb5b6fac0dc155e4e52f576e304fbf11655ff339/training/README.md)。
    """)
    text("DEPTH_DECODE_SCALE_MASK_REPORT.md", """
    # 深度解码、掩码和尺度合同

    固定Reader：OmniWorld `bd91509e0b840f3082848cd561da60a695e6b70b` 的
    `scripts/utils.py:101-126`。独立实现见 `code/decode_contract.py`。
    对9张实际uint16 PNG，输出深度float32和布尔mask均与单独提取的原官方函数逐位一致。
    未导入整个上游模块、未加载模型。16项CPU合成测试另行检验边界和无效值。

    令 `x = raw.astype(float32)/65535`：

    ```text
    valid = not(x < 0.0015 or x > 65500/65535)
    depth = x / (1000 - 999*x) / 0.004
    depth[not valid] = -1
    depth[valid] *= scene_metric_scale
    ```

    原始98及以下无效，99/100有效；65500有效、65501及以上无效。
    文档的“约0..100”不能替代精确代码阈值。未使用注释掉的逐帧95%远景过滤。
    不把-1哨兵乘以尺度，不做“截断极端值后宣称GT可信”的处理。

    9帧共8,294,400像素；源mask有效7,400,288，无效894,112。
    雪地与屋顶3帧各为100%源有效；夜间赛车有效比例约67.52%至67.85%。
    “源mask有效”只代表通过源规则，不是每个像素真实准确的认证。
    夜间赛车仍存在约64,823的极远源缩放数值，完整保留于统计，不事后隐藏。

    3条Metric Scale唯一行：016d3596da27=389.5556421321845；
    03b9161e3ff2=401.8066861251384；0caf78b8eeac=207.00688933270382。
    CSV整体66,930字节、SHA256 `460ad6d26f775b265da462be679fa96bff6df4e4211a66a9b2aa7d303a826fdf`，
    Git Blob `00b580ead4422f315800191127cf749b38eff697`，均与固定来源一致。
    因此以前“207.006889未核实对应目标UID”的缺口在本轮已补齐；不能将旧结论原样照抄。

    官方把乘因子后的深度称为米制。这里承认源声明及变换实现通过，
    但独立物理精度门禁仍未通过；详见 `METRIC_SCALE_PROVENANCE_ADJUDICATION.md`。
    这不是给数据判定为伪造或断言尺度错误。
    """)
    text("METRIC_SCALE_PROVENANCE_ADJUDICATION.md", """
    # 米制尺度生成来源的证据裁定

    **当前CSV确有3个目标UID的尺度，且Reader实现正确；尚未取得这些因子的生成方法、物理锚点和误差界。**

    2025-11-06作者说明：ReShade buffer先线性化；除0.004用于数值尺度调整，不能单独解释成米。
    [作者原帖](https://github.com/yangzhou24/OmniWorld/issues/3#issuecomment-3494867729)。

    2025-11-24作者说明：Game depth来自ReShade；其他子集才用估计的stereo/prior流程。
    [作者说明](https://github.com/yangzhou24/OmniWorld/issues/10#issuecomment-3568742850)。
    同日作者提出一种可行的近似米制化方案：用MoGe-2在采样帧上预测，再取深度比值的场景尺度。
    [建议方案](https://github.com/yangzhou24/OmniWorld/issues/10#issuecomment-3570627221)。

    **这些旧评论早于2026-03-21的Metric Scale发布，不能推翻后来的发布，也不能证明当前CSV就是用MoGe-2生成。**
    本轮没有找到将具体3个数值连接到该方案或独立标尺的可验证生产记录。
    不声称用过Metric3D，不声称出现已证实的模型循环标注；当前准确说法是来源未知。

    当前审计已解决“行是否对应UID、是否为正数、乘法位置正确”三个问题。
    仍缺：因子是否由引擎坐标、实测物体或其他预测器得到；标定集/帧清单；
    每场景尺度误差；与被测Metric3D及其预训练数据的独立性。
    对具有物理单位解释的NLL、Coverage、整帧尺度错误研究，这些缺口会混淆预测错误与参考尺度错误。
    用Metric3D预测反过来估计参考尺度也不能证明其自身尺度准确。

    下一步最小证据需求是现有因子的官方生成记录或独立物理标定，非再次扩大下载。
    若另行改为仅评估源缩放参考或尺度不变形状，需先明确新的估计对象；
    不能把相对结果改名为米制深度置信校准。本阶段不开展该替代实验，也不联系作者。
    """)
    text("RGB_ALIGNMENT_AND_VIEWPOINT_REPORT.md", """
    # RGB—Depth配对与相机合同

    每UID读取split0真实帧列表，精确获取RGB/Depth的000000、000001、000002；
    3组均为1280×720，Camera数组长度与该split一致。不存在沿用VIPER RGB-1规则、
    相邻帧代替、重编号、复制补齐或对原图重编码。

    3张派生联系表展示各3帧RGB、源解码深度和原位置边缘覆盖：

    - `016d3596da27`：屋顶、建筑、植被和玩家轮廓有粗粒度对应，第三人称玩家可见。
    - `03b9161e3ff2`：夜间赛道、树木和杆体结构有粗粒度对应；没有可确认的第三人称玩家。
      原Caption的TP描述不等于实际图像证明，排除严格第三人称分组。下边缘反射/渲染带保留。
    - `0caf78b8eeac`：武器/玩家、岩石、积雪结构有粗粒度对应，第三人称玩家可见。

    这提供同网格与视觉形状支持，未证明逐像素精确时空对齐、相机真值精度或所有动态区域正确。
    无GT光流、真实逐帧同步时间和独立几何证书，故此门禁只能PARTIAL。
    联系表P01/P99只调显示范围，不改GT掩码，不拟合配准，不计算深度准确率。

    ## 相机像素中心核清

    官方`load_camera_poses`直接使用源cx/cy（此处640/360）；`get_pixel`才把像素坐标加0.5。
    初次ACQUISITION_RECEIPT中的cx_plus_half/cy_plus_half只是加法诊断值，不能作为原生K。
    本轮用原官方函数CPU核验9对K，另交付`NATIVE_K_PIXEL_CONTRACT.csv`和纠正记录；
    不改写原收据，不给K再加一次0.5；没有任何模型消费错误K。
    各帧focal有变化，应保留每帧值，不能臆定单一固定K。

    选中相机原始四元数范数均非单位，个别极大。SciPy从四元数构造旋转会归一化，
    因此“Reader返回有限旋转”不能独立证明标注来源精度。未重写源quats。
    这些相机问题不否定同一PNG的解码，但阻止未经论证的跨帧几何GT声明。
    R6已封存的Camera GT准入未被本次深度审核撤销。
    """)
    text("UID_SPLIT_AND_LEAKAGE_REPORT.md", """
    # UID分组、防泄漏与实验独立性

    本轮选样依据已封存Caption、场景差异和早期可提取帧；没有使用Metric3D预测误差选样。
    3候选中只有2个可见第三人称玩家，不能凑成三份互不相交的严格TP Calibration/Dev/Evaluation。

    `UID_DISJOINT_SPLIT_PROPOSAL.json`仅为待审批方案：

    | 角色 | UID | 状态 |
    |---|---|---|
    | Calibration | 016d3596da27 | 待尺度准入，不拟合 |
    | Development | 空 | 需要新且独立的第三人称UID；本轮不扩样 |
    | Evaluation | 0caf78b8eeac | 暂保留候选角色；已做3帧准入观察，不称全新未观察测试 |
    | 非TP诊断 | 03b9161e3ff2 | 不塞入严格TP开发组来凑数 |

    同一UID的所有split、帧、双目或增强产物必须只属一组；官方Test Split不用于拟合。
    此次所选split0不在3条Metadata的官方Test Split Index中。
    未来最终评价应单独预注册未调参材料，当前9帧只记为准入观察。
    禁止用测试集调sigmoid、isotonic、方差下限或模型选择。
    9张RGB/Depth均无完全重复数组；这不证明不同UID一定没有相同游戏、关卡、轨迹或预训练来源。
    未来还需场景/游戏来源去重，不能把“UID字符串不同”当作独立场景证书。
    """)
    text("SOURCE_INDEX.md", """
    # 固定源索引

    - Metric3D GitHub `eb5b6fac0dc155e4e52f576e304fbf11655ff339`；7份所需源码/说明/许可中的Metric3D部分随包。
    - OmniWorld GitHub `bd91509e0b840f3082848cd561da60a695e6b70b`；Reader与README随包。
    - HF `InternRobotics/OmniWorld` revision `4e34897a2fcf8e1cc44b1ae8d2bbd0188c8f2841`；精确归档路径/LFS声明、读取范围、逐成员hash在ACQUISITION_RECEIPT。
    - 7个Git Blob实测身份在 `evidence/SOURCE_BLOB_VERIFICATION.json`。
    - 作者尺度说明链接、角色、日期与释义在 `sources/AUTHOR_SCALE_EVIDENCE.json`。
    - 正确OmniWorld论文为 [arXiv2509.12201v2](https://arxiv.org/html/2509.12201v2)，其Game数据采集与相机估计来源需区分。

    既有HF元数据里的arXiv2602.04441指向SynthVerse，不能作为OmniWorld论文引用；
    本轮未沿该错链扩展数据集，未改写原始元数据。

    引用层次：源声明、实际字节与CPU函数行为、视觉观察、物理准确性、预训练成员资格分别列出。
    没有凭README“GT”字样自动认证独立精度。
    """)
    text("ACQUISITION_AND_INTEGRITY_REPORT.md", """
    # 最小获取与完整性边界

    只对3个UID、各3对RGB/Depth取样，共18张原始PNG。相机/split/FPS/Caption复用
    已有3个Others归档，不新下载完整Others。先核验归档整体SHA与清单一致，再只读目标成员。

    6个RGB/depth归档使用固定revision的HTTP Range前缀，均206且Content-Range总长与源清单相等。
    每流上限32MiB、总上限256MiB；实际读取18,759,680压缩字节（17.89MiB）。
    找到本流3个精确成员后立即关闭，未读取完整归档；没有重试、替代成员或后续扩样。

    每张PNG：完整成员字节数、逐chunk CRC、Pillow verify、完整像素解码、SHA256、dtype/尺寸均检查。
    不把TAR头校验或CDN的opaque ETag当作独立SHA认证。
    **前缀传输无法核验整归档LFS SHA或整个gzip CRC**；收据明确记为false。
    每个完整成员有本地hash及CRC，只能据此描述本次获取完整性，不能宣称整包SHA通过。

    取得的原始RGB/Depth、camera、Caption、split信息保存在本地raw_inputs，保持原字节；
    公开评审只含逐项身份、检查结果和缩小的派生审查图，不发布原始数据集文件。
    GT尺度来源阻断明确后未继续网络取样，后续均为既有9对的CPU验证与报告。
    """)
    text("NEXT_STAGE_ADMISSION_REQUIREMENTS.md", """
    # 下一阶段准入条件与停止位置

    本轮不自动进入Metric3D Confidence真实推理或统计校准。

    1. 取得现有Metric Scale因子的生成来源，以及目标UID独立物理锚点/精度证据；
       或由用户明确批准不同目标，只研究源缩放参考/尺度不变形状，不声称米制校准。
    2. 解决RGB与Depth逐像素/动态边缘对齐和同步的可量化验证；不能用观察3张缩略图代替。
    3. 建立3个严格TP且场景来源分离的Calibration/Development/Evaluation组；
       当前开发组空缺，已观察材料保持标记，最终测试不拟合。
    4. 将Metric3D精确训练成员未知列为局限；VKITTI家族明确列为有重叠，不能作为训练未见结论。

    以上通过且另获阶段授权后，才按硬件分工：本地RTX5060做小批量实测、3090做正式实验。
    本轮不联系作者、不再下载、不训练Scalix、不改Metric3D/DROID-W、不启动CADP/Confidence-aware BA。
    """)
    text("FINAL_REVIEW.md", """
    # TASK007C 最终评审：OmniWorld-Game Metric GT与训练重叠准入

    2026-11-26（Asia/Shanghai）。**本阶段审计完成；独立米制GT准入NO-GO，停在真实推理之前。**
    数据读取/解码成功与科学评价准入分开裁定；没有宣称校准实验成功。

    ## 六项执行结果

    | 用户任务 | 实际结果 |
    |---|---|
    | 纠正TASK007B数据源结论 | 新增增补报告；Virtual_KITTI进入公开Metric3D活跃训练配置，撤回VKITTI2训练未见独立测试推荐；精确版本/帧重叠未知 |
    | 2～3个UID筛选 | 检查3候选；2个视觉确认第三人称，夜间赛车文本TP标签未获图像支持 |
    | 最小RGB/Depth/Camera获取 | 各UID取0/1/2，9对RGB/Depth；18,759,680压缩字节，17.89MiB，未下载整归档；Camera复用缓存 |
    | 解码、Scale、mask、对齐 | 18PNG CRC与完整解码通过；9对深度/mask与官方函数逐位一致；3条Scale行与乘法通过；物理准确性未知，对齐仅粗粒度视觉支持 |
    | UID分组独立性 | 无拟合、无跨组共享UID；仅2个TP不足3组，开发组空缺；已观察9帧不充作全新最终测试 |
    | 下一阶段门禁 | NO-GO：不启动Metric3D Confidence推理/NLL/Coverage，不启动Scalix、DROID-W或BA |

    ## 核心裁定

    **Scale“存在且用对了”已经核实，Scale“独立且物理精确”尚未核实。**
    其中207.00688933270382确属0caf78b8eeac，旧的“目标行未知”缺口已补齐。
    不沿用旧结论否定新证据。当前Reader和发布说明宣称乘场景因子得到米制；
    但未取得3个因子的生成方法、独立物理标定与误差界。

    作者在2025年说明/0.004是数值调整，并提出MoGe-2比值作近似米制化的建议。
    这些旧评论不能证明2026年发布的CSV采用该方法；本轮也没有证据证明用过Metric3D。
    因此结论是“生成/精度独立性未知”，不是“GT已被证实错误”。
    对需要区分网络尺度错误与GT尺度错误的本任务，仍不足以启动严格米制Confidence校准。

    RGB/depth同为1280×720，源帧号与split配对一致，边缘/玩家轮廓有视觉对应；
    仅3张连续帧/UID，未证明逐像素同步、全场景可靠或Camera GT精度。
    夜间赛车仍保留源有效极远数值，未用事后过滤改善GT。

    ## 已验证与未验证

    - 实际验证：18PNG完整性；9对源decoder/mask等价；9对原生K合同；3个Scale唯一行；
      7份源码Git Blob；16/16CPU边界测试；复用5个输入前后hash、TASK007A/B封存清单复核。
    - 仅源声明/观察：尺度输出称米、Game depth来自ReShade、视觉粗对齐、2个第三人称玩家。
    - 未验证：尺度的独立精度、RGB/Depth精确同步、跨UID游戏/场景去重、基础模型精确预训练成员。
    - 未开展：Confidence推理、校准拟合、NLL、Coverage、Scalix训练、GPU/CUDA、SLAM、CADP/BA修改。

    16个测试是软件合同验证，不是16个真实场景准确性实验。
    图像CRC不能认证整个未下载的gzip/LFS归档；完整范围见获取报告。
    原生K直接使用cx/cy，像素网格独立加0.5；初次收据的加半像素诊断值已在新增记录澄清，
    没有被模型使用、没有改写源数据。

    ## 交付与停止

    完整评审含方案、源码快照、收据、统计、掩码/对齐审查、3张派生联系表、代码、测试、决策与SHA清单。
    原始18PNG及Camera等数据保留本地raw_inputs，按仓库规则不公开上传；包内包含其全部检查身份，
    不把“公开评审完整”混同于“公开再分发原始数据集”。
    根目录README、PROJECT_STATUS、REVIEW_INDEX、REVIEWING在本次发布提交统一更新；TASK007B原包封存。
    GitHub发布和匿名回读收据在maintenance独立记录，包封存后不倒改。

    最有价值的下一步是补足现有尺度因子来源/独立物理标定，而不是继续扩大下载或训练网络。
    当前停在`TASK007C_COMPLETED_STOPPED_BEFORE_INFERENCE`，等待本轮审查，不自动开展下一阶段。
    """)
    text("EXECUTION_LOG.md", """
    # 本轮执行账本

    1. 读取当前工作约定、TASK007A/B实际产物和固定源，不靠聊天摘要认证当前行为。
    2. 固定Metric3D/OmniWorld/HF版本；逐文件Blob核验；公开活跃训练列表确认VKITTI家族重叠。
    3. 只读复用3个Others归档和原始CSV；目标3UID Scale唯一行、split0与Camera计数核实。
    4. 有界前缀提取9对；网络读取17.89MiB，逐PNG CRC/解码/SHA，未下载整归档。
    5. 生成并查看3张派生RGB/depth/edge联系表，标记2个TP和1个TP证据不足候选。
    6. 核对作者尺度评论与后续发布时序，识别独立物理尺度证据阻断；停止进一步取样和扩大实验。
    7. 仅以已获取数据进行官方函数逐位对照、16项CPU测试和9对原生K检查；无模型前向。
    8. 澄清初次收据cx_plus_half为诊断算术而非原生K；新增纠正文件，原收据保留。
    9. 输出NO-GO决策、未完成UID三组方案和TASK007B增补；复核旧输入与封存清单。
    10. 封存完整评审；随后单独发布/匿名回读验证，再按用户要求只删除本轮已交付本地ZIP。

    步骤10的最终发布状态由maintenance发布回读收据证明，不能从本静态日志预认定PASS。
    本轮没有SSH研究计算、CUDA初始化、模型加载、训练、SLAM、自动重试或Baseline更改。
    """)

    state_body = f"""2026-11-26（Asia/Shanghai）。当前阶段：**TASK007C审计完成，独立米制GT准入NO-GO，停在推理之前**。

[最终评审](reviews/{SLUG}/FINAL_REVIEW.md) · [完整展开材料](reviews/{SLUG}) · [完整评审ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/{SLUG}/{ZIP_NAME})

- TASK007B推荐已纠正：公开Metric3D活跃训练列表含Virtual_KITTI，不再推荐VKITTI2为训练未见独立测试；精确权重帧重叠未知。
- 本轮3个OmniWorld候选、9对RGB/Depth、17.89MiB前缀读取；18PNG检查通过，9对decoder/mask与官方逐位一致，16/16CPU测试。
- 3个UID的Metric Scale行和应用已核实；独立物理尺度来源/精度仍未核实，RGB/Depth精确同步仅有粗视觉支持。
- 只有2个候选视觉确认第三人称；严格UID-disjoint Calibration/Dev/Evaluation尚不完整。无拟合、无NLL/Coverage、无GPU前向。
- VIPER保持VO主线，DROID-W/Metric3D冻结；本次深度审核不撤销既有OWG Camera Benchmark封存/未准入状态。
- 不启动Scalix、Confidence-aware BA或CADP，不扩大下载、不自动进入下一阶段。

上一阶段原始评审和历史状态保留于[固定提交](https://github.com/Pseven0108/GameCam-VO/tree/{BASE})；更正采用增补文件，不倒改历史ZIP。
"""
    base_entries = read("project_entries/BASE_ENTRIES.json")
    plan = []
    titles = {"README.md": "# GameCam-VO · TASK007C", "PROJECT_STATUS.md": "# GameCam-VO 项目状态 · TASK007C",
              "REVIEW_INDEX.md": "# 当前评审：TASK007C", "REVIEWING.md": "# 当前审查：TASK007C"}
    for entry in base_entries["files"]:
        content = titles[entry["display_title"]] + "\n\n" + state_body
        if entry["display_title"] == "REVIEW_INDEX.md":
            content += "\n---\n\n## 历史索引：TASK007B（数据源推荐已由TASK007C增补纠正）\n\n"
            content += f"[原始TASK007B评审](https://github.com/Pseven0108/GameCam-VO/blob/{BASE}/reviews/task007b-depth-gt-availability-alternative-data-audit-20261126/FINAL_REVIEW.md) · [当前增补](reviews/{SLUG}/TASK007B_DATA_SOURCE_SELECTION_ADDENDUM.md)\n\n"
            old = entry["content"]
            marker = "## 历史评审索引（非当前状态）"
            assert marker in old
            content += old[old.index(marker):]
        elif entry["display_title"] == "REVIEWING.md":
            content += "\n审查重点：训练家族重叠vs精确成员未知；源声明米制vs独立物理标定；PNG/decoder通过vs整归档未校验；2个TP不足3组；旧评论与新Scale发布时序。\n"
        target = "project_entries/" + entry["display_title"]
        text(target, content)
        plan.append({"path": entry["display_title"], "base_ref": BASE, "base_git_blob_sha": entry["sha"], "source_file": target})
    dump("project_entries/ENTRY_UPDATE_PLAN.json", {"base_commit": BASE, "scope": "Four root state entries in a new review branch; preserve visibility/default branch/sealed history", "files": plan})
    print(json.dumps({"decision": "NO_GO_STRICT_INDEPENDENT_METRIC_GT", "raw_pairs": 9, "CPU_tests": 16,
          "historical_reviews_checked": prior_reviews, "reports_generated": True}, indent=2))


if __name__ == "__main__": main()

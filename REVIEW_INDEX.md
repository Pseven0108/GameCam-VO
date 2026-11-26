# 当前评审：TASK007D

2026-11-26（Asia/Shanghai）。当前阶段：**TASK007D来源追溯完成；用途B（相对/辅助诊断），严格米制GT仍NO-GO**。

[最终评审](reviews/task007d-metric-scale-provenance-audit-20261126/FINAL_REVIEW.md) · [完整证据](reviews/task007d-metric-scale-provenance-audit-20261126) · [完整Review ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task007d-metric-scale-provenance-audit-20261126/GAMECAM_TASK007D_METRIC_SCALE_PROVENANCE_REVIEW.zip)

- GitHub main完整可达历史26提交、6个CSV版本及3个UID已核查。2026-03-21新增484行Metric Scale列，其余字段未变；当前CSV与发布时字节一致。
- Reader只读取/应用尺度；未找到绑定三UID的生成程序、拟合帧、独立物理标尺或误差界。
- 作者旧的MoGe-2近似建议不能当作当前因子的生产事实；是否使用Metric3D或Test拟合仍未知。
- 不启动Metric3D Confidence校准/NLL/Coverage。模型运行0、GPU/CUDA0、新原始数据/权重下载0。
- TASK007A/B/C封存141项SHA通过；不改历史Release、VIPER主线或Baseline。
- VKITTI2训练家族重叠纠正继续有效；Scalix、CADP与Confidence-aware BA不启动。

完整历史入口保留在[上一固定提交](https://github.com/Pseven0108/GameCam-VO/tree/30c4149863ce202f4545a872707f0a6fc6a0bfb1)。本次不自动进入下一阶段。

---

## 上一阶段：TASK007C

[TASK007C原始评审](https://github.com/Pseven0108/GameCam-VO/blob/30c4149863ce202f4545a872707f0a6fc6a0bfb1/reviews/task007c-omniworld-metric-gt-admission-overlap-20261126/FINAL_REVIEW.md) · [原始完整ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task007c-omniworld-metric-gt-admission-overlap-20261126/GAMECAM_TASK007C_OMNIWORLD_METRIC_GT_ADMISSION_REVIEW.zip)

---

## 历史索引：TASK007B（数据源推荐已由TASK007C增补纠正）

[原始TASK007B评审](https://github.com/Pseven0108/GameCam-VO/blob/46a616925a77ada679f2e9975b17f790ff44bdfa/reviews/task007b-depth-gt-availability-alternative-data-audit-20261126/FINAL_REVIEW.md) · [当前增补](reviews/task007c-omniworld-metric-gt-admission-overlap-20261126/TASK007B_DATA_SOURCE_SELECTION_ADDENDUM.md)

## 历史评审索引（非当前状态）

# TASK007A Confidence calibration admission audit

2026-11-26：10 cached VIPER frames; pixelwise GT admission failed. No calibration fit or GPU inference. 22/22 CPU mapping tests passed.

[TASK007A final review](reviews/task007a-mpsfm-confidence-calibration-audit-20261126/FINAL_REVIEW.md) · [完整评审ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task007a-mpsfm-confidence-calibration-audit-20261126/GAMECAM_TASK007A_CONFIDENCE_CALIBRATION_AUDIT_REVIEW.zip) · [执行规范](docs/LOCAL_EXPERIMENT_WORKFLOW.md)

TASK007A STOPPED_AT_DATA_ADMISSION. NLL, coverage and calibration curves not computed. No Scalix training or baseline change.

---

# 本地 RTX 5060 环境与三级执行规范

2026-11-26：现有 gamecam-vo 环境，12/12 合成GPU检查通过；未运行研究模型。

[环境评审](reviews/local-rtx5060-environment-20261126/FINAL_REVIEW.md) · [完整评审ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/local-rtx5060-environment-20261126/GAMECAM_LOCAL_RTX5060_ENVIRONMENT_REVIEW.zip) · [执行规范](docs/LOCAL_EXPERIMENT_WORKFLOW.md)

本条为工程环境更新；研究阶段仍保留 TASK006A-R2.2 的评审状态。

---

# 最新评审：TASK006A-R2.2

[最终评审](reviews/task006a-r2-2-depth-restoration-gt-audit-20261126/FINAL_REVIEW.md) · [展开材料](reviews/task006a-r2-2-depth-restoration-gt-audit-20261126) · [完整原始ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task006a-r2-2-depth-restoration-gt-audit-20261126/GAMECAM_TASK006A_R2_2_DEPTH_RESTORATION_GT_REVIEW.zip)

完整ZIP包含全部28份NPZ。

---

## 历史索引

# 最新评审：TASK006A-R2.1

[最终评审](reviews/task006a-r2-1-metric3d-gpu-pilot-20261126/FINAL_REVIEW.md) · [完整报告](reviews/task006a-r2-1-metric3d-gpu-pilot-20261126/R2_1_FINAL_RESEARCH_REPORT.md) · [展开材料](reviews/task006a-r2-1-metric3d-gpu-pilot-20261126) · [完整原始ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task006a-r2-1-metric3d-gpu-pilot-20261126/GAMECAM_TASK006A_R2_1_METRIC3D_GPU_REVIEW.zip)

完整ZIP含原始NPZ；展开报告与CSV可直接审查。请区分GPU推理、严格门禁失败与次级非米制诊断。

---

## 历史索引

# 最新评审：TASK006A-R2（部分完成）

[最终研究报告](reviews/task006a-r2-depth-prior-reliability-20261126/TASK006A_R2_FINAL_RESEARCH_REPORT.md) · [完整展开评审](reviews/task006a-r2-depth-prior-reliability-20261126) · [完整原始ZIP](review_packages/GAMECAM_TASK006A_R2_DEPTH_PRIOR_RELIABILITY_REVIEW.zip)

源码/数据/61项CPU工具测试已完成；真实推理与GT资格仍阻断。请保留未知项，不将未测CSV当成零。

---

## 历史评审索引

# 最新评审 · TASK006A-R1（2026-11-26）

[最终评审](reviews/task006a-r1-cadp-cpu-20261126/FINAL_REVIEW.md) · [完整展开目录](reviews/task006a-r1-cadp-cpu-20261126) · [完整评审ZIP](review_packages/GAMECAM_TASK006A_R1_CADP_CPU_REVIEW.zip)

所有R1原始文件与完整ZIP均已包含，无省略载荷。先读最终评审，再读数学推导、稳定性报告、代码及 `results/research_003`。历史R0来源随包提供。

---

# TASK005B-R3 latest review

[Expanded review](reviews/task005b-r3-reduction-u-isolation-20261125/FINAL_REVIEW.md) · [Entire evidence ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task005b-r3-reduction-u-isolation-20261125/GAMECAM_TASK005B_R3_REVIEW.zip)

---

# TASK005B-R2 latest review

[Expanded review](reviews/task005b-r2-native-numerics-20261125/FINAL_REVIEW.md) · [Entire evidence ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task005b-r2-native-numerics-20261125/GAMECAM_TASK005B_R2_REVIEW.zip)

---

# Latest GPU partial-results review

[task005b-gpu-mechanism-20261125](reviews/task005b-gpu-mechanism-20261125/FINAL_REVIEW.md) · [ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task005b-gpu-mechanism-20261125/GAMECAM_TASK005B_GPU_MECHANISM_REVIEW_20261125.zip) · [all native data assets](https://github.com/Pseven0108/GameCam-VO/releases/tag/task005b-gpu-mechanism-20261125).

---

# 最新准备评审

[task005b-depth-path-preparation-20261125](reviews/task005b-depth-path-preparation-20261125/FINAL_REVIEW.md) · [完整ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task005b-depth-path-preparation-20261125/GAMECAM_TASK005B_DEPTH_PATH_PREPARATION_REVIEW_20261125.zip)。

---

# 最新评审

[task005a-d-schedule-mechanism-20261125](reviews/task005a-d-schedule-mechanism-20261125/FINAL_REVIEW.md) · [完整ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task005a-d-schedule-mechanism-20261125/GAMECAM_TASK005A_D_SCHEDULE_MECHANISM_REVIEW_20261125.zip) · [展开文件](reviews/task005a-d-schedule-mechanism-20261125)。

---

# 最新完整评审入口

[task004c-b-crossover-full-20261125](reviews/task004c-b-crossover-full-20261125/FINAL_REVIEW.md) · [完整ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task004c-b-crossover-full-20261125/TASK004C_B_CROSSOVER_FULL_REVIEW_20261125.zip) · [展开目录](reviews/task004c-b-crossover-full-20261125)。

---

# 评审索引

最新：[GPU C0 R2报告](reviews/task004c-b-gpu-c0-r2-20261124/FINAL_REVIEW.md)。真实初始化完成，完整C0因函数闭包检查失败。

| 阶段 | 阅读入口 | 文件数 | 省略附件 |
|---|---|---:|---:|
| task001 | [报告](reviews/task001/FINAL_REVIEW.md) | 22 | 0 |
| task002a | [报告](reviews/task002a/README_PLEASE_READ.md) | 32 | 2 |
| task002b | [报告](reviews/task002b/TASK002B_FINAL_REVIEW.md) | 49 | 14 |
| task002b-addendum | [报告](reviews/task002b-addendum/TASK002B_ADDENDUM_FINAL_REVIEW.md) | 64 | 13 |
| task003 | [报告](reviews/task003/TASK003_FINAL_REVIEW.md) | 82 | 13 |
| task004-design | [报告](reviews/task004-design/TASK004_FINAL_REVIEW.md) | 80 | 0 |
| task004a-readiness | [报告](reviews/task004a-readiness/TASK004A_FINAL_REVIEW.md) | 172 | 3 |
| task004a-scope-storage | [报告](reviews/task004a-scope-storage/TASK004A_FINAL_RELEASE_RECOMMENDATION.md) | 16 | 0 |
| task004a | [报告](reviews/task004a/TASK004A_FINAL_CAUSAL_SCREENING_REVIEW.md) | 212 | 8 |
| task004b | [报告](reviews/task004b/TASK004B_FINAL_RESEARCH_REVIEW.md) | 858 | 25 |
| task004c-phase0 | [报告](reviews/task004c-phase0/FINAL_REVIEW.md) | 69 | 2 |
| task004c-a | [报告](reviews/task004c-a/TASK004C_FINAL_RESEARCH_REVIEW.md) | 219 | 16 |
| task004c-b-protocol | [报告](reviews/task004c-b-protocol/TASK004C_B_PROTOCOL_FINAL_REVIEW.md) | 64 | 0 |
| task004c-b-integration | [报告](reviews/task004c-b-integration/TASK004C_B_FINAL_BA_FILLER_HOOK_REPORT.md) | 170 | 20 |
| task004c-b-release-fixes | [报告](reviews/task004c-b-release-fixes/FINAL_REVIEW.md) | 238 | 0 |
| task004c-b-gpu-c0-20261124 | [报告](reviews/task004c-b-gpu-c0-20261124/FINAL_REVIEW.md) | 58 | 0 |
| task004c-b-gpu-c0-r2-20261124 | [报告](reviews/task004c-b-gpu-c0-r2-20261124/FINAL_REVIEW.md) | 89 | 0 |

最新包完整上传，原SHA清单保持不变。历史包省略内容以publication/manifests为准。

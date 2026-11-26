# GameCam-VO · TASK006A-R2.1 真实GPU推理验证

2026-11-26。**GPU_PILOT_COMPLETE / FORMAL_GT_ACCURACY_BLOCKED / CADP_INTEGRATION_NO_GO**。

[最终评审](reviews/task006a-r2-1-metric3d-gpu-pilot-20261126/FINAL_REVIEW.md) · [完整报告](reviews/task006a-r2-1-metric3d-gpu-pilot-20261126/R2_1_FINAL_RESEARCH_REPORT.md) · [展开材料](reviews/task006a-r2-1-metric3d-gpu-pilot-20261126) · [完整原始ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task006a-r2-1-metric3d-gpu-pilot-20261126/GAMECAM_TASK006A_R2_1_METRIC3D_GPU_REVIEW.zip)

RTX3090完成16图/33次前向，保存Native Confidence、Flip TTA和实际256-bin统计。
74项最新CPU检查通过。Confidence实测约-2.519至6.544，不是概率。
次级诊断在Calibration0000拟合单一scale，再对Test0001的3帧评价：
AbsRel>0.2 AUROC为Native0.812、Flip0.675、初始Entropy0.277；Flip的AUSE略好，不宣称全面优胜。
未核实raw GT物理单位；严格入口在7个零预测处停止，其失败保留。另有明确标注、不删点的次级诊断。
不进入CADP/BA/Task007。没有训练、SLAM、源码/权重修改或实例重启关机。

完整ZIP338,633,937 bytes，含全部16份原始模型输出；199成员CRC和198内部SHA通过。
SHA256 `fc8dfeb8e2746c8033621af9647a382e9e3138ff09bf46e8ddee453f678c7ae8`。
仓库保持Public；发布使用独立分支。下列文字是历史状态。

---

## 历史记录

# GameCam-VO · TASK006A-R2 深度先验可信度阶段证据

2026-11-26。**PARTIAL_WAITING_GPU_AND_GT_ADMISSION**。
进入联合可信度控制器：**NO-GO_INSUFFICIENT_INDEPENDENT_EVIDENCE**，并非证明 Metric3D Confidence 无效。

[最终研究报告](reviews/task006a-r2-depth-prior-reliability-20261126/TASK006A_R2_FINAL_RESEARCH_REPORT.md) · [完整展开评审](reviews/task006a-r2-depth-prior-reliability-20261126) · [完整原始ZIP](review_packages/GAMECAM_TASK006A_R2_DEPTH_PRIOR_RELIABILITY_REVIEW.zip)

已完成：实际 Metric3D commit/283 Git blobs/权重SHA核验、Confidence生成与监督源码、四篇核心论文相关全文阅读、100帧真实GT数据审计、300文件来源复核、61/61 CPU评价合同测试。

未执行：模型推理、Confidence数值分布、TTA/bin真实效果、独立GT误差评价。GPU探针Exec format error；VIPER审阅本地资产无dense-depth GT，MVS单位未核实且只有一条完整GT序列。不用R1几何输出作伪GT。

原始ZIP：2,249,504 bytes，116成员；CRC和115项内部SHA通过。SHA-256：`99b71271a53dd84292409be1e9b8dee65feeb54c8d338a777e3b4d3ebe4edb6f`。
完整源码/CSV/JSON/日志/图与原ZIP一同提供，未上传模型权重或完整原始数据。R1及其他历史封存结果保持不变。
本分支的状态取代下列历史阶段文字；仓库仍为Public，默认分支不变。

---

## 先前阶段原文（历史记录）

# GameCam-VO · TASK006A-R1 CADP CPU数学原型

2026-11-26。状态：**TASK006A_R1_COMPLETE_WAITING_FOR_HUMAN_REVIEW**。

[最终评审](reviews/task006a-r1-cadp-cpu-20261126/FINAL_REVIEW.md) · [完整展开目录](reviews/task006a-r1-cadp-cpu-20261126) · [完整评审ZIP](review_packages/GAMECAM_TASK006A_R1_CADP_CPU_REVIEW.zip)

97/97测试通过；24个合成系统、96次分块协方差对照；18组D0/D1数学端点通过。保留错误先验的反例：合成局部位姿增量误差0.20→0.33925。真实CUDA/Native-U等价性、原生估计器协方差与真实SLAM收益均未认证。

本轮全程CPU float64，没有GPU、模型、C0恢复或真实VIPER运行，未修改Baseline。R2未启动。完整ZIP与原始文件逐字节保留，内含100个成员，99项内部SHA及CRC通过。

ZIP SHA-256：`880e8d4cf2e3cf1237e413fcb94c601ae0f3f4b27e09aa3af0f72ff968613f9b`。

用户在R1完成后另行授权本次GitHub发布；封存包中“未发布GitHub”的记录描述生成包时的执行范围，见[发布说明](reviews/task006a-r1-cadp-cpu-20261126/PUBLICATION_NOTES.md)。公开可见性与默认分支保持原状，发布不构成R2授权。

---

## 先前阶段状态（历史记录）

# GameCam-VO · TASK005B-R3 reduction and U feedback isolation

Completed 16 isolated Jjj calls, 16 isolated J_linear calls and 20 two-iteration BA replays on the sealed D0_S1_RGB233 context. Both isolated reductions fluctuate under fixed inputs. Fixed U retains native affine/temp updates and blocks only U feedback into the next round. See the final report for endpoint gates, causal limits and readiness decisions. No S0, remaining S1 matrix, full-sequence model run or shutdown.

[Final review](reviews/task005b-r3-reduction-u-isolation-20261125/FINAL_REVIEW.md) · [Isolation results](reviews/task005b-r3-reduction-u-isolation-20261125/R3_REDUCTION_ISOLATION.md) · [U feedback](reviews/task005b-r3-reduction-u-isolation-20261125/R3_U_FEEDBACK.md) · [Readiness decision](reviews/task005b-r3-reduction-u-isolation-20261125/R3_CANDIDATE_READINESS.md) · [Complete review ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task005b-r3-reduction-u-isolation-20261125/GAMECAM_TASK005B_R3_REVIEW.zip)

The complete ZIP (835,515,271 bytes) contains the exact full input archive, fixed R2 intermediate, all 52 output NPZ files, complete scientific logs and independent diagnostic binary. CRC and all 299 internal SHA-256 entries verified. Reports and CSV files are expanded for direct review.

Task004C-B, Task005A, TASK005B-R1 and R2 remain sealed. Instance remains running.

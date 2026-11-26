# 当前审查：TASK006A-R2.2

[最终评审](reviews/task006a-r2-2-depth-restoration-gt-audit-20261126/FINAL_REVIEW.md) · [展开材料](reviews/task006a-r2-2-depth-restoration-gt-audit-20261126) · [完整原始ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task006a-r2-2-depth-restoration-gt-audit-20261126/GAMECAM_TASK006A_R2_2_DEPTH_RESTORATION_GT_REVIEW.zip)

重点审查：插值修复与精度改善的区别；官方resized focal与历史focal隔离；GT单位/Inf/float16精度；
198相邻检查及最大平移控制的证据边界；0001不是fresh test；不按坏预测删点；严重事件>=1；
Native raw score不是概率；高分严重错误数量和低基率/AP；原始失败证据；完整ZIP的28份NPZ。
不得据本轮批准训练、CADP接入或新的SLAM。

---

## 历史说明

# 当前审查：TASK006A-R2.1

[最终评审](reviews/task006a-r2-1-metric3d-gpu-pilot-20261126/FINAL_REVIEW.md) · [完整报告](reviews/task006a-r2-1-metric3d-gpu-pilot-20261126/R2_1_FINAL_RESEARCH_REPORT.md) · [展开材料](reviews/task006a-r2-1-metric3d-gpu-pilot-20261126) · [完整原始ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task006a-r2-1-metric3d-gpu-pilot-20261126/GAMECAM_TASK006A_R2_1_METRIC3D_GPU_REVIEW.zip)

重点检查：仅mask_token未加载的推理无mask证明；hook/nohook逐位一致；16图33forward和真实输出；
GT单位/官方5文件子集的限制；原strict零值失败与次级协议分开；校准只用0000、Test0001未拟合；
Native AUROC与Flip AUSE的指标冲突；Entropy未Test翻号；完整ZIP包含全部原始NPZ，SHA可复核。
不要据本轮宣称Night准确性或批准CADP集成。

---

## 历史说明

# 当前评审：TASK006A-R2（部分证据包）

[最终研究报告](reviews/task006a-r2-depth-prior-reliability-20261126/TASK006A_R2_FINAL_RESEARCH_REPORT.md) · [完整展开评审](reviews/task006a-r2-depth-prior-reliability-20261126) · [完整原始ZIP](review_packages/GAMECAM_TASK006A_R2_DEPTH_PRIOR_RELIABILITY_REVIEW.zip)

请优先检查：

1. 首页七个研究问题全部区分已知与未测，NO-GO仅针对当前接入资格。
2. 实际Metric3D commit与283文件、权重SHA，不使用注释旧commit。
3. Confidence loss排除严重错误像素的精确mask；没有据此宣布模型失效。
4. MVS 100帧审计、非零基线Z/range对照、单位未核实和一条完整序列的划分限制。
5. 61项CPU评价器测试与未执行GPU实验分开；原始CSV保留空值。
6. 完整ZIP及展开成员一致；R1、原始数据、生产入口和权重的保护复核。

不要用主观热图代替GT准确性，不把raw score当概率，不据当前结果进入CADP/BA融合。

---

## 历史审查说明

# 当前评审：TASK006A-R1

[最终评审](reviews/task006a-r1-cadp-cpu-20261126/FINAL_REVIEW.md) · [完整展开目录](reviews/task006a-r1-cadp-cpu-20261126) · [完整评审ZIP](review_packages/GAMECAM_TASK006A_R1_CADP_CPU_REVIEW.zip)

请审查完整材料：

1. `reviews/task006a-r1-cadp-cpu-20261126/FINAL_REVIEW.md` 与 `AUDIT_DECISION.json`。
2. `MATHEMATICAL_DERIVATION.md` 中prior-off正则化precision、消元后阻尼、原生ix<=0回代差异。
3. `results/research_003` 中97项测试、联合逆oracle、96次分块对照、18组端点及错误prior反例。
4. `src/`、`tests/`、`NUMERICAL_STABILITY_AND_LIMITATIONS.md`、完整SHA与 `deliveries/ZIP_VALIDATION.json`。

请区分合成数学验证、原生GPU等价性、概率校准及真实轨迹收益。不要把CPU端点通过解释为历史Native-U门槛通过。k/tau未校准，R2未授权。sealed文件中发布前的状态由PUBLICATION_NOTES解释，不修改原始执行证据。

---

## 旧阶段审查说明（历史记录）

# 如何审查最新实验

当前仓库为公开状态，可直接读取公开的Markdown/CSV/JSON。也可通过已连接的GitHub按仓库Pseven0108/GameCam-VO、分支codex/research-review-20261124和路径读取。

先读README.md、PROJECT_STATUS.md、REVIEW_INDEX.md，再读reviews/task004c-b-gpu-c0-r2-20261124/FINAL_REVIEW.md及同目录的TASK004C_B_GPU_C0_R2_REPORT.md、C0_CLOSURE_BLOCKER.md和TASK004C_B_C0_STATE_MANIFEST.json。

重点核对：NativeViperRGB严格零占位合同；21项真实Loader/152项回归的原始记录和首次缺测试对照文件的失败；真实16+8初始化更新与24次BA；保存器拒绝Metric3D lora_dropout；完整C0和47族未持久化；未自动重试。

不能将初始化完成当成完整C0成功，不能把GPU前的CPU测试当成真实运行证明，也不能把Rerun文件存在当成浏览器渲染成功。运行源码与GitHub快照提交分开见source/SOURCE_PROVENANCE.json。

未来若仓库改回私有，应在ChatGPT中连接GitHub并授权此仓库，具体见[官方连接说明](https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt)。

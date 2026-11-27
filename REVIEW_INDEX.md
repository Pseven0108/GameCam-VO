<!-- TASK011A-20261127 -->
# TASK011A · 深度可信度复核与融合 · 2026-11-27

当前唯一实验主线：VIPER。16张旧缓存、原指标复现、Native＋Flip固定融合和VIPER行为分析已完成；没有新GPU推理或BA接入。等权融合改善AUSE/Spearman，但对Native的AUROC/AP退化；尚无独立概率校准或VIPER深度准确率证书。

[最终报告](reviews/task011a-depth-reliability-fusion-20261127/FINAL_REVIEW.md) · [完整展开证据](reviews/task011a-depth-reliability-fusion-20261127/) · [完整ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task011a-depth-reliability-fusion-20261127/GAMECAM_TASK011A_DEPTH_RELIABILITY_FUSION_REVIEW.zip)

---

<!-- VIPER_ONLY_CURRENT_SCOPE_20261127 -->
# 当前实验主线：VIPER

2026-11-27，用户明确决定：停止早期第三人称方向，清理 WildWorld、OmniWorld-Game、DigiDogs、GameVerse 数据和早期实验。后续仅按 VIPER 的最新授权任务继续 DROID-W 优化，不从旧聊天、旧报告或历史提交自动恢复第三人称任务。

TASK010-A 已完成，结论为 `NO_GO_FOR_GENERALIZED_IMPROVEMENT`；尚无被接受的通用改进方案。保持现有 VIPER Baseline 与冻结评价协议。本次是清理和方向更新，不启动新实验。

详见 [当前范围](CURRENT_RESEARCH_SCOPE.json) 与 [清理记录](reviews/viper-only-thirdperson-cleanup-20261127/FINAL_REVIEW.md)。

---

<!-- TASK010A-20261127 -->
# TASK010-A · 2026-11-27

Status: **NO_GO_FOR_GENERALIZED_IMPROVEMENT**. Preselected candidate: `depth`. 42 matched development and126 frozen cross-scene repetitions completed; four independent model providers on9windows. Bounded local32-frame protocol; no production baseline replacement or automatic next stage.

[Complete review](reviews/task010a-dynamic-geometry-20261127/FINAL_REVIEW.md) · [All tables and evidence](reviews/task010a-dynamic-geometry-20261127/) · [Review ZIP](review_packages/GAMECAM_TASK010A_REVIEW.zip) · [Full raw-array assets](https://github.com/Pseven0108/GameCam-VO/releases/tag/task010a-research-20261127)

---

# GameCam-VO · TASK009 本地模块迁移原型

2026-11-27。已完成本地 RTX5060 的9次真实 DROID-W 运行与独立模块验证；本轮已停止推理。

[最终评审](reviews/task009-module-integration-20261127/FINAL_REVIEW.md) · [完整展开评审包](reviews/task009-module-integration-20261127) · [下载完整ZIP](review_packages/GAMECAM_TASK009_REVIEW.zip) · [ZIP SHA-256](review_packages/GAMECAM_TASK009_REVIEW.zip.sha256)

- **本窗口优先保留 BA-Track 静态目标辅助**：Sim3 ATE 2.733–3.500，对比本地E0 6.497–6.619。
- π³MOS门控与组合未改善；WildGS尚未通过跨域准入。Easi attention与LEAP仅独立推理，不声称轨迹收益。
- 32帧 Night val007 RGB301..332，216×384，stride1；距离是游戏单位，不是米。不是原R2复现，没有第三人称/跨场景泛化证据。
- 23项CPU测试、3次同输入CUDA向量化逐位核验、9组轨迹指标复算通过。
- 项目Conda实际目录 `D:\aaa\envs\gamecam-vo`，缓存和临时存储在D；107416文件迁移SHA一致，旧路径Junction兼容。系统/WSL发行版根盘未整体迁移。
- 原基线、权重、历史结果和6份用户dirty文件受保护；本轮无远程操作、无训练、无重启/关机。
- ZIP：7,132,044 bytes；CRC PASS；263项内部SHA通过；SHA-256 `68c161a32cd61226f7cc4f933ec770835024843a30b81803bcf5827d97ae7791`。

本轮独立于已封存TASK008支线；按新任务授权只读复用已有概率缓存，没有恢复其服务器实验。
可重跑代码在 `gamecam/modules/` 与 `experiments/TASK009/scripts/`；统一说明配置在 `configs/task009/local_exploration.json`。
完整作用范围、耗时边界、失败尝试与未完成项目见评审报告。权重、环境二进制、原始RGB/GT和大型先验不公开上传。

<details>
<summary>上一阶段封存记录（dc5f1f23b0e9，历史状态）</summary>

# 当前评审：服务器清理与Baseline方向恢复

2026-11-27（Asia/Shanghai）。**TASK008已按用户指令停止并封存，研究方向恢复为DROID-W Baseline优化。当前没有新实验运行。**

[本轮清理报告](reviews/task008-task007d-server-cleanup-baseline-resume-20261127/FINAL_REVIEW.md) · [完整清理评审](reviews/task008-task007d-server-cleanup-baseline-resume-20261127) · [完整ZIP](https://github.com/Pseven0108/GameCam-VO/releases/download/task008-task007d-server-cleanup-baseline-resume-20261127/GAMECAM_SERVER_CLEANUP_BASELINE_RESUME_REVIEW.zip)

- 数据盘实测释放7.468 GiB，可用11.126 GiB；系统盘释放5.062 GiB，可用5.745 GiB。
- 清理TASK008专用环境/权重/安装缓存/已备份服务器预测，以及TASK007D重复ZIP。2,318份源码、RGB和Manifest保护核验一致。
- 本地64份原始浮点预测、历史报告和GitHub Release保留。TASK007D严格米制GT结论不变。
- 不再推进π³mos支线；没有修改DROID-W、Metric3D、BA或R2配置，没有启动新消融，没有关闭/重启实例。
- 下一项Baseline优化实验的具体范围待另行确定，本次存储维护不扩大算法授权。

历史封存：[TASK008](https://github.com/Pseven0108/GameCam-VO/tree/9341fce81a540a9ef1711b0f0b6cb49873ce990b) · [TASK007D](https://github.com/Pseven0108/GameCam-VO/tree/3bf7da7bb39192081cefe9898e948784ae6cd5aa)。

</details>

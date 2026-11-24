# GameCam-VO Task 002B 评审入口

先读 `TASK002B_FINAL_REVIEW.md`。想核对机制和公平性，再读 `INPUT_PREPROCESSING_PARITY_REPORT.md` 和 `TASK002B_SOURCE_EXCERPTS.txt`。`R2_ENVIRONMENT_MOTION_MAP.md` 集中呈现五环境的平移、旋转和 ATE/RPE 排序反例。精确结果在 CSV，校验与执行日志在 `analysis_only/`。

建议请评审者重点核查：

1. 同一 JPEG 和有效 K 的证据，是否合理地区分了历史回执、CPU 重建和未保存的 GPU 张量？
2. 一次区段尺度、独立区段边界和源序列等权配对，是否符合原评分协议？
3. `val_007` 症状的复发证据与因果推断是否分开？哪些机制仍缺同状态或分阶段证据？
4. 固定 K、虚拟相机、名义时钟以及 filler 补位的限制，是否正确保留在结论中？

供聊天版单独上传的 `GAMECAM_TASK002B_CHAT_REVIEW.txt` 包含主报告、方法、五环境表和案例复核，无需解压。ZIP 中包含 11 份指定交付物、分析脚本、日志、源代码摘录和身份清单；原始 JPEG、GT/轨迹数组、权重或完整仓库没有打入。若要再现原始数值计算，需要本地冻结 R2、GT 和 RGB 档案。`FILE_SHA256_MANIFEST.json` 列出 ZIP 中除清单本身以外的成员。

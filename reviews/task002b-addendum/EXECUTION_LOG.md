# 执行及校验记录

阶段：GameCam-VO Task 002B-Addendum，2026-11-22。只分析封存的 `VIPER_MATCHED_DUAL_BASELINE_R2_V1`，写入本任务目录。Python 运行使用已有 `gamecam-vo` 环境，`-B -X utf8`，`CUDA_VISIBLE_DEVICES` 为空；未导入或启动模型。未变更上游、原始配置或结果。

| 执行项 | 实际结果 | 原始日志 |
|---|---|---|
| `analysis_only/decompose.py` | Exit 0。运行原评价器自检，检查源 ZIP 2,391 个成员的 CRC；184 份轨迹，736 个分组 RPE 与父报告复核；四个案例行复现；986 个历史文件内容核验。 | `logs/decompose.stdout.log`、`.stderr.log`、`.exit.txt` |
| `analysis_only/aggregate.py` | Exit 0。原始序列内分组、配对统计、时间与 GT 运动分层及位移压缩筛查。 | `logs/aggregate.*` |
| `analysis_only/verify_sources_and_anchors.py` | Exit 0。15 个源码/运行器身份；3,092 个共同 K→K 对的导出来源敏感性；复查 736 项计数/SSE。 | `logs/verify_sources_and_anchors.*` |
| `analysis_only/render_figures.py` | 最终版 Exit 0。修正重复的子图标题后重绘三张 PNG，逐张检查最终图面。没有重跑轨迹评价。 | `logs/render_figures.*` |
| `analysis_only/verify_delivery_evidence.py` | Exit 0。核对报告的 6 行位姿、28 行 RPE、6 行筛查统计和 `val_007` 关键数字；复查 184 份导出、736 项 RPE、986 个历史文件、15 个源码/运行器。 | `logs/verify_delivery_evidence.*` |
| `analysis_only/package_review.py` | 两份 ZIP 各自生成成员清单，重开归档检验 CRC 及各成员 SHA-256，包外记录最终 ZIP SHA-256。 | `evidence/DELIVERY_VERIFICATION.json`（包外） |

本轮数据来源及前四项结果见 `evidence/NUMERICAL_VERIFICATION.json`、`evidence/AGGREGATE_SUMMARY.json`、`evidence/SOURCE_AND_ANCHOR_VERIFICATION.json`。CSV、图、日志和附录报告均为本轮独立衍生文件。报告收尾没有重复执行已通过的计算，也没有创建 Task 003 运行或 GPU Attempt。

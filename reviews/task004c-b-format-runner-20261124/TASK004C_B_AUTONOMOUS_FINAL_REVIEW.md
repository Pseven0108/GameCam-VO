# Task004C-B Format 闭合与运行器验收：最终评审

更新时间：2026-11-24T23:00:48.099368+08:00（北京时间）。最终状态：**PARTIAL — STOPPED_RGB019_OUTPUT_DIRECTORY_COLLISION**。

**本轮已完成 Format 修复、真实模型 CPU 新进程恢复、真实 GPU C0 采集，以及真实 C0 的新 GPU 进程状态恢复；RGB019 尚未处理，Short80 和正式 B1～B4 均未启动。**

| 证据层次 | 实际结果 | 证据入口 |
|---|---|---|
| Format 专项 | 22/22；保留 timm 0.9.10 原枚举单例身份 | raw_evidence/cpu_tests/FORMAT_UNIT_R1/ |
| ConfigDict 回归 | 14/14；原 Adapter 保持 | raw_evidence/cpu_tests/CONFIGDICT_REGRESSION_R1/ |
| 历史回归 | 152/152；最终候选重新运行 | raw_evidence/evidence/CPU_LEGACY152_STAGE_R1_RECEIPT.json |
| Stage / driver / guard | 20 + 3 + 6 项 CPU Mock 通过 | raw_evidence/cpu_tests/ |
| CPU 发布验收总数 | 217/217 | raw_evidence/evidence/CPU_FINAL_ACCEPTANCE.json |
| 真实带权模型 CPU 往返 | 最终源码版本通过；47 状态族、849 Storage、18,062 节点、71 callable；输出/梯度 SHA 精确一致 | raw_evidence/cpu_tests/REAL_MODEL_FINAL_SOURCE_ROUNDTRIP_R1/FRESH_PROCESS_RECEIPT.json |
| 真实 GPU C0 | RGB001～018；24 次初始化 BA；RGB019 未读取；退出码 0 | raw_evidence/attempts/capture/ |
| C0 文件核验 | 852 Storage 文件 + 2 元数据，共 854/854；2,517,456,938 bytes | evidence/C0_POST_CAPTURE_INTEGRITY_SUMMARY.json |
| 新 GPU 进程恢复 | 18,143 对象节点及 Tensor/alias/对象图重编码一致；下一输入身份匹配；RNG 最后恢复 | raw_evidence/attempts/restore_check/RESTORE_RECEIPT.json |
| RGB019 续跑 | **FAIL，退出码 1**；进入 Tracker 前发生目录冲突，0 个 frame event | raw_evidence/attempts/restore_check/process.stderr.txt |
| Short80 / 正式487 | NOT STARTED：0/4、0/4 | state/STAGE_LEDGER.json |

## 本轮两个可确认的工程进展

`timm.layers.format:Format` 通过精确类、版本、源码 SHA、枚举成员 name/value 白名单恢复为安装包原单例，未降格为字符串，未知枚举继续失败关闭。保留已接受的 ConfigDict 和 Metric3D identity Adapter。

真实 GPU 初始化边界首次封存为本轮的不可变 C0：state SHA `18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92`。这与 CPU fixture 是两种不同的证据；真实 C0 含 18,143 个对象节点、852 个唯一 Storage，未压缩 Storage 合计 10,027,350,972 bytes，完整归档 2,517,456,938 bytes（2.344564 GiB）。下一输入明确是 RGB019，counter=12。

## 为什么停止

`native_control/native_driver.py:115` 首先创建 `SummaryWriter(out/'native')`，实际 TensorBoard Writer 会建立该目录。C0 恢复和 `rebind_output()` 后，`native_driver.py:146` 又对同一 `tracker.output` 执行 `mkdir(parents=True, exist_ok=False)`，因此抛出 `FileExistsError`。

这次异常发生在 `tracker.run(stream)`、续跑 Rerun 子进程、Short80 和正式四组实验之前。`RESTORE_RECEIPT.json` 已写入，`native_trace.jsonl` 为 0 bytes；不能把状态恢复成功写成 RGB019 已运行。对真实 SummaryWriter 的独立 CPU 诊断复现了相同错误，未加载模型、未初始化 CUDA。

CPU Mock 将 Writer 换成不创建目录的空 Sink，而且 fake scene 使用 synthetic，未覆盖真实 scene=native 的输出目录生命周期。这解释了 217 项通过仍会遇到运行器故障；这些测试没有证明完整原生续跑。

遵守停止条件：没有修补运行中的源码、没有自动重试、没有运行后续阶段。失败 Arena、C0、日志和原始证据均保留。Format 专项 1/1；本轮 C0 1/2，独立 GPU 恢复检查 1 次；Short80 0/4，Formal487 0/4。不能将剩余 C0 额度解释为可自动重试当前失败阶段。

## 源码与科学含义

- 原始研究 Baseline：DROID-W `c3414af6047d06bafc1a6645d09f23247f3b2cdc`。
- 接受的起点：`aa0cca3ed0d6e5d381422d8219234b8c0c6ad065`。
- Format 专项 commit：`0184690a51877223de32c78ada65002afa91103d`。
- 最终实验候选：`5d357c1d3079de134dd8b41a20a00632da37f0b0`；tree `c018a65009aaf4f7457e2da5225a5f322a168b77`。
- 本轮 diff 分为 Format 与 stage runner 两份；Source commit 与 GitHub 发布 commit 分别记录。
- 原始 R2 YAML、模型权重、CUDA 扩展及发布源码保护共 3,759 项再次核验一致。未重编译 CUDA、未修改 BA 数学或 Metric3D 的生产前向计算。

没有新全序列轨迹、ATE/RPE、D 的直接效应或四组交叉实验结果；不能据此宣称算法改善。Formal487 的阶段接口与原生 Final BA/Filler 保存路径仅完成静态/CPU Mock，尚未通过真实 GPU 验收；统一离线指标也未执行。

## 资源与下一步

结束时数据盘 13.647614 GiB 可用，仍超过 10 GiB；3090 保持在线、GPU compute apps 为空。未关机、重启或释放 GPU，未删除历史文件或此次失败 Arena。C0 采集的原生 Rerun recording 已生成（3,495,924 bytes）；未验证浏览器实时画面。恢复阶段尚未启动 Viewer。

最小后续工作是修复新运行目录的创建顺序/所有权校验，并增加使用真实 SummaryWriter、scene=native 的 CPU 生命周期测试。只建议方案，本轮没有实施。当前 C0 固定了旧 candidate commit；任何新源码修复后，必须明确处理兼容性授权或另行采集 C0，不能伪造 commit 或绕过 source pin 后重放。详见 `NEXT_MINIMAL_RUNNER_FIX_PROPOSAL.md`。

公开包含真实日志、退出收据、源码 diff、CPU 测试与 C0 结构元数据，省略模型权重、RGB/GT、Tensor payload、Arena 和 Rerun 二进制。公开 SHA 对脱敏字节计算；原始→公开映射另附，不能把脱敏后的结构文件当作可直接加载的原始 C0。

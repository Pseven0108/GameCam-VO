# TASK006A-R0 最终评审

2026-11-26（Asia/Shanghai）。执行结论：**R0 源码与配置审计完成；PASS_WITH_RECORDED_LIMITATIONS，等待人工评审。** 本次没有实施整个 CADP，也没有自动进入 R1。

## 已有实际证据

|检查|结果|
|---|---|
|官方 DROID-W 提交|`c3414af6047d06bafc1a6645d09f23247f3b2cdc`|
|官方 Git blob 逐文件核验|208/208 PASS|
|R3 参考提交源码核验|`1b54d9074a5fbf051f3e74b9c315cc474515da5c`，与本地保留源码一致|
|R3 原生 CUDA 前缀|完整官方源码前缀一致|
|R3 原始 ZIP|300 个成员，CRC PASS，整包 SHA 与封存记录一致|
|R3 ZIP 内部 SHA|299/299 PASS|
|R3 展开文件 SHA|243/243 PASS|
|新增 R0 静态检查|38/38 PASS，不包含 R1 数学或 GPU 测试|
|GPU/CUDA/模型/真实前缀|0 次|
|权重或 Tensor 反序列化|0 次|

## 五个关键结论

**1. 配置冲突已闭合。** 官方基础 YAML 的 `gamma_depth=0.001` 是默认值；实际 R2、Task004B 封存配置和 R3 BA 调用均为 `0.01`。R2 原 YAML 与封存 YAML 逐字节相同，SHA 为 `a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc`。没有修改配置。

**2. CADP 两个代数端点与原生定义对应。** D0 是传零 prior 走 eta，D1 是有效 prior 区域用 alpha 替换 eta 并加入梯度。方案不能改成 `Cg+eta+rho*alpha`，也不能用 gamma=0 代替 D0。有限有效输入上的代数一致不等于 GPU Native U 多轮等价性通过。

**3. 协方差必须使用原生消元后阻尼。** 先得到 prior-off 的 `H0=A-EQ0Eᵀ`，再采用 `H0+diag(ep+lm*diag(H0))`；不能给 A 先加另一种阻尼，也不能复制 Pi3MOS 的常数 1.0。该协方差依赖原 W/U、eta、权重尺度和 gauge，是局部正则化近似。

**4. 当前 R3 日志不足以直接得到完整协方差。** R3 保存 A/H/Schur/Cg 等，但没有导出 Eii/Eij/E；Schur 矩阵不能唯一还原逐深度交叉块。原始输入快照仍在封存包中，未来可在获批阶段重建；本轮没有从日志伪造 E 或协方差。

**5. 工程可行性仍是后续关卡。** 当前 LLT 每次只服务一个 RHS；直接形成 54,000×54,000 的 FᵀF 会产生约21.73 GiB的单个 float64 数组。分块列二次型方案值得 R2 审查，但当前没有精度、在线耗时或显存通过记录。

另外记录了原生回代对索引0的排除和 Schur 边界判定差异。它们属于源码注意项，未被修改、未被认定为本项目最终根因。

## 决策与交付

源路径、参数传递、数学定义和配置证据已经完整列入四份专项报告，原始来源与 SHA 作为附件保存。`evidence/PRESERVATION_AFTER.json` 记录审计前后原文件保护及外层 Git 状态核验；完整交付 SHA 与 ZIP 验收见 `deliveries/`。

可以提交 **R0 人工评审**；下一步若获批，仅应进入 R1 CPU 数学原型。当前仍不能宣称“CADP 第一阶段完成”“协方差已经精确算出”或“轨迹已经改善”。

最终状态：**TASK006A_R0_COMPLETE_WAITING_FOR_HUMAN_REVIEW**。

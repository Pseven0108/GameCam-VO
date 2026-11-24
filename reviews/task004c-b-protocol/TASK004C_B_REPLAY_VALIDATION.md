# C0恢复与Schedule重放验收合同

本文件是未来验证设计。**本轮未做原生恢复、CUDA数值测试或四臂实验；设计自检不能替代它们。**

## 分级验收与运行预算

| 层 | 必须验证 | 通过标准 | 当前 |
|---|---|---|---|
| V0 证据身份 | 原始源码、执行补丁、YAML、权重、extension、487RGB/预处理 | 实际加载/输入hash匹配冻结锁；输入GT隔离 | 本轮只复用并检查本地证据，正式执行前再验 |
| V1 C0原子性 | 全状态闭包、alias、RNG、游标、第二阶段初始化、无pending写入 | COMPLETE marker及每tensor/storage/配置hash全部一致 | 未采集 |
| V2 恢复往返 | 相同C0独立恢复两次 | 任何研究计算前所有逻辑tensor逐位一致，stride/layout/storage别名相同，RNG逐位相同 | 未实现/未运行 |
| V3 原生同D短控制 | 同C0、同D、同Schedule的一段原生续接 | 离散事件完全一致，数值在预注册阈值内 | 需另批短运行；不自动增加第5次完整序列 |
| V4 记录闭包 | S1/S0的所有frame、mutation、BA、Final图和Filler批次 | 无缺失/重复ordinal，完整before/native-after/clamp-after、hash链与footer一致 | 没有实际Schedule |
| V5 跨D重放 | 同一Schedule的不同D臂 | 离散事件/引用/边序/age/window/BA调用数完全一致，数值可自然不同 | 尚未运行 |
| V6 输出与评分 | Local/Final/Filler来源、487全RGB、固定尺度和统一GT | 关键帧指标缺失写NA；不同来源分开；评价只离线 | 未产生新结果 |

C0采集与V2/V3是正式四臂之前的准入工作。4臂不包含两次额外完整重复，也不能跳过V3后声称CUDA确定性已经验证。可申请“一次共同初始化短前缀 + 两次短的同D同Schedule续接”作为独立工程验证预算；实际最短区间必须覆盖首次主循环候选及增删边/retained或drop分支。未覆盖的分支用静态审计保留风险，不伪称全部动态通过。本轮不发起此请求或运行。

## 完全一致与数值容差分开

以下没有容差：文件/张量逻辑hash、C0恢复字节、RNG、RGB身份、离散事件、slot map、active/inactive/bad有序边、age、索引、t0/t1、调用次数、iterations和 flags模板。相同C0在首次研究运算之前任何hash不同都停止；不能用allclose掩盖恢复损坏。

CUDA源码包含atomicAdd等规约；seed相同和cuDNN deterministic不等于所有自定义kernel完全确定。本轮没有重复测量，不能声明“已保证逐位可重复”。

为未来同D验证提出以下**待审核工程阈值**，仅用于同D同Schedule，不用于D1/D0处理差异：

- float32连续状态：逐元素 |a−b| <= 1e−6 + 1e−5×max(|a|,|b|)。
- float16网络特征/隐状态：|a−b| <= 1e−3 + 1e−3×max(|a|,|b|)。
- 恢复后第一次BA仍要求输入tensor hash逐位相同；BA之后的差异再按上述阈值和每tensor max/RMS/超阈值比例报告。
- Pose四元数采用归一化后的角距离核验，仅把q与−q视为同一旋转；原始恢复hash不允许符号变化。额外阶段旋转差候选上限1e−5 rad。
- 端点指标的同D重复差必须单列，不把它扣除或归零；若处理效应不高于同D噪声范围则标记无法分辨。不得用GT或预期消融结果调宽阈值。

这些阈值尚未实测校准，不是已达到的性能保证。任何超限都先停止并报告原因，若需更改阈值或额外重复，须在看到正式四臂结果前另行审查。CUDA kernel、精度flags和deterministic设置保持原样，不为追求通过偷偷改规约或关闭模型。

## 逐事件断言

- 读输入前核验RGB ID、index、timestamp和next cursor；C0后不可重放已处理前缀。
- Motion admission、Local keep/drop以及force flag分别登记，强制分支不得通过只改track返回值实现。
- 每个source/target映射到当时真实存在的实例。删除/slot重排后所有活跃与选入inactive引用有效；bad列表保留原始语义，不自动“纠正”原生行为。
- add_factors建立corr/net/inp/target行数必须与实际ordered active edges一致；inactive target/weight行数与pool一致；damping的source支持与原生native调用一致。
- 所有嵌套rm_factors、dedup和cap变化只消费一次，不能出现额外未登记图修改；图create/clear、age增量、inactive支持也受账本校验。
- 强制Schedule所需RGB必须可读，所需候选分支必须确实生成特征/prior；不能用另一臂的feature/target填补。
- D变化导致低可见支持或负disparity，只按原生处理和记录，不自动额外clamp/换图；出现NaN/Inf、native错误、OOM即失败。
- Final graph按完整Schedule约束；若只核验前端图，不允许判为全过程固定拓扑。
- Filler N+16<=500，临时slots不会覆盖真实关键帧；每批counter回退，所有487输出都存在，关键帧直接Pose在Filler前单独封存。

## 失败与回滚

任一层失败停止，不运行下一臂、不自动重试、不改算法或配置。保留C0、不完整Schedule、所有已写事件和退出码。若必须补采完整487帧或修改BA数学才能闭合，退回用户评审；本轮协议不授予这些操作。

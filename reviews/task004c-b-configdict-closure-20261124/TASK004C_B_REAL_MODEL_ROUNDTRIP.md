# 实际加权模型跨 Python 进程恢复

本轮完整恢复测试 FAIL。源模型建立和保存前固定输入比较通过，保存后的新 Python 子进程未能恢复整个模型对象图。

## 执行链与失败位置

测试 stdout 依次到达：`BUILD_REAL_WEIGHTED_MODELS`、`CHECK_HISTORICAL_FORWARD_SHA`、`BUILD_CPU_TRACKER_CLOSURE`、`SEAL_WITH_REUSED_HISTORICAL_TENSOR_FILES`、`RESTORE_IN_FRESH_PID`。

父进程最终 exit 1，总耗时 271.928 秒。恢复子进程在通用 object 分配路径中对 Format 调用 `object.__new__`，产生：

```text
TypeError: object.__new__(Format) is not safe, use str.__new__()
ControlError: Class needs an explicit construction-free adapter: timm.layers.format:Format
```

这里没有实际调用 `str.__new__` 修复，也没有将 Enum 降格为普通字符串。失败状态和部分输出保留。

## 独立类型的真实来源

实际安装 timm 0.9.10；精确类为 `timm.layers.format:Format`，MRO 为 Format → str → Enum → object。安装源码 SHA：`8b4d8d2d76d65cfbf8589092505e0c9d28d0a7af7df941abe59deb9cc664dfae`。

真实源模型值为 Format.NHWC。最短引用路径：

```text
root['models']['FiT3D']._modules['model']._modules['patch_embed'].output_fmt
```

图追踪显示 ConfigDict 祖先为 0；历史未修复 CPU 快照也存在相同 Format 类节点。因此这是独立的既存对象类型阻断，被更早的 ConfigDict 分配失败遮挡，不是 ConfigDict 新增的配置字段，也不是关闭 D/U/W 导致的运行变化。

## ConfigDict 定向复核

为了准确界定本轮专项修复结果，额外执行仅包含实际模型 ConfigDict 可达状态的精确诊断。它使用失败测试产生的真实源对象图，保留 6 个 ConfigDict 和 24 个可达图节点。映射、属性、类型、顺序、alias/cycle 的规范化图比较通过；源快照未被改写。

诊断耗时 4.069 秒，状态 PASS；完整模型恢复状态仍 FAIL。该小型诊断不包含独立的 FiT3D Format，因此不证明 FiT3D 恢复后的 forward 或梯度正确。

## 已完成与未到达

- 实际源模型固定输入输出与历史 SHA：已比较且断言通过。
- ConfigDict 完整 mapping/属性专项与真实子图：通过。
- 真正新进程启动：已经执行。
- 完整恢复图重编码、全部 Storage/alias、47 状态族恢复比较：未到达。
- 恢复模型 Metric3D/FiT3D/DroidNet forward 与 LoRALinear 梯度：未到达。
- GPU C0、RGB019 原生续步、RGB080 短程及487帧正式实验：未启动。

CPU 测试使用上游无 xformers Attention 分支及对应 CPU 常量适配；方法和限制见 `TASK004C_B_CPU_FIXTURE_METHODOLOGY.md`，不能推断 CPU/GPU kernel 等价。

## 下一步最小条件

要解除完整恢复阻断，需要独立审核安装版本固定的 Format/Enum 状态编码与恢复规则，保持枚举类型、值、类身份、共享引用和行为，并重新通过完整实际模型新进程验收。不能用剩余 ConfigDict 专项额度默许无关通用类型修复。当前定向预算为 1/2，未耗尽；本轮在 CPU 总门槛失败处停止。

后续 GPU 执行还需要通过既有 C0 状态和空间准入；只读阶段审计另发现正式 487 帧 runner 的阶段控制接入尚待完成。两项均不能由此 CPU 部分通过替代。

本任务未提供任何新的尺度恢复效果、D 负面作用或算法故障因果证据；研究结论仍应以此前授权实验的实际数据为准。

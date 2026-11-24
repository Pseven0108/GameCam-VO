# ConfigDict 专用状态适配设计与边界

本轮方案用于保存和恢复安装版本的 ConfigDict，不更改 DROID-W 的 BA 公式、Metric3D 网络前向、权重或原始 R2 配置。

## 变更身份

第一轮候选提交：`aa0cca3ed0d6e5d381422d8219234b8c0c6ad065`；对应源码树：`4dcec1e2c80f6bcc3e42046229d0dd54f9464ff8`。

| 文件 | SHA-256 |
|---|---|
| `native_control/configdict_adapter.py` | `7a4535739d385300a8eef522a6c3ccae98a26b85f0b126ba0d032505886f388f` |
| `native_control/snapshot.py` | `07775f9f2df18f67d21cd7548ead70b4126b0014e4178f2562fb0171386ce8c1` |
| 原有 Metric3D identity adapter（保持不变） | `b723b0eecb68449d9f9126c3453ec940c473d17a377d1ff4629dc32be036a3b4` |

安装 Metric3D 源码身份仍为 `24b832c6e831d25a101ebb8c02b1b3df4b5d5474530481078d6df56c7ff93951`。本任务没有借 ConfigDict 专项预算重新设计此前已验收的 identity callable adapter。

## 严格白名单

适配器只接纳精确的 `mmcv.utils.config:ConfigDict` 类；验证运行时类对象、完整 MRO、mmcv-full 1.7.2、Addict 2.4.0，以及两份安装源码的 SHA。快照 pin 也必须与受支持 pin 完全相同。未知 dict 子类不会自动进入通用对象恢复路径。

这是一份针对实际安装版本的兼容合同；切换类、版本或源码后应失败关闭，不能将该测试扩大解释为所有 MMCV/Addict 版本均可恢复。

## 编码

每个 ConfigDict node 分别保存：

1. 按原始插入顺序保存的 mapping key/value 引用。
2. 实际 `__dict__` 的对象图引用。
3. 精确类与安装源码 pin。

映射键、值与属性字典共用现有 memo。业务配置不是通过转成普通 dict 后再丢失类型的方式保存。属性字典也作为图节点保存，因此可表达属性字典自身与其他对象的 alias。

## 两阶段恢复

第一阶段通过已核验的 `dict.__new__(ConfigDict)` 创建空壳，将壳对象登记到解码 memo。此时暂不恢复 mapping 边。

完成根对象图解码后，再处理已登记的 ConfigDict：以 `dict.__setitem__` 写入 mapping 条目，随后使用 `object.__setattr__(..., '__dict__', captured_attrs)` 安装捕获的实际属性字典。

这避免 Addict 的 parent 关联和冻结检查在恢复中产生额外写入。恢复 mapping 的过程没有永久删除冻结标记，也没有把对象永久解冻。实际冻结行为、缺失属性、parent/key 关联、循环和 alias 均由测试核验。

## 失败关闭

- 对未知 dict 子类抛出异常。
- class/version/source pin 不一致时抛出异常。
- ConfigDict node 字段不完整时抛出异常。
- 旧格式将 ConfigDict 记作普通 object 且缺少 mapping 时，明确拒绝；不伪造遗漏内容。
- 不受支持的对象值保留现有拒绝行为。

此处处理 ConfigDict 引用循环，并不授权通用序列化器忽略其他不支持的对象图或循环结构。遇到新的不支持状态仍应保留异常证据。

## 已执行 CPU 结果

专项测试 14/14 通过，退出码 0；测试覆盖 alias、循环、空对象、顺序、键类型、嵌套、parent/key、已删除的 parent/key、冻结/解冻、缺少键/属性、错误 pin、未知子类与不受支持的值。

完整历史回归 152/152 通过，失败 0、错误 0，退出码 0；其中保留历史 118 项及既有新增 34 项。报告记录该回归未初始化 CUDA、未构造预训练模型、未读取真实 RGB，未创建原生 C0。

真实权重新进程恢复测试退出码为 1，独立阻断是 FiT3D PatchEmbed.output_fmt 中的 timm Format。实际模型 ConfigDict 子图的补充诊断通过，但不能替代完整模型恢复。以上测试不代表 GPU C0、真实 Tracker 恢复或四组交叉实验通过。

## 剩余准入

仍须取得真实模型对象图重编码、全部 Tensor Storage、共享 alias、视图 shape/stride/offset、固定输入输出及梯度、RNG、Tracker 相关状态的严格恢复证据。CPU 全部门槛通过后，才适用原授权中的 GPU C0、RGB019 新进程续步与交叉实验。


## 本轮最终边界

ConfigDict 专项修复消耗 1/2；剩余额度未用于独立 timm Enum 类型。完整 CPU 门槛失败，因此 GPU C0 0/2、短程交叉 0/4、完整 B1～B4 0/4。正式 487 帧 runner 的阶段控制接入仍未完成。该任务没有产生关于 D 关闭、轨迹压缩原因或算法改进收益的新实验证据。详细失败链见 `TASK004C_B_REAL_MODEL_ROUNDTRIP.md`。

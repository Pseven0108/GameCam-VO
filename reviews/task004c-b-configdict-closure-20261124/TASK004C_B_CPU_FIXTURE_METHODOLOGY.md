# 真实权重 CPU 新进程恢复验证方法

状态：完整真实权重新进程恢复 FAIL（退出码 1，271.928 秒），失败在 timm.layers.format:Format 对象分配。源模型固定输入通过历史 SHA 比较；恢复后前向与梯度未到达。ConfigDict 的独立实际模型子图诊断 PASS。GPU 阶段未启动。

## 验证对象

测试在 CUDA 不可见的 CPU 进程中，以原 seed43 加载冻结的实际 Metric3D、FiT3D 与 DroidNet 权重。目标是核验保存/恢复是否保持对象状态和固定输入行为，不能用 CPU fixture 证明 GPU kernel 数值等价或 SLAM 轨迹改善。

测试源代码为 `tools/model_roundtrip.py`；固定输入评价器沿用已保存的 CPU real-model fixture。新进程必须具有不同 PID，不得在原对象上原地恢复后冒称跨进程恢复。

## 参考数值与比较标准

先比较当前 CPU 源模型输出与上一轮已归档的固定输入输出 SHA。对应项包含 Metric3D 深度、置信度、法线，FiT3D 中间特征，DroidNet fnet/cnet，以及实际加权 LoRALinear 输出和输入梯度。

之后在真正新 Python 进程中恢复对象，再按相同输入和严格 SHA 比较这些结果。不能因失败而调整容差、替换预期值或删除比较项。已有 71 个 identity callable 的精确识别与共享引用验证保持原适配器定义。

## ConfigDict 与对象图

测试重新从真实加权模型采集配置 mapping 和属性元数据。恢复后重新编码对象图，并比较根引用、节点与类源码 pin；单独核验 ConfigDict mapping、顺序及属性字典图。

另行检查模型对象与 Tracker、MotionFilter、Frontend Graph、Filler 间共享引用，Video/计数器/日志服务重绑，以及专门构造的 Tensor alias 视图的 shape、stride、storage offset。

## Tensor Payload 复用

历史 CPU 快照遗漏了 ConfigDict mapping，故不能将其当作完整可恢复配置。新测试重新构造实际模型对象元数据，但不复制一遍相同权重文件：仅对 byte size、raw SHA、device 与 shared 标记相同的历史 Tensor Storage 文件建立硬链接。

历史文件在复用前须通过原 manifest 的文件 SHA 核验，新的 manifest 也须通过自己的内容清单核验。新的小型 fixture 状态另存独立文件。复用是测试阶段的存储优化，不给原生 GPU snapshot reader 或 saver 增加绕过完整性核验的通路。

历史 manifest 和原始 payload 不可修改；完成后再核验历史内容。最终报告必须以实际 reuse 收据填写复用文件数、新增文件数和逻辑/物理字节，不能把“计划复用 798 份”直接写成已完成结果。

## Tracker 47 状态族的范围

测试构造真实 CPU Tracker/Video/Filler 接口对象；尚未由真实 RGB 推进的循环状态、相关性缓存、关键帧缓存使用明确标记的合成 fixture。47 个协议状态族的值、shape、dtype、stride 与 offset 应逐项比较。

它核验状态保存格式及引用闭包，不证明真实原生初始化边界 C0 已生成，也不证明恢复后已经处理 RGB019。原生 C0 必须在实际 GPU 初始化后、RGB018 frame-end、RGB019 尚未读取的边界另行捕获，并核验既有 47 状态族与 24 次初始化 BA 调用。

## 必须披露的 CPU 分支

- 可选 xformers GPU 后端不能用于本次 CPU fixture；该 fixture 选择模型上游已有的无 xformers Attention 路径。
- Metric3D 上游 `get_bins()` 包含 CUDA 常量分配；CPU fixture 注册对应的非持久 CPU 常量：`exp(linspace(log(min_val), log(max_val), 256))`，命名为 `depth_expectation_anchor`。
- 上述 CPU fixture 选择不能带入 GPU 正式运行，也不能被描述为未作任何 CPU 适配的原生 GPU 执行。

## 准入判断所需收据

| 证据 | 当前状态 |
|---|---|
| ConfigDict 14 项专项测试 | PASS，14/14，exit 0 |
| 152 项历史完整回归 | PASS，152/152，exit 0 |
| 源模型固定输入与历史 SHA | PASS；在保存前比较断言已通过 |
| 完整新进程对象图与 Storage/alias 一致 | BLOCKED；Format 分配失败，未到达完整比较 |
| 新进程固定输出与梯度 SHA | NOT_REACHED |
| 完整新进程 RNG/47 状态族一致 | NOT_REACHED；源侧曾建立 fixture 清点，不代表恢复侧验收 |
| 原历史快照保全 | 失败后再次复核通过：798 份 payload SHA 与两份元数据检查均通过，历史快照 800 个文件保持完整 |
| 实际模型 ConfigDict 子图 | PASS；6 个 ConfigDict、24 个可达图节点，规范化后精确一致 |
| 真实 GPU C0 | 未执行，0/2；CPU 总门槛未通过 |

最终报告应保留全部失败现场、stdout、stderr、退出码和哈希。若测试失败，要区分测试装配错误、对象图适配缺陷及模型数值差异；不能把测试进程退出成功单独当作全部验收项通过。


## 本轮最终边界

ConfigDict 专项修复消耗 1/2；剩余额度未用于独立 timm Enum 类型。完整 CPU 门槛失败，因此 GPU C0 0/2、短程交叉 0/4、完整 B1～B4 0/4。正式 487 帧 runner 的阶段控制接入仍未完成。该任务没有产生关于 D 关闭、轨迹压缩原因或算法改进收益的新实验证据。详细失败链见 `TASK004C_B_REAL_MODEL_ROUNDTRIP.md`。

# 下一步最小建议（未实施、未授权运行）

建议限定为显式、只对已核验LoRALayer identity callable生效的序列化适配，保留其他未知函数拒绝策略。不要改BA、dropout率、模型前向、权重或原R2，也不要为保存而删除lora_dropout字段。

候选适配应核验owner类、模型源文件SHA、确切属性名，以及运行时函数是否确为无闭包的单参数identity；使用有版本的符号标记持久化，并在恢复时重建等价无状态callable。先做CPU等价、Tensor对象身份/alias、dtype/shape/stride、NaN/Inf、梯度和RNG不变测试，同时证明其他lambda继续失败关闭。

还需审查真实模型结构中是否有其他不支持字段，不能只解决第一个异常就宣布完整闭包通过。只有完整状态清单及CPU验证通过，并获得下一次GPU生命周期授权后，再采集C0。

本轮没有应用上述设计，没有重跑GPU或进入restore/四臂。此报告不自动授予下一阶段授权。

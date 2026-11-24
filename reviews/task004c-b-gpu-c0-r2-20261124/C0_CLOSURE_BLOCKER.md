# C0首个真实状态闭包阻断

直接证据：GPU traceback显示Metric3D路径`Tracker.motion_filter.metric_depth_estimator...LoRALinear.lora_dropout: Unregistered closure/function`。保存器按原安全策略停止，未丢弃该字段来凑齐C0。

安装版本的Metric3D源码SHA：`24b832c6e831d25a101ebb8c02b1b3df4b5d5474530481078d6df56c7ff93951`。对应`RAFTDepthNormalDPTDecoder5.py`：LoRALayer第19～22行，dropout>0时用nn.Dropout，否则赋值`lambda x: x`；LoRALinear在第41行调用该基类构造器。

这为lora_dropout函数对象的来源提供静态解释。GPU进程已退出，未恢复该真实函数对象，不能声称已核查其运行时closure/freevars。

首次源码提取只扫描LoRALinear类体，因此lambda列表为空；后续沿LoRALayer基类定位到identity lambda。两份取证记录均保留，最终判断依据`evidence/CLOSURE_BASE_CLASS_EVIDENCE.json`。

当前序列化器只接受可按模块符号重新解析的函数，拒绝lambda/局部函数是既有设计。本轮仅获准修复输入适配层，所以没有修改该保护、模型类或Metric3D源文件。

这只是遇到的第一个真实闭包阻断，尚不能证明其后没有其他不支持字段。完整C0、Tensor别名、RNG和网络buffer的持久化核验仍未完成。

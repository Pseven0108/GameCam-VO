# Checkpoint闭包修复结果

最终状态：BLOCKED_CPU_RESTORE_CONFIGDICT。两轮修正已用尽，没有第三轮修改。

起点02f8c8308274489ff7eff83fa9b87b98db74122e；候选提交a324b57760fdaf4929385f2271991d773533799d；树19b22b429226383c3ef996e40c4a5483a5339acf。
只有native_control/metric3d_identity.py和native_control/snapshot.py改变。BA公式、CUDA扩展、安装Metric3D前向源码、权重和原R2没有改变。

## 已完成

真实安装Metric3D权重加载到CPU；71个lora_dropout均来自源码SHA24b832c6e831d25a101ebb8c02b1b3df4b5d5474530481078d6df56c7ff93951，函数字节码7c005300，唯一位置参数、无defaults/kwdefaults/closure/freevars。
8个LoRALinear、1个ConvTranspose2dLoRA、62个Conv2dLoRA均检查严格同对象返回、输入无修改、CPU RNG不变、输入梯度为预期值。

专用标记metric3d_lora_identity_callable_v1，绑定三个实际类中的具体owner、属性、源码SHA、函数签名和字节码SHA。恢复对象由顶层受控callable构建，并经过memo。未知lambda、有闭包函数和不支持对象的拒绝测试3/3通过。

第二轮还采用gzip level1流式无损封装完整torch存储档案，格式V3。没有降低dtype、忽略未使用尾部、删去字段或修改优化计算。历史152项CPU用例在最终代码上全部通过；这是通用夹具证据。

## 尚未解决

真实加权模型的遍历产生17,447个节点，71个专用callable节点、1,752,008,320唯一存储bytes。**遍历接受不等于完整状态闭包成功。**

新进程恢复失败于mmcv.utils.config:ConfigDict。其MRO经过addict.Dict到dict；object.__new__不安全。更严重的是，现编码器只对精确dict类型保存items，对ConfigDict保存vars，实测vars只有__parent/__key/__frozen，不能表示alpha/nested等字典条目。
实际模型夹具的ConfigDict节点仅保存了这三个私有属性。因此只改构造器也不够，必须分别证明映射内容、类型、插入顺序、缺省/冻结语义、别名、循环引用和新进程还原。

本轮未实现上述新适配器。不能宣布真实模型恢复、网络Buffer/RNG/alias一致，也不能启动GPU来替代未通过的CPU门槛。

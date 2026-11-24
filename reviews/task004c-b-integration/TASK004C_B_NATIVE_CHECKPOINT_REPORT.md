# 原生Checkpoint接入

结论：**CPU接口通过；真实C0未采集，原生恢复未验证。**

`native_control/snapshot.py` 使用显式JSON对象图和Tensor-only存储文件。保留Tensor别名、storage offset、stride、dtype、device、Parameter身份、CPU共享标志以及重复Python对象引用。逐文件、逐存储和逐Tensor核验SHA。恢复绕过对象构造器，不重跑模型构造或整个Tracker的pickle。保存原子安装，失败保留staging现场。

真实入口为 `native_control/binding.py::capture_c0`。要求三组各8次初始化graph.update已成功返回、第二阶段完成、Tracker帧尾、下一帧未读取，实际边界必须符合RGB018候选；不符合就停止提交协议复核。源码静态分析不能证明此次实际边界已达到。

保存前暂停Rerun写入并等待其CUDA同步应答，再持有video锁和同步Tracker CUDA。全容量Video、Tracker/MotionFilter/Frontend/Graph/Corr、先验模块、模型缓存和状态、observer、循环游标、RNG均进入对象闭合扫描。未知类型或无法保留的别名直接拒绝。eta与有效UBA权重在此边界没有活动的BA局部变量，保留其完整输入并沿原生路径重算。

Tracker帧尾存储5项活跃循环状态。`image/timestamp/starting_count/i` 的前一帧局部值在下次使用前由下一次取帧覆写；必要的持久特征由MotionFilter和Graph保存。新循环从保存的游标恢复，不把迭代器重新从0读起。

CPU测试实际验证了独立Python进程退出后恢复模拟、模型buffer/mode、绑定方法、共享storage、RNG、未知字段拒绝和构造器不执行。可检查的小型样本在 `evidence/CPU_DEMONSTRATION_handoff/`，其13个Tensor明确为CPU合成样本，**不是C0，也不是预训练模型**。

尚缺：真实模型对象闭合清点、CUDA/IPC恢复逐Tensor证据、真实Rerun跨进程屏障、原生下一帧与下一次BA收据。当前C0实际字节数和state SHA均为null。

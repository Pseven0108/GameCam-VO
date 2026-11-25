# TASK005B-R2：原生数值重复性与端点等价性

唯一输入为 R1 封存的 D0_S1_RGB233；不重新生成快照，不跑模型、RGB前缀、S0或新机制组合。

## 预注册调用预算

1. 原安装 droid_backends.ba：2次，同状态独立克隆，每次内部2轮。
2. R1候选 ba_reference：2次；R1候选 ba_paths(0,0)：2次。
3. 新独立观测模块 trace_reference：2次；trace_paths(0,0)：2次。

总计最多10次双迭代BA调用。串行，无自动重试；每次恢复同一随机状态、storage alias、值、shape、stride、offset和 no_grad。

原扩展和reference的D0使用全零disps_sens；paths使用真实mono再关闭C/G。两者有效D0语义相同，但prior实参字节不同，分别记录SHA。

保持 atol=1e-6、rtol=1e-5。超差本身是本轮诊断对象，不因此提前终止对照；非有限值、OOM、输入身份错误、磁盘不足必须停止。

未埋点重复性与观测版分别评价。观测追加同步/复制可能改变atomic调度；不能将观测版等同于原安装二进制。

## 输出与保护

独立新目录与独立新扩展，不替换原.so、R1候选、源码、配置或权重。远端预留10GiB，R2新增工作与归档总量预留1.5GiB。输入快照引用并复核原归档，不重复写入远端。完整评审ZIP及原始数组发布到新GitHub分支与Release。完成停止，不进入后续机制实验，不关机。

# TASK011D — A7 Adapter 修复与双层验证准备评审

2026-11-28，Asia/Shanghai。父提交 `408de2c4a8f3a6f8baed9b2f91d409d57649df21`。唯一数据集：VIPER。

**本轮准备阶段通过：ENGINEERING_READY + DATA_ADMISSION_READY + EXPERIMENT_PROTOCOL_FROZEN + GPU_NOT_STARTED。**

这里 GPU_NOT_STARTED 仅指正式 SLAM / Pilot：两者均 0 次。已在本地 RTX 5060 做合成 CUDA
测试；没有加载 Metric3D、DINO、DROID-W，也没有调用真实 Native BA、编译或替换扩展。
本轮没有产生 A5/A7 的机制或完整轨迹性能结论。

## 1. A7 全 Buffer 回传已消除

每次调用仅处理 `unique(arange(t0,t1)∪ii)`，按这些源槽位提取时间戳并在 GPU 缓存中索引。
不再读取全部 live timestamps，不再构造全 Buffer 的 A5/validity，也不逐源帧 `.item()`。
FP32 均值、掩码、支持集和检查都在设备上完成；只将 `[source_count+1,14]` 的索引/统计包传回。
Native 接口仍收到完整 strength，GPU 上 zeros_like 后 index_copy_，非源帧保持零。

| 合成条件 | 显式 D2H 摘要 | Adapter p50 / p95 | 进程峰值 allocated |
|---|---:|---:|---:|
| Buffer 500，7源帧 |896 bytes|2.842 / 3.280 ms|30285824 bytes|
| Buffer 500，32源帧 |3696 bytes|2.851 / 3.271 ms|31458304 bytes|

独立 PyTorch Profiler 在32源帧调用记录总 D2H **3704 bytes**：3696 字节摘要加8字节内部小传输。
不能将显式算子审计的3696字节写成所有驱动层流量。两套审计均未出现完整像素 Buffer 回传。
旧 C 路径负对照实际捕获4次全 Buffer 拷贝：A5、validity、mono，另加结果审计；共23,400,000字节。
未虚构速度提升百分比，也未将这个小型测试的显存解释为模型显存。

本地 CUDA 合成探针最大均值误差 `4.49635374489e-08`，小于固定1e-6，无容差放宽、补偿或掩码变更。
α=0.01，U/UBA、30个原生实参、原生求解器和迭代不改；A0/A1/A4/A5 继续调用冻结 B 实现。

## 2. 原生环境兼容性问题已在模型运行前修复

本地 PyTorch 2.15 支持多维 `all((1,2))`，服务器冻结 PyTorch 2.1 不支持。
远端 CPU 复核直接发现并保留该错误。已改成空间展平后 `all(1)`，保持相同布尔条件。
最终代码在远端 `2.1.0+cu118` 的纯 CPU 合成检查通过，包括源槽位、乱序时间戳、均值和别名复制；
CUDA 未初始化。其最大均值误差2.980232238769531e-7也低于1e-6。

这不是远端3090 Native BA或完整模型证书；Linux原生模型和多进程实际执行仍需后续批准。

## 3. Route A 数据已实际准入

按批准规则：47总序列−20个TASK011B源序列=27；val_014中点GT path约1.0419e-5，
不满足0.0001，因此26条通过既有元数据筛选。按序号升序冻结19条，天气4/4/3/4/4。
这19条均有历史全序列 Baseline 暴露，TASK011B暴露为false，blind_validation=false。
不得称为新数据集、未见数据或盲测。

选定1216张 JPEG 全部完成成员CRC、Pillow完整解码、1920×1080 RGB检查和SHA。
RGB ID−1、完整GT、K偏差、GT path均通过。逐张与原始 BaseDataset 的未修改CPU方法比较，
1216/1216预处理结果逐位一致，内参满足原R2映射；冻结R2 YAML字节哈希未变。
不声称其他未选7条也完成了本轮解码；未下载新数据，未解压全数据集。

## 4. 两套框架已独立建立，但未运行真实实验

**Fixed-State Replay：**未来A0运行的所有合格主循环局部BA调用作为参考，无结果筛选。
保存30个原始参数、源帧映射、A5/A7场、Native-valid、RNG与别名/stride/offset。
A5、A7、A5重复分别从独立状态开始，恢复相同RNG；原生U更新允许在各自分支内发生，
不把“相同初始U”错误实现成冻结整个U更新。输出更新差异和同二进制A5-A5波动，不生成轨迹，
不算FSR的ATE/RPE。没有既有残差时，不添加Native诊断，不把较小更新直接叫作更准确。

**End-to-End：**19源序列×5组×3 seeds=285个独立任务，串行顺序已冻结；各自初始化、
关键帧、BA历史和轨迹独立。A7只匹配自己当前状态的反事实A5，禁止强制跨轨迹对齐状态。
默认CLI仅验证计划，显式授权、参数绑定、源码哈希和一次性输出目录共同保护真正入口。
未授权即在导入模型/Native代码前停止，未生成任何已批准运行文件。

## 5. 测试与统计边界

最终 **169/169 项通过，无跳过**：原122项回归、新增10项CPU、5项合成CUDA/传输、
32项框架测试。旧56项Adapter测试通过隔离导入实际针对新D实现运行，没有改原测试文件。
状态复制验证了别名、shape、stride、offset、RNG和原始输入保护；合成Stub不是Native求解结果。

主指标沿用100×Sim3 ATE RMSE / 同窗口GT path；不使用各自估计path作分母。
先在源序列内配对共同可评分seed，再按源序列做10,000次bootstrap，种子20261128、95%CI；
三seed全可评分子集作敏感性分析。失败和对齐退化不填零，独立报告计划/完成/初始化/可评分数。
常量估计轨迹仍保留raw path ratio误差，不伪造Sim3 ATE。

次指标阈值只基于B历史数据形成候选，**没有批准或用于判定**。
A0含快照采集和缓存核验开销，不能拿其总时间当干净算法运行时间；采集耗时单列，
A5/A7无快照采集，但其不同Adapter开销仍须如实记录。

## 6. 保护与待审批事项

父版本 B/C `146` 份文件及原生产源码 `110` 份前后SHA一致。
历史B/C代码、报告、Release未覆盖。未加载权重，不声明本轮重新核验了远端全部权重身份。
每次真正保存快照前检查唯一Storage大小并保留至少10GiB；真实快照大小、合格调用数及总存储量
尚未知，不能用合成小样本保证完整FSR容量。不得自动删除历史结果。

请评审批次指标退化边界和下一阶段正式GPU范围；Route A本身已按本次授权落实。
在此之前，不启动Pilot、Native重放或285次运行。

[实施审查](IMPLEMENTATION_REVIEW.md) · [传输审计](CUDA_TRANSFER_AUDIT.md) ·
[数据准入](DATA_ADMISSION_REPORT.md) · [FSR协议](FIXED_STATE_REPLAY_PROTOCOL.md) ·
[E2E协议](END_TO_END_PROTOCOL.md) · [统计方案](STATISTICAL_ANALYSIS_PLAN.md) ·
[待决事项](DECISION_REQUIRED.md)

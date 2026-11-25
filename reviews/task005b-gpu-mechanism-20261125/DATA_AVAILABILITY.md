# 原始证据的分层与位置

- **展开报告及轻量评审ZIP**：所有报告、候选源码、运行/分析脚本、CPU测试、4个完整状态的64行逐轮指标、小型原生线性系统、逐Pose更新、全部输入哈希/调用收据、超差逐元素CSV及图。
- **同一Release的4个result_*.tar**：4个完整状态的8格×两轮原生trace、4份原安装扩展参照、COMMON_INPUTS、逐次收据与SUCCESS。
- **同一Release的partial_D0_S1_RGB233.tar**：失败状态的4份原扩展对照、5个成功返回的候选格、1份失败端点完整数组及ENDPOINT_FAILURE。失败前未生成COMMON_INPUTS或SUCCESS，不能伪造补写。完整输入snapshot另存本地。
- **同一Release的task005b_run_evidence.tar.gz**：2条真实前缀、5个启动的context02重放及首次context guard故障的完整运行日志、调度链、配置、恢复/终态收据、构建记录和远端副本回收记录。逐成员SHA核验通过，发布前解压扫描凭据。
- **仅本地保留的6个snapshot_*.tar**：包含真实BA全部输入与DINO派生特征的完整存储快照；逐成员SHA均核验。封存C0继续保留。其来源/大小/SHA列于00_intake/LOCAL_IMMUTABLE_ARCHIVE_INDEX.json；不自动公开大型输入快照、RGB、GT或模型权重。

全部发布资产的大小和SHA见07_release/RAW_ASSET_INDEX.json。轻量ZIP不是全部大型数值数组的容器；完整数组均以同一Release的独立资产提供。本次失败状态远端源文件保留，未做故障后清理。

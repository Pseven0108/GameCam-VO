# 评审包范围与复算依赖

本包提供Task005A全部主要分析脚本、派生CSV/JSON、CPU测试、源码证据、图表、封存记录和执行日志。大型原始输入沿用已封存Task004C-B及本机保存资产，不复制模型权重、C0、VIPER原始RGB或完整GT到公开GitHub。

[原完整Task004C-B评审包](https://github.com/Pseven0108/GameCam-VO/releases/download/task004c-b-crossover-full-20261125/TASK004C_B_CROSSOVER_FULL_REVIEW_20261125.zip)及[固定Commit展开证据](https://github.com/Pseven0108/GameCam-VO/tree/a24ba97a515ec4fb6e4fd195922b4ac25e532d74/reviews/task004c-b-crossover-full-20261125)继续有效。INPUT_PROVENANCE.json列出本轮实际读取文件的路径、字节数与SHA；这些本地路径不是下载URL。

重新计算ATE需要用户合法持有的VIPER Camera GT（本地val_007.npz SHA在清单中）及四组保存轨迹/快照。没有这些数据时，本包仍可审查派生证据和公式，但不是无外部数据依赖的一键完整复现包。

读取npz使用allow_pickle=False，不加载images数组。数学反例和单元测试是CPU合成检查，不能替代真实原生solver取证。完整早期失败、资源门槛偏离、可视化限制保留在原包，不被本轮改写。

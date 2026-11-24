# 执行记录

所有运行在独立Task004C recovery目录；保留失败的准备日志。
- Capture E0: phase=complete; exit=0; elapsed=148.575909s; peak GPU=16733MiB; peak shm=2247864320B.
- Capture E1: phase=complete; exit=0; elapsed=148.324115s; peak GPU=16747MiB; peak shm=2247946240B.
- Replay E0_D1: phase=complete; exit=0; elapsed=24.965156s; peak GPU=3013MiB; peak shm=1474560B.
- Replay E0_D0: phase=complete; exit=0; elapsed=25.128376s; peak GPU=3013MiB; peak shm=1474560B.
- Replay E1_D1: phase=complete; exit=0; elapsed=25.037375s; peak GPU=3029MiB; peak shm=1474560B.
- Replay E1_D0: phase=complete; exit=0; elapsed=25.128277s; peak GPU=3029MiB; peak shm=1474560B.
- 初始默认Python缺少NumPy，改用现有CPU依赖；无安装。
- 准备阶段UTF-8授权读取问题在模型启动前修正；原错误日志保留。这不是GPU重试。
- 合同测试10/10，独立分析测试14/14；输出和退出码见test_logs。
- 两次远端CPU分析退出码均0；本地端点评价退出码0。
- 无CUDA/native运行失败，无自动GPU重试。
- 原始源码208项与其他保护文件复核通过；GPU查询0MiB计算占用，实例保持在线。
- 原始快照归档与下载由独立收据记录，此处不伪造完成。
- 本地汇编程序第一次有字符串换行语法错误，修复后发现本机缺Matplotlib；改用远端已有CPU绘图库，无安装、无GPU计算。后续汇编及绘图退出码0，原失败日志保留。
- 原始证据ZIP本机校验：170个成员CRC、169项内部SHA通过；外层SHA与远端一致，原件未删除。

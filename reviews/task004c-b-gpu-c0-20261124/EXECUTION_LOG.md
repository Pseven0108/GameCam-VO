# 执行日志（Asia/Shanghai，2026-11-24）

1. 已知Host Key核验sc01:30448，读取GPU、磁盘、shm与保护pin。
2. 从完整已评审668a88c7建立独立克隆；复制原CPU proof/report，发布仅capture的鉴权元数据。
3. 系统Python缺少Torch分发metadata，模型启动前中断。保留exit1收据，native预算消耗0。
4. 采用已有wild环境，最终admission通过，启动PID773；native生命周期1。
5. 运行58.316秒，首帧RGB-only合同失败，原生进程exit1，未自动重试。
6. 原loader CPU实读复现，唯一失败谓词depth_is_None；没有初始化CUDA或加载权重。
7. 采集全部日志、trace、resource与Rerun文件身份。C0未生成，不加载任何快照。
8. 确认无进程/映射后回收本轮两个全零临时Arena；保护pin和源码再次核验，历史删除0。
9. 本地打包，保留失败过程，并向已有私有GitHub评审分支发布。

传输收据在evidence/*_TRANSPORT.json；实际native OS退出码见remote_evidence/attempts/capture/PROCESS_RECEIPT.json。
SSH包装exit0不代表原生GPU成功。本次原生exit1、CPU诊断exit0必须分别解读。完整raw transport日志保留在本地logs/，评审包以结构化收据和原生stdout/stderr为主。

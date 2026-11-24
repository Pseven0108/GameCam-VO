# 本次临时Arena生命周期

原生SLAM创建了两块500-slot file-backed CPU存储，共2,246,400,000 bytes；GPU启动失败后两块均为全零。它们没有有效跟踪帧，属于可重建的本次临时存储。

回收前后核验：

1. 唯一进程组773已退出；nvidia-smi无compute进程。
2. 扫描/proc所有可见maps，无这两块文件映射，权限失败0。
3. 路径严格限定本次`attempts/capture/shared_cpu`，目录内只有这两块文件。
4. 文件owner、mode0600、device、inode、size匹配；文件名与inode一致；不是symlink。
5. SHA与失败后封存记录一致，并与同长度全零流的SHA一致。
6. 仅逐文件unlink这两块临时存储；完整日志、收据、Rerun与诊断保留，历史删除0。

回收逻辑bytes=2,246,400,000；磁盘实际可用增加2,246,410,240bytes。14个保护pin再次核验一致，独立source和原release source均保持clean。

Resource tracker曾报告一个leaked semaphore警告；完整stderr已保留。结束时shm使用81920bytes，没有擅自清理/dev/shm命名空间。不能将本轮空Arena回收等同于真实C0恢复后的完整共享生命周期验证。

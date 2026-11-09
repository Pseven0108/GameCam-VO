# Session 写入边界

43项实际子进程操作全部通过。明细在SESSION_WRITE_BOUNDARY_REPORT.json。

允许：model/正式输出；cuda_samples.jsonl、frame_samples.jsonl、ipc_worker_events.jsonl仅追加；cuda.latest.json、worker_terminal.json仅由当前PID专属临时文件原子替换。只读：work.permit.json、nvml.latest.json、supervisor_heartbeat.jsonl。

授权账本、Supervisor/NVML控制文件不在Worker写权限中。IPC交给绑定Session、目录inode/UID/权限与当前PID规则的IPCPolicy；fallback中的arbitrary.txt和嵌套文件拒绝。符号/硬链接创建、已存在控制链接、非法rename/unlink、继承目录fd操作均已实际探测。

同UID应用层边界：Python audit不是OS/native-code沙箱；不能防恶意native代码或已有可写fd。真实DepthVideo在CPU模式还使用torch原生共享tensor；测得其torch_*为已unlink但仍持有fd的共享内存，在退出后无新增残留，不能宣称这些资源属于专属Arena路径。

对固定、已核验源码的非对抗性实验，以上作为明确限定的应用层防误写保护；如研究要求抵抗恶意Worker，需要独立Unix UID/权限隔离或容器/namespace另行验收。本轮不把同UID保护冒称强隔离。

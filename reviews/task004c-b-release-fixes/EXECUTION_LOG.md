# CPU执行记录

时区Asia/Shanghai。SSH目标sc01-ssh.gpuhome.cc:30414，使用已有pin，未重启/关机、未查询GPU。以下exit是SSH包装进程值，模型运行次数均为0；测试子进程退出码见对应RESULT.json。

| 启动时间 | 收据 | SSH exit |
|---|---|---:|
| 2026-11-24T13:48:05.550768+08:00 | BASELINE_REMOTE_093_receipt.json | 0 |
| 2026-11-24T13:49:14.446180+08:00 | API_SHARING_PROBE_receipt.json | 0 |
| 2026-11-24T13:53:57.792078+08:00 | API_SHARING_PROBE_v2_receipt.json | 0 |
| 2026-11-24T14:06:26.715522+08:00 | CPU_initial_receipt.json | 0 |
| 2026-11-24T14:09:47.678768+08:00 | CPU_revision02_receipt.json | 0 |
| 2026-11-24T14:13:23.717950+08:00 | FULL_BUFFER_CPU_PROOF_receipt.json | 0 |
| 2026-11-24T14:18:13.139248+08:00 | CPU_final_receipt.json | 0 |
| 2026-11-24T14:25:40.535627+08:00 | FINAL_CPU_RELEASE_AUDIT_receipt.json | 0 |

1. 核验远端完整093候选，克隆独立副本，导出3721路径身份和原118记录。
2. 探索直接from_file的失败与迁回tmpfs现象；保留v1失败，v2做显式对照。
3. 修复Local flags、实现受限文件storage reducer与精确序列化预算。
4. initial完整回归145/148，发现3个CLI路径问题；修复工作区ROOT定位。
5. revision02完整回归148/148。
6. 执行原尺寸2.2464GB双spawn读写试验，PASS；没有加载真实模型。
7. 新增4项存储admission校验，final完整回归152/152。
8. 独立CPU预算fixture38,616 bytes闭环；核验原资产保护、核心AST，提交新完整候选668a88c74c7f7a88a572679d2bd8e86c0a05514b。
9. 在无活动映射并校验SHA后回收两份本轮大合成payload，保留全部证据与小fixture；历史删除0。
10. 本地整理五份报告与评审包；真实C0、RGB前缀和B四臂仍未执行。

远端原始transport日志仍保存在工作区logs/；为避免无意义的base64返回包及SSH调试噪声，ZIP以结构化收据、内部stdout/stderr和原unittest日志为执行证据。未省略已知失败。

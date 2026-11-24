# Release CPU回归测试报告

最终：**152/152 PASS，failures=0，errors=0，子进程退出码0**。原118项+新增34项，耗时52.820秒。所有Python子进程设置`CUDA_VISIBLE_DEVICES=""`；Torch版本2.1.0+cu118只用于CPU Tensor和spawn，不初始化CUDA。

## 原118项如何保留

原始报告逐字节保留：`evidence/ORIGINAL_118_CPU_TEST_REPORT.json`，SHA256 `d594db46b3d640c8fc59998836099f12066c6ae18d8d11e3cbfefdfa98a7cabd`。6份原测试源码也按baseline identity中的SHA逐项核验并保存在`evidence/ORIGINAL_118_TEST_SOURCES/`；新目录中重跑同118个test ID，不改历史文件。

新目录中的`test_local_W_and_U_are_not_redefined`只为video fixture补充vanilla cfg字段，因为修复后恢复了原local_flags的严格前置校验；断言与test ID不变。原版本源码和补丁保留，不能说所有测试源码逐字节未变。

## 新增覆盖

| 测试类 | 项数 | 结果 |
|---|---:|---|
| ExactBudgetTests | 9 | PASS |
| FileSharingTests | 11 | PASS |
| ScopeGuardTests | 10 | PASS |
| StorageAdmissionTests | 4 | PASS |

用户要求的missing phase、incorrect phase、motion_only、有效INIT_D=0、有效Local D toggle均真实执行。另核对原local_flags所有vanilla拒绝条件，非Local无扩大D范围。

## 失败和修订记录

| 轮次 | 结果 | 处理 |
|---|---|---|
| API探索v1 | 内层退出1，Bad file descriptor | 保留；v2显式对照重建失败机制 |
| initial | 145/148，3个旧CLI用例失败 | 独立工作区symlink解析ROOT错误；修复两个CLI工作区寻址 |
| revision02 | 148/148 | 验证路径修复与30项新测试 |
| final | 152/152 | 再加入4项存储admission验证后重跑完整套件 |

这属于获批CPU修复迭代，不是真实模型自动重试。全部历史测试结果保留，不能只展示最后一次通过。

## 可追溯证据

最终逐项结果：`evidence/CPU_final/artifacts/RELEASE_CPU_final/CPU_TEST_REPORT.json`；每条包含input、seed、expected、actual、seconds、stdout、stderr、exit_code、stdout/stderr SHA。单项exit_code为测试框架映射的通过/失败结果，不声称每个用例都有独立OS进程。

套件真实OS子进程stdout/stderr和退出码：`evidence/CPU_*_RESULT.json`；unittest原日志在各轮artifact目录。SSH包装进程退出码和CPU子进程退出码分别保存；例如initial的SSH包装退出0、测试子进程退出1，报告以内部测试结果为准。

全尺寸共享压力测试另计一次CPU试验，非新增GPU运行；小型预算fixture另计CPU证据，不伪装为NATIVE_C0。当前候选完整提交为`668a88c74c7f7a88a572679d2bd8e86c0a05514b`，父提交`0931141cf88247dc8fb0c7628c1d91b6531fea90`。

## 复现方式及限制

包内提供093基线相关文件、改后源码、patch、测试和合成生成脚本。应在独立副本/独立输出目录、同Torch版本执行CPU套件，标签必须唯一，避免覆盖已有结果。Linux文件映射与posix_fallocate测试不声称已在Windows验证。

本轮没有导入实际DROID-W模型、加载预训练权重、运行RGB、重编译CUDA或启动B四臂。CPU结果不能证明正式GPU数值一致、速度或轨迹改进。

# Task004C-B Native Release Fixes

日期：2026-11-24（Asia/Shanghai）。状态：**CPU_FIXES_COMPLETE_WAITING_FOR_REVIEW**。

## 版本来源

唯一基线是远端完整候选 `0931141cf88247dc8fb0c7628c1d91b6531fea90`。本轮在独立目录和 `codex/task004c-b-native-release-fixes` 分支修改，生成完整候选 `668a88c74c7f7a88a572679d2bd8e86c0a05514b`，其唯一父提交就是上述基线。未使用文本参考提交 `2e5e5767c8a4154ad184ef38721e2ab6f190f621` 作为源码来源。

原候选目录 3,721 个路径与起始清单一致；14 个保护资产 pin 一致。1,906 个 C/CUDA、几何及网络核心路径保持不变，原生扩展调用的 AST 保持一致。原始 `task004_controls.py`、原始 R2 YAML、权重和 CUDA 扩展未修改。证据：`evidence/FINAL_RELEASE_AUDIT.json`、`evidence/REMOTE_BASELINE_IDENTITY.json`。

## 修复和验收

| 项目 | 实际变更 | 验收范围 |
|---|---|---|
| Local BA 失败关闭 | 缺 phase、阶段错配、motion_only 立即 STOP；恢复全部 vanilla 前置条件 | CPU 单元测试 |
| 初始化 D=0 | 三个初始化 observer 阶段保持 INIT_D=0；motion_only 初始化拒绝干预 | CPU 单元测试 |
| 非 Local BA | 无 marker 时原样返回原生 D/W/U；有非法 marker 时 STOP | CPU 单元测试 |
| 大型 CPU 共享存储 | 数据盘 MAP_SHARED + 受限 storage reducer；只改两处 CPU 分配 | 小型 alias/stride 测试及原尺寸双 spawn 进程实测 |
| C0 保存 | 完整对象图去重后，逐 archive 预计算真实序列化字节和 SHA；每次写盘前检查余量 | CPU 合成快照；真实 C0 未创建 |
| 路径入口 | 支持独立工作区 symlink 布局，保留已有运行授权保护 | 原118项中的 CLI 回归 |

`selected_flags()` 位于 `candidate/native_control/install.py:9-33`。Local 条件仍要求原生 `metric_depth_reg/use_u/update_u/uncertainty_aware/enable_affine_transform` 为真、bidirectional U 与 loop 为假、`gamma_depth=0.01`。controller 只决定 D，W/U 不在此重写。

## 实测结果

- 原118项保留并重新执行；新增34项，总计 **152/152 PASS**，退出码0，耗时 52.820 秒。
- 原尺寸 CPU 缓冲区 **2,246,400,000 bytes**：父进程和两个独立 spawn 子进程内容 SHA、dtype、shape、stride、offset 一致；写入后双方和父进程看到相同更新。
- 合成跨进程实测 `/dev/shm` 增量 **61,440 bytes（60 KiB）**，保持 buffer=500。
- CPU 合成快照预算 **38,616 bytes**，实际逻辑文件总量 **38,616 bytes**，实际分配53,248 bytes。
- 收尾数据盘可用 **26,886,483,968 bytes（25.0400 GiB）**；`/dev/shm` 2 GiB，使用量恢复0。

## 未被本轮证据证明的事项

1. CPU worker 是 Tracker/Rerun 的共享读写替身；没有运行真实 Tracker、Rerun Viewer 或任何模型。不能将其写成原生 GPU 跨进程验证通过。
2. 完整真实 C0 大小仍是 UNKNOWN。7,468,230,540 bytes 只覆盖23个 Video 数组，不含模型、相关体、其他对象状态、元数据等。完整实时闭包的预算器已实现，但本轮没有权限生成该闭包。
3. mmap 将容量压力转移到数据盘和页缓存；保留多个未来 attempt 的 backing 文件会累积占用。本轮没有授权自动删除历史或未来研究输出。
4. admission 中64 MiB是小型 IPC 的静态预算，不是测得的真实 Tracker/Rerun 最低需求；CPU proof不会授予 GPU 运行权限。

## 变更与下一阶段边界

补丁：`evidence/FINAL_ARTIFACTS/artifacts/RELEASE_FIXES_FROM_093.patch`。完整远端候选已提交；包内 `candidate/` 是用于审阅的相关源码子集，不包含全部官方仓库、权重或数据。

本轮 GPU、CUDA 初始化、真实 C0、RGB前缀、B1/B2/B3/B4均为0。未重编译扩展、未降低buffer、未调整BA公式。完成后停止；未自动进入任何真实运行。

# CPU 共享存储设计

## 问题和已排除的简化方案

2 GiB tmpfs 容量为2,147,483,648 bytes，小于两块CPU存储2,246,400,000 bytes。计算来自buffer=500、float32 images及DINO原生shape，未把CUDA Tensor算入tmpfs。

对现有Torch 2.1.0+cu118的CPU实验发现：

| 方案 | 实测 | 决定 |
|---|---|---|
| `torch.from_file(shared=True)` 后直接传Tensor，file_descriptor | spawn序列化触发Bad file descriptor | 不采用 |
| 同上，file_system | 可共享，但映射迁入 `/dev/shm/torch_*`，原数据盘文件没有收到写入 | 不解决容量问题 |
| 传路径descriptor、子进程重新打开 | 同inode映射、父子写入一致 | 作为受限reducer的基础 |

首个未捕获异常的探索也保留在 `evidence/API_PROBE_RECEIPT.json`；后续v2对照将这些作为显式负对照。不是只凭API支持宣称通过。

## 选择的实现

`candidate/native_control/file_backed.py` 使用独立的owner目录和0600 backing文件；先以 `posix_fallocate` 真实预分配，再用 `torch.from_file(shared=True)` 建立MAP_SHARED。ordinary Tensor的数值、dtype和view元数据由原Torch Tensor reducer保留。

仅为注册过的 `torch.UntypedStorage` 使用自定义storage reducer，发送schema、绝对路径、长度、device/inode和权限信息；子进程验证后打开同一个文件。每进程cache保证同一storage只重建一次，保留别名。未注册的CPU storage退回安装版本的原reducer；没有改CUDA Tensor reducer。

对 `src/depth_video.py` 仅替换 `images` 与 `dino_feats` 两个CPU分配。默认未设置 `GAMECAM_FILE_BACKED_CPU_ROOT` 时保留原有zeros/share_memory行为；未来独立attempt显式设置该变量。未改buffer、计算device、dtype、形状或BA。

C0恢复通过可选CPU storage factory为每个已共享CPU storage分配一次mmap，再恢复各view。默认V2 reader仍可读原快照；没有将整套runtime object pickle化。

## 保持的语义和边界

- 普通Tensor；values、dtype、shape、stride、storage offset、storage alias以真实spawn及序列化恢复测试验证。
- 非连续transpose/slice、不同dtype、非零offset均有合成覆盖。
- inode/文件长度/路径身份变更、非法目录等条件失败关闭。
- 写入由既有锁/屏障调度，mmap不提供新的优化算法或额外并发锁语义。
- Python强引用和backing文件在所有消费者退出前必须存活；无自动历史清理功能。
- 私有目录并非恶意root隔离；路径检查用于运行身份与完整性，不声称安全沙箱。

## 容量与生命周期

2,246,400,000 bytes现在占数据盘而非tmpfs。写盘前检查10GiB余量。两份大文件实际物理分配分别1,382,404,096与864,006,144 bytes。页缓存仍受容器RAM约束，本轮不声称真实GPU峰值RAM已测定。

64MiB residual shm阈值仅是静态小型IPC预算；只有版本、模块SHA及完整尺寸CPU proof一致时才可选择mmap路径。缺失/过期proof不会放宽门禁。正式GPU授权保护保留。

本轮测试完成后只回收本轮两块可重建的合成大payload：先查无活动映射、核对路径/inode/size和SHA。历史删除数0；完整证据与小型fixture保留。未来真实C0/研究输出不得套用该清理动作。

## 证据及来源

主依据为本机安装版本的实测和 `evidence/artifacts/API_SHARING_PROBE_v2/INSTALLED_reduce_storage.py`。官方v2.1.0源可辅助核对：[PyTorch reductions.py](https://raw.githubusercontent.com/pytorch/pytorch/v2.1.0/torch/multiprocessing/reductions.py)。不将较新在线文档替代安装版本行为。

结论：**CPU共享机制可行，真实Tracker/Rerun原生运行尚未验证**。不能据此跳过后续真实运行前的完整闭包、进程启动及资源核验。

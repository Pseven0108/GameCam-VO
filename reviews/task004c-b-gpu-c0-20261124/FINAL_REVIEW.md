# Task004C-B-GPU-C0 最终评审 · 2026-11-24

**状态：BLOCKED_AT_FIRST_RGB_INPUT_CONTRACT。已执行1次真实GPU启动；C0未生成。**

| 项目 | 实际结果 |
|---|---|
| 当前实例 | sc01-ssh.gpuhome.cc:30448；RTX3090 24GB |
| 运行源码 | 668a88c74c7f7a88a572679d2bd8e86c0a05514b；未改动 |
| 独立原生进程生命周期 | 1次，退出码1；不自动重试 |
| 总耗时 | 58.316秒，主要为模型/进程启动 |
| 首帧 | RGB001已被CPU解码，进入Tracker前被输入合同拒绝 |
| 进入跟踪的有效帧 | 0 |
| Native BA / 初始化完成 | 0 / 否 |
| 真实C0 / 完整C0大小 | 未创建 / UNKNOWN |
| GPU显存采样峰值 | 7,439MiB；不是完整初始化显存需求 |
| shm采样峰值 | 212,992bytes（208KiB） |
| Restore / 跨D / B1-B4 | 全部未执行 |

## 已确认根因

`NativeViperRGB.__getitem__()`要求`depth is None`，但其实际父类`BaseDataset.__getitem__()`在`depth_paths=None`时返回`torch.zeros(H,W)`作为无深度占位。首帧得到float32、CPU、shape=(360,640)的全零Tensor，因此被这一项检查拒绝。

CPU实读核对：timestamp=0正确；RGB shape=(1,3,360,640)正确；pose=None正确；仅depth_is_None为假。depth_paths与poses均为None，没有引入GT。已用未经改动的真实父类loader与真实第一张RGB复现，非模拟推测。

## 解释范围

这是候选输入适配层的合同错误，不是DROID-W优化失败，也不是C0序列化、显存或磁盘不足。此前152项CPU测试通过仍然是历史事实，但没有覆盖这一真实loader分支，不能视为GPU-ready证明。

原生Tracker与Rerun进程已创建，2255-byte录制文件存在；由于0帧进入跟踪，不能声称真实数据读写/几何显示已验证。浏览器未验证。完整C0与恢复能力仍未知。

## 现场和空间

保存完整stdout/stderr、资源采样、native trace、CPU复现、配置/源码身份和运行收据。GPU进程组已退出，GPU无剩余compute进程。仅回收本次两份全零临时Arena，先核对owner、路径、inode、device、size、mode、SHA，并扫描/proc确认无活动映射。释放2,246,410,240个实际字节，历史删除0。清理后可用24.5886GiB。

## 停止状态

未修改668a88c7源码、BA数学、R2配置、权重或扩展；没有自动重跑、恢复、跨D或正式B四臂。实例保持在线，没有重启或关机。

下一步应先修正并CPU验证这一个占位深度合同，再另行批准一次C0采集。建议细节见`NEXT_CAPTURE_RECOMMENDATION.md`，本包未把建议应用到任何GPU运行。

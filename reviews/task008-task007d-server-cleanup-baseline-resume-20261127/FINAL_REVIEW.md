# TASK008停止、服务器清理与Baseline优化方向恢复

2026-11-27（Asia/Shanghai）。本轮是用户授权的存储维护和研究方向更新。

**执行结论：清理完成；TASK008停止并封存；恢复DROID-W Baseline优化方向。没有启动新的实验。**

| 文件系统 | 清理前可用 | 清理后可用 | 实测增加 |
|---|---:|---:|---:|
| 数据盘 `/root/rivermind-data` | 3.658 GiB | 11.126 GiB | 7.468 GiB |
| 系统盘 `/` | 0.683 GiB | 5.745 GiB | 5.062 GiB |

表中为清理完成时的文件系统实测值。审计与发布记录后续写入会占用少量空间；逻辑文件字节数与实际释放量分开报告，未重复计算Conda硬链接。

## 删除范围

实际删除八个精确路径：TASK008专用wheelhouse、安装临时目录、源码传输bundle、服务器预测输出副本、官方π³mos权重目录、独立`pi3mos-infer`环境，以及TASK008/TASK007D两个已发布的重复ZIP。逐项路径、字节及文件数量见`DELETED_PATHS.csv`。

TASK007D在该实例仅有约85 KiB重复评审ZIP，没有本阶段新增的大型原始OmniWorld数据。未为追求释放量扩大到TASK007C、早期OmniWorld或其他历史数据。其报告、源码证据、尺度结论和GitHub Release均保留。

## 删除前验证

- 本地TASK008原始结果520份、866,457,714 bytes全部重新核对SHA-256；其中服务器输出目录488份逐项与本地备份匹配后才删除。
- TASK008展开评审526项、TASK007D展开评审47项内部SHA-256重新通过。
- 两个删除ZIP分别匹配既有公开发布收据SHA-256；TASK008权重在删除前匹配已封存官方文件SHA-256。
- 每个目标路径解析后与精确允许列表一致。检查进程cwd/exe、打开fd和映射文件，删除前无活动占用。没有终止其他任务。
- 所有允许路径在删除后确认不存在。完整删除前文件身份清单以无损gzip保存；环境二进制和权重没有进入评审包。

## 保护结果

**2,318份受保护文件前后SHA-256、大小、inode、设备号、权限和mtime一致。** 覆盖既有1830份DROID-W源码/配置/观测JSON、487张val_007原始RGB及原始输入Manifest。

DROID-W与Metric3D生产路径、权重、CUDA扩展、既有环境和历史Task004/005等目录不在删除允许范围，未执行写入。此次2318项哈希核验不应被扩大描述为对全部模型权重和所有历史文件重新逐项验收。

Conda注册表仅移除`/opt/gamecam-pi3mos/envs/pi3mos-infer`这一行，其余注册条目保留。官方π³mos源码、运行日志、配置及加载失败记录仍保留在服务器；独立环境和权重如要重启该支线需重新部署，不能再声称服务器可立即复跑。

## 阶段状态与后续边界

- TASK008：`STOPPED_AND_PARKED_BY_USER`，不再推理、扩大样本或接入DROID-W。
- TASK007D：审计成果封存，仅移除重复服务器ZIP；严格米制GT准入结论保持原样。
- 研究方向：回到DROID-W Baseline优化。当前没有新运行任务，不将本次清理授权视为算法修改、BA集成或新增消融授权。
- 当前`nvidia-smi`返回Exec format error、`/dev/shm`为2 GiB，与用户此前无卡启动情况一致；没有尝试修复驱动、重启或改变资源。
- 清理GPU推理次数0；实例关闭/重启次数0；原有R2配置、源码、权重和已有评价成绩不变。

## 结果保留位置

- 私有本地原始预测：`D:/aaa/GameCam-VO/experiments/task008_pi3mos/retrieved`，64份float32 NPZ保留。
- 服务器审计：`/root/rivermind-data/GAMECAM_TASK008_TASK007D_CLEANUP_20261127`。
- TASK008原始封存评审：[固定提交](https://github.com/Pseven0108/GameCam-VO/tree/9341fce81a540a9ef1711b0f0b6cb49873ce990b/reviews/task008-pi3mos-night007-independent-inference-20261126)。
- TASK007D原始封存评审：[固定提交](https://github.com/Pseven0108/GameCam-VO/tree/3bf7da7bb39192081cefe9898e948784ae6cd5aa/reviews/task007d-metric-scale-provenance-audit-20261126)。

本次追加清理及状态变更记录，不改写上述历史报告与Release。

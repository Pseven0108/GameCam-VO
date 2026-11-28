# 本地运行环境与共同协议差异

仅使用本地 RTX5060 8GB；远端连接、资源变更与服务变更均为0。
Windows 控制入口 `D:\aaa\envs\gamecam-vo\python.exe`；实际 Linux CUDA 运行环境为已有 WSL `/home/lsuser/.local/share/gamecam-vo/envs/droid-w/bin/python3.10`。
Python3.10.22、PyTorch2.7.1+cu128、CUDA12.8、sm120。没有安装驱动或修改原共享环境。

| 项目 | 本地共同处理 | 可比性限制 |
|---|---|---|
| 输入 | 原始1920×1080，原生预处理到640×360，stride1 | K 来自准确窗口 Manifest，加载后与 tracker 内参核对 |
| buffer | 所有组96 | 最多64输入+16 filler槽，没有淘汰；不等同于服务器500槽协议 |
| 进程 | 原生Tracker单进程 | 不复现服务器spawn/GUI调度开销 |
| Metric3D | sm120不兼容可选xFormers，运行时改用SDPA | 权重/预处理/归一化不改，浮点后端不同 |
| FiT3D | pretrained=False创建同结构，严格加载完整fine-tuned checkpoint | 跳过会被完整checkpoint覆盖的基础权重下载，所有key匹配 |
| prior/features | 各模型顺序生成公共缓存，运行时按帧取回 | 避免8GB中模型和BA同时常驻；正式计时不包含公共缓存生成 |
| A5扩展 | 单独构建local_a5_splat_c3414af6 | 仅候选兼容副本更新dispatch API与头文件搜索，未替换安装扩展 |
| allocator | expandable_segments:True，所有正式组一致 | Day004首次BASE因碎片OOM，失败完整保留 |
| Viewer | 本地关闭在线Viewer | 不影响/不查询远端可视化；最终派生图完整保存 |

本地安装扩展来自既有依赖树43c1425b；已与c3414af6原生CUDA源码比较，BA算术相同，差异为旧PyTorch `.type()` dispatch API到`.scalar_type()`。
候选A5原文与本地构建兼容副本分别保留。不要把本地构建等价检查推广为远端所有配置的逐位一致。

四组Tracker+FinalBA+Filler计时约BASE63.66s、A567.32s、SCALE57.81s、SCALE_A559.19s。
A5计时包含4次端点核验BA；公共缓存生成未计入，因此这些数据不能作为稳定的速度改进结论。
allocated峰值约5.302GiB；reserved分别为6.355/6.746/7.078/6.863GiB。reserved不是Windows桌面总显存。

三份共享checkpoint、安装的原扩展SHA最终一致；208份源码按Git blob/LF归一化核验。
最初SOURCE_AND_ASSET_AUDIT.json的byte-exact=false源于CRLF，V2记录预期Git blob与LF归一化匹配；两份报告均保留，不隐藏最初告警。

所有新代码、编译产物、数据副本和缓存位于D盘。原始源码工作树、权重与原安装扩展未修改。

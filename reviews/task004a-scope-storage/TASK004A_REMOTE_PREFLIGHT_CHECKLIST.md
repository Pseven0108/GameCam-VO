# Task004A：远端预检待验证项

状态：`REMOTE_PREFLIGHT_NOT_AUTHORIZED`。下表是授权后的核验合同，本轮无 SSH、无服务器探针、无 CUDA、无模型加载。历史通过只能帮助识别待比对的身份。

| 待查 | 获准后应提供的证据与准入方式 |
| --- | --- |
| 目标实例 / SSH / RTX 3090 | 从用户确认的连接信息和独立可信主机指纹核对目标。记录当前实例/boot、GPU 型号/显存/算力与 GPU UUID；物理卡可能变化，UUID 用于记录与本次绑定。按历史 Task003 资源规则核对 3090、24,576 MiB、CC 8.6、空闲至少 23,000 MiB、无其他计算进程；禁止抢占，不启动或重启 GPU。任一身份不明时停止。 |
| CUDA 与扩展 | 静态核对现有 CUDA 11.8 环境、Python 3.10 ABI、库解析、驱动和原 `droid_backends.cpython-310-x86_64-linux-gnu.so`。SHA-256 应等于 `6dcf8de36cadc2174023b649b026f04e61b1231420d98763cc5aa3b294a91c3e`，与 `Task003/evidence/TASK003_FINAL_PREFLIGHT.json` 对照。预检不导入扩展或张量模型，不重编译。 |
| 冻结源码 | 对照 DROID-W `c3414af6047d06bafc1a6645d09f23247f3b2cdc` 的提交、工作区和子模块，独立对比审过的候选补丁与所有 postimage；不要改生产源码。候选与正式启动入口仍需发布和授权，不能用 `--native` 绕过保护。 |
| 四个权重 | 用 Task003 `evidence/STAGE_VERIFICATION.json` 的四个 `weights[].path/bytes/sha256`：`droid.pth`、`dinov2_reg_small_finetuned.pth`、`metric_depth_vit_large_800k.pth`、DINOv2 的 `model.safetensors`。只对解析路径、大小、SHA-256 做校验，不反序列化，不下载替代件。 |
| 原始 R2 YAML / arm 策略 | R2 YAML SHA-256 `a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc`。核对 `buffer=500`、`setup_seed=43`、`stride=1`、固定内参与原 Metric3D、U、UBA、Final BA、Filler 及 Rerun；当前政策只替换两个主循环局部 BA。校验每组独立策略 SHA 和预定顺序。 |
| 487 帧和合同 | `val_007_full_00001-00487`，逐张核对有序原始 ID、字节与哈希，确认 640×360、stride=1、输入 K；参考封存 `INPUT.json` SHA-256 `5547cdd407e022ba27a8b9af18f1ef4e9471ea58c1e0df96aec38fee180aa537`，差异必须有审批证据，缺帧不补。GT 与评分路径保持离线独立。 |
| 卷、磁盘、接收端 | 对源结果、原生保存，spool 和接收目的地分别核对真实路径、挂载设备、文件系统、当前可用字节/inode；每组前至少 13 GiB，保留线 10 GiB，按 3 GiB 单组预算及归档峰值验证连续八组。正式绑定窗口机器 D: 的接收路径和可用量，验证异机校验回执。 |
| `/dev/shm` 和容器内存 | 记录 tmpfs 容量和可用量、容器 `memory.max` / `memory.current` / `memory.events`，检查有效限额和并用。Task003 上次有卡记录为 24 GiB shm / 100 GiB 内存；旧预检 8 GiB shm 是协议门槛，不是算法最低需求。不要因为无卡快照小就改 `buffer`；历史数据不能替代当前测量。 |
| 原生 Rerun 三端口 | 9875：SDK TCP；9876：HTTP Viewer；9877：WebSocket。确认当前服务器与本机的监听归属、端口空闲/冲突、viewer 版本及回环绑定；HTTP 和 WS 用经核验的本机转发（记录本机实际端口与目标端口）。不把一次 HTTP 200 当作可视化成功。 |
| Rerun 远端无模型渲染 | 只有获准连接后，才从**目标服务器**的 9875 注入本次唯一 recording ID 的三个彩点和视锥；在真实浏览器核对相同实体、接收非空 WebSocket 流、前后画面与截图 SHA。核对浏览器连接没有指向本机探针/旧录制。探针不通过不允许启动模型。 |
| 生产流与调度保护 | 模型启动后另验证该 attempt 发送的实时相机实体和帧数/画面，不用合成探针代替。每次一个 E3→E4→E7→E0→E8→E6→E1→E2，独立 attempt/output/策略 SHA。任何失败保留现场并停止，禁止跳组、自动重试和删除。`require_approved_runtime()` 与 `--native` 均保持阻断。E5-F0 `BLOCKED_FOR_NATIVE_EXECUTION`。 |

当前 Rerun 三条证据互相独立：

| 证据状态 | 结论 |
| --- | --- |
| `LOCAL_SYNTHETIC_RENDER_PASS` | 已有 Task004-A `_local_probe/probe_05/RERUN_LOCAL_PROBE_RESULT.json`：Windows viewer、合成数据、浏览器 WebSocket 101、21 帧非空传输、彩点和视锥像素实际出现。本轮复核 `browser_after.png` SHA。 |
| `REMOTE_SYNTHETIC_RENDER_PENDING` | 尚无本次目标服务器的隧道与真实浏览器证据；Task003 的旧服务不等于 Task004A 当前服务。 |
| `NATIVE_DROIDW_STREAM_PENDING` | Task004A 8 组均未运行，没有任何当前 attempt 的真实位姿流。 |

下一次可以独立审批远端只读预检与无模型探针。即使它们通过，正式筛选仍要自己获得授权、容量就绪及可执行候选发布。此次只交付清单。

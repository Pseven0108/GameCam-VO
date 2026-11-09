# 项目与启动链路审计

本轮基线为 6733e8a57c73ffbc4738d4bfaf376b4e433e39c3，独立工作区 /root/rivermind-data/gamecam/staging/GameCam-VO-DROIDW-Entry-Readiness-20261109T063658。原 session-write-boundary-fix 远端分支未发现，因此实际完成修复后单独封存该修复，再在 readiness 分支继续。生产项目、旧候选、main 和历史 Tag 均受保护。

启动入口 launcher_v2 → LaunchContext.validate_candidate → supervise_once → NVML启动屏障 → 消费独立授权与Nonce账本 → prepare_owner → native_child_v2 → 子进程再次验证 → RuntimePins → IPCPolicy → 精确文件边界 → Guard → 原生适配器。真实 Tracker/先验/BA 路线本轮不进入。

正式输入是 K4 的120张7953–8072 PNG与固定 K；原生 RGB_NoPose 数据集及适配器仅提供RGB/索引，Pose=None，GT评价独立。本轮使用 CPU fake tracker 逐帧核对原图，未执行模型推理。

模型输出、Worker遥测、Supervisor/Monitor控制文件、Arena与fallback分别设置权限。Worker与Supervisor同为UID0，0600/0700仅防其他UID；它们不是彼此的OS隔离。Python audit不覆盖已打开文件描述符任意写入、ctypes和native syscall。预打开目录fd的路径型攻击已拒绝；任意已有可写文件fd仍在该策略范围之外。

所有GPU测试为独立合成张量/扩展，不创建模型Attempt；未来真实模型仍需独立用户授权。

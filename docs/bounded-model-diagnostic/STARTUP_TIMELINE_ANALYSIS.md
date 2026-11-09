# 15秒屏障的真实覆盖范围

NVML屏障起点：GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/runner_core.py:47；启动Monitor后需要两个至少间隔0.25秒的新鲜样本，在Supervisor启动起点15秒内完成。随后重新检查并消费许可、建立IPC，再启动Worker。

Worker屏障起点：GameCam-WW-V5_7-NA-K6-A-GPU-R2-PATH-CONTRACT-REPAIR/scripts/runner_core.py:102。从Popen前起计，覆盖子进程创建、候选与用户证据校验、IPC/IO边界、Torch导入、CUDA context建立和首批遥测。需要至少两个递增CUDA样本，父进程写work.permit.json。

Guard的许可等待在CUDA context与心跳线程建立后开始，也保持15秒。Guard返回后才导入重型Tracker/先验模块、构造DroidNet、加载真实权重、分配DepthVideo和构造Tracker。因此不能把15秒解释为完整模型初始化的总时限。

本轮修复一个状态边界：尚未permit时，Worker启动15秒限制也覆盖“已有首个CUDA文件但未通过样本屏障”的状态，不能因文件存在跳过超时检查；阈值未提高。活跃CUDA/NVML仍为3秒，故无进展时可能更早按3秒规则停止。

FULL_MODEL_STARTUP_TIMING_UNVERIFIED：本轮仅有合成进程时间线，真实候选校验+Torch+CUDA是否在15秒内建立合格遥测以及Tracker完整构造时长均需未来实测。重型Python/C++初始化可能阻塞心跳线程；这是未来诊断的停止风险，不能预先承诺通过。

全局3600秒、Terminal清理5秒、SIGTERM宽限5秒保持。零帧诊断不能产生30帧增长窗口，本轮不会伪造帧事件；该规则保留且条件不可满足，独立记录阶段内存与周期CUDA/NVML样本，并持续执行512MiB绝对底线。

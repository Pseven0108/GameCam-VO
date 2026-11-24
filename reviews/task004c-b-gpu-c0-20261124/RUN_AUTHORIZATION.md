# 本轮授权边界

已批准：当前3090实例上的一次初始化/C0采集；源自已评审668a88c7；保持原R2参数、buffer500、stride1；file-backed CPU storage；采集后停止；完成后通过私有GitHub提供评审材料。

本轮实际：1次原生GPU进程启动，第一帧输入检查失败，exit1，无自动模型重试。CPU postmortem与只回收本次全零临时Arena均保留证据。

未执行：真实C0恢复、S1/S0、跨D重放、正式B1-B4、全487帧、DROID-SLAM、训练、算法修复运行。未重启或关闭GPU/实例。

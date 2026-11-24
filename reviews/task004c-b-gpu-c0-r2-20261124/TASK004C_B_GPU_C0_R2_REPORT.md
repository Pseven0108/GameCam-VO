# GPU C0 R2 实际运行报告

**最终：共同初始化完成，完整C0保存被状态闭包检查拒绝。任务完整成功标准尚未达到。**

| 项目 | 实测 |
|---|---|
| 实例 | sc01-ssh.gpuhome.cc:30448；RTX3090 24GB |
| 运行候选 | 02f8c8308274489ff7eff83fa9b87b98db74122e |
| 配置 | 原R2，buffer500，640×360，stride1，seed43，INIT_D=0 |
| 本轮GPU生命周期 | 1次，PID2058，exit1，无自动重试 |
| 运行耗时 | 56.164秒 |
| 实际完成RGB | 001～018，下一输入index18/RGB019未读取 |
| 第一阶段graph.update | neighborhood8 + proximity8 = 16 |
| 第二阶段graph.update | 8 |
| Native BA调用 | begin24 / end24 |
| 请求的native内迭代 | 48（API参数合计；无逐retraction独立计数） |
| 初始化完成与frame-end | 均有真实trace，下一帧输入前进入C0 callback |
| C0文件与完整性 | 未生成，complete=false，47族未持久化 |
| 完整C0字节数 | UNKNOWN，不记0 bytes |
| 显存采样峰值 | 13,865MiB |
| shm采样峰值 | 294,912bytes（288KiB，包含启动前80KiB） |
| 结束时可用数据盘 | 23,934,451,712bytes（22.2907GiB） |

## C0语义边界证据

`native_trace.jsonl`记录三阶段各8个完成的graph.update、24个native.ba.end、一次init.complete和RGB018的frame.end(next_input_index=18)，随后实际调用capture_c0。不是仅根据RGB编号或单条init_done判断。

Native BA前后Pose/Disparity/U逻辑SHA均有记录。INIT_D=0依据固定controller与未改动的阶段路由；没有独立捕获每次CUDA实参的完整原始副本，不能把该项升级为逐字节CUDA重放证明。

## 本轮停止位置

`capture_c0 -> state_inventory -> ObjectEncoder`遍历真实Metric3D模型时，在`LoRALinear.lora_dropout`遇到未注册函数对象并抛出ControlError。程序尚未进入prepare_state或实际checkpoint写入。

不是磁盘门禁或OOM触发；监督器未发出资源停止信号。没有生成完整/部分类C0文件，没有执行后续恢复、S0/S1、跨D、正式四臂或Final BA。

## 资源与数据保护

GPU前四份权重、原R2、扩展和历史源码pin核验通过；487张RGB逐SHA匹配INPUT manifest。旧Arena无文件或活动映射。GPU后14个保护pin再核验一致，运行源码仍只有输入适配层一项变化。

两份本轮Arena包含已处理RGB/特征，合计2,246,400,000逻辑bytes，现保留作失败现场；无活动映射或残留本轮进程。没有删除历史数据。GPU/实例保持在线，没有重启或关机。

原生Rerun录制文件3,450,264 bytes，记录SHA见postmortem。没有验证浏览器渲染，不将录制文件存在等同于可视化成功。stderr中的resource_tracker警告原样保留；没有擅自清理/dev/shm命名空间。

# 当前状态 · 2026-11-24

- VIPER / DROID-W / stride=1；stride=4分支不作为当前主线。
- 当前运行源码：02f8c8308274489ff7eff83fa9b87b98db74122e；只修NativeViperRGB。
- 当前任务：TASK004C-B-GPU-C0-R2。
- 状态：BLOCKED_AT_C0_CLOSURE_UNREGISTERED_LORA_DROPOUT_FUNCTION，等待人工评审。

已通过：21个真实Loader用例、18帧CPU连续校验、最终152项完整回归、487张RGB SHA及原始保护资产核验。

实际GPU：1次生命周期、18帧完成、16+8次graph.update、24次native BA，进入frame-end保存边界；56.164秒后exit1，无自动重试。C0未生成，47族/网络Buffer/RNG未持久化，完整大小未知。

首个保存阻断是Metric3D lora_dropout未注册函数。未改序列化器或模型，后续是否还存在未知字段尚未验证。没有restore、S0/S1、跨D或B1-B4；无轨迹性能提升结论。

原BaseDataset、BA、CUDA扩展、原R2、权重、RGB和历史结果保持不变。两块本轮Arena保留取证；GPU进程已退出，服务器保持在线。GitHub发布不授予下一阶段实验授权。

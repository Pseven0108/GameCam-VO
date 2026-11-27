# CUDA传输与性能

本地RTX5060，PyTorch 2.15.0+cu132 / CUDA 13.2；仅合成Tensor。
运行时TorchDispatch审计能看到显式copy-to-CPU与CUDA scalar read，旧路径负对照能实际捕获问题。
独立Profiler同时捕获了32源帧新路径的3704字节D2H，其中8字节为内部小传输，3696为摘要。
没有[500,45,80]或[64,45,80]像素Tensor D2H。日志统计与设备索引允许传回；没有逐源帧item。

Buffer500/S7：p50=2.842300ms，p95=3.280465ms，显式D2H=896 bytes。
Buffer500/S32：p50=2.851400ms，p95=3.271470ms，显式D2H=3696 bytes。
每条件3次warmup、20次计时，包含摘要处理；峰值包含合成缓存/输入/输出，不是模型显存。
完整原始trace、逐次时间、全部测试日志包含在本包reproducibility的TASK011D/reports。

不宣称速度提升百分比，不把本地5060结果当作3090原生运行开销。
远端2.1.0+cu118只做CPU兼容性与别名复制检查，没有初始化CUDA。

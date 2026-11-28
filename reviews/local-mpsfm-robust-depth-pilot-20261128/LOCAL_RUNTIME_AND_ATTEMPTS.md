# 本地运行与尝试登记

四次Tracker尝试：BASE_001、A5_001、ROBUST_001、ROBUST_A5_001，全部首次完成，无自动重试。
额外6次双迭代BA仅用于同状态端点诊断，不是新的轨迹重复；另有一次合成GPU prior公式检查。
GPU前的第一次只读preflight因WSL PATH未含nvidia-smi失败，指定已有绝对路径后完成核验。
保留PREFLIGHT_LOG.txt及PREFLIGHT_LOG_002.txt，未改驱动、共享环境或算法。

沿用上一轮local buffer96、单进程Tracker、固定原始K、缓存原生深度/特征、cu128/sm120。
64输入外加16个Filler临时槽不会耗尽96槽；无buffer淘汰。原正式协议buffer500没有被改写。
Metric3D/DINO缓存复用相同原生预处理和此前声明的本地SDPA数值后端；本轮未重新推理这两个模型。
GUI未启动，以控制8GB共驻显存。图表来自完成后的离线结果。

run_four_arms.py固定串行顺序；算法参数和窗选择在PROTOCOL.json评分前封存。
所有原始日志、配置、轨迹、关键帧状态、逐轮权重、Endpoint数组完整保留。
本轮没有SSH、服务器进程修改或关机动作。

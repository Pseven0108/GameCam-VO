# Recorder原生接入

Motion Filter、关键帧管理、FactorGraph primitive、图过滤与低内存后端，以及真实DepthVideo.ba入口均已接入候选。Motion Filter的原始运动统计继续由Task003 observer记录；新journal记录可重放的接纳结果、force、阈值和理由。

事件采用begin/end分离，能表达add_factors内部再次rm_factors等嵌套调用。每次事件包含有序拓扑上下文和哈希链。RGB身份由原始0-based timestamp+1映射；同一buffer slot重用后获得新的RGB token。Filler临时槽有独立token。边具有实例ID、稳定RGB两端、age和active/inactive/bad状态。

实际BA的before/native-after/clamp-after仍由原observer记录。新增轨迹、disparity、U、target、weight和eta的SHA摘要写入独立trace。它们不进入可选调度输出。

CPU测试执行了实际FactorGraph Python方法体；CUDA decorators、CNN及扩展计算是明确的CPU mock。这证明接口位置与离散副作用的可测试行为，不证明真实CUDA优化行为。真实Recorder流尚未生成。

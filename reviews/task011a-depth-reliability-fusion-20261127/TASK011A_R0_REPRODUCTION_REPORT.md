# TASK011A-R0 复现

原scale15.985507037495662、48项逐帧排名指标均复现，绝对差0，atol1e-10。GT掩码仍为有限正值，7个零预测保留；原严格门禁失败不改为PASS。见intake原配置、historical_reproduction.csv与cache_manifest.csv。

16份原模型缓存均经SHA核验。0000仅校准，0001已观察，不是新盲测；物理米制未认证。10张VIPER无合格DenseDepthGT，不计算深度准确性。CPU读取器仅在私有目录适配当前Python，原模型和数据保持不变。

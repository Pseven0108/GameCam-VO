# 真实CPU模型跨进程验证

结果：FAIL，父进程与子进程退出码均为1。子进程确为新Python进程；在模型前向比较前，恢复ConfigDict失败。

已执行原模型：Metric3D深度/置信度/法线；FiT3D中间特征；DroidNet fnet/cnet；真实加权LoRALinear输出与输入梯度；71个identity语义检查。固定输入linspace(-1,1)，shape1×3×112×112，float32CPU。输出有限、CPU RNG未改变，SHA见EXPECTED_FORWARD.json。

CPU范围限制：使用真实权重和原有方法；CPU进程在导入时令可选xformers不可用，从而选择安装源码自带Attention.forward备用路径；原get_bins硬编码CUDA，夹具按同一公式在CPU预置非持久depth_expectation_anchor。没有改安装模型源码或GPU运行配置。这不是GPU内核数值等价验证，也不是640×360真实SLAM。

CPU封存夹具：1,635,317,622bytes，800文件，包括Tensor档案1,633,177,144bytes与元数据。独立数据盘副本800/800 SHA匹配。未将此夹具叫作C0。

未完成：恢复模型输出对比、恢复后梯度对比、完整运行对象alias/RNG还原证明。预期容差原定为逐输出SHA完全相同；没有因失败而放宽容差。

真实CPU构造的Video仍为buffer500、360×640，诊断加入合成recurrent/cache值并枚举47族。它不是GPU初始化状态；相关体夹具16×16不代表真实45×80相关体。不得把这项诊断写成47族真实C0恢复通过。

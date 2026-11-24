# Format 专项闭合

状态：PASS；专项修复额度 1/1。仅精确接受 `timm.layers.format:Format` / timm 0.9.10 / source SHA `8b4d8d2d76d65cfbf8589092505e0c9d28d0a7af7df941abe59deb9cc664dfae`。

成员白名单 NCHW、NHWC、NCL、NLC。保存类身份、name、value、pin；恢复通过原安装枚举 `__members__` 查找，保持 `restored is Format.NHWC`。未调用通用 object.__new__ 恢复 Enum，未将其降为字符串，未知 Enum/str 子类失败关闭。读取快照时先验证这类节点，再反序列化 Tensor-only Storage。

代码：`candidate_source/native_control/timm_format_adapter.py`、`snapshot.py`；完整 diff：`source_diff/FORMAT_ONLY.patch`。ConfigDict 及 Metric3D identity Adapter SHA 保持不变。

22/22 真实安装枚举专项、14/14 ConfigDict、152/152 历史回归通过。真实带权模型 CPU 完整往返及真实 GPU C0 对象恢复也通过；RGB019 的新失败属于目录生命周期，与 Format 单例恢复不同。

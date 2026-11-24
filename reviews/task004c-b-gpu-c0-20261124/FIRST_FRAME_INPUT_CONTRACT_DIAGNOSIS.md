# 首帧RGB-only合同错误取证

结论等级：**CONFIRMED_BY_REAL_GPU_FAILURE_AND_CPU_LOADER_REPRODUCTION**。

| 检查 | CPU实读 | 原适配层要求 | 结果 |
|---|---|---|---|
| timestamp | 0 | index=0 | PASS |
| color shape | (1,3,360,640) | 同左 | PASS |
| pose | None | None | PASS |
| depth | float32 CPU Tensor，(360,640)，全零 | None | FAIL |

对应代码：

- `source_evidence/native_control/dataset.py:28-29`：调用父类后检查`depth is not None`。
- `source_evidence/src/utils/datasets.py:202-229`：depthloader返回None时构造`torch.zeros(color_data.shape[-2:])`。
- 同文件RGB_NoPose类把depth_paths、poses设置为None。
- `source_evidence/src/tracker.py:66`：Tracker解包`timestamp,image,_,_`，本轮在loader抛错后没有进入图像处理。

原始zero-depth SHA256：`0b150fd32588b1daca5569992ebe559c0102c837306b1af4c44d35128ec58366`。Native stream的seen在失败后仍为0。对原`NativeViperRGB[0]`再次调用仅发生在CPU诊断中，同样抛出相同异常；没有运行Tracker/模型或再次使用GPU。

## 诊断边界

CPU诊断禁用CUDA并拦截torch.load以防加载预训练权重；末尾cuda_initialized=false。只读原第一张RGB，不读取Camera Pose GT、depth标签或测试GT。diag中depth_paths=None、poses=None。没有纠正RGB/Camera映射或改原始数据。

## 为什么原CPU测试没有发现

此前152项验证控制、storage、快照格式与Mock接口；真实RGB_NoPose父类的无深度零占位分支没有形成该精确合同的端到端测试。GPU-ready状态不应再由这些测试计数单独判断。

这不否定Local BA安全修复或mmap CPU压力实测，但限制真实输入与C0准入结论。本次0帧跟踪、0次BA，无法评价优化行为或深度正则的科学效果。

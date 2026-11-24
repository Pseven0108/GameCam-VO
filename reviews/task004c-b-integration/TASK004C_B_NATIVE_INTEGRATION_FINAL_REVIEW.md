# Task004C-B 原生控制接入评审

**状态：CPU_NATIVE_INTEGRATION_CANDIDATE_VERIFIED_GPU_VALIDATION_PENDING_NO_CARD。CPU接入候选已提交，GPU三项验收均未执行；正式四组实验尚不可启动。**

用户在执行中确认当前仍为无卡启动。保留原始模型、配置与历史结果，没有启动或释放GPU，也没有改成完整487帧运行。

| 验收 | 结论 | 证据 |
|---|---|---|
| 原始资产保护 | PASS | 原源码3694/3694、RGB487/487及14项资产SHA一致 |
| 原生控制接入候选 | PASS_STATIC_AND_CPU | 10份源文件接口、显式状态恢复、离散重放 |
| CPU回归与新增测试 | **118/118 PASS** | 54项原测试+64项新增测试；退出0，CUDA未初始化 |
| CUDA/BA公式不变 | PASS_STATIC | 1896份C/CUDA/头文件、Python BA与Corr未改，原生调用AST一致 |
| 真实C0采集 | NOT_EXECUTED | actual SHA和字节数均null |
| 真实退出进程后恢复 | NOT_EXECUTED | 只有CPU独立进程fixture证据 |
| 真实S1→D0、S0→D1 | NOT_EXECUTED | 双向CPU接口测试通过，CUDA/CNN为mock |
| Final BA/Filler | PASS_STATIC_AND_CPU_ONLY | 保留7/12阶段和12次Filler motion-only；真实记录待正式授权 |
| 正式B1/B2/B3/B4 | NOT_AUTHORIZED | 0次；原启动保护保留 |

当前数据盘可用25.3059GiB。无卡容器的/dev/shm为2GiB，不调整buffer=500。完整C0大小仍未知，实际原生模型对象闭合、CUDA/IPC恢复和Rerun写屏障必须在将来有限GPU验证中逐项验收。

候选对未知运行字段、不能保留的对象/别名、未配对事件、图/age/输入/BA次序不符采用停止策略。不能把本次CPU通过解释成真实DROID-W恢复成功，更不能据此声称轨迹精度改善或直接启动487帧四组。

下一步仅为已有授权范围内的有限GPU验证：有卡实例准入后，一份C0、独立进程恢复、RGB019–080的S1/S0与相反D重放。若边界、状态闭合、存储或调度任一不符就停止；不自动延长，不自动重试。

先看本报告、GPU_SMOKE_TEST与原始CPU报告。全部新增代码、10份前后源码、完整patch、身份/保护清单和失败修订记录一并提交。ZIP外PACKAGE_INTEGRITY.json记录实际CRC/SHA核验值。

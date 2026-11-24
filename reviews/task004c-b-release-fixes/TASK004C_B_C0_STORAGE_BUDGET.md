# 完整C0存储预算与保存门禁

## 当前结论

**完整真实C0字节数：UNKNOWN。精确实时序列化预算器已实现并经CPU合成验证。** 本轮未加载模型、未执行RGB前缀，无法观测真实完整对象闭包，不能用Video小计冒充完整C0。

当前数据盘复核：26,886,483,968 bytes（25.0400 GiB）可用。起始实测为26,955,452,416 bytes（25.1042 GiB）；用户给出的25.3059 GiB不能当作本次最终值。

## 23项Video静态逻辑清单

以下按源码和固定buffer=500、H=360、W=640、feature_dim=384计算，**没有创建真实Video**。

| Field | Shape | 原配置device / 本候选CPU存储 | Logical bytes |
|---|---|---|---:|
| timestamp | [500] | CUDA | 2,000 |
| images | [500, 3, 360, 640] | CPU file-backed | 1,382,400,000 |
| dirty | [500] | CUDA | 500 |
| npc_dirty | [500] | CUDA | 500 |
| poses | [500, 7] | CUDA | 14,000 |
| disps | [500, 45, 80] | CUDA | 7,200,000 |
| zeros | [500, 45, 80] | CUDA | 7,200,000 |
| disps_up | [500, 360, 640] | CUDA | 460,800,000 |
| intrinsics | [500, 4] | CUDA | 8,000 |
| mono_disps | [500, 45, 80] | CUDA | 7,200,000 |
| mono_disps_up | [500, 360, 640] | CUDA | 460,800,000 |
| depth_scale | [500] | CUDA | 2,000 |
| depth_shift | [500] | CUDA | 2,000 |
| valid_depth_mask | [500, 360, 640] | CUDA | 115,200,000 |
| valid_depth_mask_small | [500, 45, 80] | CUDA | 1,800,000 |
| fmaps | [500, 1, 128, 45, 80] | CUDA | 460,800,000 |
| nets | [500, 128, 45, 80] | CUDA | 460,800,000 |
| inps | [500, 128, 45, 80] | CUDA | 460,800,000 |
| dino_feats | [500, 25, 45, 384] | CPU file-backed | 864,000,000 |
| dino_feats_resize | [500, 384, 45, 80] | CUDA | 2,764,800,000 |
| uncertainties | [500, 45, 80] | CUDA | 7,200,000 |
| affine_weights | [385] | CUDA | 1,540 |
| temp_y_cdot | [500, 45, 80] | CUDA | 7,200,000 |

合计 **7,468,230,540 bytes（6.9553 GiB）**。CUDA项需要写入快照，但不占/dev/shm。两块mmap合计2,246,400,000 bytes属于上述Video状态，写C0时仍会额外存在一份live backing，占用数据盘，必须同时计入。

完整C0还需要：graph/edge/correlation/hidden buffers、Tracker/MotionFilter/Frontend/Filler对象字段、model参数和buffer、RNG/observer/timer状态、源类pin、manifest、Torch ZIP头与padding等。按底层storage去重，view或重复对象引用不可重复计费。不能用checkpoint文件大小估计live model closure，后者可能包含额外状态。

## 精确实时算法

1. 在原writer barrier及Video锁下停止状态写入；保留真实闭包验证。
2. 现有ObjectEncoder枚举全部可注册对象和唯一storage；遇未知字段或非支持别名即STOP。
3. 对每个唯一storage使用当前安装版本的`torch.save`写入counting/hash sink，得到**精确archive逻辑bytes和SHA**，不创建临时archive。
4. 确定全部manifest字段与COMPLETE内容，计数其真实UTF-8字节。
5. 写盘前检查 `free >= round_each_file + 16MiB metadata reserve + 512MiB retained scratch + 10GiB floor`。
6. 每份tensor archive、manifest和COMPLETE实际保存前重新测量余量；tensor文件预分配实际块；实际大小和SHA必须与plan一致。
7. 如果状态在plan后变化、磁盘缩水或最终SHA不符，保留FAILED staging并STOP，不封存成功、不覆盖旧C0、不删除历史。

逻辑字节精确，filesystem物理overhead不声称精确；使用当前f_frsize向上取整及明确保守预留。动态其他进程写盘仍可能触发STOP，不能将预检当作独占容量保证。每块storage一次CPU副本/哈希产生RAM和I/O开销，未测真实闭包耗时或内存峰值。

## CPU实测预算闭环

合成fixture的3份storage archive总36,244 bytes；manifest2,286、COMPLETE86；合计**38,616 bytes**。实际逻辑总量也是38,616；实际块量53,248。不是NATIVE_C0。

测试覆盖serialize padding边界、完整storage而非仅view、alias去重、state变动、plan篡改、保存中磁盘缩水、每次写盘检查、floor边界、RNG不变。证据：`evidence/FINAL_ARTIFACTS/artifacts/EXACT_BUDGET_CPU_FIXTURE/`与最终测试报告。

## 当前空间可以说明什么

若只有一份live arena和一份C0，使用已知Video下限、10GiB floor、512MiB scratch与16MiB metadata后，剩余给未知闭包与其他新日志的理论上限约 **5.4769 GiB**，还要减实际archive头与文件系统开销。这不是完整C0可放下的证明。

若保留capture、restore-check及四个后续arm各自完整arena，共6份，光arena+C0的Video下限+10GiB floor就要 **29.5081 GiB**，已经高于当前可用25.0400 GiB，尚未含其他闭包和日志。即使只保留capture与四臂5份arena也不能直接宣布全阶段存储就绪。

因此必须逐阶段实测、分别预算；未来若需回收新产生的临时arena，应另有清晰生命周期和用户批准，或增加存储。**本候选不自动删除任何真实attempt或历史产物。** 不把单个CPU测试通过解释成B1/B2/B3/B4存储准入通过。

## 实现位置

`candidate/native_control/storage_budget.py`、`snapshot.py::prepare_state/save_prepared_state`；`binding.capture_c0`会保存`C0_EXACT_BUDGET_BEFORE_SAVE.json`。该实际NATIVE_C0路径本轮未执行。

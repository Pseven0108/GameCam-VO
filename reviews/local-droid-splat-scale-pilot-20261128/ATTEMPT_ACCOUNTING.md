# 全部Tracker尝试

共8次，4次纳入正式四组对照，2次失败，2次完整但尺度未激活。未把失败或未激活运行删除或替换成成功记录。

| Attempt | 状态 | 说明 |
|---|---|---|
| BASE_001 | FAILED_INITIALIZATION | Train Day001近静止；64帧仅1个关键帧。 |
| BASE_002 | FAILED_GPU_OOM | Day004初始化后factor-removal相关性复制OOM；随后统一改allocator。 |
| BASE_003 | PRIMARY_COMPLETE | 正式BASE。 |
| A5_001 | PRIMARY_COMPLETE | 正式A5，包含单状态端点核验。 |
| SCALE_001 | INACTIVE_COMPLETE | 1260条拟合全部单位回退，保留轨迹且单独评分。 |
| SCALE_A5_001 | INACTIVE_COMPLETE | 同上；不算有效尺度消融。 |
| SCALE_002 | PRIMARY_COMPLETE | V3源码门槛修正后561条拟合通过。 |
| SCALE_A5_002 | PRIMARY_COMPLETE | V3源码门槛修正后562条拟合通过。 |

Day001改窗与统一allocator修正发生在有效四组比较之前。源码V3修正发生在任何ATE/RPE比较评分之前，依据官方norm和全地图300像素门槛，不根据GT选参数。
旧版controller、runner及测试保留于 `candidate/evidence/controller_v2_noop`。V3 active运行另存runtime_source_snapshot。

未激活的SCALE_001 Sim3 ATE为1.107686，较BASE约-1.50%；SCALE_A5_001为0.763890，较A5约+0.605%。
这些是观察到的同类输入数值差异，**不是正式独立重复，也不是噪声置信界**，详见INACTIVE_CANDIDATE_ATTEMPTS.csv。
为审查保留common prior smoke、模型兼容和编译失败日志；这些不是额外完整轨迹比较。正式对照只有本表4次PRIMARY_COMPLETE。

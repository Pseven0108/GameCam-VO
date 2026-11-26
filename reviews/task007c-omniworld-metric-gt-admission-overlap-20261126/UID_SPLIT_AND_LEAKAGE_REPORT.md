# UID分组、防泄漏与实验独立性

本轮选样依据已封存Caption、场景差异和早期可提取帧；没有使用Metric3D预测误差选样。
3候选中只有2个可见第三人称玩家，不能凑成三份互不相交的严格TP Calibration/Dev/Evaluation。

`UID_DISJOINT_SPLIT_PROPOSAL.json`仅为待审批方案：

| 角色 | UID | 状态 |
|---|---|---|
| Calibration | 016d3596da27 | 待尺度准入，不拟合 |
| Development | 空 | 需要新且独立的第三人称UID；本轮不扩样 |
| Evaluation | 0caf78b8eeac | 暂保留候选角色；已做3帧准入观察，不称全新未观察测试 |
| 非TP诊断 | 03b9161e3ff2 | 不塞入严格TP开发组来凑数 |

同一UID的所有split、帧、双目或增强产物必须只属一组；官方Test Split不用于拟合。
此次所选split0不在3条Metadata的官方Test Split Index中。
未来最终评价应单独预注册未调参材料，当前9帧只记为准入观察。
禁止用测试集调sigmoid、isotonic、方差下限或模型选择。
9张RGB/Depth均无完全重复数组；这不证明不同UID一定没有相同游戏、关卡、轨迹或预训练来源。
未来还需场景/游戏来源去重，不能把“UID字符串不同”当作独立场景证书。

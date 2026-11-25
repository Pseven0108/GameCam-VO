# gamma_depth 配置差异闭合

结论：**CONFIRMED：本研究的封存有效值是 0.01；官方基础默认值 0.001 不是本研究运行值。** 无需修改任何原配置。

|来源|gamma_depth|证据等级|
|---|---:|---|
|官方 c3414 的 `configs/droid_w.yaml`|0.001|CONFIRMED_STATIC_BASE_DEFAULT|
|官方 `configs/Dynamic/YouTube/youtube.yaml`|0.01|CONFIRMED_STATIC_SCENE_OVERRIDE|
|官方 `configs/Dynamic/DROIDW/droidw.yaml`|0.01|CONFIRMED_STATIC_SCENE_OVERRIDE|
|匹配 R2 val_007 的实际 `native_config.yaml`|0.01|CONFIRMED_SEALED_RUNTIME_CONFIG|
|Task004B `r2_sealed_config.yaml`|0.01|CONFIRMED_SEALED_RUNTIME_CONFIG|
|Task004B Seed44 E0 的 `native_config.yaml`|0.01|CONFIRMED_SEALED_RUNTIME_CONFIG|
|Task005B-R3 `INPUT_IDENTITY.json` 的真实 BA 实参|0.01|CONFIRMED_RECORDED_CALL_ARGUMENT|

R2 原始 `native_config.yaml` 和 Task004B 封存配置逐字节相同，均为 3371 bytes，SHA-256：

`a213d74874ad953000dde6b7506694b369fad9b2eaccaff58f063accdfbb50fc`

该值又与 Task005B 历史 `FROZEN_IDENTITY_AFTER_STOP_PUBLIC.json` 的运行保护 pin 一致。所有来源文件及逐文件 SHA 见 `CONFIG_EVIDENCE.csv` 和 `evidence/GAMMA_DEPTH_EVIDENCE.json`。

R3 真实调用还记录：`iterations=2`、`lm=0.0001`、`ep=0.1`、`gamma_data=0.1`、`gamma_prior=0.05`、`gamma_depth=0.01`、`lr=0.1`、`weight_decay=0.002`、`enable_update_uncer=True`、`enable_udba=True`、`enable_affine_transform=True`、`enable_bidirectional_uncer=False`。这是 D0_S1_RGB233 单一封存状态的调用记录，不能概括所有 BA 阶段的参数。

E0/R2 静态协议包括 `buffer=500`、`stride=1`、640×360、`metric3d_vit_large`、DINO fine 特征、W/U 开启、online BA 关闭、Final BA 开启。R2 的种子与 Task004B 各组种子不同，不能因 gamma 相同就把配置整体视为完全相同；本报告只对对应字段及封存身份作结论。

后续 R1 数学原型的 alpha 应使用 `0.01`。是否将新的 CADP 应用到更广范围、如何选择 k/tau，均不是本轮审计结论。不得用基础 YAML 的 `0.001` 覆盖历史运行记录，也不得为了端点测试改 gamma 或 U/W。

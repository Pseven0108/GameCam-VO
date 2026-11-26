# 独立 Pi3.forward 接口

输入：RGB float32 [B,N,3,H,W]，0–1，不重复ImageNet归一化。当前B=1，N=3或5，H=378，W=672。

| 输出 | 原生形状 | 本次保存 |
|---|---|---|
| dynamic_masks | [1,N,1,H,W,1] | float32最后帧模型网格与原图网格概率 |
| conf | [1,N,H,W,1] | float32最后帧；不是DROID-W U |
| local_points | [1,N,H,W,3] | float32最后帧及z辅助深度 |
| camera_poses | [1,N,4,4] | 最后帧；不拼接为正式相机轨迹 |
| points / dynamic_logits | 见真实接口收据 | 检查有限性；未作为后续DROID输入 |

模型在BF16 autocast下计算，但原始参数与最终返回张量为float32；实际收据见evidence/MODEL_INTERFACE_RECEIPT.json。规范化动态输出：dynamic_masks[0,:,0,:,:,0]。不再次sigmoid，不转换成U，不推导米制尺度。

每个目标NPZ包括 dynamic_probability_model、dynamic_probability_original、confidence_model、depth_model、local_points_last、camera_pose_last、context_rgb_ids、target_rgb_id；原始连续值不由8bit图像重建。

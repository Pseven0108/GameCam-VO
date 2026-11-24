# GameCam-VO

游戏渲染场景视觉SLAM研究。当前主线为VIPER、DROID-W、stride=1，研究深度先验、不确定性和优化/关键帧选择之间的关系。

## 当前最新评审

- [GPU C0 R2最终报告](reviews/task004c-b-gpu-c0-r2-20261124/FINAL_REVIEW.md)
- [全部17个阶段的评审索引](REVIEW_INDEX.md)
- [当前状态和授权边界](PROJECT_STATUS.md)
- [源码身份](source/SOURCE_PROVENANCE.json)
- [当前DROID-W源码](source/DROID-W/README.md)
- [ChatGPT阅读说明](REVIEWING.md)

## 最新实际结果 · 2026-11-24

首帧修复通过：真实Loader测试21/21、历史回归最终152/152，真实RGB001～018 CPU连续校验通过。运行源码只修改NativeViperRGB。

唯一一次GPU运行完成18帧、第一阶段16次和第二阶段8次graph.update、24次native BA调用，并在当前帧收尾后进入C0 callback。

**完整C0仍未生成。** 保存前的state_inventory在Metric3D LoRALinear.lora_dropout函数对象处失败，序列化器没有放行未知函数。没有自动重跑，没有恢复、S0/S1、跨D或正式四臂。完整C0大小未知，47族未持久化。

运行源码：`02f8c8308274489ff7eff83fa9b87b98db74122e` ← `668a88c74c7f7a88a572679d2bd8e86c0a05514b` ← `0931141cf88247dc8fb0c7628c1d91b6531fea90`。GitHub发布提交只用于评审，不冒充运行提交。

## 材料范围

最新评审包完整展开，Markdown、CSV、JSON、日志和补丁可直接阅读。历史阶段按各自出版清单保留，所有原始报告不覆盖。数据集、模型权重、Arena及大型运行二进制保留在原工作区/服务器，身份和SHA随报告记录。

上游版权与许可证见source/DROID-W及thirdparty目录。当前仓库为公开状态；本次发布没有修改仓库可见性。

# 完整评审包说明

入口：FINAL_REVIEW.md。

- 官方VIPER GT渠道审查、local train_dense补充、替代数据选择、MVS尺度不变数学边界、划分JSON及下一阶段门禁。
- 所有发现的归档路径/类型/检查状态，471个ZIP中央目录结果、20个VIPER相关ZIP、3份dense目录、TAR有界补查。
- 官方源码/许可及Blob来源、公开页面访问摘要、HEAD字节数/身份、原始官方MD5文本。
- 内容识别与尺度不变原型、18项合成软件测试代码/日志、保护与安全记录。
- 四个统一项目根入口的字节副本和更新计划；全包SHA清单。

不分发原始RGB、GT、模型权重、C0、GPU中间状态或历史巨大数据包。
只有元数据读取和软件验证，因此没有被遗漏的本轮真实推理输出。
全包SHA覆盖ZIP所有成员，清单自身除外；ZIP整体SHA与CRC在外层deliveries/PACKAGE_VERIFICATION.json，避免自引用。
发布后完整匿名回读及只删除本轮本地ZIP的记录位于maintenance/GITHUB_TASK007B_PUBLICATION_20261126。

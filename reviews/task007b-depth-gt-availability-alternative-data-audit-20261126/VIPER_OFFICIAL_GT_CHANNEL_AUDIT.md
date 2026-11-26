# VIPER Monodepth：官方GT渠道审查

结论：**当前没有找到可为本项目10个VIPER预测帧准入的公开配对深度GT获取渠道。**
这是已检查渠道的结论，不能写成官方从未生成深度或任何条件下都不可能提供GT。

| 证据 | 直接支持 | 不支持 |
|---|---|---|
| 官方工具README，固定Commit 2f1d391 | 列出RGB、camera、segmentation、boxes、flow | 未列depth不等于证明它永远不存在 |
| 官方prepare_submission.py | 将用户预测PFM编码为测试提交；没有GT下载步骤 | PFM提交格式不能证明Validation GT公开 |
| 官方Monodepth网页 | 存在在线深度任务及汇总指标 | 不是逐像素残差或校准标签接口 |
| RVC 2022深度devkit说明 | 此任务的VIPER不供应training data，仍要求test predictions | 不否认VIPER其他任务有Train/Validation数据 |
| 当前匿名download页 | HTTP200，许可条款表单；本轮未提交表单 | 未取得当前完整下载清单，不能把门前页当完整模态清单 |
| 本地历史完整download index | 当时RGB稠密采样、camera、flow等产品说明 | 不能代替当前服务端产品认证 |

已核对官方Issues中的深度提交问题#9/#12，其内容涉及编码/服务端评价失败，没有建立训练或验证集深度GT下载渠道。
本轮未联系作者、未注册或提交预测、未绕过下载表单。

## 可行渠道与当前决定

在线测试评测渠道已确认存在，但不能拿Test排行榜反复选择Confidence参数，也不能据汇总分数重建像素级GT。
若未来提供官方授权GT、公开发行的depth产品及清晰单位/有效性规范，可重新审查；本轮没有取得这种证据。
因此**VIPER继续承担原有VO主线，像素Confidence校准维持NO-GO**。没有变更VIPER数据划分、测试窗口或已有评测协议。

来源：

- [VIPER官方README](https://github.com/srrichter/viper/blob/2f1d3918473e4e7785d420bf43b9a1895a5c6450/README.md)
- [VIPER深度提交代码](https://github.com/srrichter/viper/blob/2f1d3918473e4e7785d420bf43b9a1895a5c6450/prepare_submission.py)
- [RVC官方深度devkit](https://github.com/ozendelait/rvc_devkit/blob/9ea8963069be7ff8ef6768ebfc141099e111a10d/depth/README.md)
- [官方Monodepth任务](https://playing-for-benchmarks.org/leaderboards/monodepth/) · [当前下载入口](https://playing-for-benchmarks.org/download/)

本轮访问状态、公开文本SHA、官方代码Blob身份见 `sources/`；没有保存许可表单的CSRF值。

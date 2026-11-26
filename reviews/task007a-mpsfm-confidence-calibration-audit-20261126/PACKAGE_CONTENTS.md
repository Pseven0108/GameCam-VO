# 完整评审包内容

入口：FINAL_REVIEW.md。结论为GT准入阻断，未开展统计校准。

- `data_audit/`：10帧真实Confidence完整性/分布、16归档中央目录清单、44个散落候选及逐项分类。
- `metrics/`：五环境校准/NLL/覆盖率未计算状态，null不是0。
- `sources/`：固定Commit的MP-SfM原始源码、配置、Apache LICENSE及来源。
- `code/`：只读缓存准入脚本、独立未拟合方差映射、打包/验证脚本。
- `tests/`、`logs/`：22项合成软件测试及真实执行报告，审计脚本先前三次停止记录。
- `evidence/`：74项已读取输入身份、源码Blob身份、最终保护核验、CPU执行收据。
- 统计评价合同、Scalix必要性判断、最小GT要求、完整执行日志、安全记录及全包SHA清单。

没有新GPU输出，因此没有应收录而遗漏的本轮预测数组。
不重新分发原始RGB、深度GT、模型权重或历史数百MB输入包；依赖的封存数组由SHA和路径精确指向：

- [R2.1完整历史评审](https://github.com/Pseven0108/GameCam-VO/tree/9e8e1f609796ed78a0a27b942d3d7440bcf23d72/reviews/task006a-r2-1-metric3d-gpu-pilot-20261126)
- [R2.2完整历史评审](https://github.com/Pseven0108/GameCam-VO/tree/536ad7c253b4febd182bbc8c3805476a2f83e54b/reviews/task006a-r2-2-depth-restoration-gt-audit-20261126)

SHA清单覆盖全部ZIP成员（清单自身除外）；ZIP整体SHA及CRC记录位于外层`deliveries/PACKAGE_VERIFICATION.json`，避免自引用。
发布后回读和仅删除本轮本地ZIP的收据保存在独立maintenance目录，不倒改封存ZIP。

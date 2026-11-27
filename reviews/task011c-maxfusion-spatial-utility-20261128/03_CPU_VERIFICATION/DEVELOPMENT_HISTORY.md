# 保留的工程失败与修复

1. 首轮 ZIP 中央目录去重将公共 directory entries 算作重复图像。修正为仅比较
   非目录、扩展名为 .jpg 的文件成员。首轮未完成输出仍保留在本地 data_audit；
   最终 data_audit_final 为新目录，没有覆盖历史源数据。
2. 首轮完整回归中，原测试读取的历史 NATIVE_REGRESSION_FORMAL_REAL_FIRST_LOCAL.json
   不在父提交顶层 task 目录，只在同提交展开评审里。恢复原始字节，不改测试，
   第二轮 122 项全部通过。results_001 的 stdout/stderr 与 JSON 均包含于本包。

这些修复不改变 A5、BA 或数据选择规则。

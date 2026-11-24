# CPU回归

最终候选：152/152 PASS；118历史用例+34既有Release Fix用例；failures0、errors0；37.895秒；CUDA未初始化。

原测试与断言未修改。每项输入、seed43、预期、实际、stdout、stderr、退出码和SHA见raw_evidence/artifacts/RELEASE_CPU_AUTONOMOUS_R2/CPU_TEST_REPORT.json。

第一轮候选也为152/152；第二轮后再次完整运行。两次通过不计为304个独立新科学实验。

这些测试不构造预训练模型，因此不能用它们覆盖真实模型恢复的ConfigDict失败。真实模型CPU测试单独记录为FAIL。

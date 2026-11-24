# 新进程恢复与RGB019失败

状态：**真实状态恢复PASS / 阶段续跑FAIL**。

源PID 5490；新PID 5676。18,143节点、全部Tensor/对象/alias/属性重编码匹配；下一输入身份匹配；RNG最后恢复。C0 hash `18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92`。

下一输入=RGB019，index18；RGB/SHA/K由不可变C0记录。此报告没有宣称已经重新执行恢复后Metric3D GPU forward；新的RGB019推理未开始。

真实原生阶段退出码1，耗时285.193267s。错误为 `FileExistsError`：实际SummaryWriter先创建out/native，rebind后tracker.output相同，随后mkdir(exist_ok=False)拒绝重复创建。错误发生在viewer.start()及tracker.run()之前。native_trace和observer均为空，SUCCESS不存在。

CPU独立诊断使用实际安装SummaryWriter，精确重现相同路径行为；它的退出码0表示“预期故障被复现”，并不表示续跑修复成功。没有应用修复、没有自动重试、没有修改C0或源码。

原始traceback：`raw_evidence/attempts/restore_check/process.stderr.txt`；对象恢复收据：同目录RESTORE_RECEIPT.json；CPU诊断：`raw_evidence/cpu_tests/DIRECTORY_LIFECYCLE_DIAGNOSTIC_R1/`。

# Formal487 运行器能力

状态：IMPLEMENTED_AND_CPU_MOCKED / NATIVE_GPU_UNVERIFIED。

矩阵与顺序：B1(D1自然S1) → B2(D0重放S1) → B4(D0自然S0) → B3(D1重放S0)。W=U=1；INIT_D=0；原始R2模型、seed43、buffer500、640×360、stride1。D只作用于规定前端Local BA；Final BA/Filler保留原生作用范围。

候选代码将真实 Tracker 状态恢复后运行至RGB487，记录前端关键帧快照，调用原生 SLAM.backend() 与 SLAM.terminate()，保存最终BA关键帧及Filler全487帧。Final BA原生外层7/12迭代；Filler独立seen计数。CPU AST driver mocks模拟这些调用及输出路径。

CPU Mock并未执行原生CUDA、真实Final BA或Filler。实际RGB019续跑已在目录生命周期失败；正式四组为0/4。完整487导出、原生Filler、真实调度兼容性和统一离线指标尚未验收。不得称正式runner已通过GPU验证。

已知文档问题：native_driver.py开头旧bounded-only说明未同步到新增formal模式；以函数实现和实测状态为准，本轮停止后未修改源码。

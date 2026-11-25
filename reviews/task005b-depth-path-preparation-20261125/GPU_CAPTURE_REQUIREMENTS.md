# 完整BA输入与存储要求

每个native调用前捕获13个实参Tensor：poses、disps、intrinsics、selected_prior、targets、weights、uncertainties、temp_y_cdot、dino_feats_resize、affine_weights、eta、ii、jj。同时另存真实cached_mono_disps；D0的selected_prior全零并不代表真实mono不存在。保存所有17个标量：t0/t1/iterations/lm/ep/gamma_data/gamma_prior/gamma_depth/lr/weight_decay/motion_only/depth_only/enable_update_uncer/enable_udba/enable_affine_transform/enable_bidirectional_uncer/debug。

附带active_count、slot↔RGB、调度前缀SHA、native调用编号与阶段、source/config/extension pins、真实RNG状态及原始输出。每Tensor记录shape、dtype、stride、storage_offset、device、全部字节SHA以及storage alias关系。反序列化后重算；有alias时必须保留，禁止逐Tensor clone后仍声称alias一致。

原生求解器新增trace每轮22项：poses/disps/U before，C_geometry/w_geometry，C/w/Q/E/kx，A/v、Schur扣除矩阵及右端、H/rhs/L、dx/dz、poses/disps/U after。还要保留不可变full target/weight/K/图/先验，才能计算完整像素残差，不把旧observer采样当full objective。

当前磁盘只有约3.498GiB超过10GiB安全余量；本地C盘接收空间约19.66GiB，D盘约5.90GiB，均为本轮检查时快照。完整DINO resize缓冲单独为2,764,800,000 bytes；其他输入、trace、模块编译产物和临时归档也需计算。真实总量UNKNOWN。

复用已封存C0只读文件；不再次复制整套C0或模型。采集前按唯一storage精确计数，写入前检查最坏原始空间，压缩是后续优化，不拿预计压缩比准入。保存一次、传本地、SHA验证、ZIP/归档CRC验证，再决定本轮临时输出的生命周期；不删除任何旧产物。当前没有执行删除、移动或新的数据传输。

若空间不足，提交该次实际storage字节数和最小扩容/转存方案。不要为通过门槛降低buffer、精度、分辨率或丢弃必须的输入。

# C0共同检查点规范 V1

配套 TASK004C_B_COMMON_CHECKPOINT_MANIFEST.json 是设计模板，status=NOT_CAPTURED、complete=false，所有实际hash为null。本次没有生成真正的C0。47个张量/张量族条目加上模型buffer与RNG，不能仅凭清单长度声称完整。

## 唯一状态与边界不变量

只生成一份INIT_D=0的C0，再只读恢复到四个独立进程。满足：warmup=12、frontend.is_initialized=true、两阶段初始化完成、本帧收尾完成、主循环local BA尚未发生、没有正在执行的原生kernel、next_input尚未读取。候选位置RGB018之后，但必须以真实语义边界验证。四臂均记录相同C0内容摘要和原始输入流身份。

共同初始化仍预测Metric3D、FiT3D/DINO并保留mono_disps；D=0指原生BA的prior输入切换至zeros，同时走原生eta路径，不指禁止深度模型。配置原文保持不变。初始化所有BA的D选择需要新的独立参数路由；旧Task004B授权/runner不可借用为新实验许可。

## 必须保存的对象闭包

| 持有者 | 必须保存或核验的状态 |
|---|---|
| DepthVideo | timestamp、images、dirty、npc_dirty、poses、disps、zeros、disps_up、intrinsics、mono_disps/up、depth_scale/shift、valid_depth_mask/small、fmaps、nets、inps、dino_feats、dino_feats_resize、uncertainties、affine_weights、temp_y_cdot、counter、slice/down_scale、有效开关。 |
| Frontend | t1、is_initialized、num_keyframes_dropped、iters1/2、warmup、阈值/窗口/边上限、last_pose/disp/time、last_loop_t是否存在；初始化边清理完成状态。 |
| Frontend.graph | ii/jj/age的精确顺序，active/inactive/bad pools，target/weight及inactive副本，net/inp/damping、coords0、CorrBlock四层金字塔及num_levels/radius，边实例与RGB/插槽映射。 |
| MotionFilter | 最近通过motion admission的net/inp/fmap、count、MEAN/STDV、阈值、Metric3D/feature extractor对象状态及绑定；它可能不是最近保留关键帧。 |
| Tracker及循环栈 | prev_kf_counter、finish_first_online_ba、ba_freq等；run里的prev_kf_idx/curr_kf_idx/prev_ba_idx、i/timestamp/starting_count、已处理与下一RGB/输入index。函数局部变量不会自动进入state_dict。 |
| Stream/runner | ids、seen、fill_seen、phase、peak、输入/预处理身份，RGB累计流摘要的可验证前缀。hashlib对象不应未经设计地pickle；用已确认的前缀内容摘要和独立后缀摘要/最终全流重算验证。 |
| 网络与模型 | DROID/Metric3D/FiT3D/DINO的所有parameters、buffers、eval/train模式、dtype/autocast、运行时可变属性。完全只读的权重可按不可变文件引用去重，但必须核验实际加载后的tensor身份和别名。不能只有权重文件hash而漏掉运行时buffer。 |
| 其他对象 | frontend.loop_closing、tracker.online_ba、slam.ba配置/计数（R2在线/loop关闭）；Filler的模型绑定和初始化阶段；打印器、观测器、计时器和输出身份。 |

没有持久化“独立UBA权重缓存”不代表漏项：原生W由当前U和weight计算。保存其输入和算子/flags，若运行时发现持久缓存则必须纳入；不能从上一臂复制最终有效权重。eta是graph.damping按source支持派生的临时BA实参：C0应保存damping与计算规则；若边界有活跃临时eta则不允许保存，先退回静止边界。

## 每个张量及存储

实际manifest必须有name、dtype、shape、stride、layout、device、contiguous、storage_offset、storage_id、requires_grad、共享标志、逻辑值SHA256、底层存储字节SHA256、文件SHA256和大小。逻辑hash按固定小端、C顺序定义并绑定元数据；底层存储hash覆盖真实storage，以保留stride/view/别名。不同字段共享storage时恢复同一底层storage和view，不能全部clone成互不相关张量。审计是否允许的写时别名变化需要单独证明。

buffer仍为500。保存有效行、下一预测槽位和全部曾写过的scratch/tail；不把只存12行当成完整500行状态。允许无损分块、默认值游程和内容去重，但只有逐块证明与构造器默认字节完全相同才可省略存储。非默认尾块必须保留；恢复后完整逻辑tensor逐位hash一致。未初始化storage间隙应按存储原样保存，不能静默置零。

## 随机状态与数学环境

在真正tracking子进程捕获Python完整state、NumPy完整state、torch CPU RNG字节、所有CUDA设备RNG字节及显式Generator；记录PyTorch/CUDA/cuDNN/驱动、扩展文件SHA、TF32、deterministic flags、benchmark、线程数、autocast/grad mode。原生setup_seed设置deterministic=true、benchmark=false，保持实际值，不因协议另加设置。历史子进程seed收据只有摘要，不足以恢复。

网络构造/权重加载/进程spawn可能消耗随机数。未来恢复顺序必须为：构造对象并绑定模型 → 安装全部tensor/storage/标量 → 重建非数学OS资源 → 校验 → 最后恢复实际tracking RNG → 立即按游标继续。不能最后再setup_seed(43)覆盖C0的前进后RNG状态。哈希、写日志、checkpoint ID生成不得消耗研究RNG。

## 原子保存与恢复事务

1. 仅由tracking所有者停在语义边界；确认无pending BA/网络调用。与Rerun writer握手，排空/隔离通知，保存dirty及进程语义状态。mapping必须保持关闭。
2. 同步所有相关CUDA stream，等待native操作完成。逐storage流式拷到CPU小块，不额外clone整个GPU状态。记录设备/形状/stride/alias，写唯一C0.incomplete目录；不覆盖任何旧C0。
3. fsync每个payload和manifest；重读逐项hash并核验对象闭包、RNG、图引用和next cursor。全部满足才生成COMPLETE marker，按同文件系统原子发布新目录；内容摘要不包含会变化的PID、输出目录和时间戳。
4. 恢复只读读取COMPLETE版本；为每个B臂建立独立目标。不能通过共享可写C0 tensor污染其他臂；只读模型参数可共享，优化状态不可跨臂共享。
5. 进程句柄、socket、锁、pipe和Event不能作为checkpoint持久值恢复。重新构造并验证“已过启动屏障、无待处理计算、可视化只观察”的语义。当前runner无暂停/恢复entry，需要未来独立harness；不能直接pickle整套SLAM对象。
6. 故障回滚指恢复事务失败时不发布COMPLETE、不启动后续计算，保留不完整输出并停止；不是自动重试，也不是抹去失败现场或回滚C0。

## 完整性判定

“字段可设计保存”与“已验证恢复”分开。必须由未来运行时属性白名单扫描列出实际所有对象/模型buffer/显式Generator，任何未知可变项使complete=false。需要原生CUDA状态往返、同C0两次独立恢复和同D短重放的数值一致性验证。本轮只完成源码清点和规范，未执行上述验证。现有RGB328原生调用输入不含网络/关联缓存/循环局部状态，禁止升级标记为C0。

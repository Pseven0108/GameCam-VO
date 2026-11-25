# R2-7 梯度候选：DEFERRED

没有执行 backward 或训练。A/B/C 尚无真实 GT 评价，不能将“未执行”解释成“三者已失败”，
因此没有满足用户规定的梯度备用方法启动前提。
已读 GrUMoDepth 方法、实验、局限及官方入口；其固定模型辅助预测 loss 的特征梯度可无需微调提取，
但 Metric3D 的 inference 包含 no_grad，不能直接在该入口得到梯度。
未来若需要，应在独立脚本里走明确可微的 forward、冻结参数更新、只取指定特征梯度，
保持生产模型 eval、禁止 optimizer.step，并测真实显存。这里不修改模型、不执行该候选。
原论文 Monodepth2 的层选择、通道归约和热图归一化不能直接当作 Metric3D 的最优规则。

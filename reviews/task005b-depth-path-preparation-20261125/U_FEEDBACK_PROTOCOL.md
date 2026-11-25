# U反馈的时间顺序

原生循环先生成geometry→solve→pose/disparity retraction，再执行U更新。因而在相同完整初始状态下，第一轮允许/禁止U更新不应改变第一轮dx/dz；这里只可能有原生浮点非确定性，需逐项检查。

第二轮固定U组使用旧U，更新U组使用上一轮产生的新U；目标/原始weight/eta/图不重新由网络产生。两轮必须保留在同一个ba调用里；其J_linear等scratch缓冲并不是每次独立调用都相同的生命周期。把两次独立1-iteration调用等同于一次2-iteration调用没有源码依据。

记录U、affine_weights、temp_y_cdot的更新，以及实际源端乘子，不因开关相同就说权重相同。第一轮各C/G组的U_after可以不同，它通过第二轮参与反馈。固定初态的第二轮差异是本地U反馈效应，不等于网络target/eta等完整前端反馈。

残差需同时报告冻结before权重和更新后的实际权重；减小自适应加权损失不能单独证明几何更准。

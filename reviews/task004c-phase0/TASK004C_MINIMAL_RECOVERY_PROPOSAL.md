# 最小恢复方案（待批准，未执行）

优先只恢复A需要的状态：两条前缀，各读RGB1–328，沿原E0与E1策略运行，W=U=1，在RGB328第一个满足312/328有效窗口和双向直接边的predecision BA入口前暂停并保存完整输入。最多656次RGB输入处理，不执行Final BA或Filler，不生成完整487帧成绩。BA编号由新运行实际记录，不能硬称复现历史550/660。新捕获状态使用新ID，不能声称恢复了历史逐位状态。

## 隔离改动清单

1. 在新Task004C源码副本中加入完整checkpoint writer，唯一捕获点为原生BA入口前；原始R2 YAML、权重、扩展不改。
2. 保存 poses/disps/intrinsics/mono_disps/zeros/U/temp_y_cdot/dino_feats_resize/affine_weights/target/weight/eta/ii/jj 全量张量、dtype、shape、layout、RGB-slot映射和全部标量。
3. 若需要连续三个外层图更新重放，额外保存graph corr/net/inp、active/inactive/bad边、age、damping、target/weight缓存及RNG；单次native BA不需要重新执行神经前端。不得在两分支之间注入历史后续target来冒充在线演化。
4. 克隆每个状态为D=1和D=0独立副本，核对所有共同输入逐张量SHA；W=U=1；只切换prior/zeros输入。native-after与clamp-after分开。
5. 首次捕获不满足完整性立即停止，不自动重试。

## 时间与空间依据

历史E0/E1从tracking_start到RGB328分别为101.973s和105.553s，合计207.526s；不包括新进程模型启动、完整快照拷贝/写盘和审核开销，因此不能承诺新运行只需这些时间。

四次BA本体的历史观测包络约每次0.025s，但重新装载GPU输入和U更新输出也有成本，完整重放总时长UNKNOWN。

按完整buffer500、45×80、384维DINO和源码预期float32/int64估算，两份native输入原始payload合计5,628,821,864 bytes（5.242 GiB）。该数不含完整前端corr/hidden、分支输出、压缩临时副本和Rerun。已有可用20.473 GiB，扣两输入和10GiB安全线，剩约5.231 GiB；完整B的磁盘预算仍未闭合，不承诺可同时留存全部4臂。逐阶段空间预算重新实测，禁止自动删除历史结果。

## B的后续最小要求

需要一次共同RGB1–18初始化的真实完整检查点，再为四臂恢复相同字节状态，处理RGB19–487，并强制S1/S0所有插入/删除/cache/edge/window/BA顺序。四臂完整轨迹指标本身要求处理全序列剩余部分，无法靠四次BA替代。若现有边界日志不足以无歧义恢复所有mutation，须先授权新的S1/S0调度捕获，不能凭最终关键帧ID补造。

建议先批准两条328帧前缀及四次BA配对重放；A证据通过后再审B完整调度恢复和具体预算。当前审批包未执行任何新GPU计算，也未授权自动扩大工作量。GPU继续在线等待决定。

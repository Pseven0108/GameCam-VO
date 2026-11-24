# Task004C-B：共同C0四组受控交叉实验完整评审

状态：COMPLETE_WITH_LIMITATIONS。四组真实GPU实验完成，等待科研评审。

四组均exit0，完成原生Final BA、Trajectory Filler与487行最终轨迹。从同一个真实GPU C0恢复，每组实际新处理RGB019–487共469帧；RGB001–018属于共同初始化，不重新采集C0。执行顺序B1→B2→B4→B3。未运行DROID-SLAM、训练或追加消融。

## 主要结果

| Arm | D | Schedule | KF | Sim3 ATE（游戏单位） | 全局拟合scale | RGB312→328位移比例 | Runtime s |
|---|---:|---|---:|---:|---:|---:|---:|
| B1 | 1 | S1 | 127 | 17.469482 | 4.177532 | 63.0378% | 994.844 |
| B2 | 0 | S1 | 127 | 8.680145 | 62.586212 | 96.5903% | 1018.362 |
| B4 | 0 | S0 | 86 | 83.255019 | 3471.171519 | 30.7923% | 956.730 |
| B3 | 1 | S0 | 86 | 66.501751 | 6.901193 | 33.6124% | 963.402 |

ATE使用最终全部487帧与GT的一次全局Sim3；端点位移比例使用同一次全局拟合，不按路段重拟合。长度保持VIPER游戏单位，不能自动写成米；scale是GT拟合因子，不是系统自主恢复的物理尺度。GT仅在本地CPU离线评分使用。

核心判断：D的作用依赖离散调度路径。在固定S1下关闭D更好；在固定S0下开启D更好。D_on−off的ATE差在S1为8.789337，S0为-16.753268，方向相反。不能概括成“关闭深度正则普遍改善”。应研究深度约束与关键帧、拓扑及BA调度的条件关系。

## 身份和干预合同

- val_007、seed43、stride1、640×360、buffer500、INIT_D=0。
- 冻结控制候选commit：5d357c1d3079de134dd8b41a20a00632da37f0b0；tree：c018a65009aaf4f7457e2da5225a5f322a168b77。它是原生控制接入候选，不冒充无控制代码的上游原版。
- C0 SHA256：18ab8ceff97339eded44af2e716cb6c43c8d5679a212a8183f84751fce9fad92；真实初始化边界RGB018，counter12。
- B1=D1自然S1 producer；B2=D0回放S1；B4=D0自然S0 producer；B3=D1回放S0。
- 仅干预Frontend main-loop Local BA的D。W/U、Final BA、Filler保留原协议；不改优化公式、原始权重、R2 YAML或CUDA扩展。

固定的是插入/删除、拓扑和BA的离散调度，连续Pose、Disparity和对应关系各自演化。这是固定离散调度下整段条件效果，不是相同Tensor输入的一次BA纯直接效应，也不是原始E0从零运行。

## 控制和阶段证据

COMPLETED_STAGE_CONTROL_AUDIT.json核验9个成功阶段，无缺失：恢复检查1个、短程控制4个、正式arm4个。各新进程恢复18,143个对象节点，Tensor、alias、RNG及下一帧身份匹配。

S1两组8,395个离散事件逐项一致，S0两组8,233个逐项一致，包含context/payload。自C0后S1各1,230次BA三联日志、S0各1,148次；其中Local BA D/W/U实参分别核验839和757次。进程累计计数还包含C0继承的24次BA，不能混用。每对连续状态Pose哈希均有差异，不是复制producer连续解。

S1有127个KF，S0有86个KF。调度组内KF数相同是控制结果，不证明D不影响自然KF选择。S1中312与328均为保留KF；S0中312保留、328不保留。因此S0有固定RGB最终指标，但直接KF312→328必须保持ENDPOINT_UNAVAILABLE，没有插值补造。S0的最终328由Filler生成。

原生full_traj_fill计算全帧，并在保留KF时间戳使用最终KF Pose覆盖。四组KF/导出一致性符合float32与六位文本输出精度，不是bit-exact。Frontend与Post-Final-BA各自在该阶段全部保留KF上做一次全局Sim3；不直接跨阶段比较原始长度规范。487帧ATE与KF子集ATE采样不同，差值不能全部归因于Filler。

## 限制、测试和资产保护

单序列、单seed、每格n=1；没有p值或置信区间，不支持跨环境泛化。S1/S0是producer形成的内生路径，不是随机化外生调度；D×S差分仅描述这两条路径。共同INIT_D=0与原始R2/E0不同，不能直接合并成绩。继承S_REF=19.1341794347仅为历史GT拟合诊断，不是本C0的物理标定。

BA_MECHANISM_TIMELINE.csv与BA_STAGE_DIAGNOSTIC_SUMMARY.csv保留native-after负disparity采样、clamp-after网格floor、U分位数及有效权重。负值采样不是全网格负像素总数；网格floor不是本次新增clamp数。

最终身份核验：候选与原目录各3745文件均匹配；6个保护资产、8个运行库/配置资产和852个C0存储文件均匹配；两个源码工作区clean。详见FINAL_ASSET_PRESERVATION.json。

CPU评价13/13自检通过，控制审计及最终评价exit0。两次CPU输出失败分别为NumPy float32 JSON序列化与缺少Matplotlib，完整收据/日志保留。修复仅为数值输出与本机独立画图库，不重跑模型或改变指标公式。

早期R2-B1在Filler离线torch.hub解析处失败，现场保留，不计成功arm，不视为算法精度失败。R3使用冻结cached_priors注册离线模型类后完成四组，完整执行次数可追溯。

## 存储偏离与清理

存储协议不能标为全程PASS。5秒目标采样共999条，其中53条低于10GiB，最低8.636204GiB。3段偏离的采样近似时长与原始timeline均保留。完成时数据盘13.497543GiB。全部结果下载验证无损坏，不抹去门槛偏离。

14个闲置安装归档共2,134,549,899bytes已下载本地，14/14成员SHA一致，确认无活动FD/maps及身份匹配后删除远端缓存，约1.988GiB。它们此前已转至系统盘，所以最后删除主要释放系统盘，不能说数据盘直接增加1.988GiB。安装库、权重、RGB、C0和历史科研结果未删除。

## 发布与关机

ZIP包含报告、控制源码、配置、完整文本日志（大JSONL无损gzip分块）、轨迹、评价表、测试和SHA。RGB/GT数组、模型权重、完整C0/Arena、RRD和含RGB的video.npz二进制保留本地，公开SHA/大小及必要数组清单，不声称这些二进制均上传GitHub。

原生Rerun记录保留；没有本轮浏览器渲染验收。用户授权归档与GitHub发布核验后终端shutdown。本ZIP封存时尚未关机，实际命令返回和连接观察单独补充回执。

结论：完成共同初始化下的D×离散调度机制实验，得到方向相反的条件效果；尚未证明普遍有效的修复。本轮结束，不自动新增seed、场景、训练或Improved DROID-W。

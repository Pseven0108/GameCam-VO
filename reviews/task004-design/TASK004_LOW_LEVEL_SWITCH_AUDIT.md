# Task 004｜低层开关审计

**结论：三项都能在指定调用单独控制。** 确认层级是锁定源码和 CPU Mock；本轮未加载原生 CUDA 扩展，实际 GPU 时序与内核数值尚未验证。

源码引用以 Task001 核验的冻结快照 DROID-SLAM-to-DROID-W 取证目录中的 sources/DROID-W 为根，commit c3414af6047d06bafc1a6645d09f23247f3b2cdc。相对行号指未打补丁的文件；记录见 [源码身份](evidence/SOURCE_AND_CANDIDATE_IDENTITY.json)。实际候选差异见 [Task004-on-Task003](candidates/TASK004_ON_TASK003.diff)。

| 因子 | 冻结入口与底层实效 | 关闭时的保留行为 | 核验 |
| --- | --- | --- | --- |
| **D，深度正则** | src/depth_video.py:332–378 的 BA 入口在 mono_disps 与已有 zeros 缓冲区之间切换。src/lib/droid.cpp:118–165 原样传参；src/lib/droid_kernels.cu:1876–1883 使用深度输入大于零的掩码。局部候选用每调用的 use_depth，保持对象上的 metric_depth_reg=true。 | Metric3D 仍初始化和预测（src/motion_filter.py:34、72–80、101–110），先验逆深度仍缓存（src/depth_video.py:125–130），保留原始深度摘要和原配置的磁盘保存策略。gamma_depth 始终为 0.01。D=0 同时恢复被先验掩码替代的 eta 项。 | CONFIRMED_STATIC_AND_CPU_MOCK |
| **W，源端 UBA** | src/factor_graph.py:236–281 → src/depth_video.py:332–375 → src/lib/droid.cpp:144–165 → src/lib/droid_kernels.cu:315–356。只改变 enable_udba，决定几何观测的 x/y 权重是否乘源端 U 系数。 | 原生对应权重、几何深度门、U 数值和 W=0 下仍可运行的 U 更新分支。enable_bidirectional_uncer 始终 false。 | CONFIRMED_STATIC_AND_CPU_MOCK |
| **U，BA 内 U 更新** | src/lib/droid_kernels.cu:1909–1970 在位姿和视差更新以后由独立 enable_update_uncer 分支控制特征投影、先验正则、仿射参数及 U 更新；该分支不要求 enable_udba=true。 | 不关闭 uncertainty_params.activate，不移除 DINO/FiT3D 特征，不把 U 置为 1。新槽位用仿射和特征初始化 U 的原生路径、前端复制/重算下一槽位、Warmup 的 U 更新、后续使用存量 U 的机制均保留。 | CONFIRMED_STATIC_AND_CPU_MOCK |

### D 的精确定义

为某个活跃深度槽位设 m=[prior_disparity>0]、α=gamma_depth、d=当前逆深度，原生联合求解给深度法方程加上：

- 曲率项：m·α＋(1−m)·eta。
- 右端项：−m·α·(d−prior_disparity)。

D=0 时原生零缓冲区让 m 恒为零，右端没有先验残差，曲率保留 eta。D=1 时没有正先验的位置本来就走 eta；该组若没有正掩码支持，不能解读为深度约束实际发挥作用。把 gamma_depth 设为零会在 m=1 处同时拿掉 α 和 eta，得到另一种系统，禁止作为等价消融。

### W 与 U 的区别

W=1 时，在原生深度几何有效门之后，源端乘子为 clip(1 / max(45U−35, 0.1), 0, 1)，原始 x/y 观测权重仍乘 0.001。W=0 时源端乘子为 1。U 是正值且无固定上界的变量；U=0 在实验编号中指「停止该次 BA 更新」而不是把变量赋为 0。乘子饱和区域内 U 变化可能不改变 W 的实际权重；采用源端乘子分布核验。

U 的原生更新计算单独使用特征、当前投影及 U（含其目标投影比较）；关闭 W 不会关闭这些计算。W 可以改变本轮几何求解，因此也能间接改变 U 更新所读的姿态和视差。U 改变后又可影响后续内迭代及下游阶段。能独立控制的是调用开关；观测耦合是实验对象。

### 不能用全局开关代替

- enable_opt_dyn_mask 在前端同传给 W、U（src/frontend.py:66–109、137–148、183–188），还用于 Final BA 的 W（src/slam.py:128–141）。全局关闭会同时改变多项及多阶段。
- metric_depth_reg 全局改动会影响优化以外按此属性进行的深度读取等路径（如 src/depth_video.py:745）。本候选不更改该属性的前端值。
- activate=false 会改变特征、U 和仿射缓冲区的构造；DepthVideo.ba 仍从这些对象取参数。不能当作安全的 U 更新单因素操作。
- enable_bidirectional_uncer=false 排除源端之外的目标端 UBA 权重，不等价于 W=0。

### 实现证据与剩余界限

[CPU 日志](logs/cpu_mock_release.stderr.txt) 的 16 项测试包含八组在两种目标局部调用的 16 组参数联接、E0 与冻结代码实参等价、非目标阶段透传、正深度缓存保留和观测覆盖。检查了既有 Python → C++ → CUDA 签名；候选补丁不修改 C++、CUDA 或构建文件，不需要为开关重新编译扩展。未来仍须通过原扩展 SHA、运行时兼容和 E0 观测等价核验；未执行的实际 GPU 数值不能标记 PASS。

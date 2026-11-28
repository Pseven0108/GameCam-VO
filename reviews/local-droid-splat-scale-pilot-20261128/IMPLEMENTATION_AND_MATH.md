# 实现与数学

## 对应源码

上游：DROID-Splat `src/depth_video.py:591`、`:440`、`:660` 与 `src/geom/__init__.py:159`。
本地：`candidate/src/scale_alignment.py`、`scale_controller.py`；A5 来源位于 `source_reference/GameCam-VO/`。

令 p 为原始 Metric3D 逆深度，d 为当前 BA 估计逆深度，v 为有效支持。固定相机，只拟合 s，偏移为零：

\[
s^*=\arg\min_s\sum_p v_p(s p_p-d_p)^2
=\frac{\sum_p v_p p_p d_p}{\sum_p v_p p_p^2},\qquad \widetilde d_m=s^*p.
\]

归约使用 float64，输出回原生 float32。s 非有限、s<0.05、分母退化或支持不足时回退 s=1，不根据 GT 选 s。
逆深度乘 s 对应深度除 s。每次从原始先验生成校正副本，禁止累乘，原始 `mono_disps` 不改写。

支持条件：native depth_filter 的至少 2-view 支持、阈值 0.05；d>1e-3、d>0.01*帧均值；对应边权先按边均值再取 xy 范数>0.1；排除最新候选关键帧。depth_filter 只看到有效帧，未用 buffer 槽不计支持。
先检查选定地图总支持>=300，再对各帧有正分母的支持拟合。门槛作用范围和置信度归约经过 V3 源码修正。
这里用 DROID-W 原生对应边权近似 DROID-Splat 的 tracker confidence，属于迁移适配，不是完整上游数据流复制。
同一输入帧首次 eligible BA 拟合，后续 BA 复用该帧拟合，下一输入帧重新拟合。不是把所有 BA 内部迭代改成尺度优化。

## 四组与 BA 方程

| 组 | 先验 | 强度 a |
|---|---|---|
| BASE | 原始 d_m | 1 |
| A5 | 原始 d_m | 原有 ValidityAwareMax |
| SCALE | s*d_m | 1 |
| SCALE_A5 | s*d_m | 原有 ValidityAwareMax |

A5 的系数从原始 depth、native confidence、flip disagreement 计算，不因 scale 拟合重新校准。
它保持 TASK011B 的零效应端点与部分强度插值：

\[
C=C_g+(m a)\alpha+(1-m a)\eta,\quad
b=b_g-(m a)\alpha(d-\widetilde d_m),\quad \alpha=\gamma_{depth}=0.01.
\]

m 是原生有效先验掩码；BASE/SCALE 使用 a=1，A5 使用原有系数。a=0 恢复原生无先验 eta 阻尼，a=1 恢复有效先验正则。
**A5 降低强度时也改变该插值下的深度曲率与 eta 分支，不能描述成只乘 residual。** 原始 BA 数学没有在生产扩展中改写；独立 A5 扩展复用既有 TASK011B 实现。
UBA 几何对应权重、U 更新开关、原生 Schur 消元、阻尼、Pose/Disparity retraction 保持原有路径。SCALE 不增加新的 CUDA BA 算术。

## 作用范围与恢复

实例级代理只允许 `FRONTEND_MAIN_LOOP_LOCAL_BA` 且 metric_depth_reg=True、motion_only=False 时介入。
初始化/第二阶段初始化、Final Global BA、Trajectory Filler、Online Global BA 透传安装的原扩展；未知阶段停止。
本轮 Online Global BA 和 mapping 原本关闭，未为了对照打开。Final BA 沿用原生 7+12 外层调用及其暂时关闭 metric_depth_reg 的流程。
Tracker/Frontend 自然选择关键帧，没有强制固定选择；事后发现四组关键帧 ID 相同。图边与状态仍可能不同，因此不主张纯固定状态效应。

## 与完整 DROID-Splat 的差异

本轮只借用固定 Pose 地图对齐与加权 LS 思路，改成 scale-only；没有 affine shift、联合 depth/scale 求解、完整交替优化、上采样 confidence 存储或 3DGS mapping。
官方 `linear_align_prior` 自身也提示地图对齐与 optical-flow 目标不同，不保证正确的单目尺度。
本轮结果不能被标为 DROID-Splat 系统的复现成绩。

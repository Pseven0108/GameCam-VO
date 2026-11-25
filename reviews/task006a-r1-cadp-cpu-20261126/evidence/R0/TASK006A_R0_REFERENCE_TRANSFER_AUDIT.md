# Pi3MOS 参考机制与 DROID-W 迁移边界

本轮通过 GitHub 连接器读取官方 Pi3MOS 固定提交 `1b81d729c4259a5a775eb4aae41f959eea38ae14` 的四个文件：`dpvo/fastba/ba_cuda.cu`、`dpvo/dpvo.py`、`dpvo/patchgraph.py`、`dpvo/config.py`。它们只作为源码证据，没有导入或运行。

官方来源：[Pi3MOS-SLAM 固定提交](https://github.com/PRBonn/Pi3MOS-SLAM/tree/1b81d729c4259a5a775eb4aae41f959eea38ae14)。关键源码：[ba_cuda.cu](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/fastba/ba_cuda.cu#L549)。

|比较项|Pi3MOS 源码事实|对 CADP 的含义|
|---|---|---|
|计算时机|`itr==0` 时由未加入 prior 的 C 和 pose Hessian 计算|可参考“每次 BA 一次、先 prior-off 后注入”的顺序|
|对角修正|`C_inv + diag(F^T F)`，F 来自三角求解|不能拿 1/C 当完整协方差|
|相对不确定性|标准差除 inverse depth 后按每帧 patch 取中位数|迁移到稠密像素时要定义有效像素与空帧|
|映射|sigmoid，当前配置 k=10、threshold=2|参数与权重尺度相关，不直接复制|
|先验写入|`C += wp_eff; u += wp_eff*(prior-z)`|DROID-W 的 eta 由 m 控制，不能只复制额外加项|
|pose 阻尼|对 Schur 对角使用 `1e-4*diag + 1.0`|DROID-W Local 是 `lm=1e-4,ep=0.1`，必须分别保持|
|矩阵求解|GPU 稠密/块结构 Cholesky 路径|DROID-W 原版 Eigen CPU SparseBlock，不是同一 API|
|中间矩阵|显式构造 F^T F|稠密 DROID-W 存储代价可能不可接受|
|阶段|`dpvo.py` 全局 BA 调用显式禁用 cov adaptive|不能将此机制概括为所有 BA 阶段自适应|

源码里的高效 E 分支仍需独立核对其协方差取值和维度，不能因为作者存在 fast path 就宣称已有可直接移植的在线实现。本轮不是 Pi3MOS 复现，也不提供其性能证书。

本轮确认的是结构依据和迁移差异：利用局部几何不确定性调 prior 强度有官方先例；并不证明它一定修复 DROID-W 的 S1/S0 效果反转。单独移植 sigmoid 权重不构成已证实的新颖贡献。

CADP 的后续实证需要至少区分固定 D0、固定 D1、固定 rho 和自适应 rho；同一离散调度分别评估 S1/S0。几何不确定性高不代表 Metric3D 预测就正确；本阶段尚不包含深度可信度估计，不应暗含该假设。

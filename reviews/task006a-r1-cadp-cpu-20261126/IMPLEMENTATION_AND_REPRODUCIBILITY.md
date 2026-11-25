# 实现与独立复核

## 运行范围

这是独立 NumPy/SciPy CPU float64 原型，不修改或导入 DROID-W/Pi3MOS 模型。没有 PyTorch、CUDA、VIPER、C0、原始权重或远端服务访问。

执行解释器为已有 `D:\Python\Python3\Python3.9.13\python.exe`，NumPy 2.0.2、SciPy 1.13.1。默认 miniconda Python 没有 NumPy，因此复用已有解释器；没有安装依赖或修改环境。

## 主要文件

|文件|职责|
|---|---|
|src/cadp_cpu.py|prior-off Schur、完整协方差、分块对角、子块、原生与CADP深度项、独立联合求解、帧级统计、只读rho plan、E全局索引|
|src/synthetic.py|按种子生成每个残差只关联一个深度的线性最小二乘系统；大维度Gram系统|
|tests/test_cadp.py|联合逆与稀疏解oracle、端点、稳定性、mask、反例、索引与只读合同|
|tools/run_research.py|运行完整合成研究，保存输入、对照CSV及机器可读结果；防覆盖|
|tools/prepare_evidence.py|只读采集R0文字来源、配置与保护哈希；不读取Tensor|
|tools/write_reports.py|从最终真实结果生成评审与决策文件|
|tools/package_review.py|只读保护复核、完整SHA、ZIP CRC与内部SHA验证|

## PowerShell 复核

以下命令在本评审目录或它的完整副本中执行。所有 Python 子进程须保持 CPU 环境。仅输出到新的目录，不覆盖已封存 results。

```powershell
$env:CUDA_VISIBLE_DEVICES = ''
$env:OPENBLAS_NUM_THREADS = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:PYTHONUTF8 = '1'
& 'D:\Python\Python3\Python3.9.13\python.exe' -B tools\run_research.py --out results\independent_recheck
```

换机器可使用装有 NumPy/SciPy 的普通 CPU Python；本包未附 Python 环境。跨BLAS/平台不保证逐位重复，联合矩阵 oracle 应保持固定混合容差（atol=rtol=2e-11）。不同随机生成器/库版本可能影响相同种子的生成结果，原版本及数组哈希已记录。

`SYNTHETIC_SMALL_INPUTS_AND_ORACLES.npz` 是本轮自行生成的数值数组，独立读取必须使用 `numpy.load(path, allow_pickle=False)`。它不是封存 C0 或模型 checkpoint。大维度样本用生成器、种子、shape、dtype和数组SHA复核，未携带庞大的完整协方差。

## 简单API示例

```python
from synthetic import make_fixture
from cadp_cpu import build_adaptive_plan, cadp_depth_terms, solve_ba_step

x = make_fixture(seed=43)
g = x.geometry
plan = build_adaptive_plan(g, x.disparity, x.frame_ids, x.observation_count,
                          k=2.0, tau=2.0, block_size=256)
# k/tau仅为合成示例，未获真实数据校准。
c, b = cadp_depth_terms(g.Cg, x.bg, g.eta, x.disparity,
                        x.mono_disparity, plan.pixel_rho, alpha=0.01)
dx, dz, factor = solve_ba_step(g, x.bx, b, c)
```

一次BA内应复用只读 plan；此处没有接入原生迭代，未测试真实U反馈。不要把该API直接挂到生产源码。

## 独立原型的数值政策

- 只处理有限的对角正深度曲率与SPD Schur系统；材料性非对称/不一致几何直接拒绝。
- 仅在对称性检查后消除舍入级反对称误差。
- 条件数上限1e12是CPU原型的显式验收政策，不是新增生产算法参数。
- 不加自适应jitter，不改阻尼，不用伪逆，不裁剪负方差，不自动放宽容差。
- midpoint median、有效像素集合、epsilon与最小支持数均显式记录；没有空帧fallback。
- 完整Sigma只用于小系统，分块对角不丢弃跨帧/跨pose耦合。

## 结果版本

最终科学结果以 `results/research_003` 为准。`cpu_validation_001`、`research_001`、`research_002` 是新增测试/反例/只读plan前的中间CPU验证，原位保留。它们不是额外随机重复实验；不得把三次测试执行数量相加当成统计样本。

正式批次的命令、退出码、stdout/stderr SHA在 `logs/RESEARCH_EXECUTION_RECEIPT_003.json`。各测试名称与结果在 `UNIT_TEST_REPORT.json`，原始测试输出在 `unit_tests.stdout.txt`。

## 来源

Pi3MOS 参考读取官方固定提交：
[ba_cuda.cu](https://github.com/PRBonn/Pi3MOS-SLAM/blob/1b81d729c4259a5a775eb4aae41f959eea38ae14/dpvo/fastba/ba_cuda.cu#L549)。本轮重新读取官方HEAD与相关源码片段，提交与R0一致；完整文本复用R0哈希锁定副本。Pi3MOS 的补充曲率、阻尼常数、patch聚合和运行阶段不能照搬为 DROID-W 的dense实现。

DROID-W 依据 [冻结源代码](https://github.com/MoyangLi00/DROID-W/blob/c3414af6047d06bafc1a6645d09f23247f3b2cdc/src/lib/droid_kernels.cu#L1878) 与封存R2 YAML；来源路径与SHA在 `evidence/INTAKE_VERIFICATION.json`。本轮不是Pi3MOS复现，也没有新颖性或性能优越性声明。

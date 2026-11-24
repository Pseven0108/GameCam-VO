# GPU C0采集运行报告

## 授权与执行

仅限val_007初始化/C0采集，buffer500、640×360、stride1、seed43、INIT_D=0、原R2配置、原权重及CUDA扩展。C0保存成功后应立即停止，禁止恢复、跨D及B1-B4。本次未成功到达该边界。

独立目录：`/root/rivermind-data/DROID_W_TASK004C_B_GPU_C0_20261124_R1`。原生进程PID773；命令见`remote_evidence/attempts/capture/PROCESS_STARTED.json`。实际运行58.316秒，exit1，未自动重试。

## 启动前资源

RTX3090总24576MiB、空闲24125MiB、无compute占用；数据盘26,617,909,248bytes可用；shm24GiB；容器RAM上限100GiB。实际保护pin、R2 YAML、INPUT manifest均匹配。克隆后的独立源码/元数据占用已在最终admission再次扣除。

这里只证明静态下限和启动资源通过，不证明完整C0可放下。真实完整预算函数未执行，因为在第一帧检查就终止。

## 时间线

1. 第一次运行准备使用了系统Python，stdlib admission查询不到Torch分发元数据，模型启动前退出；native生命周期0。完整失败收据保留。
2. 使用既有wild Python环境读取同一元数据并通过admission；没有修改依赖或源码。
3. 建立唯一capture launch intent，启动唯一GPU进程生命周期。启动器在构造SLAM之前设置spawn，与官方`run.py:26`一致；其余使用已评审CLI的model-child鉴权和实际capture函数。
4. 加载预训练模型、创建file-backed Video与原生进程。Rerun产生小型录制文件。
5. Tracker取RGB001时，严格适配层发现父类返回depth为Tensor而非None，抛出ControlError。
6. 原生入口因没有SUCCESS/C0收据返回exit1；父进程停止，未重试。
7. 用CPU、原loader及原RGB复现唯一失败谓词；完成收尾和安全临时Arena回收。

## 关键日志

```text
native_control/dataset.py:29
ControlError: R2 RGB-only input contract mismatch

native_control/native_driver.py:98
ControlError: Capture child failed; no automatic retry
```

`INFO: 0 images got!`来自父类初始化时对文件布局的默认glob；子类随后使用已核验的487项INPUT manifest重设color_paths。首张图像能够实际解码，因此不能把该日志单独解释为数据集丢失。

## 资源与证据限制

显存采样峰值7439MiB、shm采样峰值212992bytes、资源间隔约2秒。启动即失败，这不是完整RGB018初始化或完整C0的资源测量。无模型性能、无轨迹、无ATE/RPE。

完整日志和逐样本资源记录在`remote_evidence/attempts/capture/`。本轮保留的候选与算法完全一致；新增的是启动收据、可见的spawn入口和诊断代码。

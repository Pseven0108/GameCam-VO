# 共享存储跨进程CPU实测

## 原尺寸压力测试

证据：`evidence/FULL_BUFFER/artifacts/FULL_BUFFER_CPU_PROOF/FULL_BUFFER_PROOF.json`；入口：`tools/full_buffer_stress.py`。Torch 2.1.0+cu118，spawn，CPU-only，随机种子固定；数值为合成确定性输入。

| Tensor | shape | dtype | logical bytes |
|---|---|---|---:|
| images | (500,3,360,640) | float32 | 1,382,400,000 |
| dino | (500,25,45,384) | float32 | 864,000,000 |
| 合计 | buffer=500 | | 2,246,400,000 |

父进程PID908，两个独立spawn子进程PID975、976，分别标记TRACKER_CPU_STANDIN和RERUN_CPU_STANDIN，退出码均0。二者是合成读写worker，不是真实Tracker或Rerun服务。

过程：父进程填充数据；两子进程传入同一Tensor对象图，各自完整哈希；barrier之后一个worker更新尾部值（73.25、-18.5）；两worker再读并完整哈希；父进程同步核验。前后均比较dtype/shape/stride/offset和descriptor inode。完整结果为PASS。

`/dev/shm` baseline=0、采样峰值=61440、增量=61440 bytes。测试时长28.905秒；采样峰值不是对所有可能微瞬态或真实模型负载的上界证明。

## 别名与元数据测试

新增FileSharingTests共11项：跨spawn别名；双reader；非连续stride、非零offset与核心dtype；未注册CPU storage保留Torch原行为；file_system全局策略下owned storage不迁回tmpfs；snapshot恢复别名；allocator有/无选项；物理预留及descriptor损坏拒绝。

这些小型测试覆盖别名/布局；原尺寸压力测试覆盖容量和多进程同一文件。不能把原尺寸连续Tensor测试单独说成覆盖全部view关系。

## 证据留存

最终152项测试逐项stdout/stderr、退出码和SHA在 `evidence/CPU_final/artifacts/RELEASE_CPU_final/CPU_TEST_REPORT.json`。全尺寸测试的外层退出码、stdout/stderr在 `evidence/FULL_BUFFER_RESULT.json`；受信SSH收据单独保存。

两块大合成payload在验证所有worker结束、无活动映射并核对SHA后回收；不将2.09GiB测试payload塞入评审ZIP。测试参数、生成脚本、完整前后SHA和descriptor保留，用户可在独立目录复现。真实RGB/模型/C0均为0，CUDA未初始化。

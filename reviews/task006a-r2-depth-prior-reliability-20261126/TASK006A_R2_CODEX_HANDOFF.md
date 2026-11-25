# 下一对话恢复入口

当前任务仅部分完成，不能把此包当作可信度效能验证通过。
根目录：D:\aaa\GameCam-VO\reviews\task006a-r2-depth-prior-reliability-20261126。
R1 已封存，发布 commit b6e8b552aa1d5f57ada46fae4b809aedfbaaed94。

已完成：00/01 的关键源码与状态、02 文献、03 数据审计、独立 evaluator 与 61 项 CPU 测试。
未完成：01 输出分布、04 Native 对 GT、05 TTA、06 bin 真值效果、08 实测比较。
07 梯度按条件延后；09 只有输出合同候选，不是获准使用的模块。

当前远端 sc01-ssh.gpuhome.cc:30601，可信 ED25519：
SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA。
remote_probe.py/remote_read.py 使用专用 known_hosts、HostKeyAlias、StrictHostKeyChecking=yes；
不清空 known_hosts，不自动接受新 key。端口变了先由用户提供；指纹不同独立确认。
当前探针 nvidia-smi 为 Exec format error，不能用历史 RTX3090 作为当前硬件证据。

remote runtime：/opt/gamecam-viper-fullseq-3090-20261120-061408/envs/wild/bin/python。
模型目录与 checkpoint 在 metric3d_confidence_probe.py 的 BASE/HUB/CHECKPOINT 常量；
预期 Metric3D eb5b6fac0dc155e4e52f576e304fbf11655ff339，权重 15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972。
该推理脚本 **UNEXECUTED**。恢复时先 AST/来源/shape/预处理复核，再在可用 GPU 上少量 smoke，
不能宣称已经运行通过。hook 需确认只读，加载 key 不匹配应停止，不准静默继续。
1..16 图的 manifest 必须先逐张身份/fx 核验；不要直接全量 VIPER。

独立输出仅允许 /root/rivermind-data/GAMECAM_TASK006A_R2_*，不要写历史模型/SLAM目录。
每 sample 保留 native/flip 原始 confidence、depth、真实 anchors 和 bin 统计；
记录 runtime、峰值显存、分位数、异常计数。GT 只进 evaluator，不能作推理输入。

GT 当前：MVS-Synth GTAV_540/0000 100 帧，单位未知，另四序列只有 preview。
先核单位；若采用数值单位校准，需要预注册且独立完整 Calibration/Test 序列。
未授权整包大下载；不要将同序列相邻帧随机拆开。
Native risk=-c，error thresholds 0.1/0.2/0.5；tie handling、AP、AUSE 定义见 evaluator 与报告。

本地复算（PowerShell，各行依次执行）：

```powershell
$env:CUDA_VISIBLE_DEVICES=''
$env:PYTHONUTF8='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
```

在 experiments/scripts 中调用 test_reliability.run(Path(new_output_dir))，
或 python -B -m unittest test_reliability -v；脚本 CLI 本身是 unittest，不接受自创的 --out 参数。
要写结构化结果使用前一种接口，路径必须新建，不能覆盖 unit_tests_001/002。
audit_datasets.py 需要本研究 runtime_site 中的 OpenEXR；第三方依赖不随评审 ZIP 分发，
可在新的独立 target 安装相同版本，不升级生产环境。

不运行 SLAM、不训练、不修改生产/CUDA、不把 confidence 接入 CADP；没有后续单独授权不进入算法实现。
最后仍须上传完整 ZIP 与展开评审文件，保持 Public，不改仓库可见性，提供固定 commit 链接。

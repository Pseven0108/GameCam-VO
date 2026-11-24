# Task004C Phase0 原始快照核查

状态：**TASK004C_PHASE0_BLOCKED_INCOMPLETE_CHECKPOINTS_GPU_KEPT_ONLINE**。A 0/4，B 0/4；未启动模型，未初始化 CUDA，3090 保持在线。

## 当前资源与身份

- 已严格核验 SSH ED25519 与公钥登录。目标 sc01-ssh.gpuhome.cc:30414，主机 jupyter-yd6gks8uzfbxzdb4。
- NVIDIA GeForce RTX 3090；空闲显存 24,125 MiB；无计算进程。
- 数据盘可用 21,982,736,384 bytes（20.473 GiB）；共享内存总量24 GiB，可用约24 GiB。
- 四份权重、R2 YAML、CUDA 扩展与已冻结 SHA 匹配。PyTorch 安装静态版本2.1.0+cu118，nvcc11.8；未导入 torch，也未新建 CUDA context。
- 部署目录不带 .git，git rev-parse/status 返回128，不能声称当前 Git HEAD 读取成功。已用原始冻结源码清单重新核对208/208个文件，全部一致，清单对应 c3414af6047d06bafc1a6645d09f23247f3b2cdc。

## 两份原始归档

| Arm | 归档大小 bytes | CRC | 内部SHA | 目标BA | 有效窗口 | 有向边 |
|---|---:|---|---:|---|---|---:|
| E0/Seed43 | 199505553 | PASS | 26/26 |550/551/552|[55,70)|128|
| E1/Seed43 | 366800294 | PASS | 26/26 |660/661/662|[112,125)|94|

两组共974条逐帧决策；6个目标调用前都含312和328，并有两个方向直接边；窗口和参数有记录。完整性通过不等于重放资格通过。

## 真正缺少什么

目标时刻的完整 disparity、target、weight、eta、U、temp_y_cdot、dino_feats_resize、affine_weights 未封存。observer 把它们变成统计摘要；其几何只做确定性边/像素采样，不能逆推出全量张量。pose 活跃行、ordered ii/jj、kernel K与调用标量能够从日志读回，仍不足以构成完整BA输入。

原生 video.npz 是 Final BA 后、Filler 前保存的最终关键帧状态，并非 BA550/660 之前的快照。E0只有87个最终关键帧，E1为157个；E1的RGB328只在瞬态候选窗口中，最终缓存没有该RGB的Metric3D预测。E0最终prior候选覆盖70/70目标行，E1为124/125；这也不能恢复历史目标时刻的优化变量和网络隐状态。

## B 的额外阻断

两组初始化RGB身份相同，均在RGB18结束第二初始化阶段，12个pose行；但原始pose分量最大差 0.002861261367797852，并非逐位一致状态。不能将两组独立运行拼成共同初态，也不能归因于D。当前缺少完整共同初始化检查点、active/inactive/bad graph/cache、correlation/context/hidden及全部mutation调度。现有BA边界列表可复用作审计，但不是已通过的可执行schedule。

## 旧检查点排除

已找到并核对旧BA278全输入，文件名仍为BA280；其实际RGB341、stride4、buffer154、gamma_depth0.001。不是本轮stride1、buffer500、RGB328、gamma_depth0.01的E0/E1状态；未替换执行。

## 判定

A不可启动；B不可启动。不是GPU或环境故障。保持当前3090在线，不重启、不切换无卡、不重新部署；按本轮缺少完整快照的停止条件，先提交最小恢复方案，未擅自新增487帧完整采集。

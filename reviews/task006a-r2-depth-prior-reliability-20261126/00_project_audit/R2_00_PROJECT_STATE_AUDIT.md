# R2-0 项目与运行身份审计

**SOURCE_IDENTITY_PASS；MODEL_INFERENCE_BLOCKED。** 本轮只进行了只读远端访问和本地 CPU 工作。

## 实际工作区

本地项目 D:\aaa\GameCam-VO；HEAD `388fedf14ab1a071ab9c6955174ff092589300f3`，
分支 repro/2026-11-01-phase5。已有六个 tracked 修改，见 LOCAL_GIT_STATE.json；没有清理、重置或暂存它们。
R2 的发布分支独立创建，不改变本地研究分支或远端默认分支。

只读 SSH 指向 sc01-ssh.gpuhome.cc:30601，使用历史用户确认的 ED25519 指纹并开启严格校验。
认证和主机身份核验通过。REMOTE_PROBE.stdout.txt 记录当前主机及完整探针。
nvidia-smi 执行失败（Exec format error）；这不能证明硬件损坏，也不能据此假定当前有 3090。
数据盘可用 12,522,487,808 bytes，/dev/shm 容量 2 GiB；都是该次探针时的值。
本轮不将历史 SLAM 的共享内存安全门槛套用到独立 Metric3D 推理。

## 模型与配置

- 基础 DROID-W 冻结身份：c3414af6047d06bafc1a6645d09f23247f3b2cdc；实际 metric_depth_estimators.py 与 R0 源码快照逐字节一致。
- Metric3D 当前实际 hub HEAD：eb5b6fac0dc155e4e52f576e304fbf11655ff339；283/283 个 Git blob 与官方固定提交一致。
- metric3d_vit_large，ViT Large + RAFTDepthNormalDPT5，8 次迭代。
- 权重 metric_depth_vit_large_800k.pth，1,647,972,663 bytes，SHA-256：15328ffc42b528b95f188687418f6f03b3f123eb34ccdbd686c112abbea6d972。
- 封存配置 gamma_depth=0.01；本轮没有改动。该参数属于 BA，不参与本轮独立可信度推理。
- 元数据读取：PyTorch 2.1.0+cu118、torchvision 0.16.0+cu118、NumPy 1.26.4、OpenCV 4.8.1.78、timm 0.9.10。
  这是包元数据证据，不是 CUDA 可执行性测试。未导入模型或反序列化权重。

生产 hub 调用没有 pin revision，不能用注释 34afafe... 代表运行版本；当前缓存的真实版本已单独锁定并核验。

## R1 与历史边界

读取 R1 最终报告、数学推导、决策与数值局限。R1 完成 CPU float64 几何协方差原型，
97 项测试和合成端点实验通过，不是实际深度先验可靠性的证明。
R1 的深度边缘协方差依赖不加 Metric3D 先验的几何系统；R2 研究模型先验本身。
R1 的不准确先验反例说明必须独立审查先验，不能把几何协方差拿来当先验误差 GT。

Task003/004/005 的 BA、D/W/U、调度与归约证据是上游动机，不是原生 Confidence 标定数据。
本轮未加载 C0、R3 张量或旧 SLAM uncertainty 作为可信度标签。
现有生产入口只保存深度，不保存原生 Confidence；本轮没有找到可用于本任务的已核验 Confidence/TTA 推理收据。
这一检查覆盖当前指定入口和已审阅证据，不声称扫描了所有历史二进制文件。

## 数据流与缺口

RGB → native resize/normalize/pad → Metric3D → (depth, confidence, output_dict)；
生产代码只保留 depth → unpad/bicubic/focal scaling/clamp → DROID-W。
Confidence 在 tuple unpack 时被丢弃。代码行为可确认，作者为何这样设计没有文档证据，记为 UNVERIFIED。
当前缺口是输出数值实测及独立 GT 误差验证，而不是再一次 SLAM 重跑。

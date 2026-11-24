# 最小后续方案（未实施）

已确定故障：native_driver.py先用真实SummaryWriter创建native目录，后又用exist_ok=False创建相同目录。无需改BA、预处理、模型或权重。

建议先决定单一目录所有者：attempt目录仍使用排他创建；在新attempt内明确创建并校验native目录（拒绝链接、外部路径、旧结果），然后再初始化SummaryWriter。不能泛化为吞掉所有FileExistsError，也不能复用旧失败attempt覆盖日志。

CPU回归必须使用实际SummaryWriter、R2 scene=native、实际rebind_output及真实文件系统；覆盖新目录成功、既有合法空目录/服务子目录、旧实验目录拒绝、链接/逃逸拒绝。补齐Mock中Writer无副作用及fake scene带来的盲区。该建议本轮未应用，也没有因此增加GPU运行。

C0源身份不可规避：当前C0 pin为5d357c1d3079de134dd8b41a20a00632da37f0b0。任何新候选commit都不应冒用此pin。后续需要单独审查：批准纯I/O兼容overlay并验证全部被捕获类/Storage适配器/优化文件未变，或批准新源码下重新采集C0。不能悄悄放宽source检查、改写旧manifest、伪造旧commit或自动挪用剩余额度。

优先验证目标是新进程实际处理RGB019；通过之后才按现有次序进入Short80及四组，不重跑DROID-SLAM。

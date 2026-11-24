# GameCam-VO Task 002A｜评审请先读

这是 DROID-W 消融开关依赖关系的静态审计交付。没有运行 GPU、模型或新消融。正式 E0 是 `stride=1` VIPER R2，审计不纳入 `stride=4` 历史分支。请先读 `DROID_W_ABLATION_SWITCH_MATRIX.md` 和 `DROID_W_PROPOSED_ABLATION_PLAN.md`，再用源码和运行快照复核。

建议评审四点：

1. `metric_depth_reg=false` 与 `gamma_depth=0` 是否等价；是否误把不使用 Metric3D 先验当成不运行 Metric3D。
2. U 更新与 UBA 的两个 native 参数如何经前端、Final BA、filler 传递；E2 和 E3 能否单独归因，哪些 `activate` 组合会留下缺失属性。
3. E0 是否以 `gamma_depth=0.01` 的正式 R2 为基准；E5 是否保留补位和轨迹导出，并解决冻结入口限制。
4. 哪些是已证实的静态调用关系，哪些是推断的运行风险，哪些仍需获批后验证。给出需要修订的对照和证据缺口，不执行新实验。

证据路径：原五份 Markdown 保持原始字节。原报告使用本机路径；在包内按下表找到对应源码和快照，用原行号即可复核。

| 报告简称 | 包内目录 |
| --- | --- |
| W / DROID-W `c3414af6047d06bafc1a6645d09f23247f3b2cdc` | `evidence/DROID-W/`，关键文件原样复制 |
| S / DROID-SLAM `2dfd39f0dcad44012ca7bbb8aa70b55edbfa9c99` | `evidence/DROID-SLAM/`，相关 BA 接口 |
| R1 已封存的启动入口 | `evidence/R1/pipeline/run_segment.py` |
| 正式 R2 配置与身份 | `evidence/R2/`，含冻结 92 片段清单、协议锁、保全哈希账本、`val_007` 实际配置和回执。其余原始配置及回执由审计报告引用，本包未重复附载。 |
| Task 001 的源码身份记录 | `evidence/Task001/SOURCE_IDENTITY_VERIFICATION.json` |

`FILE_SHA256_MANIFEST.json` 列出除 SHA 清单本身之外的全部成员。证据只供阅读，不附数据集、权重、轨迹或完整仓库。同目录的 `GAMECAM_DROID_W_TASK002A_REVIEW_FOR_CHAT.txt` 含五份报告和带行号的关键摘录，可以独立上传评审，无需解压。

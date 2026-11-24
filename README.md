# GameCam-VO

面向游戏渲染场景的视觉SLAM研究。当前主线为 **VIPER、DROID-W、stride=1**，研究深度先验、不确定性与优化/关键帧选择之间的关系。

## 从这里开始评审

- [最新评审：GPU C0首次采集失败取证](reviews/task004c-b-gpu-c0-20261124/FINAL_REVIEW.md)
- [全部阶段目录与证据索引](REVIEW_INDEX.md)
- [当前项目状态和授权边界](PROJECT_STATUS.md)
- [给 ChatGPT 的评审说明](REVIEWING.md)
- [当前 DROID-W 完整相关源码](source/DROID-W/README.md)
- [源码身份和逐文件导出清单](source/SOURCE_PROVENANCE.json)

源码候选：`668a88c74c7f7a88a572679d2bd8e86c0a05514b`，父提交为完整远端候选 `0931141cf88247dc8fb0c7628c1d91b6531fea90`。本仓库发布提交是便于阅读的独立快照，不冒充上述运行源码提交。

## 最新实际GPU执行（2026-11-24）

**GPU C0采集未成功：1次原生GPU启动，exit1；0帧进入跟踪、0次BA、无C0。**

CPU实读已确认输入适配层错误：父类无深度数据时返回全零占位Tensor，候选层却要求depth=None。时间戳、RGB尺寸、pose=None均通过。未修改候选源码，未自动重试；restore、跨D、B1-B4均未启动。

完整取证、资源采样、日志与临时Arena生命周期见[最新报告](reviews/task004c-b-gpu-c0-20261124/FINAL_REVIEW.md)。此前152项CPU测试是背景证据，不能替代真实loader端到端测试。

## 前一阶段CPU状态

Task004C-B发布修复完成CPU回归：原118项 + 新增34项 = **152/152通过**。buffer=500的2,246,400,000 bytes共享CPU缓冲区通过双spawn实测，shm增量60KiB。

**真实Tracker/Rerun链路未验证；完整真实C0大小仍未知。本轮没有GPU、模型、真实C0、RGB前缀或B1/B2/B3/B4运行。** CPU测试不等于轨迹性能改进。

## 内容范围

本分支保存当前源码和Task001至Task004C-B的16份评审材料，展开Markdown、CSV、JSON、测试和补丁供直接阅读。最新评审包完整保存并逐SHA核验；历史阶段以文本材料为主，未上传附件在各阶段publication manifest中逐项列出。

数据集、模型权重、编译缓存和大型运行产物仍保留在原工作区/服务器。源码的上游二进制、示例媒体和数据文件列表也以明确清单省略。原有main、实验分支和历史结果没有覆盖。

上游版权和许可证保留在[source/DROID-W](source/DROID-W/)及各thirdparty目录。本文档不重新授权上游代码或数据。

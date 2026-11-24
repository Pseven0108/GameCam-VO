# ConfigDict 专项修复报告

本轮结论：ConfigDict 编码缺陷已在源码、14 项专项测试和实际模型配置子图中获得定向验证；完整模型跨进程恢复仍失败，不能进入 GPU。

起点为 `a324b57760fdaf4929385f2271991d773533799d`，专项第一轮提交为 `aa0cca3ed0d6e5d381422d8219234b8c0c6ad065`。只改变 `native_control/configdict_adapter.py` 和 `native_control/snapshot.py`；保存全部 ordered mapping、实际属性字典及对象引用关系，使用严格安装版本及源码 SHA 白名单与两阶段分配/填充恢复。Metric3D identity adapter 保持 SHA `b723b0eecb68449d9f9126c3453ec940c473d17a377d1ff4629dc32be036a3b4`。

CPU 回归：ConfigDict 14/14、完整历史回归 152/152，均 exit 0。实际加权模型源侧固定输入通过历史 SHA 比较；完整新进程恢复 exit 1，失败于 FiT3D 的 `timm.layers.format:Format`。新的精确诊断恢复真实模型中的六个 ConfigDict 及其 24 个可达对象图节点，mapping、属性、嵌套类型、顺序及 alias/cycle 的规范化图一致，但此诊断不包含独立 Format 对象，不能替代全模型恢复。

只读引用链证明 Format 位于 `root['models']['FiT3D']._modules['model']._modules['patch_embed'].output_fmt`；它没有 ConfigDict 祖先，且此前历史快照已包含此类型。因此它是此前失败遮挡的独立序列化器类型支持问题，不应算作 ConfigDict 修复第二轮，也不能宣称新增预算已耗尽。

本轮 ConfigDict 预算消耗 1/2。因完整 CPU gate 未通过，GPU C0 为 0/2、短程实验 0/4、完整四组 0/4。未创建真实 C0，未改变 BA 数学、模型前向、原始权重或 R2 配置；未训练、未推理 SLAM、未从本轮得出算法结论。

继续所需最小工作是独立审核 pinned timm Format/Enum 状态恢复方案，再重新完成全模型新进程 gate。该类型修复超出本轮 ConfigDict 定向修复范围，当前保留阻断，不将状态降格为字符串或忽略字段。后续原生 RGB019 续步与正式 487 帧 runner 的阶段控制仍须完成和验证。

详见 `TASK004C_B_CONFIGDICT_SOURCE_AUDIT.md`、`TASK004C_B_CONFIGDICT_FIX_DESIGN.md`、`TASK004C_B_CONFIGDICT_TEST_REPORT.md`、`TASK004C_B_REAL_MODEL_ROUNDTRIP.md`。所有正式阶段是否启动以最终账本及收据为准。
